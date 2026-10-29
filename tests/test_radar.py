"""Radar de Sorpresas: equipos en racha y en baja, jugadores en racha y sus próximos partidos."""

from datetime import UTC, datetime, timedelta

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


# --------------------------------------------------------------------------- avisos


def radar_row(team, kind, figures=()):
    return {"team_id": team.id, "name": team.name, "competition": "EPL", "kind": kind, "score": 1.5 if kind == "racha" else -1.5,
            "n_matches": 2, "reason": {"type": "suma"}, "figures": list(figures), "next_matches": []}


def upcoming_match(s, home, away):
    from apuestas.ingest import store

    comp = store.ensure_competitions(s)["EPL"]
    season = store.get_season(s, comp, 2026)
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=AS_OF + timedelta(days=1),
                 home_team_id=home.id, away_team_id=away.id, status="scheduled")
    s.add(mt)
    s.flush()
    return mt


def test_avisos_dos_equipos(s):
    a, b = make_teams(s, 2)
    mt = upcoming_match(s, a, b)
    cached = {a.id: radar_row(a, "racha"), b.id: radar_row(b, "baja")}
    alerts = radar.alerts_for_match(s, mt, AS_OF, cached)
    assert [x["side"] for x in alerts] == ["home", "away"]
    assert [x["kind"] for x in alerts] == ["racha", "baja"]
    assert all(x["caveat"] == radar.NOTE for x in alerts)


def test_figura_en_el_once(s):
    a, b = make_teams(s, 2)
    mt = upcoming_match(s, a, b)
    p1, p2, p3 = (m.Player(name=n) for n in ("Uno", "Dos", "Tres"))
    s.add_all([p1, p2, p3])
    s.flush()
    s.add_all([m.Lineup(match_id=mt.id, team_id=a.id, player_id=p1.id, status="predicted", is_starter=True),
               m.Lineup(match_id=mt.id, team_id=a.id, player_id=p2.id, status="confirmed", is_starter=True)])
    s.flush()
    figs = [{"player_id": p.id, "name": p.name, "score": 2.0} for p in (p1, p2, p3)]
    alert = radar.alerts_for_match(s, mt, AS_OF, {a.id: radar_row(a, "racha", figs)})[0]
    assert [f["lineup"] for f in alert["figures"]] == ["probable", "confirmado", None]


def test_sin_radar_sin_avisos(s):
    a, b = make_teams(s, 2)
    assert radar.alerts_for_match(s, upcoming_match(s, a, b), AS_OF, {}) == []


def test_attach_alerts_pone_la_lista_en_todo():
    from apuestas.services import picks

    report = {"matches": [{"match_id": 1}, {"match_id": 2}], "value_bets": [{"match_id": 1}, {"match_id": 2}],
              "pick_of_day": {"match_id": 1}}
    aviso = {"team_id": 9, "kind": "baja"}
    picks.attach_alerts(report, {1: [aviso]})
    assert report["matches"][0]["alerts"] == [aviso] and report["matches"][1]["alerts"] == []
    assert report["value_bets"][0]["alerts"] == [aviso] and report["value_bets"][1]["alerts"] == []
    assert report["pick_of_day"]["alerts"] == [aviso]


def test_proximos_partidos_llevan_avisos(s, monkeypatch):
    from contextlib import contextmanager

    from apuestas.services import queries

    @contextmanager
    def scope():
        yield s

    monkeypatch.setattr(queries, "session_scope", scope)
    a, b = make_teams(s, 2)
    mt = upcoming_match(s, a, b)
    mt.kickoff_utc = datetime.now(UTC) + timedelta(days=1)
    s.flush()
    monkeypatch.setattr(radar, "flagged_now", lambda: {b.id: radar_row(b, "baja")})
    row = next(r for r in queries.upcoming(days=3) if r["match_id"] == mt.id)
    assert [(x["side"], x["kind"]) for x in row["alerts"]] == [("away", "baja")]


# --------------------------------------------------------------------------- arreglos de la revisión final


def test_figura_sin_once_publicado(s):
    a, b = make_teams(s, 2)
    mt = upcoming_match(s, a, b)
    p = m.Player(name="Uno")
    s.add(p)
    s.flush()
    figs = [{"player_id": p.id, "name": p.name, "score": 2.0}]
    alert = radar.alerts_for_match(s, mt, AS_OF, {a.id: radar_row(a, "racha", figs)})[0]
    assert alert["figures"][0]["lineup"] == "sin_once"


def test_partido_terminado_sin_avisos(s):
    a, b = make_teams(s, 2)
    mt = upcoming_match(s, a, b)
    mt.status = "finished"
    s.flush()
    assert radar.alerts_for_match(s, mt, AS_OF, {a.id: radar_row(a, "racha")}) == []


def test_un_fallo_del_radar_no_rompe_las_paginas(monkeypatch):
    def boom():
        raise RuntimeError("radar roto")

    monkeypatch.setattr(radar, "get", boom)
    assert radar.flagged_now() == {}


# --------------------------------------------------------------------------- detalles pendientes de la revisión


def test_figuras_solo_de_partidos_sorprendentes(s):
    played, arsenal = build_week(s)
    played.home_goals, played.away_goals = 0, 1  # Arsenal pierde el partido en que Saka brilló
    (rival,) = make_teams(s, 1)
    add_played(s, arsenal, rival, KICKOFF - timedelta(days=2), 1, 0, p_home=5.0, p_draw=4.0, p_away=1.6)  # batacazo
    s.flush()
    row = next(x for x in radar.build(s, AS_OF)["racha"] if x["name"] == "Arsenal")
    assert row["reason"]["type"] == "batacazo"
    assert "Saka" not in [f["name"] for f in row["figures"]]


def test_filas_del_radar_llevan_sus_partidos(s):
    build_week(s)
    arsenal = next(x for x in radar.build(s, AS_OF)["racha"] if x["name"] == "Arsenal")
    assert [x["label"] for x in arsenal["matches"]] == ["Arsenal 2-1 Chelsea"]
    assert set(arsenal["matches"][0]) == {"match_id", "label", "kickoff_local", "score"}


def test_el_aviso_lleva_su_advertencia_aparte_de_la_nota_de_claude(s):
    a, b = make_teams(s, 2)
    alert = radar.alerts_for_match(s, upcoming_match(s, a, b), AS_OF, {a.id: radar_row(a, "racha")})[0]
    assert alert["caveat"] == radar.NOTE and "note" not in alert
