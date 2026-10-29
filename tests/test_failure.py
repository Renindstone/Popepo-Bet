"""«Por qué falló»: la previa guardada frente a lo que pasó cuando se pierde la apuesta del día."""

from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_weekly import KICKOFF, add_played, build_week, make_teams, no_bundle

from apuestas.db import models as m
from apuestas.services import failure, queries


@pytest.fixture
def s(monkeypatch):
    no_bundle(monkeypatch)
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(failure, "session_scope", scope)
        yield session


def lost_pick(s, match, result="loss", pod=True):
    p = m.Pick(match_id=match.id, pick_date=date(2026, 10, 20), stage="confirmed", market="1x2", selection="away",
               bookmaker="betano", odds=3.5, model_prob=0.33, fair_odds=3.0, ev=0.15, confidence=0.7, stake_pct=0.02,
               is_pick_of_day=pod, was_pick_of_day=pod, qualifies=True, status="settled", result=result,
               announced_at=KICKOFF - timedelta(hours=6), announced_odds=3.5,
               created_at=KICKOFF - timedelta(hours=6))
    s.add(p)
    s.flush()
    return p


def test_fallo_con_previa(s):
    played, arsenal = build_week(s)
    r = failure.analyze(s, lost_pick(s, played))
    assert r["has_preview"] is True and r["score"] == "2-1" and r["result"] == "loss"
    home = next(t for t in r["teams"] if t["side"] == "home")
    assert home["team"] == "Arsenal" and any(i["item"] == "goals" for i in home["items"])
    assert 0 < len(r["players"]) <= 3 and r["players"][0]["name"] == "Saka"


def test_fallo_sin_previa(s):
    a, b = make_teams(s, 2)
    mt = add_played(s, a, b, KICKOFF, 2, 0)
    r = failure.analyze(s, lost_pick(s, mt))
    assert r["has_preview"] is False and r["teams"] == [] and r["players"] == []


def test_lo_avisaba(s):
    a, b, c = make_teams(s, 3)
    add_played(s, a, c, KICKOFF - timedelta(days=7), 1, 0, p_home=5.0, p_draw=4.0, p_away=1.6)  # batacazo de a
    mt = add_played(s, a, b, KICKOFF, 1, 1)
    r = failure.analyze(s, lost_pick(s, mt))
    assert [(f["team"], f["kind"]) for f in r["flagged"]] == [(a.name, "racha")]


@pytest.mark.parametrize("result, pod", [("win", True), ("loss", False), ("push", True)])
def test_solo_perdidas_de_la_apuesta_del_dia(s, result, pod):
    a, b = make_teams(s, 2)
    p = lost_pick(s, add_played(s, a, b, KICKOFF, 1, 0), result=result, pod=pod)
    with pytest.raises(queries.NotFound):
        failure.get(p.id)


def test_medio_perdida_cuenta(s):
    a, b = make_teams(s, 2)
    p = lost_pick(s, add_played(s, a, b, KICKOFF, 1, 0), result="half_loss")
    assert failure.get(p.id)["result"] == "half_loss"


def test_historial_y_dia_pasado_llevan_pick_id(s, monkeypatch):
    from apuestas.services import picks

    @contextmanager
    def scope():
        yield s

    monkeypatch.setattr(picks, "session_scope", scope)
    monkeypatch.setattr(queries, "session_scope", scope)
    monkeypatch.setattr(picks, "today_local", lambda: date(2026, 10, 25))
    a, b = make_teams(s, 2)
    p = lost_pick(s, add_played(s, a, b, KICKOFF, 1, 0))
    assert picks.pick_history(30)["last"][0]["pick_id"] == p.id
    assert queries.pick_of_day("2026-10-20")["pick_of_day"]["pick_id"] == p.id


def test_api_expone_por_que_fallo():
    from apuestas.api.app import app

    assert "/picks/{pick_id}/failure" in {r.path for r in app.routes}
