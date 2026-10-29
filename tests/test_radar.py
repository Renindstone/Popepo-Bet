"""Radar de Sorpresas: equipos en racha y en baja, jugadores en racha y sus próximos partidos."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_weekly import KICKOFF, add_played, build_week, make_teams, no_bundle

from apuestas.db import models as m
from apuestas.services import radar


@pytest.fixture
def s(monkeypatch):
    no_bundle(monkeypatch)
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


AS_OF = KICKOFF + timedelta(days=3)


def names(rows):
    return [r["name"] for r in rows]


def test_batacazo_entra_en_racha(s):
    a, b = make_teams(s, 2)
    add_played(s, a, b, KICKOFF, 1, 0, p_home=5.0, p_draw=4.0, p_away=1.6)
    r = radar.build(s, AS_OF)
    row = next(x for x in r["racha"] if x["name"] == a.name)
    assert row["kind"] == "racha" and row["reason"]["type"] == "batacazo" and row["reason"]["p_win"] <= 0.25


def test_pinchazo_entra_en_baja(s):
    a, b = make_teams(s, 2)
    add_played(s, a, b, KICKOFF, 0, 1, p_home=1.45, p_draw=4.5, p_away=7.0)
    r = radar.build(s, AS_OF)
    row = next(x for x in r["baja"] if x["name"] == a.name)
    assert row["kind"] == "baja" and row["reason"]["type"] == "pinchazo" and row["reason"]["p_win"] >= 0.60


@pytest.mark.parametrize("score, upset, flop, kind", [
    (1.0, False, False, "racha"), (0.99, False, False, None), (-1.0, False, False, "baja"),
    (-0.99, False, False, None), (0.2, True, False, "racha"), (0.1, False, True, "baja"),
])
def test_limites_de_suma(score, upset, flop, kind):
    assert radar.classify(score, upset, flop) == kind


def test_ventana_de_28_dias(s):
    a, b = make_teams(s, 2)
    add_played(s, a, b, AS_OF - timedelta(days=29), 1, 0, p_home=5.0, p_draw=4.0, p_away=1.6)
    assert a.name not in names(radar.build(s, AS_OF)["racha"])


def test_figuras_y_jugadores(s):
    build_week(s)
    r = radar.build(s, AS_OF)
    arsenal = next(x for x in r["racha"] if x["name"] == "Arsenal")
    assert "Saka" in [f["name"] for f in arsenal["figures"]]
    saka = next(p for p in r["jugadores"] if p["name"] == "Saka")
    assert saka["score"] >= radar.PLAYER_SUM and saka["minutes"] >= radar.PLAYER_MIN_MINUTES


def test_jugador_con_pocos_minutos_no_entra(s):
    build_week(s)
    row = s.scalar(select(m.PlayerMatchStats).join(m.Player).where(m.Player.name == "Saka"))
    row.minutes = 80
    s.flush()
    assert "Saka" not in names(radar.build(s, AS_OF)["jugadores"])


def test_proximo_partido(s):
    build_week(s)  # Arsenal vs Everton, aplazado a dos días del primero
    arsenal = next(x for x in radar.build(s, KICKOFF + timedelta(days=1))["racha"] if x["name"] == "Arsenal")
    assert [n["label"] for n in arsenal["next_matches"]] == ["Arsenal vs Everton"]


def test_sin_partido_proximo(s):
    build_week(s)
    arsenal = next(x for x in radar.build(s, AS_OF)["racha"] if x["name"] == "Arsenal")
    assert arsenal["next_matches"] == []


def test_maximo_8_por_lista(s):
    t = make_teams(s, 20)
    for i in range(10):
        add_played(s, t[2 * i], t[2 * i + 1], KICKOFF + timedelta(hours=i), 1 + i % 3, 0,
                   p_home=5.0, p_draw=4.0, p_away=1.6)
    racha = radar.build(s, AS_OF)["racha"]
    assert len(racha) == radar.MAX_ROWS
    scores = [x["score"] for x in racha]
    assert scores == sorted(scores, reverse=True)


def test_api_expone_el_radar():
    from apuestas.api.app import app

    assert "/radar" in {r.path for r in app.routes}
