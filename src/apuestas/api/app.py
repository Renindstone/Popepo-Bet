"""API REST (FastAPI). Documentación interactiva en /docs.

Autenticación: cabecera `X-API-Key` con la clave del usuario. Desde la propia máquina (127.0.0.1)
se permite sin clave usando el usuario por defecto.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from apuestas import __version__
from apuestas.config import get_settings
from apuestas.db.session import session_scope
from apuestas.services import picks, queries, tracker

app = FastAPI(title="Apuestas fútbol", version=__version__,
              description="Análisis de apuestas: Premier League, Bundesliga, LaLiga y Champions League")


def current_user(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    if x_api_key:
        with session_scope() as s:
            user = tracker.user_by_key(s, x_api_key)
            if user is None:
                raise HTTPException(401, "Clave inválida")
            return user.username
    client = request.client.host if request.client else ""
    if client in ("127.0.0.1", "::1", "localhost", "testclient"):
        return get_settings().default_user
    raise HTTPException(401, "Falta la cabecera X-API-Key")


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except queries.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, "Modelos no entrenados todavía (apuestas train)") from exc


class OddsIn(BaseModel):
    match: str
    market: str
    selection: str
    odds: float
    line: float | None = None
    bookmaker: str = "betano"
    player: str | None = None


class BetIn(OddsIn):
    stake: float
    notes: str | None = None


class AbsenceIn(BaseModel):
    team: str
    player: str
    kind: str = "injury"
    reason: str | None = None
    expected_return: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/status")
def status(user: str = Depends(current_user)) -> dict:
    return queries.data_status()


@app.get("/matches")
def matches(days: int = 3, competition: str | None = None, user: str = Depends(current_user)) -> list[dict]:
    return queries.upcoming(days, competition)


@app.get("/matches/{ref}/analysis")
def match_analysis(ref: str, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.match_analysis, ref)


@app.get("/picks")
def pick_of_day(day: str | None = None, refresh: bool = False, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.pick_of_day, day, refresh)


@app.get("/picks/history")
def pick_history(days: int = 60, user: str = Depends(current_user)) -> dict:
    return picks.pick_history(days)


@app.post("/odds/evaluate")
def evaluate(o: OddsIn, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.evaluate_odds, o.match, o.market, o.selection, o.odds, o.line, o.bookmaker, o.player)


@app.get("/teams/{team}/absences")
def absences(team: str, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.absences, team)


@app.post("/absences")
def add_absence(a: AbsenceIn, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.add_absence, a.team, a.player, a.kind, a.reason, a.expected_return)


@app.get("/referees/{name}")
def referee(name: str, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.referee_profile, name)


@app.get("/players/{name}")
def player(name: str, match: str | None = None, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.player_projection, name, match)


@app.post("/bets")
def register_bet(b: BetIn, user: str = Depends(current_user)) -> dict:
    return _wrap(queries.register_bet, user, b.match, b.market, b.selection, b.odds, b.stake, b.line,
                 b.bookmaker, b.player, b.notes)


@app.get("/bets")
def bets(pending_only: bool = False, user: str = Depends(current_user)) -> list[dict]:
    return queries.my_bets(user, pending_only)


@app.get("/performance")
def performance(days: int | None = None, user: str = Depends(current_user)) -> dict:
    return queries.performance(user, days)
