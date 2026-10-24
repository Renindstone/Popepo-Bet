"""Sincronización manual desde el panel (botón «Sincronizar» de Datos).

Hace lo mismo que las tareas de las 05:30 y las 08:30 con las fuentes gratuitas (FotMob, football-data y
Understat), liquida y reentrena el modelo. **No usa OddsPapi**: cada petición gasta cupo (250 al mes) y sus cuotas ya
se bajan a las 08:30. Corre en segundo plano dentro de la API, una vez a la vez, con una pausa de `COOLDOWN` entre una
y otra para no cargar a las fuentes, y no arranca si el worker está descargando.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from apuestas.db import models as m
from apuestas.db.session import session_scope

log = logging.getLogger(__name__)

COOLDOWN = timedelta(minutes=10)
# Una tarea del worker que lleva más de esto «en curso» es de un reinicio a medias, no una descarga de verdad
STALE_RUN = timedelta(hours=2)


class SyncRefused(RuntimeError):
    """No se puede sincronizar ahora (ya hay una en marcha, la pausa o el worker descargando)."""


def steps() -> list[tuple[str, Callable[[], object]]]:
    from apuestas.core.competitions import season_start_year
    from apuestas.ingest import pipeline
    from apuestas.models.fitting import fit_all, save_bundle, store_team_ratings
    from apuestas.services.picks import settle_all

    cur = season_start_year(datetime.now(UTC).date())

    def retrain() -> None:
        bundle = fit_all()
        save_bundle(bundle)
        store_team_ratings(bundle)

    return [
        ("Calendario y resultados de FotMob", lambda: pipeline.sync_fotmob_leagues([cur])),
        ("Resultados y cuotas de cierre de football-data", lambda: pipeline.sync_football_data([cur])),
        ("xG de Understat", lambda: pipeline.sync_understat([cur])),
        ("Equipos duplicados", pipeline.merge_duplicate_teams),
        ("Detalles de los partidos jugados", lambda: pipeline.sync_fotmob_details(days_ahead=1, backfill_limit=150)),
        ("Liquidación de apuestas", settle_all),
        ("Alineaciones, bajas y árbitros de los próximos partidos",
         lambda: pipeline.sync_fotmob_details(days_ahead=4, backfill_limit=0, force_upcoming=True)),
        ("Cuotas de bet365 de football-data", pipeline.sync_upcoming_odds),
        ("Reentrenando el modelo", retrain),
    ]


_lock = threading.Lock()
_state: dict = {"running": False, "started_at": None, "finished_at": None, "step": None, "done_steps": 0,
                "total_steps": 0, "error": None}


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def status() -> dict:
    with _lock:
        st = dict(_state)
    nxt = st["finished_at"] + COOLDOWN if st["finished_at"] and not st["running"] else None
    if nxt and nxt <= datetime.now(UTC):
        nxt = None
    return {**st, "started_at": _iso(st["started_at"]), "finished_at": _iso(st["finished_at"]),
            "next_allowed_at": _iso(nxt)}


def worker_busy() -> bool:
    """El worker (u otra descarga) tiene una tarea de ingesta en curso de verdad."""
    with session_scope() as s:
        return bool(s.scalar(select(func.count()).select_from(m.IngestionRun).where(
            m.IngestionRun.status == "running", m.IngestionRun.started_at >= datetime.now(UTC) - STALE_RUN)))


def start() -> dict:
    now = datetime.now(UTC)
    with _lock:
        if _state["running"]:
            raise SyncRefused("Ya hay una sincronización en marcha.")
        if _state["finished_at"] and now - _state["finished_at"] < COOLDOWN:
            wait = _state["finished_at"] + COOLDOWN - now
            raise SyncRefused(f"Se sincronizó hace poco: vuelve a intentarlo en {max(1, round(wait.seconds / 60))} min.")
    if worker_busy():
        raise SyncRefused("El worker está descargando datos ahora mismo; espera a que termine.")
    plan = steps()
    with _lock:
        if _state["running"]:
            raise SyncRefused("Ya hay una sincronización en marcha.")
        _state.update(running=True, started_at=now, finished_at=None, step=plan[0][0], done_steps=0,
                      total_steps=len(plan), error=None)
    threading.Thread(target=_run, args=(plan,), name="sincronizacion-manual", daemon=True).start()
    return status()


def _run(plan: list[tuple[str, Callable[[], object]]]) -> None:
    log.info("Sincronización manual: inicio")
    try:
        for i, (label, fn) in enumerate(plan):
            with _lock:
                _state.update(step=label, done_steps=i)
            fn()
    except Exception as exc:  # noqa: BLE001 - se muestra en el panel en vez de tumbar la API
        log.exception("Sincronización manual: falló en «%s»", _state["step"])
        with _lock:
            _state["error"] = f"Falló en «{_state['step']}»: {str(exc).splitlines()[0][:160]}"
    finally:
        with _lock:
            _state.update(running=False, finished_at=datetime.now(UTC), step=None,
                          done_steps=_state["total_steps"] if _state["error"] is None else _state["done_steps"])
        log.info("Sincronización manual: fin")
