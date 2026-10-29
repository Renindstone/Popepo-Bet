"""«Por qué falló»: lo que se salió de lo esperado cuando se pierde la apuesta del día.

Compara la previa guardada del partido (`services/predictions.py`) con lo que pasó, con la misma puntuación por
sorpresa de `services/weekly.py`, y dice si el radar (`services/radar.py`) ya marcaba a alguno de los dos equipos
cuando se generó la apuesta. Sin previa (partidos de antes del 24-10-2026) no hay con qué comparar.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services import predictions, queries, radar, weekly

LOST = ("loss", "half_loss")
MAX_PLAYERS = 3


def analyze(s: Session, pick: m.Pick) -> dict:
    mt = pick.match
    home, away = mt.home_team.name, mt.away_team.name
    out = {"pick_id": pick.id, "match": f"{home} vs {away}", "score": f"{mt.home_goals}-{mt.away_goals}",
           "result": pick.result, "has_preview": False, "teams": [], "players": [], "flagged": []}
    previas, _ = predictions.usable(s, [mt])
    if mt.id in previas:
        out["has_preview"] = True
        # Un instante alrededor del inicio basta: solo cuenta este partido
        scored = weekly.score_range(s, mt.kickoff_utc - timedelta(minutes=1), mt.kickoff_utc + timedelta(minutes=1))
        for t in scored["teams"]:
            for x in t["matches"]:
                if x["match_id"] == mt.id:
                    side = "home" if t["team_id"] == mt.home_team_id else "away"
                    out["teams"].append({"team": t["name"], "side": side, "score": x["score"], "items": x["items"]})
        out["teams"].sort(key=lambda t: t["side"] != "home")
        players = [{"name": p["name"], "team": p["team"], "score": x["score"], "items": x["items"]}
                   for p in scored["players"] for x in p["matches"] if x["match_id"] == mt.id]
        out["players"] = sorted(players, key=lambda p: -abs(p["score"]))[:MAX_PLAYERS]

    flagged = radar.status(s, pick.created_at)
    played = {pid for pid, mins in s.execute(select(m.PlayerMatchStats.player_id, m.PlayerMatchStats.minutes)
                                             .where(m.PlayerMatchStats.match_id == mt.id)) if mins}
    for team_id in (mt.home_team_id, mt.away_team_id):
        row = flagged.get(team_id)
        if row:
            out["flagged"].append({"team": row["name"], "kind": row["kind"], "reason": row["reason"],
                                   "figures_played": [f["name"] for f in row["figures"] if f["player_id"] in played]})
    return out


def get(pick_id: int) -> dict:
    """«Por qué falló» de una apuesta del día perdida (o medio perdida)."""
    with session_scope() as s:
        pick = s.get(m.Pick, pick_id)
        if pick is None or not pick.is_pick_of_day or pick.result not in LOST:
            raise queries.NotFound(f"La apuesta {pick_id} no es una apuesta del día perdida")
        return analyze(s, pick)
