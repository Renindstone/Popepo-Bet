"""Apuestas que pasan el corte: se marcan al guardarse, salen primero y tienen su propio contador de aciertos."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import picks, queries


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(picks, "session_scope", scope)
        monkeypatch.setattr(queries, "session_scope", scope)
        yield session


def bet(**kw):
    """Apuesta con valor que pasa el corte por defecto (goles, cuota 2,0, 55 %, +10 %, confianza 0,8)."""
    base = dict(market="ou_goals", selection="over", line=2.5, bookmaker="bet365", odds=2.0, prob=0.55,
                fair_odds=1.82, ev=0.10, confidence=0.8, stake_pct=0.01, reasons=[])
    return SimpleNamespace(**{**base, **kw})


def match(s, kickoff=datetime(2026, 10, 20, 19, tzinfo=UTC)):
    comp = m.Competition(code="EPL", name="Premier League", country="England", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    home, away = m.Team(name="Arsenal"), m.Team(name="Chelsea")
    s.add_all([season, home, away])
    s.flush()
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=kickoff, home_team_id=home.id,
                 away_team_id=away.id, status="finished", home_goals=2, away_goals=1)
    s.add(mt)
    s.flush()
    return mt


@pytest.mark.parametrize("change, passes", [
    ({}, True),
    ({"confidence": 0.4}, False),  # poca confianza
    ({"odds": 3.5, "ev": 0.2}, False),  # cuota fuera del rango de la apuesta del día
    ({"market": "ou_corners"}, False),  # córners: aún no entran en la apuesta del día
])
def test_upsert_marks_whether_it_passes(s, change, passes):
    mt = match(s)
    p = picks._upsert_pick(s, mt, bet(**change), date(2026, 10, 20), "pre_lineup")
    assert p.qualifies is passes


def test_recalculation_can_take_it_out_of_the_cut(s):
    mt = match(s)
    day = date(2026, 10, 20)
    p = picks._upsert_pick(s, mt, bet(), day, "pre_lineup")
    s.flush()
    again = picks._upsert_pick(s, mt, bet(confidence=0.5), day, "confirmed")  # con la alineación baja la confianza
    assert again.id == p.id and again.qualifies is False


def test_qualified_record_counts_only_those_that_passed(s):
    mt = match(s)
    day = date(2026, 10, 20)
    rows = [
        dict(selection="over", qualifies=True, status="settled", result="win", odds=2.0, is_pick_of_day=True),
        dict(selection="under", qualifies=True, status="settled", result="loss", odds=1.9),
        dict(selection="yes", qualifies=True, status="open", result=None, odds=1.8),
        dict(selection="no", qualifies=True, status="withdrawn", result=None, odds=2.1),  # retirada: no cuenta
        dict(selection="home", qualifies=False, status="settled", result="win", odds=2.5),  # no pasó el corte
    ]
    for r in rows:
        s.add(m.Pick(match_id=mt.id, pick_date=day, stage="pre_lineup", market="ou_goals", line=2.5,
                     bookmaker="bet365", model_prob=0.55, fair_odds=1.8, ev=0.1, confidence=0.8, stake_pct=0.01,
                     created_at=datetime(2026, 10, 20, 14, tzinfo=UTC), **r))
    s.flush()
    out = picks.qualified_picks(days=10_000)
    rec = out["record"]
    assert (rec["settled"], rec["hits"], rec["misses"], rec["pending"]) == (2, 1, 1, 1)
    assert rec["profit_units"] == pytest.approx(0.0)  # +1 a 2,0 y −1
    assert rec["since"] == "2026-10-20"
    listed = {p["selection"]: p for p in out["picks"]}
    assert set(listed) == {"over", "under", "yes"}
    assert listed["over"]["is_pick_of_day"] and listed["over"]["profit_units"] == 1.0
    assert listed["yes"]["profit_units"] is None


def test_past_day_lists_the_ones_that_passed_first(s):
    mt = match(s, kickoff=datetime.now(UTC) - timedelta(days=3))
    day = picks.today_local() - timedelta(days=3)
    for sel, ev, passed, status, odds in (("a", 0.30, False, "settled", 2.0), ("b", 0.05, True, "settled", 2.0),
                                          ("c", 0.20, True, "withdrawn", 2.0), ("d", 0.08, True, "settled", 2.0),
                                          ("e", 0.01, False, "settled", 1.15)):  # cuota de menos de 1.20: no sale
        s.add(m.Pick(match_id=mt.id, pick_date=day, stage="pre_lineup", market="1x2", selection=sel,
                     bookmaker="bet365", odds=odds, model_prob=0.5, fair_odds=2.0, ev=ev, confidence=0.8,
                     stake_pct=0.01, qualifies=passed, status=status))
    s.flush()
    rows = queries.pick_of_day(day.isoformat())["value_bets"]
    # Pasan el corte (d, b por valor) y después el resto, incluida la retirada aunque pasara el corte
    assert [r["selection"] for r in rows] == ["d", "b", "a", "c"]
    assert rows[0]["qualifies"] is True and rows[2]["qualifies"] is False
    # Probabilidad y confianza guardadas, para poder ordenar por ellas en el panel
    assert rows[0]["prob"] == 0.5 and rows[0]["confidence"] == 0.8
