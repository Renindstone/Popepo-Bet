"""Clásicos y derbis (`core/rivalries.py`, tabla `rivalry`): cuál es el de un partido y cómo fueron los últimos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m

HISTORY = 6
STATS = ("fouls", "cards", "shots", "offsides")


def index(s: Session) -> dict[frozenset[int], str]:
    """Nombre del clásico de cada par de equipos, para marcar listas de partidos de una vez."""
    return {frozenset((a, b)): name for a, b, name in
            s.execute(select(m.Rivalry.team_a_id, m.Rivalry.team_b_id, m.Rivalry.name))}


def name_for(s: Session, home_id: int, away_id: int) -> str | None:
    a, b = sorted((home_id, away_id))
    return s.scalar(select(m.Rivalry.name).where(m.Rivalry.team_a_id == a, m.Rivalry.team_b_id == b))


def _stat(st: m.TeamMatchStats | None, stat: str) -> int | None:
    if st is None:
        return None
    if stat == "cards":
        return None if st.yellow_cards is None else st.yellow_cards + (st.red_cards or 0)
    return getattr(st, stat)


def history(s: Session, home_id: int, away_id: int, before: datetime) -> dict:
    """Los últimos enfrentamientos terminados (en cualquier competición), con faltas, tarjetas, remates y offsides de
    cada equipo, y la media del total de cada estadística en los que la tienen."""
    rows = s.scalars(select(m.Match).where(
        or_(and_(m.Match.home_team_id == home_id, m.Match.away_team_id == away_id),
            and_(m.Match.home_team_id == away_id, m.Match.away_team_id == home_id)),
        m.Match.status == "finished", m.Match.kickoff_utc < before).order_by(m.Match.kickoff_utc.desc()).limit(HISTORY))
    tz = get_settings().tz
    matches, totals = [], {st: [] for st in STATS}
    for mt in rows:
        stats = {x.team_id: x for x in s.scalars(select(m.TeamMatchStats).where(m.TeamMatchStats.match_id == mt.id))}
        row = {"match_id": mt.id, "date": mt.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d"),
               "competition": mt.competition.code, "home": mt.home_team.name, "away": mt.away_team.name,
               "score": f"{mt.home_goals}-{mt.away_goals}"}
        for st in STATS:
            pair = [_stat(stats.get(mt.home_team_id), st), _stat(stats.get(mt.away_team_id), st)]
            row[st] = pair
            if None not in pair:
                totals[st].append(sum(pair))
        matches.append(row)
    return {"matches": matches,
            "averages": {st: round(sum(v) / len(v), 1) if v else None for st, v in totals.items()}}
