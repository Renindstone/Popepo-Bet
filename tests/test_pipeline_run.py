"""Mensajes de la ingesta: una fuente en mantenimiento no llena la pantalla de trazas y el historial largo avisa."""

import logging
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.ingest import pipeline
from apuestas.ingest.http import SourceUnavailable


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session
            session.flush()

        monkeypatch.setattr(pipeline, "session_scope", scope)
        yield session


def test_source_in_maintenance_is_one_line_without_traceback(s, caplog):
    def fails() -> int:
        raise SourceUnavailable("understat.com no devolvió datos (¿está en mantenimiento?)")

    with caplog.at_level(logging.INFO, logger=pipeline.log.name):
        assert pipeline._run("understat", "L1 2026", fails) == 0
    record = next(r for r in caplog.records if r.name == pipeline.log.name)
    assert record.levelno == logging.WARNING and record.exc_info is None
    assert "mantenimiento" in record.getMessage()
    run = s.query(m.IngestionRun).one()
    assert run.status == "error" and "Traceback" not in run.error


def test_unexpected_error_keeps_the_traceback(s, caplog):
    def fails() -> int:
        raise ValueError("inesperado")

    with caplog.at_level(logging.INFO, logger=pipeline.log.name):
        pipeline._run("fotmob", "x", fails)
    assert any(r.exc_info for r in caplog.records)
    assert "Traceback" in s.query(m.IngestionRun).one().error
