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
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from apuestas import __version__
from apuestas.config import get_settings
from apuestas.db.session import session_scope
from apuestas.services import capture_engines, captures, failure, picks, queries, radar, sync, tracker

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        capture_engines.recover()  # capturas que quedaron pendientes o a medias
    except Exception:  # noqa: BLE001 - que la API arranque aunque la BD no esté lista
        log.exception("No se pudo revisar la cola de capturas")
    yield


app = FastAPI(title="Apuestas fútbol", version=__version__, lifespan=lifespan,
              description="Análisis de apuestas: Premier League, Bundesliga, LaLiga, Serie A, Ligue 1 y Champions League")

# Panel web (web/, Next.js) en desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


LOCAL_CLIENTS = ("127.0.0.1", "::1", "localhost", "testclient")
# Cabeceras que añaden los proxies y túneles (nginx, cloudflared, ngrok…): la petición viene de fuera aunque
# llegue desde 127.0.0.1, así que no se trata como local y necesita clave.
FORWARD_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded", "x-real-ip", "cf-connecting-ip")


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


class CaptureBetIn(BaseModel):
    stake: float
    line: int | None = None  # índice de la cuota en la captura; sin él, la combinada entera
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


@app.get("/sync")
def sync_status(user: str = Depends(current_user)) -> dict:
    """Estado de la sincronización manual (botón de Datos)."""
    return sync.status()


@app.post("/sync")
def sync_start(user: str = Depends(current_user)) -> dict:
    """Descarga ahora lo de las 05:30 y las 08:30 de las fuentes gratuitas (sin OddsPapi) y reentrena, en segundo plano."""
    try:
        return sync.start()
    except sync.SyncRefused as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/matches")
def matches(days: int = 3, competition: str | None = None, user: str = Depends(current_user)) -> list[dict]:
    return queries.upcoming(days, competition)


@app.get("/matches/{ref}/odds")
def match_book_odds(ref: str, bookmaker: str = "betano", user: str = Depends(current_user)) -> dict:
    """Cuotas guardadas de una casa (Betano por defecto) para el partido, evaluadas con el modelo."""
    return _wrap(queries.match_book_odds, ref, bookmaker)


@app.get("/teams/{team_id}/logo")
def team_logo(team_id: int) -> Response:
    """Escudo del equipo. Público (sin clave): es una imagen pública y un <img> no puede mandar X-API-Key."""
    try:
        data = queries.team_logo(team_id)
    except (queries.NotFound, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(404, "Sin escudo") from exc
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/matches/{ref}/lineups")
def match_lineups(ref: str, user: str = Depends(current_user)) -> dict:
    """Alineaciones probables o confirmadas, con formación y posición en el campo, suplentes y bajas."""
    return _wrap(queries.match_lineups, ref)


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


@app.get("/week")
def week(day: str | None = None, period: str = "semana", user: str = Depends(current_user)) -> dict:
    """Equipo, jugador y once de la semana o del mes (4 semanas): quién sorprendió a la casa (equipos) y a nuestro
    modelo (jugadores)."""
    return _wrap(queries.week_recap, day, True, period)


@app.get("/picks/{pick_id}/failure")
def pick_failure(pick_id: int, user: str = Depends(current_user)) -> dict:
    """«Por qué falló» una apuesta del día perdida: la previa del modelo frente a lo que pasó."""
    return _wrap(failure.get, pick_id)


@app.get("/radar")
def radar_now(user: str = Depends(current_user)) -> dict:
    """Equipos en racha y en baja y jugadores en racha de las últimas 4 semanas, con su próximo partido."""
    return _wrap(radar.get)


@app.get("/picks/qualified")
def qualified_picks(days: int = 60, user: str = Depends(current_user)) -> dict:
    """Las que pasaron el corte (no solo la apuesta del día): aciertos desde el inicio y las de los últimos días."""
    return picks.qualified_picks(days)


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


class MeIn(BaseModel):
    ai_enabled: bool


@app.get("/me")
def get_me(user: str = Depends(current_user)) -> dict:
    """El usuario de esta clave y sus ajustes: si usa la IA y si puede pedir explicaciones a Claude."""
    return queries.me(user)


@app.put("/me")
def put_me(body: MeIn, user: str = Depends(current_user)) -> dict:
    """Enciende o apaga la IA para este usuario (capturas y explicaciones de Claude)."""
    return queries.set_me(user, body.ai_enabled)


@app.get("/performance")
def performance(days: int | None = None, user: str = Depends(current_user)) -> dict:
    return queries.performance(user, days)


# --------------------------------------------------------------------------- capturas de cuotas


@app.post("/captures")
async def upload_capture(file: Annotated[UploadFile, File()], match: Annotated[str | None, Form()] = None,
                         bookmaker: Annotated[str | None, Form()] = None, note: Annotated[str | None, Form()] = None,
                         user: str = Depends(current_user)) -> dict:
    """Sube una captura de cuotas. Si el usuario tiene motor automático, una IA la lee en segundo plano."""
    try:
        queries.require_ai(user)
    except queries.AiDisabled as exc:
        raise HTTPException(409, str(exc)) from exc
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
def reprocess_capture(capture_id: int, fallback: bool = False, user: str = Depends(current_user)) -> dict:
    """Vuelve a mandar la captura a la IA (p.ej. tras un error). `fallback` la lee con el motor alternativo
    (Claude) en lugar del habitual (la IA local)."""
    st = get_settings()
    if st.captures_engine_for(user) is None:
        raise HTTPException(409, "Tus capturas las procesa tu propio agente por MCP (capturas_pendientes)")
    engine = None
    if fallback:
        engine = st.captures_fallback_for(user)
        if engine is None:
            raise HTTPException(409, "No hay un motor alternativo configurado")
    _wrap(captures.reset_for_retry, user, capture_id)
    capture_engines.submit(capture_id, user, engine)
    return _wrap(captures.get, user, capture_id)


@app.post("/captures/{capture_id}/bet")
def register_capture_bet(capture_id: int, body: CaptureBetIn, user: str = Depends(current_user)) -> dict:
    """Registra como apuesta una cuota de la captura o su combinada, sin pasar por Evaluar cuota."""
    return _wrap(captures.register_bet, user, capture_id, body.stake, body.line, body.notes)


@app.put("/captures/{capture_id}/lines")
def correct_capture(capture_id: int, body: CaptureLinesIn, user: str = Depends(current_user)) -> dict:
    """Corrige a mano las cuotas leídas (o el partido) y las reevalúa con el modelo, sin volver a la IA."""
    return _wrap(captures.update_lines, user, capture_id, body.lines, body.match)


@app.delete("/captures/{capture_id}")
def delete_capture(capture_id: int, user: str = Depends(current_user)) -> dict:
    return _wrap(captures.delete, user, capture_id)
