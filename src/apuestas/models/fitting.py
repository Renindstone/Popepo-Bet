"""Ajuste de todos los modelos a partir de la base de datos y guardado del "paquete" de modelos.

Paquete (var/models/latest.json):
- goals: fuerza ataque/defensa con objetivo = 15% goles + 85% xG (el xG predice mejor que los goles),
  más los goles esperados implícitos en las cuotas de cierre como observaciones extra (MARKET_WEIGHT)
- rho: corrección Dixon-Coles para marcadores bajos
- counts[stat]: modelos de remates, remates a puerta, córners, faltas y tarjetas (binomial negativa)
- referees: factor de tarjetas/faltas de cada árbitro (con contracción hacia 1)
- players: tasas por 90' de cada jugador (remates, a puerta, goles, xG, faltas, amarillas)
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
COUNT_STATS = ("shots", "shots_on_target", "corners", "fouls", "cards")
PLAYER_STATS = ("shots", "shots_on_target", "goals", "xg", "fouls_committed", "yellow_cards")


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
            m.Competition.code.in_(list(COMPETITIONS)),
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
        if xh is not None and xa is not None:
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
            m.Competition.code.in_(list(COMPETITIONS)),
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


def market_obs(rows: list[MatchRow], implied: dict[int, tuple[float, float]],
               weight: float = MARKET_WEIGHT) -> list[MatchObs]:
    if weight <= 0:
        return []
    return [MatchObs(r.home, r.away, r.day, *implied[r.match_id], r.neutral, weight=weight, market=True)
            for r in rows if r.match_id in implied]


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


def fit_players(s: Session, before: datetime, half_life_days: float = 200.0) -> tuple[dict[int, dict], dict]:
    """Tasas por 90' ponderadas por antigüedad y medias por posición."""
    since = before - timedelta(days=500)
    q = (
        select(m.PlayerMatchStats, m.Match.kickoff_utc, m.Player.position, m.Player.name)
        .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
        .join(m.Player, m.Player.id == m.PlayerMatchStats.player_id)
        .where(m.Match.kickoff_utc < before, m.Match.kickoff_utc >= since, m.PlayerMatchStats.minutes > 0)
    )
    acc: dict[int, dict] = {}
    pos_acc: dict[str, dict[str, float]] = {}
    as_of = before.date()
    for pms, ko, pos, name in s.execute(q):
        w = 0.5 ** ((as_of - ko.date()).days / half_life_days)
        a = acc.setdefault(
            pms.player_id,
            {"name": name, "position": pos, "team_id": pms.team_id, "w_minutes": 0.0, "starts": 0, "apps": 0,
             "starter_minutes": 0.0, "last": None, **{st: 0.0 for st in PLAYER_STATS}},
        )
        mins = pms.minutes or 0
        a["w_minutes"] += w * mins
        a["apps"] += 1
        if pms.is_starter:
            a["starts"] += 1
            a["starter_minutes"] += mins
        if a["last"] is None or ko.date() > a["last"]:
            a["last"], a["team_id"] = ko.date(), pms.team_id
        p = pos_acc.setdefault(pos or "MF", {"minutes": 0.0, **{st: 0.0 for st in PLAYER_STATS}})
        p["minutes"] += mins
        for st in PLAYER_STATS:
            v = getattr(pms, st)
            if v is not None:
                a[st] += w * float(v)
                p[st] += float(v)
    priors = {
        pos: {st: (v[st] / v["minutes"] * 90 if v["minutes"] else 0.0) for st in PLAYER_STATS}
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
            "starts": a["starts"],
            "apps": a["apps"],
            "avg_starter_minutes": round(a["starter_minutes"] / a["starts"], 1) if a["starts"] else None,
            "last_match": a["last"].isoformat() if a["last"] else None,
        }
    return players, priors


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
    for stat in COUNT_STATS:
        obs = count_obs(rows, stat)
        if len(obs) >= 200:
            counts[stat] = ratings.fit(obs, as_of.date(), half_life_days=half_life_days, l2=1.0)
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
