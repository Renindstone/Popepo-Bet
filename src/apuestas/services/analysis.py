"""Análisis completo de un partido: modelo + alineaciones + bajas + árbitro + contexto + cuotas."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.features import context as ctx
from apuestas.features import lineup as lu
from apuestas.models.distributions import Outcome
from apuestas.models.fitting import ModelBundle
from apuestas.services.match_model import MatchModel, PlayerProjection

MY_BOOKS = ("bet365", "betano")
SHARP_BOOKS = ("pinnacle", "betfair_ex")
W_MODEL = 0.25  # peso del modelo frente al mercado afilado: el backtest muestra que el mercado sabe más
MAIN_MARKETS = ("1x2", "ou_goals", "ah", "btts", "dnb", "dc")

# Equipos que el mercado no ha visto (ligas que no se descargan, p.ej. Bodø/Glimt): su rating sale de pocos
# partidos europeos y el modelo puede ver un partido parejo donde la cuota dice lo contrario. No hay cuotas de
# esos partidos para medirlo con el backtest, así que es una regla de prudencia, no un parámetro ajustado:
# - por debajo de MARKET_COVERED partidos con cuotas de cierre en el último año, la confianza baja (hasta x0,6);
# - en mercados de goles sin mercado afilado, la probabilidad se mezcla con la de la propia cuota sin margen,
#   con el peso del modelo W_MODEL (el mismo de la mezcla con Pinnacle) cuando no hay ninguna cuota del equipo.
MARKET_COVERED = 10
MIN_MARKET_FACTOR = 0.6
BOOK_MARGIN = 0.05  # margen típico de bet365/Betano en estos mercados, para quitarlo de una cuota suelta
GOAL_MARKETS = ("1x2", "dc", "dnb", "btts", "ah", "eh")


def market_coverage_weight(n_market: int | None) -> float:
    """Peso del modelo frente a la cuota (1 = solo modelo) según los partidos del equipo con cuotas."""
    if n_market is None or n_market >= MARKET_COVERED:
        return 1.0
    return W_MODEL + (1 - W_MODEL) * n_market / MARKET_COVERED


# Estadísticas (córners, tarjetas…): su modelo no se ha validado contra cuotas reales. Si la propia casa, sin
# margen, ve la apuesta muy distinta, lo más probable es que se equivoque el modelo: baja la confianza.
# Regla de prudencia (no hay historial de cuotas de estadísticas para ajustarla con el backtest).
STAT_DISAGREE_TOLERANCE = 0.05  # hasta 5 puntos no se penaliza: ahí está el valor que se busca
STAT_DISAGREE_SPAN = 0.15  # de 5 a 20 puntos la confianza baja linealmente hasta el mínimo
STAT_DISAGREE_MIN_FACTOR = 0.3


def book_fair_prob(odds_rows: list[m.OddsSnapshot], bookmaker: str, market: str, selection: str,
                   line: float | None) -> float | None:
    """Probabilidad sin margen que da una casa a una selección, si tiene todos los lados de esa línea."""
    rows = [r for r in odds_rows if r.bookmaker == bookmaker and r.market == market]

    def price(sel: str, ln: float | None) -> float | None:
        return next((r.price for r in rows if r.selection == sel and r.line == ln), None)

    if market.startswith("ou_"):
        over, under = price("over", line), price("under", line)
        if over and under:
            p_over, p_under = oddsmath.devig([over, under])
            return p_over if selection == "over" else p_under
    elif market.startswith("ah") and line is not None and selection in ("home", "away"):
        mine, other = price(selection, line), price("away" if selection == "home" else "home", -line)
        if mine and other:
            return oddsmath.devig([mine, other])[0]
    elif market.startswith("1x2") or market == "eh":
        trio = [price(s, line) for s in ("home", "draw", "away")]
        if all(trio):
            return dict(zip(("home", "draw", "away"), oddsmath.devig(trio), strict=True)).get(selection)
    return None


def stat_disagreement_factor(model_p: float, book_p: float) -> float:
    gap = abs(model_p - book_p)
    if gap <= STAT_DISAGREE_TOLERANCE:
        return 1.0
    return max(STAT_DISAGREE_MIN_FACTOR, 1 - (gap - STAT_DISAGREE_TOLERANCE) / STAT_DISAGREE_SPAN)


def is_goal_market(market: str) -> bool:
    """Mercados de goles: los únicos validados en el backtest contra cuotas reales."""
    return market in GOAL_MARKETS or market.startswith("ou_goals")
COUNT_LINE_STATS = ("shots", "shots_on_target", "corners", "cards", "fouls")
MARKET_LABELS = {
    "1x2": "Resultado", "ah": "Hándicap asiático", "eh": "Hándicap (3 vías)", "ou_goals": "Goles",
    "btts": "Ambos marcan", "dnb": "Empate no válido", "dc": "Doble oportunidad",
    "ou_shots": "Remates totales", "ou_shots_on_target": "Remates a puerta", "ou_sot": "Remates a puerta",
    "ou_corners": "Córners", "ah_corners": "Hándicap de córners", "1x2_corners": "Más córners",
    "ou_cards": "Tarjetas", "ah_cards": "Hándicap de tarjetas", "1x2_cards": "Más tarjetas",
    "ou_fouls": "Faltas", "player_shots": "Remates del jugador",
    "player_sot": "Remates a puerta del jugador", "player_card": "Tarjeta al jugador",
    "player_goal": "Gol del jugador", "player_fouls": "Faltas del jugador",
    "player_assist": "Asistencia del jugador", "player_goal_assist": "Gol o asistencia del jugador",
}


def bet_label(market: str, selection: str, line: float | None, home: str, away: str,
          player_name: str | None = None) -> str:
    """Texto de una apuesta como lo vería el usuario: "Hándicap (3 vías): Coventry +2"."""
    sel = {"home": home, "away": away, "draw": "Empate", "over": "Más de", "under": "Menos de",
           "yes": "Sí", "no": "No"}.get(selection, selection)
    base = MARKET_LABELS.get(market.replace("_home", "").replace("_away", ""), market)
    if market.endswith("_home"):
        base += f" ({home})"
    elif market.endswith("_away"):
        base += f" ({away})"
    if player_name:
        base += f" — {player_name}"
    if market.startswith("ah") and line is not None:
        return f"{base}: {sel} {line:+g}"
    if market == "eh" and line is not None:
        # La línea se guarda como hándicap del local; se muestra como en la casa: "Coventry +2"
        if selection == "away":
            return f"{base}: {away} {-line:+g}"
        if selection == "draw":
            return f"{base}: Empate ({home} {line:+g})"
        return f"{base}: {home} {line:+g}"
    if line is not None:
        return f"{base}: {sel} {line:g}"
    return f"{base}: {sel}"


@dataclass
class BetEval:
    market: str
    selection: str
    line: float | None
    bookmaker: str
    odds: float
    model_prob: float
    sharp_prob: float | None
    prob: float  # probabilidad final (mezcla)
    fair_odds: float
    ev: float
    stake_pct: float
    confidence: float
    player_id: int | None = None
    reasons: list[str] = field(default_factory=list)

    def label(self, home: str, away: str, player_name: str | None = None) -> str:
        return bet_label(self.market, self.selection, self.line, home, away, player_name)

    def to_dict(self) -> dict:
        return {
            "market": self.market, "selection": self.selection, "line": self.line, "bookmaker": self.bookmaker,
            "odds": self.odds, "model_prob": round(self.model_prob, 4),
            "sharp_prob": round(self.sharp_prob, 4) if self.sharp_prob is not None else None,
            "prob": round(self.prob, 4), "fair_odds": round(self.fair_odds, 3), "ev": round(self.ev, 4),
            "stake_pct": self.stake_pct, "confidence": round(self.confidence, 3), "player_id": self.player_id,
            "reasons": self.reasons,
        }


@dataclass
class MatchAnalysis:
    match: m.Match
    model: MatchModel
    stage: str
    difficulty: dict
    adjustments: dict
    context: dict
    referee: dict | None
    data_quality: dict
    bets: list[BetEval]
    min_odds_props: list[dict]

    def to_dict(self) -> dict:
        mt = self.match
        return {
            "match_id": mt.id,
            "competition": mt.competition.name,
            "kickoff_utc": mt.kickoff_utc.isoformat(),
            "kickoff_local": mt.kickoff_utc.astimezone(get_settings().tz).strftime("%Y-%m-%d %H:%M"),
            "home": mt.home_team.name,
            "away": mt.away_team.name,
            "home_id": mt.home_team_id,
            "away_id": mt.away_team_id,
            "stage": self.stage,
            "model": self.model.summary(),
            "difficulty": self.difficulty,
            "lineups_and_absences": self.adjustments,
            "context": self.context,
            "referee": self.referee,
            "data_quality": self.data_quality,
            "value_bets": [
                {**b.to_dict(), "label": b.label(mt.home_team.name, mt.away_team.name,
                                                 self.model.players[b.player_id].name if b.player_id in self.model.players else None)}
                for b in self.bets if b.ev > 0
            ],
            "props_min_odds": self.min_odds_props,
            "players": [p.to_dict() for p in sorted(self.model.players.values(), key=lambda p: -p.lam.get("shots", 0))[:16]],
        }


# --------------------------------------------------------------------------- piezas


def _team_avg(model, team_id: int, home: bool) -> float:
    """Media del equipo contra un rival promedio (para escalar a los jugadores)."""
    return math.exp(model.mu + (model.home_adv if home else 0) + model.attack.get(team_id, 0.0))


def _player_projections(
    s: Session, bundle: ModelBundle, match: m.Match, team_id: int, is_home: bool, count_means: dict, goal_lam: float
) -> list[PlayerProjection]:
    lineup = s.execute(
        select(m.Lineup, m.Player).join(m.Player, m.Player.id == m.Lineup.player_id)
        .where(m.Lineup.match_id == match.id, m.Lineup.team_id == team_id)
    ).all()
    out_players = {
        a.player_id for a in s.scalars(
            select(m.Availability).where(m.Availability.team_id == team_id, m.Availability.active.is_(True))
        ) if a.kind in ("injury", "suspension")
    }
    candidates: list[tuple[int, str, str | None, float]] = []  # player, name, pos, start_prob
    if lineup:
        confirmed = lineup[0][0].status == "confirmed"
        for row, p in lineup:
            if row.is_starter:
                candidates.append((p.id, p.name, row.position or p.position, 1.0 if confirmed else 0.85))
            else:
                candidates.append((p.id, p.name, row.position or p.position, 0.0))
    else:
        for pid, pr in bundle.players.items():
            if pr["team_id"] == team_id and pid not in out_players and pr["starts"] >= 2:
                rate = pr["starts"] / max(pr["apps"], 1)
                candidates.append((pid, pr["name"], pr["position"], min(0.9, rate)))

    goals_model = bundle.goals
    team_shots_ratio = 1.0
    if "shots" in bundle.counts:
        team_shots_ratio = count_means["shots"][0 if is_home else 1] / _team_avg(bundle.counts["shots"], team_id, is_home)
    goals_ratio = goal_lam / _team_avg(goals_model, team_id, is_home)
    cards_ratio = 1.0
    if "cards" in bundle.counts:
        cards_ratio = count_means["cards"][0 if is_home else 1] / _team_avg(bundle.counts["cards"], team_id, is_home)

    projections = []
    for pid, name, pos, start_prob in candidates:
        pr = bundle.players.get(pid)
        prior = bundle.priors.get(pos or "MF") or bundle.priors.get("MF") or {}
        k = 4.0  # equivale a 4 partidos completos de la media de su posición
        rates = {}
        for st in ("shots", "shots_on_target", "goals", "xg", "assists", "xa", "fouls_committed", "yellow_cards"):
            obs90, mins90 = (pr["per90"].get(st, 0.0), pr["minutes90"]) if pr else (0.0, 0.0)
            rates[st] = (obs90 * mins90 + prior.get(st, 0.0) * k) / (mins90 + k)
        avg_start_min = (pr or {}).get("avg_starter_minutes") or 78.0
        exp_min = start_prob * avg_start_min + (1 - start_prob) * (0.55 * 22 if lineup else 0.0)
        if exp_min < 5:
            continue
        f = exp_min / 90
        if "goals_share" in prior:
            # Parte de los goles de su equipo que marca (y asiste) en los minutos que juega, contraída hacia la de su
            # posición, por los goles que se esperan de su equipo en ESTE partido. No se escala contra un "rival
            # promedio": ese rival incluye ligas más débiles e infla la media del equipo (docs/modelos.md, sección 4).
            exposure = (pr or {}).get("team_goals90") or 0.0
            obs = (pr or {}).get("share") or {}
            k_goals = 6.0  # unos 4 partidos de goles de un equipo medio
            sh = {st: (obs.get(st, 0.0) * exposure + prior.get(f"{st}_share", 0.0) * k_goals) / (exposure + k_goals)
                  for st in ("goals", "xg", "assists", "xa")}
            goals_lam = (0.5 * sh["goals"] + 0.5 * sh["xg"]) * f * goal_lam
            assists_lam = (0.5 * sh["assists"] + 0.5 * sh["xa"]) * f * goal_lam
        else:  # paquete de modelos anterior: tasas por 90' escaladas contra el rival promedio
            goals_lam = (0.5 * rates["goals"] + 0.5 * rates["xg"]) * f * goals_ratio
            assists_lam = (0.5 * rates["assists"] + 0.5 * rates["xa"]) * f * goals_ratio
        lam = {
            "shots": rates["shots"] * f * team_shots_ratio,
            "shots_on_target": rates["shots_on_target"] * f * team_shots_ratio,
            "goals": goals_lam,
            "assists": assists_lam,
            "fouls_committed": rates["fouls_committed"] * f,
            "yellow_cards": rates["yellow_cards"] * f * cards_ratio,
        }
        projections.append(PlayerProjection(pid, name, team_id, pos, exp_min, start_prob, lam))
    return projections


def _latest_odds(s: Session, match_id: int) -> list[m.OddsSnapshot]:
    rows = s.scalars(
        select(m.OddsSnapshot)
        .where(m.OddsSnapshot.match_id == match_id, m.OddsSnapshot.kind != "closing")
        .order_by(m.OddsSnapshot.captured_at)
    ).all()
    latest: dict[tuple, m.OddsSnapshot] = {}
    for r in rows:
        latest[(r.bookmaker, r.market, r.selection, r.line)] = r
    return list(latest.values())


def _sharp_prob(odds_rows: list[m.OddsSnapshot], market: str, selection: str, line: float | None) -> float | None:
    """Probabilidad sin margen según Pinnacle / Betfair Exchange para esa selección."""
    for book in SHARP_BOOKS:
        rows = [r for r in odds_rows if r.bookmaker == book and r.market == market]
        if market == "1x2":
            book_odds = {r.selection: r.price for r in rows}
            if len(book_odds) == 3:
                probs = oddsmath.devig([book_odds["home"], book_odds["draw"], book_odds["away"]])
                return dict(zip(["home", "draw", "away"], probs, strict=True))[selection]
        elif market == "ou_goals":
            pair = {r.selection: r.price for r in rows if r.line == line}
            if len(pair) == 2:
                p_over, p_under = oddsmath.devig([pair["over"], pair["under"]])
                return p_over if selection == "over" else p_under
        elif market == "ah":
            home = next((r.price for r in rows if r.selection == "home" and r.line == (line if selection == "home" else -line)), None)
            away = next((r.price for r in rows if r.selection == "away" and r.line == (line if selection == "away" else -line)), None)
            if home and away:
                ph, pa = oddsmath.devig([home, away])
                return ph if selection == "home" else pa
    return None


def _confidence(
    market: str, quality: dict, has_sharp: bool, model_p: float, sharp_p: float | None, rotation: str
) -> float:
    c = quality["lineup_factor"] * quality["sample_factor"] * quality.get("market_factor", 1.0)
    if market.startswith("player_"):
        c *= 0.65
    elif market in MAIN_MARKETS:
        c *= 1.0 if has_sharp else 0.85
    else:
        c *= 0.75
    if sharp_p is not None:
        c *= 0.5 + 0.5 * (1 - min(1.0, abs(model_p - sharp_p) / 0.2))
    if quality["lineup_status"] != "confirmed":
        c *= {"alta": 0.75, "media": 0.9}.get(rotation, 1.0)
    return max(0.0, min(1.0, c))


def evaluate_bet(
    analysis_model: MatchModel, quality: dict, rotation: str, odds_rows: list[m.OddsSnapshot],
    market: str, selection: str, line: float | None, odds: float, bookmaker: str, player_id: int | None = None,
) -> BetEval:
    settings = get_settings()
    out: Outcome = analysis_model.outcome(market, selection, line, player_id)
    model_p = out.effective_prob()
    sharp_p = _sharp_prob(odds_rows, market, selection, line) if market in ("1x2", "ou_goals", "ah") else None
    prob = W_MODEL * model_p + (1 - W_MODEL) * sharp_p if sharp_p is not None else model_p
    w_cov = quality.get("market_weight", 1.0)
    book_p = None
    if sharp_p is None and w_cov < 1.0 and is_goal_market(market):
        book_p = min(0.99, 1 / (odds * (1 + BOOK_MARGIN)))
        prob = w_cov * model_p + (1 - w_cov) * book_p
    no_push = max(1e-9, 1 - out.push)
    ev = (prob * odds - 1) * no_push
    stake = oddsmath.stake_pct(prob, odds, settings.kelly_fraction, settings.max_stake_pct)
    conf = _confidence(market, quality, sharp_p is not None, model_p, sharp_p, rotation)
    reasons = []
    if not is_goal_market(market) and not market.startswith("player_"):
        house_p = book_fair_prob(odds_rows, bookmaker, market, selection, line)
        if house_p is not None:
            factor = stat_disagreement_factor(model_p, house_p)
            conf *= factor
            if factor < 1.0:
                reasons.append(f"La casa (sin margen) da {house_p:.0%} y el modelo {model_p:.0%}: discrepan mucho, "
                               "probablemente se equivoca el modelo (confianza baja)")
    if sharp_p is not None:
        reasons.append(f"Modelo {model_p:.0%} · mercado afilado {sharp_p:.0%} · mezcla {prob:.0%}")
    elif book_p is not None:
        reasons.append(f"Modelo {model_p:.0%} · cuota sin margen {book_p:.0%} · mezcla {prob:.0%}: "
                       f"{quality.get('no_market_note', 'equipo con pocas cuotas de referencia')}")
    else:
        reasons.append(f"Probabilidad del modelo {model_p:.0%} (sin referencia de mercado afilado)")
    # float(): los cálculos devuelven tipos numpy, que no se serializan a JSON (p.ej. numpy.bool en comparaciones)
    return BetEval(market, selection, line, bookmaker, float(odds), float(model_p),
                   float(sharp_p) if sharp_p is not None else None, float(prob),
                   1 / float(prob) if prob > 0 else float("inf"), float(ev), float(stake), float(conf),
                   player_id, reasons)


# --------------------------------------------------------------------------- análisis


def analyze(s: Session, bundle: ModelBundle, match: m.Match) -> MatchAnalysis:
    home, away = match.home_team_id, match.away_team_id
    base_h, base_a = bundle.goals.expected(home, away, match.neutral_venue)

    adj_h = lu.adjustment(s, match, home)
    adj_a = lu.adjustment(s, match, away)
    lam_h = base_h * adj_h.attack_mult * adj_a.defence_mult
    lam_a = base_a * adj_a.attack_mult * adj_h.defence_mult

    referee = None
    ref_cards = ref_fouls = 1.0
    if match.referee_id:
        r = bundle.referees.get(match.referee_id)
        ref = s.get(m.Referee, match.referee_id)
        referee = {"name": ref.name, **(r or {"matches": 0, "note": "Sin historial suficiente"})}
        if r:
            ref_cards, ref_fouls = r["cards_factor"], r.get("fouls_factor", 1.0)

    count_means: dict[str, tuple[float, float]] = {}
    dispersion: dict[str, float] = {}
    for stat, cm in bundle.counts.items():
        mh, ma = cm.expected(home, away, match.neutral_venue)
        if stat in ("shots", "shots_on_target", "corners"):
            # Un equipo más fuerte de lo habitual genera más volumen ofensivo (efecto atenuado)
            mh *= (adj_h.attack_mult * adj_a.defence_mult) ** 0.7
            ma *= (adj_a.attack_mult * adj_h.defence_mult) ** 0.7
        elif stat == "cards":
            mh, ma = mh * ref_cards, ma * ref_cards
        elif stat == "fouls":
            mh, ma = mh * ref_fouls, ma * ref_fouls
        count_means[stat] = (mh, ma)
        dispersion[stat] = cm.dispersion

    mm = MatchModel(home, away, lam_h, lam_a, bundle.rho, count_means, dispersion)
    for is_home, tid, lam in ((True, home, lam_h), (False, away, lam_a)):
        for pp in _player_projections(s, bundle, match, tid, is_home, count_means, lam):
            mm.players[pp.player_id] = pp

    # Dificultad para cada equipo: con la fuerza base (ambos al completo) y con la alineación real
    difficulty = {
        "home": {"base": ctx.difficulty_label(base_h - base_a), "ajustada": ctx.difficulty_label(lam_h - lam_a),
                 "goal_diff": round(lam_h - lam_a, 2)},
        "away": {"base": ctx.difficulty_label(base_a - base_h), "ajustada": ctx.difficulty_label(lam_a - lam_h),
                 "goal_diff": round(lam_a - lam_h, 2)},
    }
    c_h = ctx.team_context(s, match, home, lam_h - lam_a)
    c_a = ctx.team_context(s, match, away, lam_a - lam_h)
    rotation = max((c_h.rotation_risk, c_a.rotation_risk), key=["baja", "media", "alta"].index)

    lineup_status = "confirmed" if adj_h.source == adj_a.source == "confirmed" else (
        "predicted" if "predicted" in (adj_h.source, adj_a.source) else adj_h.source)
    lineup_factor = {"confirmed": 1.0, "predicted": 0.85, "injuries_only": 0.72, "none": 0.6}.get(lineup_status, 0.7)
    n_min = min(bundle.goals.n_matches.get(home, 0.0), bundle.goals.n_matches.get(away, 0.0))
    cov = bundle.goals.market_matches
    market_min = min(cov.get(home, 0), cov.get(away, 0)) if cov else None
    thin = [t.name for t in (match.home_team, match.away_team) if cov and cov.get(t.id, 0) < MARKET_COVERED]
    quality = {
        "lineup_status": lineup_status,
        "lineup_factor": lineup_factor,
        "sample_factor": round(min(1.0, 0.4 + n_min / 25), 3),
        "weighted_matches_min": round(n_min, 1),
        "referee_known": referee is not None,
        "model_as_of": bundle.as_of.isoformat(),
        # Cobertura del mercado (ver MARKET_COVERED): None = el paquete de modelos no la trae
        "market_matches_min": market_min,
        "market_factor": round(MIN_MARKET_FACTOR + (1 - MIN_MARKET_FACTOR) * min(1.0, market_min / MARKET_COVERED), 3)
        if market_min is not None else 1.0,
        "market_weight": round(market_coverage_weight(market_min), 3),
    }
    if thin:
        quality["no_market_note"] = (f"{' y '.join(thin)} casi sin cuotas de su liga en nuestros datos; "
                                     "el modelo es poco fiable en este partido")

    # Evaluar todas las cuotas disponibles de mis casas
    odds_rows = _latest_odds(s, match.id)
    bets = []
    for r in odds_rows:
        if r.bookmaker not in MY_BOOKS:
            continue
        try:
            bets.append(evaluate_bet(mm, quality, rotation, odds_rows, r.market, r.selection, r.line, r.price, r.bookmaker))
        except ValueError:
            continue
    bets.sort(key=lambda b: -b.ev)

    # Props sin cuota: cuota mínima a pedir en Betano/bet365 para tener +5% de valor
    min_odds = []
    for stat in COUNT_LINE_STATS:
        if stat not in count_means:
            continue
        total = sum(count_means[stat])
        for ln in (math.floor(total) - 1.5, math.floor(total) - 0.5, math.floor(total) + 0.5, math.floor(total) + 1.5):
            if ln <= 0:
                continue
            for sel in ("over", "under"):
                o = mm.outcome(f"ou_{stat}", sel, ln)
                p = o.effective_prob()
                if 0.55 <= p <= 0.80:
                    min_odds.append({"market": f"ou_{stat}", "selection": sel, "line": ln, "prob": round(p, 3),
                                     "fair_odds": round(1 / p, 2), "min_odds": round(1.05 / p, 2)})
    for pp in mm.players.values():
        if pp.start_prob < 0.8:
            continue
        for market, sel, ln in (("player_shots", "over", 0.5), ("player_shots", "over", 1.5),
                                ("player_sot", "over", 0.5), ("player_goal_assist", "yes", None),
                                ("player_card", "yes", None)):
            p = mm.outcome(market, sel, ln, pp.player_id).effective_prob()
            if 0.5 <= p <= 0.85 or (market in ("player_card", "player_goal_assist") and p >= 0.35):
                min_odds.append({"market": market, "selection": sel, "line": ln, "player_id": pp.player_id,
                                 "player": pp.name, "prob": round(p, 3), "fair_odds": round(1 / p, 2),
                                 "min_odds": round(1.05 / p, 2)})
    min_odds.sort(key=lambda x: -x["prob"])

    def adj_dict(a: lu.LineupAdjustment) -> dict:
        return {"source": a.source, "attack_mult": a.attack_mult, "defence_mult": a.defence_mult,
                "xi_attack": a.xi_attack, "base_attack": a.base_attack, "xi_defence": a.xi_defence,
                "base_defence": a.base_defence, "missing_regulars": a.missing_regulars, "notes": a.notes}

    def ctx_dict(c: ctx.TeamContext) -> dict:
        return {"rest_days": round(c.rest_days, 1) if c.rest_days is not None else None,
                "matches_last_14d": c.matches_last_14d, "next_match_days": c.next_match_days,
                "next_match_competition": c.next_match_competition, "rotation_risk": c.rotation_risk,
                "notes": c.notes}

    return MatchAnalysis(
        match=match,
        model=mm,
        stage=lineup_status,
        difficulty=difficulty,
        adjustments={"home": adj_dict(adj_h), "away": adj_dict(adj_a)},
        context={"home": ctx_dict(c_h), "away": ctx_dict(c_a)},
        referee=referee,
        data_quality=quality,
        bets=bets,
        min_odds_props=min_odds[:25],
    )


def evaluate_user_odds(
    s: Session, bundle: ModelBundle, match: m.Match, market: str, selection: str, line: float | None,
    odds: float, bookmaker: str = "betano", player_id: int | None = None,
) -> tuple[MatchAnalysis, BetEval]:
    """Evalúa una cuota que el usuario ve en su casa de apuestas."""
    an, (ev,) = evaluate_user_odds_many(s, bundle, match, [(market, selection, line, odds, bookmaker, player_id)])
    if isinstance(ev, Exception):
        raise ev
    return an, ev


def evaluate_user_odds_many(
    s: Session, bundle: ModelBundle, match: m.Match,
    items: list[tuple[str, str, float | None, float, str, int | None]],
) -> tuple[MatchAnalysis, list[BetEval | ValueError]]:
    """Evalúa varias cuotas del mismo partido con un solo análisis (p.ej. todas las de una captura).

    Cada elemento es (mercado, selección, línea, cuota, casa, id_jugador). Una cuota con un mercado o línea
    no válidos devuelve su ValueError en su posición, sin impedir evaluar las demás.
    """
    an = analyze(s, bundle, match)
    rotation = max((an.context["home"]["rotation_risk"], an.context["away"]["rotation_risk"]),
                   key=["baja", "media", "alta"].index)
    odds_rows = _latest_odds(s, match.id)
    out: list[BetEval | ValueError] = []
    for market, selection, line, odds, bookmaker, player_id in items:
        try:
            out.append(evaluate_bet(an.model, an.data_quality, rotation, odds_rows, market, selection, line,
                                    odds, bookmaker, player_id))
        except (ValueError, KeyError) as exc:
            out.append(exc if isinstance(exc, ValueError) else ValueError(f"Selección no válida: {exc}"))
    return an, out


def now_utc() -> datetime:
    return datetime.now(UTC)
