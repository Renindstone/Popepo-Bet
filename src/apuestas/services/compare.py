"""Comparar precios: las cuotas de Betano que pagan más que la cuota justa (sin margen) de Pinnacle.

No usa el modelo. Pinnacle es la casa más afilada que se descarga (OddsPapi, a las 08:30 y antes de los partidos con
apuestas abiertas): si Betano paga por encima de su precio justo, la ventaja sale de la diferencia entre casas, que
es lo único que dio rendimiento positivo en la auditoría del modelo. Medido con las cuotas guardadas desde el
19-10-2026 (`experimentos/validacion/betano_pinnacle.py`, docs/modelos.md sección 6): en córners y tarjetas pasa a
menudo y Pinnacle no se mueve después hacia Betano; en goles casi nunca.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services import analysis, picks

MIN_EDGE = 0.02
REFERENCE = "pinnacle"
GOAL_MARKETS = ("1x2", "dc", "dnb", "btts", "ah", "eh", "ou_goals", "ou_goals_home", "ou_goals_away")
NOTE = ("Desde el 19-10-2026, en córners y tarjetas Betano pagó por encima de Pinnacle a menudo y Pinnacle no se movió "
        "después hacia Betano; en goles casi nunca. Todavía son pocas semanas: es una ventaja de precio, no una apuesta "
        "segura.")


def _seen(r: m.OddsSnapshot):
    """Cuándo se vio ese precio por última vez (antes del 29-10-2026, cuándo se guardó)."""
    return r.last_seen_at or r.captured_at


def match_edges(s: Session, match: m.Match, min_edge: float = MIN_EDGE) -> list[dict]:
    """Las selecciones de Betano con valor ≥ `min_edge` frente a Pinnacle sin margen, de mayor a menor."""
    rows = analysis._latest_odds(s, match.id)  # solo lo que cada casa sigue ofreciendo
    ref = [r for r in rows if r.bookmaker == REFERENCE]
    if not ref:
        return []
    home, away = match.home_team.name, match.away_team.name
    out = []
    for b in (r for r in rows if r.bookmaker.startswith("betano")):
        p = analysis.book_fair_prob(ref, REFERENCE, b.market, b.selection, b.line)
        if not p:
            continue
        edge = b.price * p - 1  # con devolución posible (líneas enteras) es el valor de la parte que se decide
        if edge >= min_edge:
            seen = max(_seen(r) for r in ref if r.market == b.market)
            out.append({"match_id": match.id, "market": b.market, "selection": b.selection, "line": b.line,
                        "label": analysis.bet_label(b.market, b.selection, b.line, home, away),
                        "group": "goles" if b.market in GOAL_MARKETS else "estadísticas",
                        "odds": b.price, "fair_odds": round(1 / p, 3), "edge": round(edge, 4),
                        "odds_at": _seen(b), "fair_at": seen})
    return sorted(out, key=lambda x: -x["edge"])


def day_edges(day: date | None = None, min_edge: float = MIN_EDGE) -> dict:
    """Las de todos los partidos del día que aún no empezaron."""
    d = day or picks.today_local()
    tz = get_settings().tz
    with session_scope() as s:
        rows = []
        for mt in picks.matches_for_day(s, d):
            if mt.status != "scheduled":
                continue
            for e in match_edges(s, mt, min_edge):
                rows.append({**e, "match": f"{mt.home_team.name} vs {mt.away_team.name}",
                             "home_id": mt.home_team_id, "away_id": mt.away_team_id,
                             "competition": mt.competition.code,
                             "kickoff_local": mt.kickoff_utc.astimezone(tz).strftime("%H:%M"),
                             "odds_at": e["odds_at"].astimezone(tz).strftime("%d/%m %H:%M"),
                             "fair_at": e["fair_at"].astimezone(tz).strftime("%d/%m %H:%M")})
        rows.sort(key=lambda x: -x["edge"])
        return {"date": d.isoformat(), "min_edge": min_edge, "note": NOTE, "rows": rows}
