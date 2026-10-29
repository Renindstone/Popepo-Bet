"""Interruptor de la IA por usuario: cada persona que entra con su clave decide si la usa."""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.services import capture_engines, queries


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session
            session.flush()

        monkeypatch.setattr(queries, "session_scope", scope)
        yield session


OWNER = get_settings().default_user


def test_me_por_defecto(s):
    assert queries.me(OWNER) == {"username": OWNER, "ai_enabled": True, "can_investigate": True}


def test_apagar_la_ia_rechaza_capturas(s):
    queries.set_me(OWNER, ai_enabled=False)
    assert queries.me(OWNER)["ai_enabled"] is False
    with pytest.raises(queries.AiDisabled, match="La IA está apagada para tu usuario"):
        queries.require_ai(OWNER)


def test_motor_no_procesa_con_la_ia_apagada(s, monkeypatch):
    monkeypatch.setattr(capture_engines, "_executor", None)  # si intentara encolarla, fallaría
    queries.set_me(OWNER, ai_enabled=False)
    assert capture_engines.submit(123, OWNER) is False


def test_can_investigate_solo_el_duenio(s):
    queries.set_me("amigo", ai_enabled=True)
    assert queries.me("amigo")["can_investigate"] is False
    queries.set_me(OWNER, ai_enabled=False)
    assert queries.me(OWNER)["can_investigate"] is False


def test_api_expone_me():
    from apuestas.api.app import app

    assert {("/me", "GET"), ("/me", "PUT")} <= {(r.path, meth) for r in app.routes for meth in getattr(r, "methods", ())}
