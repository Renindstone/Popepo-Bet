"""Contexto del partido: descanso, calendario cargado, riesgo de rotación y dificultad."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apuestas.db import models as m

DIFFICULTY_LEVELS = [
    (1.0, "Fácil"),
    (0.4, "Medianamente fácil"),
    (-0.4, "Parejo"),
    (-1.0, "Medianamente difícil"),
]


def difficulty_label(goal_diff: float) -> str:
    """Diferencia de goles esperada (a favor - en contra) -> etiqueta de dificultad."""
    for threshold, label in DIFFICULTY_LEVELS:
        if goal_diff >= threshold:
            return label
    return "Difícil"


@dataclass
class TeamContext:
    team_id: int
    rest_days: float | None
    matches_last_14d: int
    next_match_days: float | None
    next_match_competition: str | None
    rotation_risk: str  # baja | media | alta
    notes: list[str] = field(default_factory=list)


def team_context(s: Session, match: m.Match, team_id: int, opponent_strength_gap: float) -> TeamContext:
    """opponent_strength_gap: (fuerza propia - fuerza rival) en goles esperados; >0 = rival más débil."""
    ko = match.kickoff_utc
    played = s.execute(
        select(m.Match.kickoff_utc)
        .where(
            or_(m.Match.home_team_id == team_id, m.Match.away_team_id == team_id),
            m.Match.kickoff_utc < ko,
            m.Match.kickoff_utc >= ko - timedelta(days=21),
            m.Match.status == "finished",
        )
        .order_by(m.Match.kickoff_utc.desc())
    ).all()
    upcoming = s.execute(
        select(m.Match.kickoff_utc, m.Competition.code)
        .join(m.Competition, m.Competition.id == m.Match.competition_id)
        .where(
            or_(m.Match.home_team_id == team_id, m.Match.away_team_id == team_id),
            m.Match.kickoff_utc > ko,
            m.Match.kickoff_utc <= ko + timedelta(days=7),
            m.Match.status == "scheduled",
        )
        .order_by(m.Match.kickoff_utc)
        .limit(1)
    ).first()
    rest = (ko - played[0][0]).total_seconds() / 86400 if played else None
    last14 = sum(1 for (k,) in played if k >= ko - timedelta(days=14))
    nxt_days = (upcoming[0] - ko).total_seconds() / 86400 if upcoming else None
    nxt_comp = upcoming[1] if upcoming else None

    notes, risk = [], "baja"
    if rest is not None and rest < 3.5:
        notes.append(f"Poco descanso ({rest:.1f} días)")
        risk = "media"
    if last14 >= 4:
        notes.append(f"Calendario cargado ({last14} partidos en 14 días)")
        risk = "media"
    if nxt_days is not None and nxt_days <= 4 and nxt_comp == "UCL" and match.competition.code != "UCL":
        notes.append(f"Juega Champions en {nxt_days:.0f} días")
        risk = "alta" if opponent_strength_gap > 0.6 else "media"
    return TeamContext(team_id, rest, last14, nxt_days, nxt_comp, risk, notes)
