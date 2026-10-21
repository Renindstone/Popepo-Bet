"""Recuperación de tareas diarias que no corrieron porque el equipo estaba apagado."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apuestas.jobs import scheduler

LIMA = ZoneInfo("America/Lima")


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "_state_path", lambda: tmp_path / "worker_state.json")


def test_last_fire():
    now = datetime(2026, 10, 20, 8, 28, tzinfo=LIMA)  # martes
    assert scheduler.last_fire(5, 30, None, now) == datetime(2026, 10, 20, 5, 30, tzinfo=LIMA)
    assert scheduler.last_fire(9, 0, None, now) == datetime(2026, 10, 19, 9, 0, tzinfo=LIMA)
    assert scheduler.last_fire(4, 0, 0, now) == datetime(2026, 10, 19, 4, 0, tzinfo=LIMA)  # lunes


def test_missed_jobs_after_a_night_switched_off(state):
    # Último arranque el 19 a las 23:00; el equipo se apagó a las 00:26 y volvió a las 07:44
    scheduler._state_path().parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime(2026, 10, 19, 23, 0, tzinfo=LIMA).isoformat()
    scheduler._state_path().write_text("{" + ",".join(f'"{k}": "{stamp}"' for k in scheduler.DAILY_JOBS) + "}")

    now = datetime(2026, 10, 20, 7, 44, tzinfo=LIMA)
    # resultados (05:30) e historial (02:00) no corrieron; la previa y la apuesta del día de ayer sí
    assert scheduler.missed_jobs(now) == ["results", "backfill"]
    later = datetime(2026, 10, 20, 9, 30, tzinfo=LIMA)
    assert scheduler.missed_jobs(later) == ["results", "preview", "daily_pick", "backfill"]


def test_old_pick_is_not_recovered(state):
    # Si el equipo arranca de noche, la apuesta del día de la mañana ya no sirve
    now = datetime(2026, 10, 20, 23, 0, tzinfo=LIMA)
    assert "daily_pick" not in scheduler.missed_jobs(now)
    assert "results" in scheduler.missed_jobs(now)


def test_safe_records_only_successes(state):
    @scheduler._safe("prueba", key="prueba")
    def ok():
        return 1

    @scheduler._safe("falla", key="falla")
    def boom():
        raise RuntimeError("x")

    assert ok() == 1 and scheduler.last_done("prueba") is not None
    assert boom() is None and scheduler.last_done("falla") is None


def test_lineup_checks_fire_once_at_each_point():
    # la tarea corre cada 5 minutos; con un partido a las 14:00 se mira a las 12:50, 13:10, 13:25, 13:40 y 13:50
    fired = [m for m in range(0, 121, 5) if scheduler.lineup_due(m)]
    assert fired == [10, 20, 35, 50, 70]
    # con un inicio que no cae en múltiplo de 5 (14:02) también se mira una vez cerca de cada punto
    fired = [m + 2 for m in range(0, 121, 5) if scheduler.lineup_due(m + 2)]
    assert len(fired) == 5 and 50 <= fired[3] <= 52
