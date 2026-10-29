"""Radar de Sorpresas: los equipos en racha o en baja y los jugadores en racha de las últimas 4 semanas.

Sale de la puntuación por sorpresa de `services/weekly.py` (equipos frente a la casa, jugadores frente a la previa del
modelo). Un **batacazo** es ganar cuando la casa daba un 25 % o menos; un **pinchazo**, perder cuando daba un 60 % o
más. El radar avisa, no predice: no cambia la probabilidad ni el corte de ninguna apuesta.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services import weekly

WINDOW_DAYS = 28
UPSET_MAX = 0.25  # batacazo: gana con esta probabilidad o menos
FLOP_MIN = 0.60  # pinchazo: pierde con esta probabilidad o más
TEAM_SUM = 1.0
PLAYER_SUM = 1.5
PLAYER_MIN_MINUTES = 90
FIGURE_MIN = 1.5
MAX_ROWS = 8
MAX_FIGURES = 2
NEXT_DAYS = 14
CACHE_S = 300
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def classify(score: float, upset: bool, flop: bool) -> str | None:
    """En racha, en baja o fuera del radar. Con batacazo y pinchazo a la vez decide el signo de la suma."""
    if upset and flop:
        return "racha" if score >= 0 else "baja"
    if upset or score >= TEAM_SUM:
        return "racha"
    if flop or score <= -TEAM_SUM:
        return "baja"
    return None


def _result(match: dict) -> tuple[int, int, float] | None:
    """Goles a favor, en contra y probabilidad de ganar que daba la vara, del dato «Resultado» de un partido."""
    item = next((i for i in match["items"] if i["item"] == "result"), None)
    if item is None or item.get("p_over") is None:
        return None
    gf, ga = (int(x) for x in item["actual"].split("-"))
    return gf, ga, float(item["p_over"])


def _local(dt: datetime) -> str:
    loc = weekly._aware(dt).astimezone(get_settings().tz)
    return f"{DIAS[loc.weekday()]} {loc:%d/%m %H:%M}"


def _next_matches(s: Session, team_ids: set[int], as_of: datetime) -> dict[int, list[dict]]:
    if not team_ids:
        return {}
    rows = s.scalars(select(m.Match).where(
        m.Match.status == "scheduled", m.Match.kickoff_utc >= as_of,
        m.Match.kickoff_utc <= as_of + timedelta(days=NEXT_DAYS),
        or_(m.Match.home_team_id.in_(team_ids), m.Match.away_team_id.in_(team_ids))).order_by(m.Match.kickoff_utc))
    out: dict[int, list[dict]] = {t: [] for t in team_ids}
    for mt in rows:
        for t in (mt.home_team_id, mt.away_team_id):
            if t in out and len(out[t]) < 2:
                out[t].append({"match_id": mt.id, "label": f"{mt.home_team.name} vs {mt.away_team.name}",
                               "kickoff_local": _local(mt.kickoff_utc)})
    return out


def _reason(team: dict, kind: str) -> dict:
    best = None
    for mt in team["matches"]:
        res = _result(mt)
        if res is None:
            continue
        gf, ga, p = res
        hit = (gf > ga and p <= UPSET_MAX) if kind == "racha" else (gf < ga and p >= FLOP_MIN)
        if hit and (best is None or (p < best[1] if kind == "racha" else p > best[1])):
            best = (mt, p)
    if best:
        mt, p = best
        kind_word = "batacazo" if kind == "racha" else "pinchazo"
    else:
        sign = 1 if kind == "racha" else -1
        mt = max(team["matches"], key=lambda x: sign * x["score"])
        res = _result(mt)
        p, kind_word = (res[2] if res else None), "suma"
    return {"type": kind_word, "match_id": mt["match_id"], "label": mt["label"], "date": mt["kickoff_local"][:10],
            "p_win": p}


def build(s: Session, as_of: datetime) -> dict:
    """El radar a la fecha dada: los partidos terminados en los 28 días anteriores."""
    as_of = weekly._aware(as_of)
    start = as_of - timedelta(days=WINDOW_DAYS)
    scored = weekly.score_range(s, start, as_of, as_of)

    teams: list[dict] = []
    for t in scored["teams"]:
        results = [r for r in (_result(mt) for mt in t["matches"]) if r]
        upset = any(gf > ga and p <= UPSET_MAX for gf, ga, p in results)
        flop = any(gf < ga and p >= FLOP_MIN for gf, ga, p in results)
        kind = classify(t["score"], upset, flop)
        if kind:
            teams.append({**t, "kind": kind})

    by_team_matches = {t["team_id"]: {x["match_id"] for x in t["matches"]} for t in teams}
    figures: dict[int, list[dict]] = {t: [] for t in by_team_matches}
    for p in scored["players"]:
        own = by_team_matches.get(p["team_id"])
        if not own:
            continue
        best = max((x["score"] for x in p["matches"] if x["match_id"] in own), default=None)
        if best is not None and best >= FIGURE_MIN:
            figures[p["team_id"]].append({"player_id": p["player_id"], "name": p["name"], "score": round(best, 3)})

    players = [p for p in scored["players"] if p["score"] >= PLAYER_SUM and p["minutes"] >= PLAYER_MIN_MINUTES]
    players = sorted(players, key=lambda p: -p["score"])[:MAX_ROWS]
    racha = sorted((t for t in teams if t["kind"] == "racha"), key=lambda t: -t["score"])[:MAX_ROWS]
    baja = sorted((t for t in teams if t["kind"] == "baja"), key=lambda t: t["score"])[:MAX_ROWS]
    nxt = _next_matches(s, {t["team_id"] for t in racha + baja} | {p["team_id"] for p in players}, as_of)

    def team_row(t: dict) -> dict:
        figs = sorted(figures.get(t["team_id"], []), key=lambda f: -f["score"])[:MAX_FIGURES] if t["kind"] == "racha" else []
        return {"team_id": t["team_id"], "name": t["name"], "competition": t["competition"], "kind": t["kind"],
                "score": t["score"], "n_matches": t["n_matches"], "reason": _reason(t, t["kind"]), "figures": figs,
                "next_matches": nxt.get(t["team_id"], [])}

    def player_row(p: dict) -> dict:
        best = max(p["matches"], key=lambda x: x["score"])
        return {"player_id": p["player_id"], "name": p["name"], "team_id": p["team_id"], "team": p["team"],
                "score": p["score"], "minutes": p["minutes"], "n_matches": p["n_matches"],
                "best": {"match_id": best["match_id"], "label": best["label"], "items": best["items"]},
                "next_matches": nxt.get(p["team_id"], [])}

    return {"window_start": start.isoformat(), "window_end": as_of.isoformat(),
            "racha": [team_row(t) for t in racha], "baja": [team_row(t) for t in baja],
            "jugadores": [player_row(p) for p in players]}


def status(s: Session, as_of: datetime) -> dict[int, dict]:
    """Los equipos del radar por id, para los avisos."""
    r = build(s, as_of)
    return {t["team_id"]: t for t in r["racha"] + r["baja"]}


NOTE = "Es un aviso para mirarlo con más cuidado: no cambia la probabilidad ni el corte."
LINEUP_WORD = {"confirmed": "confirmado", "predicted": "probable"}


def alerts_for_match(s: Session, match: m.Match, as_of: datetime, cached: dict[int, dict] | None = None) -> list[dict]:
    """Avisos de un partido: la ficha del radar de cada equipo que esté en él, con sus figuras en el once o no."""
    flagged = status(s, as_of) if cached is None else cached
    rows = [(side, flagged[t]) for side, t in (("home", match.home_team_id), ("away", match.away_team_id)) if t in flagged]
    if not rows:
        return []
    ids = [f["player_id"] for _, row in rows for f in row["figures"]]
    xi = {} if not ids else {r.player_id: LINEUP_WORD.get(r.status) for r in s.scalars(select(m.Lineup).where(
        m.Lineup.match_id == match.id, m.Lineup.player_id.in_(ids), m.Lineup.is_starter.is_(True)))}
    return [{**row, "side": side, "note": NOTE,
             "figures": [{**f, "lineup": xi.get(f["player_id"])} for f in row["figures"]]} for side, row in rows]


def flagged_now() -> dict[int, dict]:
    """Los equipos del radar de ahora, de la caché (para no recalcular 28 días en cada consulta)."""
    r = get()
    return {t["team_id"]: t for t in r["racha"] + r["baja"]}


_cache: dict[str, tuple[float, dict]] = {}


def get(as_of: datetime | None = None) -> dict:
    """El radar de ahora (en caché unos minutos) o de una fecha pasada."""
    if as_of is not None:
        with session_scope() as s:
            return build(s, as_of)
    hit = _cache.get("now")
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    with session_scope() as s:
        data = build(s, datetime.now(UTC))
    _cache["now"] = (time.monotonic(), data)
    return data
