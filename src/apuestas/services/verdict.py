"""Veredicto de los revisores: una segunda opinión debajo de la apuesta del día.

Tres papeles de Claude trabajan por separado (A favor, En contra y Juez) y dejan «Apostar», «Dudosa» o «Mejor no». Es una
opinión: no cambia la probabilidad, la confianza, el corte ni qué apuesta sale, y la decisión sigue siendo del dueño.
La confianza y la racha las escribe el código para que no dependan de la IA.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.services import picks
from apuestas.services.analysis import bet_label

FORM_MATCHES = 5
HOT_RUN = 3  # victorias seguidas
HOT_WINS = 4  # victorias en los últimos FORM_MATCHES


def team_form(s: Session, team_id: int, before: datetime) -> dict:
    """Últimos partidos terminados de un equipo antes de `before`, en todas las competiciones, y si viene en racha."""
    rows = s.scalars(select(m.Match).where(
        or_(m.Match.home_team_id == team_id, m.Match.away_team_id == team_id),
        m.Match.status == "finished", m.Match.kickoff_utc < before,
        m.Match.home_goals.is_not(None), m.Match.away_goals.is_not(None),
    ).order_by(m.Match.kickoff_utc.desc()).limit(FORM_MATCHES)).all()
    results = []
    for mt in rows:
        is_home = mt.home_team_id == team_id
        own, other = (mt.home_goals, mt.away_goals) if is_home else (mt.away_goals, mt.home_goals)
        results.append({"date": mt.kickoff_utc.date().isoformat(), "competition": mt.competition.code,
                        "opponent": (mt.away_team if is_home else mt.home_team).name,
                        "score": f"{mt.home_goals}-{mt.away_goals}", "won": own > other})
    wins = sum(r["won"] for r in results)
    run = next((i for i, r in enumerate(results) if not r["won"]), len(results))
    return {"played": len(results), "wins": wins, "run": run, "hot": run >= HOT_RUN or wins >= HOT_WINS,
            "results": results}


def against(market: str, selection: str, home_id: int, away_id: int) -> set[int]:
    """Equipos contra los que va la apuesta: gana cuando ese equipo no gana o no gana por mucho."""
    if market == "1x2" and selection == "draw":
        return {home_id, away_id}
    if market in ("1x2", "dnb", "ah", "eh"):
        return {"home": {away_id}, "away": {home_id}}.get(selection, set())
    if market == "dc":
        return {"1x": {away_id}, "x2": {home_id}}.get(selection, set())
    if selection == "under":
        return {"ou_goals_home": {home_id}, "ou_goals_away": {away_id}}.get(market, set())
    return set()


def streak_warnings(s: Session, pick: m.Pick) -> list[dict]:
    """Un aviso por cada equipo en racha contra el que va la apuesta."""
    mt = pick.match
    out = []
    for team in (mt.home_team, mt.away_team):
        if team.id not in against(pick.market, pick.selection, mt.home_team_id, mt.away_team_id):
            continue
        form = team_form(s, team.id, mt.kickoff_utc)
        if form["hot"]:
            out.append({"team": team.name, "wins": form["wins"], "played": form["played"], "run": form["run"]})
    return out


def confidence_record(s: Session) -> dict:
    """Aciertos de lo que pasó el corte con la confianza de tu regla o más, y con menos (el grupo de Mis apuestas)."""
    threshold = get_settings().verdict_min_confidence
    rows = list(s.scalars(select(m.Pick).where(m.Pick.announced_at.is_not(None))))
    def group(chosen: list[m.Pick]) -> dict:
        record = picks.record_from(chosen)
        return {"hits": record["hits"], "misses": record["misses"]}
    return {"threshold": threshold, "high": group([p for p in rows if p.confidence >= threshold]),
            "low": group([p for p in rows if p.confidence < threshold])}


def snapshot(s: Session, pick: m.Pick) -> dict:
    """Los números que ve una revisión: se guardan con ella para enseñarla como se vio."""
    mt = pick.match
    return {"odds": pick.odds, "prob": pick.model_prob, "implied": round(1 / pick.odds, 3), "ev": pick.ev,
            "confidence": pick.confidence, "stage": pick.stage,
            "label": bet_label(pick.market, pick.selection, pick.line, mt.home_team.name, mt.away_team.name),
            "streaks": streak_warnings(s, pick)}
