"""Previa guardada: lo que el modelo esperaba de cada partido justo antes del inicio.

Una fila por partido en `prediction`, que se reescribe en cada recálculo hasta el inicio (la última gana, con la
alineación confirmada si ya llegó) y nunca después. Sirve para comparar luego lo que pasó con lo que se esperaba
(resumen de la semana, `services/weekly.py`) sin rehacer el análisis con datos que antes del partido no se sabían.

El contenido va por lado (`home`/`away`), no por id de equipo, para que la fusión de equipos duplicados no lo deje
desfasado. Se guardan todos los jugadores proyectados, no los 16 que muestra el análisis.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.models.fitting import ModelBundle
from apuestas.services.analysis import MatchAnalysis
from apuestas.services.match_model import PLAYER_COUNT_DISPERSION

log = logging.getLogger(__name__)

PAYLOAD_VERSION = 1
# Una previa de un partido que luego se aplazó y se jugó días después ya no vale
STALE_DAYS = 3


def _aware(dt: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona horaria; en la BD siempre son UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _r(x: float) -> float:
    return round(float(x), 4)


def payload_from(an: MatchAnalysis, bundle: ModelBundle) -> dict:
    mm = an.model
    return {
        "v": PAYLOAD_VERSION,
        "kickoff_utc": _aware(an.match.kickoff_utc).isoformat(),
        "stage": an.stage,
        "model_as_of": bundle.as_of.isoformat(),
        "goals": {"home": _r(mm.lam_home), "away": _r(mm.lam_away), "rho": _r(mm.rho)},
        "1x2": {k: _r(v) for k, v in mm.probs_1x2().items()},
        "counts": {stat: {"home": _r(h), "away": _r(a), "dispersion": _r(mm.count_dispersion.get(stat, 0.0))}
                   for stat, (h, a) in sorted(mm.count_means.items())},
        "player_dispersion": {"shots": PLAYER_COUNT_DISPERSION, "shots_on_target": PLAYER_COUNT_DISPERSION},
        "players": [{"player_id": pp.player_id, "side": "home" if pp.team_id == mm.home_id else "away",
                     "position": pp.position, "expected_minutes": round(float(pp.expected_minutes), 1),
                     "start_prob": round(float(pp.start_prob), 3),
                     "lam": {k: _r(v) for k, v in sorted(pp.lam.items())}}
                    for pp in sorted(mm.players.values(), key=lambda p: p.player_id)],
    }


def _upsert(s: Session, match_id: int, stage: str, version: str, payload: dict, now: datetime) -> m.Prediction:
    with s.begin_nested():
        row = s.scalar(select(m.Prediction).where(m.Prediction.match_id == match_id))
        if row is None:
            row = m.Prediction(match_id=match_id, stage=stage, model_version=version, payload=payload, updated_at=now)
            s.add(row)
        elif row.payload != payload or row.stage != stage:
            # Hoy recalcula en cada visita: si nada cambió, no se reescribe
            row.payload, row.stage, row.model_version, row.updated_at = payload, stage, version, now
    return row


def store(s: Session, an: MatchAnalysis, bundle: ModelBundle, now: datetime | None = None) -> m.Prediction | None:
    """Guarda la previa del partido si aún no empezó. Nunca rompe a quien la llama (las apuestas del día)."""
    now = now or datetime.now(UTC)
    if _aware(an.match.kickoff_utc) <= now:
        return None
    try:
        payload = payload_from(an, bundle)
        version = f"{bundle.version}@{bundle.as_of.isoformat()}"[:24]
        try:
            return _upsert(s, an.match.id, an.stage, version, payload, now)
        except IntegrityError:
            # El worker y la API la escribieron a la vez: la otra ya está, se actualiza
            return _upsert(s, an.match.id, an.stage, version, payload, now)
    except Exception:  # noqa: BLE001 - la previa es un extra: las apuestas del día siguen igual
        log.exception("No se pudo guardar la previa del partido %s", an.match.id)
        return None


def usable(s: Session, matches: list[m.Match]) -> tuple[dict[int, dict], set[int]]:
    """Previas válidas por partido (escritas antes del inicio, de este formato y del mismo día) y las caducadas."""
    by_id = {mt.id: mt for mt in matches}
    ok: dict[int, dict] = {}
    stale: set[int] = set()
    if not by_id:
        return ok, stale
    for row in s.scalars(select(m.Prediction).where(m.Prediction.match_id.in_(by_id))):
        mt = by_id[row.match_id]
        p = row.payload or {}
        kickoff = _aware(mt.kickoff_utc)
        try:
            planned = _aware(datetime.fromisoformat(p["kickoff_utc"]))
        except (KeyError, TypeError, ValueError):
            stale.add(mt.id)
            continue
        if (p.get("v") != PAYLOAD_VERSION or row.updated_at is None or _aware(row.updated_at) >= kickoff
                or abs(planned - kickoff) > timedelta(days=STALE_DAYS)):
            stale.add(mt.id)
            continue
        ok[mt.id] = {**p, "stage": row.stage}
    return ok, stale
