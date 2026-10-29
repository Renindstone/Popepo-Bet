"""Previa guardada: una por partido, la última antes del inicio y nunca después."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import predictions
from apuestas.services.match_model import MatchModel, PlayerProjection

NOW = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
BUNDLE = SimpleNamespace(version="v1", as_of=date(2026, 10, 24))


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def analysis(kickoff=NOW + timedelta(hours=2), lam_home=1.6, stage="predicted", match_id=7):
    players = {
        pid: PlayerProjection(player_id=pid, name=f"J{pid}", team_id=team, position="FW", expected_minutes=80.0,
                              start_prob=0.9, lam={"shots": 2.5, "shots_on_target": 1.0, "goals": 0.4, "assists": 0.2})
        for pid, team in ((1, 10), (2, 10), (3, 20))
    }
    model = MatchModel(home_id=10, away_id=20, lam_home=lam_home, lam_away=1.1, rho=-0.01,
                       count_means={"corners": (5.4, 4.1), "shots_on_target": (4.8, 3.6)},
                       count_dispersion={"corners": 0.074, "shots_on_target": 0.017},
                       count_total_dispersion={"corners": 0.017}, players=players)
    return SimpleNamespace(match=SimpleNamespace(id=match_id, kickoff_utc=kickoff), model=model, stage=stage)


def test_one_row_per_match_updated_until_kickoff(s):
    first = predictions.store(s, analysis(), BUNDLE, NOW)
    assert first is not None and first.model_version == "v1@2026-10-24"
    p = first.payload
    assert p["goals"]["home"] == 1.6 and p["counts"]["corners"] == {"home": 5.4, "away": 4.1, "dispersion": 0.074,
                                                                           "total_dispersion": 0.017}
    assert p["counts"]["shots_on_target"]["total_dispersion"] is None
    assert [(pl["player_id"], pl["side"]) for pl in p["players"]] == [(1, "home"), (2, "home"), (3, "away")]
    assert p["player_dispersion"]["shots"] == 0.15

    # Con la alineación confirmada cambia: se actualiza la misma fila
    later = NOW + timedelta(minutes=60)
    predictions.store(s, analysis(lam_home=1.8, stage="confirmed"), BUNDLE, later)
    rows = s.scalars(select(m.Prediction)).all()
    assert len(rows) == 1 and rows[0].stage == "confirmed" and rows[0].payload["goals"]["home"] == 1.8
    assert rows[0].updated_at.replace(tzinfo=UTC) == later

    # Sin cambios no se reescribe
    predictions.store(s, analysis(lam_home=1.8, stage="confirmed"), BUNDLE, later + timedelta(minutes=5))
    assert s.scalars(select(m.Prediction)).one().updated_at.replace(tzinfo=UTC) == later


def test_never_written_after_kickoff(s):
    assert predictions.store(s, analysis(kickoff=NOW - timedelta(minutes=1)), BUNDLE, NOW) is None
    assert s.scalars(select(m.Prediction)).all() == []


def test_errors_do_not_break_the_caller(s, monkeypatch):
    def boom(an, bundle):
        raise RuntimeError("x")

    monkeypatch.setattr(predictions, "payload_from", boom)
    assert predictions.store(s, analysis(), BUNDLE, NOW) is None


def test_usable_only_before_kickoff_and_same_day(s):
    kickoff = NOW + timedelta(hours=2)
    predictions.store(s, analysis(kickoff=kickoff, match_id=1), BUNDLE, NOW)
    predictions.store(s, analysis(kickoff=kickoff, match_id=2), BUNDLE, NOW)
    s.flush()
    played = SimpleNamespace(id=1, kickoff_utc=kickoff)
    postponed = SimpleNamespace(id=2, kickoff_utc=kickoff + timedelta(days=10))  # se jugó 10 días después
    no_previa = SimpleNamespace(id=3, kickoff_utc=kickoff)
    ok, stale = predictions.usable(s, [played, postponed, no_previa])
    assert set(ok) == {1} and stale == {2}
    assert ok[1]["stage"] == "predicted" and len(ok[1]["players"]) == 3
