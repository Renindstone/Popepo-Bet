"""Sincronización manual desde Datos: en segundo plano, una a la vez, con pausa entre una y otra y sin OddsPapi."""

import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import sync


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(sync, "_state", {"running": False, "started_at": None, "finished_at": None, "step": None,
                                         "done_steps": 0, "total_steps": 0, "error": None})
    monkeypatch.setattr(sync, "worker_busy", lambda: False)


def wait_done(timeout=5.0):
    deadline = time.monotonic() + timeout
    while sync.status()["running"]:
        assert time.monotonic() < deadline, "la sincronización no terminó"
        time.sleep(0.01)
    return sync.status()


def test_runs_every_step_in_the_background(monkeypatch):
    ran = []
    monkeypatch.setattr(sync, "steps", lambda: [(f"paso {i}", lambda i=i: ran.append(i)) for i in range(3)])
    st = sync.start()
    assert st["total_steps"] == 3  # puede haber terminado ya: los pasos de prueba son instantáneos
    done = wait_done()
    assert ran == [0, 1, 2] and done["error"] is None and done["done_steps"] == 3 and done["finished_at"]
    assert done["next_allowed_at"]  # pausa antes de la siguiente


def test_refuses_while_running_and_during_the_pause(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(sync, "steps", lambda: [("descarga lenta", release.wait)])
    sync.start()
    with pytest.raises(sync.SyncRefused, match="en marcha"):
        sync.start()
    release.set()
    wait_done()
    with pytest.raises(sync.SyncRefused, match="hace poco"):
        sync.start()
    # Pasada la pausa, se puede otra vez
    sync._state["finished_at"] = datetime.now(UTC) - sync.COOLDOWN - timedelta(seconds=1)
    assert sync.status()["next_allowed_at"] is None
    sync.start()
    wait_done()


def test_refuses_when_the_worker_is_downloading(monkeypatch):
    monkeypatch.setattr(sync, "worker_busy", lambda: True)
    with pytest.raises(sync.SyncRefused, match="worker"):
        sync.start()


def test_a_failing_step_is_reported_and_stops(monkeypatch):
    ran = []

    def boom():
        raise RuntimeError("se cayó la base de datos\nTraceback ...")

    monkeypatch.setattr(sync, "steps", lambda: [("uno", lambda: ran.append(1)), ("dos", boom),
                                                ("tres", lambda: ran.append(3))])
    sync.start()
    done = wait_done()
    assert ran == [1] and done["error"] == "Falló en «dos»: se cayó la base de datos"


def test_no_oddspapi_in_the_steps():
    labels = " ".join(label for label, _fn in sync.steps()).lower()
    assert "oddspapi" not in labels and "betano" not in labels and "pinnacle" not in labels


def test_worker_busy_ignores_runs_left_running_by_a_restart(monkeypatch):
    monkeypatch.undo()  # el worker_busy de verdad
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as s:

        @contextmanager
        def scope():
            yield s

        monkeypatch.setattr(sync, "session_scope", scope)
        now = datetime.now(UTC)
        s.add(m.IngestionRun(source="fdco", task="EPL 2026", status="running", started_at=now - timedelta(hours=5)))
        s.flush()
        assert sync.worker_busy() is False
        s.add(m.IngestionRun(source="fotmob", task="league EPL", status="running", started_at=now))
        s.flush()
        assert sync.worker_busy() is True
