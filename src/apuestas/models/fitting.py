"""Ajuste de todos los modelos a partir de la base de datos y guardado del "paquete" de modelos.

Paquete (var/models/latest.json):
- goals: fuerza ataque/defensa con objetivo = 15% goles + 85% xG (el xG predice mejor que los goles),
  más los goles esperados implícitos en las cuotas de cierre como observaciones extra (MARKET_WEIGHT)
- rho: corrección Dixon-Coles para marcadores bajos
- counts[stat]: modelos de remates, remates a puerta, córners, faltas y tarjetas (binomial negativa); los de
  remates y córners, guiados por la fuerza del equipo en el modelo de goles
- referees: factor de tarjetas/faltas de cada árbitro (con contracción hacia 1)
- players: tasas por 90' de cada jugador (remates, a puerta, goles, xG, faltas, amarillas), su parte de los goles,
  remates, a puerta y tarjetas de su equipo (para repartir lo que se espera del equipo en un partido) y sus minutos
  en los últimos partidos del equipo (para los partidos que aún no tienen alineación)
- priors: tasas medias por posición (para contraer jugadores con pocos minutos)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import poisson
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from apuestas.betting import odds as oddsmath
from apuestas.config import get_settings
from apuestas.core.competitions import COMPETITIONS
from apuestas.db import models as m
from apuestas.models import market, ratings
from apuestas.models.ratings import MatchObs, RatingModel

log = logging.getLogger(__name__)

MODEL_VERSION = "v1"
GOALS_XG_WEIGHT = 0.85  # elegido por backtest 2024-26 (mejor log-loss que 0, 0.3 y 0.6)
# Competiciones cuyo xG no entra en el modelo de goles (solo sus goles): la Europa League y la Conference, que traen
# estadísticas de FotMob desde el 21-10-2026 para los modelos de conteo. Con su xG, la log-loss 1X2 de la Champions
# empeoraba (+0,0062 ± 0,0025 por partido, backtest 2024-26) y la de las ligas no cambiaba.
GOALS_XG_SKIP = frozenset(code for code, c in COMPETITIONS.items() if c.fotmob_stats)
COUNT_STATS = ("shots", "shots_on_target", "corners", "fouls", "cards")
PLAYER_STATS = ("shots", "shots_on_target", "goals", "xg", "assists", "xa", "fouls_committed", "yellow_cards")
# Goles y asistencias también como parte de los goles de su equipo en los minutos que jugó (para repartirlos)
SHARE_STATS = ("goals", "xg", "assists", "xa")
# Remates, a puerta y amarillas también como parte de los de su equipo en los minutos que jugó: estadística del
# jugador → la del equipo en los modelos de conteo (tarjetas del equipo = amarillas + rojas, como en load_matches)
VOLUME_SHARE_STATS = {"shots": "shots", "shots_on_target": "shots_on_target", "yellow_cards": "cards"}
# Minutos esperados sin alineación: media de los minutos de cada jugador en los últimos partidos de su equipo
RECENT_TEAM_MATCHES = 8


@dataclass
class ModelBundle:
    version: str
    as_of: date
    goals: RatingModel
    rho: float
    counts: dict[str, RatingModel]
    referees: dict[int, dict]
    players: dict[int, dict]
    priors: dict[str, dict[str, float]]
    league_avgs: dict[str, float] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "as_of": self.as_of.isoformat(),
            "goals": self.goals.to_dict(),
            "rho": self.rho,
            "counts": {k: v.to_dict() for k, v in self.counts.items()},
            "referees": {str(k): v for k, v in self.referees.items()},
            "players": {str(k): v for k, v in self.players.items()},
            "priors": self.priors,
            "league_avgs": self.league_avgs,
        }

    @classmethod
    def from_json(cls, d: dict) -> ModelBundle:
        return cls(
            version=d["version"],
            as_of=date.fromisoformat(d["as_of"]),
            goals=RatingModel.from_dict(d["goals"]),
            rho=d["rho"],
            counts={k: RatingModel.from_dict(v) for k, v in d["counts"].items()},
            referees={int(k): v for k, v in d["referees"].items()},
            players={int(k): v for k, v in d["players"].items()},
            priors=d["priors"],
            league_avgs=d.get("league_avgs", {}),
        )


def bundle_path() -> Path:
    return get_settings().var_dir / "models" / "latest.json"


def save_bundle(bundle: ModelBundle, path: Path | None = None) -> Path:
    path = path or bundle_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.to_json()))
    return path


_cache: dict[str, tuple[float, ModelBundle]] = {}


def load_bundle(path: Path | None = None) -> ModelBundle:
    path = path or bundle_path()
    mtime = path.stat().st_mtime
    cached = _cache.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    bundle = ModelBundle.from_json(json.loads(path.read_text()))
    _cache[str(path)] = (mtime, bundle)
    return bundle


# --------------------------------------------------------------------------- datos


@dataclass
class MatchRow:
    match_id: int
    competition: str
    day: date
    home: int
    away: int
    neutral: bool
    hg: int
    ag: int
    referee_id: int | None
    stats_h: dict[str, float | None]
    stats_a: dict[str, float | None]


def model_codes() -> list[str]:
    """Competiciones con las que se entrena. Las ligas extra solo si `extra_leagues_in_model` está activado."""
    extra = get_settings().extra_leagues_in_model
    return [code for code, c in COMPETITIONS.items() if c.fd_extra is None or extra]


def load_matches(s: Session, before: datetime, since: datetime) -> list[MatchRow]:
    th, ta = aliased(m.TeamMatchStats), aliased(m.TeamMatchStats)
    q = (
        select(m.Match, m.Competition.code, th, ta)
        .join(m.Competition, m.Competition.id == m.Match.competition_id)
        .outerjoin(th, and_(th.match_id == m.Match.id, th.team_id == m.Match.home_team_id))
        .outerjoin(ta, and_(ta.match_id == m.Match.id, ta.team_id == m.Match.away_team_id))
        .where(
            m.Match.status == "finished",
            m.Match.home_goals.is_not(None),
            m.Match.kickoff_utc < before,
            m.Match.kickoff_utc >= since,
            # Solo las competiciones que conoce esta versión del código: la BD es compartida y otra rama puede
            # haber cargado ligas que aún no se han validado con el backtest
            m.Competition.code.in_(model_codes()),
        )
    )
    rows = []
    for match, code, sh, sa in s.execute(q):

        def stats(t: m.TeamMatchStats | None) -> dict[str, float | None]:
            if t is None:
                return {}
            cards = None
            if t.yellow_cards is not None:
                cards = t.yellow_cards + (t.red_cards or 0)
            return {
                "xg": t.xg,
                "shots": t.shots,
                "shots_on_target": t.shots_on_target,
                "corners": t.corners,
                "fouls": t.fouls,
                "cards": cards,
            }

        rows.append(
            MatchRow(
                match_id=match.id,
                competition=code,
                day=match.kickoff_utc.date(),
                home=match.home_team_id,
                away=match.away_team_id,
                neutral=match.neutral_venue,
                hg=match.home_goals,
                ag=match.away_goals,
                referee_id=match.referee_id,
                stats_h=stats(sh),
                stats_a=stats(sa),
            )
        )
    return rows


def goals_obs(rows: list[MatchRow], xg_weight: float = GOALS_XG_WEIGHT) -> list[MatchObs]:
    out = []
    for r in rows:
        xh, xa = r.stats_h.get("xg"), r.stats_a.get("xg")
        if xh is not None and xa is not None and r.competition not in GOALS_XG_SKIP:
            yh = (1 - xg_weight) * r.hg + xg_weight * xh
            ya = (1 - xg_weight) * r.ag + xg_weight * xa
        else:
            yh, ya = float(r.hg), float(r.ag)
        out.append(MatchObs(r.home, r.away, r.day, yh, ya, r.neutral))
    return out


# Peso de cada partido "visto por el mercado" (goles esperados de las cuotas de cierre) frente al partido real,
# y vida media (días) de esas observaciones. Backtest 2024-26: log-loss 1X2 0,9928 -> 0,9811 (meseta entre
# peso 64-512 y vida media 7-14; 14 días aguanta mejor el arranque de temporada, tras el parón de verano).
MARKET_WEIGHT = 128.0
MARKET_HALF_LIFE = 14.0
MARKET_BOOKS = ("pinnacle", "bet365")  # por orden de preferencia
MARKET_MAX_RMSE = 0.02  # descarta cuotas que el modelo Dixon-Coles no puede reproducir (errores, mercados raros)


def load_market_goals(s: Session, before: datetime, since: datetime) -> dict[int, tuple[float, float]]:
    """Goles esperados (local, visitante) implícitos en el cierre de Pinnacle o bet365, sin margen."""
    q = (
        select(m.OddsSnapshot.match_id, m.OddsSnapshot.bookmaker, m.OddsSnapshot.market, m.OddsSnapshot.selection,
               m.OddsSnapshot.line, m.OddsSnapshot.price)
        .join(m.Match, m.Match.id == m.OddsSnapshot.match_id)
        .join(m.Competition, m.Competition.id == m.Match.competition_id)
        .where(
            m.Competition.code.in_(model_codes()),
            m.OddsSnapshot.kind == "closing",
            m.OddsSnapshot.bookmaker.in_(MARKET_BOOKS),
            m.OddsSnapshot.market.in_(("1x2", "ou_goals")),
            m.Match.kickoff_utc < before,
            m.Match.kickoff_utc >= since,
        )
    )
    prices: dict[int, dict[tuple, float]] = {}
    for mid, book, mkt, sel, line, price in s.execute(q):
        if mkt == "ou_goals" and line != 2.5:
            continue
        prices.setdefault(mid, {})[(book, mkt, sel)] = price
    ids, p1x2, p_over = [], [], []
    for mid, od in prices.items():
        for book in MARKET_BOOKS:
            o = [od.get((book, "1x2", sel)) for sel in ("home", "draw", "away")]
            if not all(o) or min(o) <= 1.0:
                continue
            p_ov = math.nan  # más/menos 2.5 de la misma casa o, si falta, de la otra
            for b in (book, *MARKET_BOOKS):
                ou = [od.get((b, "ou_goals", sel)) for sel in ("over", "under")]
                if all(ou) and min(ou) > 1.0:
                    p_ov = oddsmath.devig(ou)[0]
                    break
            ids.append(mid)
            p1x2.append(oddsmath.devig(o))
            p_over.append(p_ov)
            break
    if not ids:
        return {}
    lam, rmse = market.implied_goals(np.array(p1x2), np.array(p_over))
    return {mid: (float(lh), float(la)) for mid, (lh, la), e in zip(ids, lam, rmse, strict=True)
            if e <= MARKET_MAX_RMSE}


PREMATCH_MARKET_BOOKS = (*MARKET_BOOKS, "betano")  # antes del partido; Betano solo si no hay otra (Champions)


def prematch_market_goals(prices: dict[tuple[str, str, str], float]) -> tuple[str, float, float] | None:
    """Goles esperados (casa, local, visitante) implícitos en el 1X2 y el más/menos 2.5 de un partido, sin margen.
    `prices`: (casa, mercado, selección) -> cuota, con el más/menos solo de la línea 2.5. None si ninguna casa de
    PREMATCH_MARKET_BOOKS tiene el 1X2 o el modelo Dixon-Coles no reproduce sus cuotas (MARKET_MAX_RMSE)."""
    for book in PREMATCH_MARKET_BOOKS:
        o = [prices.get((book, "1x2", sel)) for sel in ("home", "draw", "away")]
        if not all(o) or min(o) <= 1.0:
            continue
        ou = [prices.get((book, "ou_goals", sel)) for sel in ("over", "under")]
        p_over = oddsmath.devig(ou)[0] if all(ou) and min(ou) > 1.0 else math.nan
        lam, rmse = market.implied_goals(np.array([oddsmath.devig(o)]), np.array([p_over]))
        if rmse[0] <= MARKET_MAX_RMSE:
            return book, float(lam[0][0]), float(lam[0][1])
    return None


def market_obs(rows: list[MatchRow], implied: dict[int, tuple[float, float]],
               weight: float = MARKET_WEIGHT) -> list[MatchObs]:
    if weight <= 0:
        return []
    return [MatchObs(r.home, r.away, r.day, *implied[r.match_id], r.neutral, weight=weight, market=True)
            for r in rows if r.match_id in implied]


# Contracción de los modelos de conteo hacia la media, en partidos ponderados "promedio" (`ratings.fit`,
# `prior_matches`). Antes era una L2 fija de 1, que apenas contraía (~0,1 partidos en remates y faltas, ~0,2 en
# córners, ~0,5 en tarjetas): un rival europeo con dos partidos conservaba lo que vio en ellos. Viking (5 y 7
# córners contra Stuttgart y Bayern) salía con ×1,8 de ataque en córners y Aston Villa-Viking, con 14,7 córners
# esperados frente a 10,5 de Pinnacle. Elegido con el backtest 2024-26 (walk-forward, ligas y Champions; ver
# docs/modelos.md): más contracción donde los equipos se parecen más entre sí (tarjetas) y menos en remates.
COUNT_PRIOR_MATCHES = {"shots": 1.0, "shots_on_target": 1.0, "corners": 5.0, "fouls": 5.0, "cards": 10.0}

# Estadísticas de dominio: se contraen hacia lo que predice la fuerza del equipo en el modelo de goles (`strength` en
# `ratings.fit`) en vez de hacia la media, con esta K. Las ligas solo se cruzan en córners y remates por la
# Champions (unos 14 partidos ponderados para la Eredivisie), así que antes la L2 las ponía a todas al mismo nivel y
# el Feyenoord, que domina una liga floja, salía con más córners que el Betis (4,2-5,6; Pinnacle 5,3-4,1). Con la
# fuerza como guía, más contracción mejora (antes, con más K empeoraba el reparto entre los dos equipos). Elegido
# con el backtest 2024-26 y las cuotas de Pinnacle guardadas (docs/modelos.md). En tarjetas y faltas no mejora.
COUNT_STRENGTH_PRIOR = {"shots": 8.0, "shots_on_target": 8.0, "corners": 20.0}


def count_strength(goals: RatingModel) -> dict[int, float]:
    """Fuerza de cada equipo en el modelo de goles (ataque + defensa), la referencia de las estadísticas de dominio."""
    return {t: goals.attack[t] + goals.defence[t] for t in goals.teams}


# Peso del 1X2 de la casa en el reparto de remates, a puerta y córners (`strength_shift`). Si la casa ve una
# diferencia de fuerza entre los dos equipos distinta de la del modelo de goles, esas estadísticas se mueven hacia la
# de la casa: el modelo de goles no le gana al mercado, y los conteos heredan sus errores. Betis-Feyenoord (Champions,
# 21-10-2026): el modelo de goles veía a los dos casi iguales (1X2 46/22/32; Pinnacle 60/20/20) y daba 4,6-4,7
# córners; Pinnacle, 5,3-4,1. Con el 1X2 de Pinnacle, 5,0-4,3. Elegido con el walk-forward 2024-26 con las cuotas de
# cierre de 14 ligas (docs/modelos.md): 0,75 es casi el mejor peso en las tres estadísticas.
COUNT_MARKET_SHIFT = 0.75


def strength_delta(market_goals: tuple[float, float], model_goals: tuple[float, float]) -> float:
    """Cuánta fuerza hay que sumar al local (y restar al visitante) en el modelo de goles para que la diferencia
    de goles esperados (en logaritmo) sea la de la casa: δ = ½ [log(λl/λv) casa − log(λl/λv) modelo]."""
    return 0.5 * (math.log(market_goals[0] / market_goals[1]) - math.log(model_goals[0] / model_goals[1]))


def strength_shift(cm: RatingModel, mh: float, ma: float, delta: float,
                   weight: float = COUNT_MARKET_SHIFT) -> tuple[float, float]:
    """Medias (local, visitante) de un conteo guiado por la fuerza cuando la fuerza del local sube δ y la del
    visitante baja δ: el reparto cambia en exp(±peso × (b_ataque + b_defensa) × δ) y el total del partido se queda
    como estaba (el 1X2 dice quién domina, no cuánto se juega). Sin cambios si el modelo no se ajustó con la fuerza."""
    if not cm.strength_coef or not delta:
        return mh, ma
    f = math.exp(weight * sum(cm.strength_coef) * delta)
    k = (mh + ma) / (mh * f + ma / f)
    return mh * f * k, ma / f * k


def fit_counts(obs: list[MatchObs], stat: str, as_of: date, half_life_days: float = 240.0,
               l2: float | None = None, strength: dict[int, float] | None = None) -> RatingModel:
    """Modelo de una estadística de conteo. `strength` (`count_strength` del modelo de goles) solo se usa en las de
    COUNT_STRENGTH_PRIOR. `l2` fija la L2 de antes (1,0), sin fuerza, en lugar de COUNT_PRIOR_MATCHES."""
    if l2 is not None:
        return ratings.fit(obs, as_of, half_life_days=half_life_days, l2=l2)
    if strength is not None and stat in COUNT_STRENGTH_PRIOR:
        return ratings.fit(obs, as_of, half_life_days=half_life_days, prior_matches=COUNT_STRENGTH_PRIOR[stat],
                           strength=strength)
    return ratings.fit(obs, as_of, half_life_days=half_life_days, prior_matches=COUNT_PRIOR_MATCHES[stat])


def count_obs(rows: list[MatchRow], stat: str) -> list[MatchObs]:
    out = []
    for r in rows:
        vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
        if vh is not None and va is not None:
            out.append(MatchObs(r.home, r.away, r.day, float(vh), float(va), r.neutral))
    return out


# --------------------------------------------------------------------------- ajustes


def fit_rho(rows: list[MatchRow], model: RatingModel, full_codes: set[str]) -> float:
    sample = [r for r in rows if r.competition in full_codes]
    if len(sample) < 100:
        return -0.05
    lam = [model.expected(r.home, r.away, r.neutral) for r in sample]
    lh = np.array([x[0] for x in lam])
    la = np.array([x[1] for x in lam])
    hg = np.array([r.hg for r in sample])
    ag = np.array([r.ag for r in sample])

    def nll(rho: float) -> float:
        tau = np.ones_like(lh)
        m00 = (hg == 0) & (ag == 0)
        m01 = (hg == 0) & (ag == 1)
        m10 = (hg == 1) & (ag == 0)
        m11 = (hg == 1) & (ag == 1)
        tau[m00] = 1 - lh[m00] * la[m00] * rho
        tau[m01] = 1 + lh[m01] * rho
        tau[m10] = 1 + la[m10] * rho
        tau[m11] = 1 - rho
        tau = np.clip(tau, 1e-9, None)
        return -float(np.sum(np.log(tau) + poisson.logpmf(hg, lh) + poisson.logpmf(ag, la)))

    res = minimize_scalar(nll, bounds=(-0.25, 0.15), method="bounded")
    return float(res.x)


# Contracción del factor de árbitro (en "partidos neutros" añadidos). Elegido con el backtest 2024-26:
# en faltas el árbitro ayuda (mejor con 20-40; se mantiene 20). En tarjetas, ya con árbitros de LaLiga y la
# Bundesliga (FotMob), lo mejor es 40-80: se usa 80 (+0,0044 de log-verosimilitud por partido frente a +0,0037
# con 120). Ayuda en LaLiga (+0,012) y la Bundesliga (+0,005); en la Premier no (-0,003 ± 0,002).
REFEREE_PRIOR_MATCHES = 80.0
REFEREE_PRIOR_MATCHES_FOULS = 20.0


def fit_referees(rows: list[MatchRow], cards_model: RatingModel, fouls_model: RatingModel | None,
                 k_matches: float | None = None) -> dict[int, dict]:
    """Factor de tarjetas del árbitro = (observadas + K) / (esperadas + K): se contrae hacia 1 con pocos partidos."""
    acc: dict[int, dict] = {}
    for r in rows:
        if r.referee_id is None:
            continue
        ch, ca = r.stats_h.get("cards"), r.stats_a.get("cards")
        if ch is None or ca is None:
            continue
        eh, ea = cards_model.expected(r.home, r.away, r.neutral)
        a = acc.setdefault(
            r.referee_id,
            {"matches": 0, "cards_obs": 0.0, "cards_exp": 0.0, "fouls_obs": 0.0, "fouls_exp": 0.0, "fouls_n": 0,
             "last": None},
        )
        a["matches"] += 1
        a["cards_obs"] += ch + ca
        a["cards_exp"] += eh + ea
        fh, fa = r.stats_h.get("fouls"), r.stats_a.get("fouls")
        if fouls_model is not None and fh is not None and fa is not None:
            xh, xa = fouls_model.expected(r.home, r.away, r.neutral)
            a["fouls_obs"] += fh + fa
            a["fouls_exp"] += xh + xa
            a["fouls_n"] += 1
        a["last"] = max(a["last"] or r.day, r.day)
    mean_cards = float(np.mean([v["cards_exp"] / v["matches"] for v in acc.values()])) if acc else 4.0
    k_matches = REFEREE_PRIOR_MATCHES if k_matches is None else k_matches
    k_cards = k_matches * mean_cards  # equivale a k partidos "neutros"
    out = {}
    for rid, a in acc.items():
        fouls_factor = 1.0
        if a["fouls_n"]:
            k_f = REFEREE_PRIOR_MATCHES_FOULS * (a["fouls_exp"] / a["fouls_n"])
            fouls_factor = (a["fouls_obs"] + k_f) / (a["fouls_exp"] + k_f)
        out[rid] = {
            "matches": a["matches"],
            "cards_per_match": round(a["cards_obs"] / a["matches"], 2),
            "expected_cards_per_match": round(a["cards_exp"] / a["matches"], 2),
            "cards_factor": round((a["cards_obs"] + k_cards) / (a["cards_exp"] + k_cards), 3),
            "fouls_per_match": round(a["fouls_obs"] / a["fouls_n"], 1) if a["fouls_n"] else None,
            "fouls_factor": round(fouls_factor, 3),
            "last_match": a["last"].isoformat() if a["last"] else None,
        }
    return out


def _team_volume(tms: m.TeamMatchStats | None) -> dict[str, float | None]:
    """Remates, a puerta y tarjetas del equipo en el partido, con las claves de las estadísticas del jugador."""
    if tms is None:
        return {}
    cards = tms.yellow_cards + (tms.red_cards or 0) if tms.yellow_cards is not None else None
    team = {"shots": tms.shots, "shots_on_target": tms.shots_on_target, "cards": cards}
    return {st: team[team_st] for st, team_st in VOLUME_SHARE_STATS.items()}


def fit_players(s: Session, before: datetime, half_life_days: float = 200.0) -> tuple[dict[int, dict], dict]:
    """Tasas por 90' ponderadas por antigüedad y medias por posición.

    Además, la parte de los goles (SHARE_STATS) y de los remates, a puerta y tarjetas (VOLUME_SHARE_STATS) de su
    equipo que hace cada jugador en los minutos que juega, para repartir lo que se espera del equipo en un partido.
    """
    since = before - timedelta(days=500)
    q = (
        select(m.PlayerMatchStats, m.Match.kickoff_utc, m.Player.position, m.Player.name,
               m.Match.home_team_id, m.Match.home_goals, m.Match.away_goals, m.TeamMatchStats)
        .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
        .join(m.Player, m.Player.id == m.PlayerMatchStats.player_id)
        .outerjoin(m.TeamMatchStats, and_(m.TeamMatchStats.match_id == m.PlayerMatchStats.match_id,
                                          m.TeamMatchStats.team_id == m.PlayerMatchStats.team_id))
        .where(m.Match.kickoff_utc < before, m.Match.kickoff_utc >= since, m.PlayerMatchStats.minutes > 0)
    )
    acc: dict[int, dict] = {}
    pos_acc: dict[str, dict[str, float]] = {}
    appearances: list[tuple[int, int, datetime, int, int, bool]] = []  # equipo, partido, hora, jugador, minutos, titular
    as_of = before.date()
    for pms, ko, pos, name, home_id, home_goals, away_goals, tms in s.execute(q):
        w = 0.5 ** ((as_of - ko.date()).days / half_life_days)
        a = acc.setdefault(
            pms.player_id,
            {"name": name, "position": pos, "team_id": pms.team_id, "w_minutes": 0.0, "starts": 0, "apps": 0,
             "starter_minutes": 0.0, "last": None, "team_goals90": 0.0, "share_obs": {st: 0.0 for st in SHARE_STATS},
             "vol_obs": {st: 0.0 for st in VOLUME_SHARE_STATS}, "vol_team90": {st: 0.0 for st in VOLUME_SHARE_STATS},
             **{st: 0.0 for st in PLAYER_STATS}},
        )
        mins = pms.minutes or 0
        a["w_minutes"] += w * mins
        appearances.append((pms.team_id, pms.match_id, ko, pms.player_id, mins, bool(pms.is_starter)))
        team_goals = home_goals if pms.team_id == home_id else away_goals
        if team_goals is not None:
            # exposición: goles de su equipo, en proporción a los minutos que jugó
            a["team_goals90"] += w * team_goals * mins / 90
        a["apps"] += 1
        if pms.is_starter:
            a["starts"] += 1
            a["starter_minutes"] += mins
        if a["last"] is None or ko.date() > a["last"]:
            a["last"], a["team_id"] = ko.date(), pms.team_id
        p = pos_acc.setdefault(pos or "MF", {"minutes": 0.0, "team_goals90": 0.0,
                                             "share_obs": {st: 0.0 for st in SHARE_STATS},
                                             "vol_obs": {st: 0.0 for st in VOLUME_SHARE_STATS},
                                             "vol_team90": {st: 0.0 for st in VOLUME_SHARE_STATS},
                                             **{st: 0.0 for st in PLAYER_STATS}})
        p["minutes"] += mins
        if team_goals is not None:
            p["team_goals90"] += team_goals * mins / 90
        for st in PLAYER_STATS:
            v = getattr(pms, st)
            if v is not None:
                a[st] += w * float(v)
                p[st] += float(v)
                if st in SHARE_STATS and team_goals is not None:
                    a["share_obs"][st] += w * float(v)
                    p["share_obs"][st] += float(v)
        for st, team_v in _team_volume(tms).items():
            if team_v is not None:
                # FotMob deja vacío (no 0) el remate de quien no remató: vacío = 0, como en las tasas por 90'
                v = float(getattr(pms, st) or 0)
                # exposición: remates (o tarjetas) de su equipo, en proporción a los minutos que jugó
                a["vol_obs"][st] += w * v
                a["vol_team90"][st] += w * team_v * mins / 90
                p["vol_obs"][st] += v
                p["vol_team90"][st] += team_v * mins / 90
    priors = {
        pos: {**{st: (v[st] / v["minutes"] * 90 if v["minutes"] else 0.0) for st in PLAYER_STATS},
              **{f"{st}_share": (v["share_obs"][st] / v["team_goals90"] if v["team_goals90"] else 0.0)
                 for st in SHARE_STATS},
              **{f"{st}_share": (v["vol_obs"][st] / v["vol_team90"][st] if v["vol_team90"][st] else 0.0)
                 for st in VOLUME_SHARE_STATS},
              # remates (o tarjetas) de su equipo por 90': para contraer la parte "en partidos equivalentes"
              **{f"{st}_team90": (v["vol_team90"][st] / v["minutes"] * 90 if v["minutes"] else 0.0)
                 for st in VOLUME_SHARE_STATS}}
        for pos, v in pos_acc.items()
    }
    players = {}
    for pid, a in acc.items():
        if a["w_minutes"] < 1:
            continue
        players[pid] = {
            "name": a["name"],
            "position": a["position"],
            "team_id": a["team_id"],
            "minutes90": round(a["w_minutes"] / 90, 3),
            "per90": {st: round(a[st] / a["w_minutes"] * 90, 4) for st in PLAYER_STATS},
            # parte de los goles de su equipo que marca/asiste (y su xG/xA), y cuántos goles de equipo la respaldan
            "share": {st: round(a["share_obs"][st] / a["team_goals90"], 4) for st in SHARE_STATS}
            if a["team_goals90"] > 0 else None,
            "team_goals90": round(a["team_goals90"], 3),
            # parte de los remates, a puerta y tarjetas de su equipo, y cuántos del equipo la respaldan
            "volume_share": {st: round(a["vol_obs"][st] / a["vol_team90"][st], 4)
                             for st in VOLUME_SHARE_STATS if a["vol_team90"][st] > 0},
            "volume_team90": {st: round(a["vol_team90"][st], 3) for st in VOLUME_SHARE_STATS},
            "starts": a["starts"],
            "apps": a["apps"],
            "avg_starter_minutes": round(a["starter_minutes"] / a["starts"], 1) if a["starts"] else None,
            "last_match": a["last"].isoformat() if a["last"] else None,
        }
    recent_minutes(players, appearances, RECENT_TEAM_MATCHES)
    return players, priors


def recent_minutes(players: dict[int, dict], appearances: list[tuple], n: int) -> None:
    """Minutos y titularidades de cada jugador en los últimos `n` partidos de su equipo actual, con 0 si no jugó.

    Añade `recent_minutes` (media por partido del equipo) y `recent_start_rate` a cada jugador. Solo cuentan los
    partidos desde su primer partido con ese equipo: un fichaje con 3 partidos de titular tiene ~90', no 3 × 90 / 8.
    Así los minutos de un equipo suman lo que juega de verdad (~988 por partido). La frecuencia de titularidad entre
    los partidos que jugó cada uno (starts / apps) sumaba 1.300-1.400 (docs/modelos.md, sección 4).
    """
    kickoffs: dict[int, dict[int, datetime]] = {}  # equipo → partido → hora
    first: dict[tuple[int, int], datetime] = {}  # (jugador, equipo) → su primer partido con ese equipo
    played: dict[tuple[int, int], tuple[int, bool]] = {}  # (jugador, partido) → minutos, titular
    for team_id, match_id, ko, pid, mins, starter in appearances:
        kickoffs.setdefault(team_id, {})[match_id] = ko
        first[(pid, team_id)] = min(ko, first.get((pid, team_id), ko))
        played[(pid, match_id)] = (mins, starter)
    last_n = {t: sorted(ms.items(), key=lambda x: x[1], reverse=True)[:n] for t, ms in kickoffs.items()}
    for pid, pr in players.items():
        since = first.get((pid, pr["team_id"]))
        window = [mid for mid, ko in last_n.get(pr["team_id"], []) if since is not None and ko >= since]
        rows = [played.get((pid, mid), (0, False)) for mid in window]
        pr["recent_minutes"] = round(sum(mins for mins, _ in rows) / len(rows), 1) if rows else 0.0
        pr["recent_start_rate"] = round(sum(st for _, st in rows) / len(rows), 3) if rows else 0.0


def fit_all(as_of: datetime | None = None, half_life_days: float = 240.0) -> ModelBundle:
    from apuestas.core.competitions import FULL

    as_of = as_of or datetime.now(UTC)
    since = as_of - timedelta(days=1100)
    full_codes = {c.code for c in FULL}
    with Session_() as s:
        rows = load_matches(s, before=as_of, since=since)
        implied = load_market_goals(s, before=as_of, since=since) if MARKET_WEIGHT > 0 else {}
        players, priors = fit_players(s, before=as_of)
    log.info("Ajustando modelos con %d partidos (%d con cuotas de cierre)", len(rows), len(implied))
    goals = ratings.fit(goals_obs(rows) + market_obs(rows, implied), as_of.date(), half_life_days=half_life_days,
                        market_half_life_days=MARKET_HALF_LIFE)
    rho = fit_rho([r for r in rows if (as_of.date() - r.day).days < 730], goals, full_codes)
    counts = {}
    strength = count_strength(goals)
    for stat in COUNT_STATS:
        obs = count_obs(rows, stat)
        if len(obs) >= 200:
            counts[stat] = fit_counts(obs, stat, as_of.date(), half_life_days=half_life_days, strength=strength)
    referees = fit_referees(rows, counts["cards"], counts.get("fouls")) if "cards" in counts else {}
    league_avgs: dict[str, float] = {}
    for code in full_codes:
        sub = [r for r in rows if r.competition == code and (as_of.date() - r.day).days < 400]
        if sub:
            league_avgs[f"{code}_goals"] = round(float(np.mean([r.hg + r.ag for r in sub])), 3)
    return ModelBundle(
        version=MODEL_VERSION,
        as_of=as_of.date(),
        goals=goals,
        rho=rho,
        counts=counts,
        referees=referees,
        players=players,
        priors=priors,
        league_avgs=league_avgs,
    )


def Session_() -> Session:  # noqa: N802 - pequeño atajo para tener una sesión de solo lectura
    from apuestas.db.session import _factory

    return _factory()()


def store_team_ratings(bundle: ModelBundle) -> None:
    """Guarda un histórico de ratings (útil para gráficas y para el resumen de temporada)."""
    from apuestas.db.session import session_scope

    with session_scope() as s:
        s.query(m.TeamRating).filter(m.TeamRating.as_of == bundle.as_of).delete()
        for name, model in [("goals", bundle.goals), *bundle.counts.items()]:
            for tid in model.teams:
                s.add(
                    m.TeamRating(
                        team_id=tid,
                        model=name,
                        as_of=bundle.as_of,
                        attack=round(model.attack[tid], 4),
                        defence=round(model.defence[tid], 4),
                        rating=round(model.attack[tid] + model.defence[tid], 4),
                        params={"n": round(model.n_matches.get(tid, 0), 2)},
                    )
                )


def math_safe_exp(x: float) -> float:
    return math.exp(min(max(x, -20), 20))
