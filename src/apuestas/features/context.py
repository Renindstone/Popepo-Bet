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
    prev_match: dict | None = None  # rival, competición, días y si es grande o chico en su competición
    next_match: dict | None = None
    opponent_tier: str | None = None  # el rival de este partido: grande | medio | chico


# Rival chico entre dos partidos grandes (a 4 días o menos, o de Champions): desde 2024 se vieron un 17 % menos de
# tarjetas y un 5 % menos de faltas, pero con la temporada siguiente no se confirmó (experimentos/validacion/carga.py),
# así que solo es un aviso; remates, córners y goles no cambian
SANDWICH_DAYS = 4
TIER_BIG, TIER_SMALL = 0.8, 0.4  # percentil de fuerza en su competición
_comp_teams: dict[tuple, frozenset[int]] = {}


def _teams_in(s: Session, comp_code: str, as_of) -> frozenset[int]:
    key = (comp_code, as_of.date())
    if key not in _comp_teams:
        rows = s.execute(select(m.Match.home_team_id, m.Match.away_team_id).join(m.Competition).where(
            m.Competition.code == comp_code, m.Match.kickoff_utc < as_of,
            m.Match.kickoff_utc >= as_of - timedelta(days=365)))
        _comp_teams[key] = frozenset(t for row in rows for t in row)
    return _comp_teams[key]


def tier(s: Session, strength: dict[int, float], team_id: int, comp_code: str, as_of) -> str | None:
    """grande / medio / chico según la fuerza (ataque + defensa del modelo de goles) frente a los equipos de esa
    competición en el último año; None si no hay con qué comparar."""
    rivals = [strength[t] for t in _teams_in(s, comp_code, as_of) if t in strength]
    if team_id not in strength or len(rivals) < 8:
        return None
    q = sum(v < strength[team_id] for v in rivals) / len(rivals)
    return "grande" if q >= TIER_BIG else "chico" if q < TIER_SMALL else "medio"


def _game(s: Session, mt: m.Match | None, team_id: int, ko, strength: dict[int, float]) -> dict | None:
    if mt is None:
        return None
    opp = mt.away_team if mt.home_team_id == team_id else mt.home_team
    code = mt.competition.code
    return {"opponent": opp.name, "competition": code,
            "days": round(abs((mt.kickoff_utc - ko).total_seconds()) / 86400, 1),
            "tier": "Champions" if code == "UCL" else tier(s, strength, opp.id, code, ko)}


def team_context(s: Session, match: m.Match, team_id: int, opponent_strength_gap: float,
                 strength: dict[int, float] | None = None) -> TeamContext:
    """opponent_strength_gap: (fuerza propia - fuerza rival) en goles esperados; >0 = rival más débil. `strength`
    (ataque + defensa del modelo de goles) marca si el rival y los partidos de antes y después son grandes o chicos."""
    ko = match.kickoff_utc
    strength = strength or {}
    mine = or_(m.Match.home_team_id == team_id, m.Match.away_team_id == team_id)
    played = s.scalars(
        select(m.Match).where(mine, m.Match.kickoff_utc < ko, m.Match.kickoff_utc >= ko - timedelta(days=21),
                              m.Match.status == "finished")
        .order_by(m.Match.kickoff_utc.desc())
    ).all()
    upcoming = s.scalars(
        select(m.Match).where(mine, m.Match.kickoff_utc > ko, m.Match.kickoff_utc <= ko + timedelta(days=7),
                              m.Match.status == "scheduled")
        .order_by(m.Match.kickoff_utc).limit(1)
    ).first()
    rest = (ko - played[0].kickoff_utc).total_seconds() / 86400 if played else None
    last14 = sum(1 for p in played if p.kickoff_utc >= ko - timedelta(days=14))
    nxt_days = (upcoming.kickoff_utc - ko).total_seconds() / 86400 if upcoming else None
    nxt_comp = upcoming.competition.code if upcoming else None
    prev_g = _game(s, played[0] if played else None, team_id, ko, strength)
    next_g = _game(s, upcoming, team_id, ko, strength)
    opp_id = match.away_team_id if match.home_team_id == team_id else match.home_team_id
    opp_tier = tier(s, strength, opp_id, match.competition.code, ko) if strength else None

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
    big = [g for g in (prev_g, next_g) if g and g["days"] <= SANDWICH_DAYS and g["tier"] in ("grande", "Champions")]
    if opp_tier == "chico" and big:
        notes.append(f"Rival chico entre partidos grandes ({', '.join(g['opponent'] for g in big)}): desde 2024 en estos "
                     "partidos se vieron menos tarjetas y faltas, aunque no se confirmó; remates y goles, sin cambio")
    return TeamContext(team_id, rest, last14, nxt_days, nxt_comp, risk, notes, prev_g, next_g, opp_tier)
