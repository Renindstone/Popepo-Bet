"""API REST (FastAPI). Documentación interactiva en /docs.

Autenticación: cabecera `X-API-Key` con la clave del usuario. Desde la propia máquina (127.0.0.1)
se permite sin clave usando el usuario por defecto.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from apuestas import __version__
from apuestas.config import get_settings
from apuestas.db.session import session_scope
from apuestas.services import capture_engines, captures, picks, queries, tracker

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        capture_engines.recover()  # capturas que quedaron pendientes o a medias
    except Exception:  # noqa: BLE001 - que la API arranque aunque la BD no esté lista
        log.exception("No se pudo revisar la cola de capturas")
    yield


app = FastAPI(title="Apuestas fútbol", version=__version__, lifespan=lifespan,
              description="Análisis de apuestas: Premier League, Bundesliga, LaLiga y Champions League")

# Panel web (web/, Next.js) en desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


LOCAL_CLIENTS = ("127.0.0.1", "::1", "localhost", "testclient")
# Cabeceras que añaden los proxies y túneles (cloudflared, ngrok, el proxy /api del panel): la petición viene
# de fuera aunque llegue desde 127.0.0.1, así que no se trata como local.
FORWARD_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded", "x-real-ip", "cf-connecting-ip",
                   "x-apuestas-proxy")


def is_local(request: Request) -> bool:
    client = request.client.host if request.client else ""
    return client in LOCAL_CLIENTS and not any(h in request.headers for h in FORWARD_HEADERS)


def current_user(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    if x_api_key:
        with session_scope() as s:
            user = tracker.user_by_key(s, x_api_key)
            if user is None:
                raise HTTPException(401, "Clave inválida")
            return user.username
    if is_local(request):
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


class CaptureLinesIn(BaseModel):
    match: str | None = None
    lines: list[captures.CaptureLine]


class SlipLegIn(BaseModel):
    market: str
    selection: str
    line: float | None = None
    player: str | None = None
    odds: float | None = None


class SlipBlockIn(BaseModel):
    match: str
    odds: float | None = None  # cuota del Bet Builder de este partido, si se conoce
    legs: list[SlipLegIn]


class SlipIn(BaseModel):
    blocks: list[SlipBlockIn]
    total_odds: float | None = None


class ComboBetIn(SlipIn):
    total_odds: float
    stake: float
    bookmaker: str = "betano"
    notes: str | None = None


class BankrollIn(BaseModel):
    bankroll: float
    currency: str = "PEN"


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


@app.get("/picks/record")
def pick_record(user: str = Depends(current_user)) -> dict:
    """Contador de aciertos de la apuesta del día desde el inicio."""
    return picks.pick_record()


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


@app.post("/combos/evaluate")
def evaluate_slip(body: SlipIn, user: str = Depends(current_user)) -> dict:
    """Evalúa un cupón: Bet Builders (varias selecciones de un partido) y combinada entre partidos."""
    return _wrap(queries.evaluate_slip, [b.model_dump() for b in body.blocks], body.total_odds)


@app.post("/combos")
def register_combo(body: ComboBetIn, user: str = Depends(current_user)) -> dict:
    """Registra un cupón como una sola apuesta; se liquida sola cuando terminan sus partidos."""
    return _wrap(queries.register_combo, user, [b.model_dump() for b in body.blocks], body.total_odds, body.stake,
                 body.bookmaker, body.notes)


@app.put("/bankroll")
def set_bankroll(body: BankrollIn, user: str = Depends(current_user)) -> dict:
    """Cambia la banca inicial (y la moneda) del usuario."""
    return _wrap(queries.set_bankroll, user, body.bankroll, body.currency)


@app.get("/performance")
def performance(days: int | None = None, user: str = Depends(current_user)) -> dict:
    return queries.performance(user, days)


# --------------------------------------------------------------------------- capturas de cuotas


@app.post("/captures")
async def upload_capture(file: Annotated[UploadFile, File()], match: Annotated[str | None, Form()] = None,
                         bookmaker: Annotated[str | None, Form()] = None, note: Annotated[str | None, Form()] = None,
                         user: str = Depends(current_user)) -> dict:
    """Sube una captura de cuotas. Si el usuario tiene motor automático, una IA la lee en segundo plano."""
    limit = int(get_settings().captures_max_mb * 1024 * 1024)
    data = await file.read(limit + 1)
    cap = _wrap(captures.create, user, data, match, bookmaker, note)
    if cap["status"] == "pendiente":
        capture_engines.submit(cap["id"], user)
    return cap


@app.get("/captures")
def list_captures(limit: int = 30, user: str = Depends(current_user)) -> list[dict]:
    return captures.list_for(user, min(limit, 100))


@app.get("/captures/{capture_id}")
def get_capture(capture_id: int, user: str = Depends(current_user)) -> dict:
    return _wrap(captures.get, user, capture_id)


@app.get("/captures/{capture_id}/image")
def capture_image(capture_id: int, user: str = Depends(current_user)) -> FileResponse:
    path, mime = _wrap(captures.image_file, user, capture_id)
    if not path.exists():
        raise HTTPException(404, "La imagen ya no está en el disco")
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})


@app.post("/captures/{capture_id}/process")
def reprocess_capture(capture_id: int, user: str = Depends(current_user)) -> dict:
    """Vuelve a mandar la captura a la IA (p.ej. tras un error)."""
    if get_settings().captures_engine_for(user) is None:
        raise HTTPException(409, "Tus capturas las procesa tu propio agente por MCP (capturas_pendientes)")
    _wrap(captures.reset_for_retry, user, capture_id)
    capture_engines.submit(capture_id, user)
    return _wrap(captures.get, user, capture_id)


@app.put("/captures/{capture_id}/lines")
def correct_capture(capture_id: int, body: CaptureLinesIn, user: str = Depends(current_user)) -> dict:
    """Corrige a mano las cuotas leídas (o el partido) y las reevalúa con el modelo, sin volver a la IA."""
    return _wrap(captures.update_lines, user, capture_id, body.lines, body.match)


@app.delete("/captures/{capture_id}")
def delete_capture(capture_id: int, user: str = Depends(current_user)) -> dict:
    return _wrap(captures.delete, user, capture_id)
