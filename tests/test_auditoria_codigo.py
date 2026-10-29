"""Fallos de la auditoría de código del 26-10-2026: datos que no pueden entrar, liquidación que no se frena,
apuestas del día sin duplicar, partidos empezados fuera de «Con valor» y el archivo de temporadas."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.archive import seasons
from apuestas.betting import settlement
from apuestas.db import models as m
from apuestas.ingest import store
from apuestas.services import picks, tracker

KICKOFF = datetime(2026, 10, 20, 19, 0, tzinfo=UTC)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    m.Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def s(engine):
    with Session(engine) as session:
        yield session


def match(s, status="finished", season_year=2026):
    comp = store.ensure_competitions(s)["EPL"]
    season = store.get_season(s, comp, season_year)
    a, b = m.Team(name=f"A{season_year}{status}"), m.Team(name=f"B{season_year}{status}")
    s.add_all([a, b])
    s.flush()
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KICKOFF, home_team_id=a.id,
                 away_team_id=b.id, status=status, home_goals=2, away_goals=1)
    s.add(mt)
    s.flush()
    return mt


# --------------------------------------------------------------------------- 1 y 2: lo que no puede entrar


@pytest.mark.parametrize("market, needs", [("ou_goals", True), ("ou_corners_home", True), ("ah", True), ("eh", True),
                                           ("ah_corners", True), ("1x2", False), ("btts", False), ("dc", False),
                                           ("player_shots", False), ("player_goal", False)])
def test_que_mercados_necesitan_linea(market, needs):
    assert settlement.needs_line(market) is needs


@pytest.mark.parametrize("market", ["ou_goals", "ah", "eh"])
def test_apuesta_sin_linea_se_rechaza(s, market):
    user = tracker.get_or_create_user(s, "amigo")
    with pytest.raises(ValueError, match="línea"):
        tracker.register_bet(s, user, match(s), "betano", market, "over", None, 1.9, 10.0)


@pytest.mark.parametrize("odds, stake", [(1.9, 0.0), (1.9, -5.0), (1.0, 10.0), (0.5, 10.0)])
def test_importe_y_cuota_validos(s, odds, stake):
    user = tracker.get_or_create_user(s, "amigo")
    with pytest.raises(ValueError):
        tracker.register_bet(s, user, match(s), "betano", "1x2", "home", None, odds, stake)


def test_apuesta_valida_entra(s):
    user = tracker.get_or_create_user(s, "amigo")
    bet = tracker.register_bet(s, user, match(s), "betano", "ou_goals", "over", 2.5, 1.9, 10.0)
    assert bet.id is not None


# --------------------------------------------------------------------------- 1: una apuesta rota no frena las demás


def test_una_apuesta_rota_no_frena_la_liquidacion(s, monkeypatch):
    @contextmanager
    def scope():
        yield s

    monkeypatch.setattr(picks, "session_scope", scope)
    monkeypatch.setattr(picks, "fill_missing_clv", lambda _s: 0)
    monkeypatch.setattr(picks, "set_clv", lambda *_: None)
    mt = match(s)
    rows = [m.Pick(match_id=mt.id, pick_date=date(2026, 10, 20), stage="confirmed", market=mk, selection="over",
                   line=2.5, bookmaker="betano", odds=1.9, model_prob=0.6, fair_odds=1.7, ev=0.1, confidence=0.7,
                   stake_pct=0.02, status="open") for mk in ("roto", "ou_goals")]
    s.add_all(rows)
    s.flush()
    real = settlement.settle

    def settle(sess, match_, market, *a, **k):
        if market == "roto":
            raise TypeError("dato corrupto")
        return real(sess, match_, market, *a, **k)

    monkeypatch.setattr(picks, "settle", settle)
    out = picks.settle_all()
    assert out["picks"] == 1
    assert [p.status for p in rows] == ["open", "settled"]


# --------------------------------------------------------------------------- 3: la apuesta del día no se duplica


def test_bloqueo_del_dia_en_postgres():
    calls = []
    pg = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
                         execute=lambda sql, params=None: calls.append((str(sql), params)))
    picks._lock_day(pg, date(2026, 10, 29))
    assert "pg_advisory_xact_lock" in calls[0][0]
    lite = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
                           execute=lambda *_: calls.append("no"))
    picks._lock_day(lite, date(2026, 10, 29))
    assert len(calls) == 1


# --------------------------------------------------------------------------- 4: sin partidos empezados en «Con valor»


def test_con_valor_no_lista_partidos_empezados():
    assert picks._listed(1.9, started=False) is True
    assert picks._listed(1.9, started=True) is False
    assert picks._listed(1.1, started=False) is False  # menos de 1.20: tampoco


# --------------------------------------------------------------------------- 5: archivo de temporadas


def odd(i, mt, kind, minutes, sel="over"):
    return m.OddsSnapshot(id=i, match_id=mt.id, bookmaker="bet365", market="ou_goals", selection=sel, line=2.5,
                          price=1.9, kind=kind, source="fdco", captured_at=KICKOFF - timedelta(minutes=minutes))


def test_poda_de_cuotas_deja_primera_ultima_apertura_y_cierre(s, engine, monkeypatch):
    monkeypatch.setattr(seasons, "get_engine", lambda: engine)
    mt = match(s)
    s.add_all([odd(1, mt, "opening", 500), odd(2, mt, "live", 400), odd(3, mt, "live", 300), odd(4, mt, "live", 200),
               odd(5, mt, "live", 100), odd(6, mt, "closing", 5), odd(7, mt, "live", 300, sel="under")])
    s.commit()
    assert seasons.prune_odds(mt.season_id) in (2, -1)  # SQLite no cuenta un DELETE con WITH; PostgreSQL sí
    left = sorted(s.scalars(select(m.OddsSnapshot.id)))
    assert left == [1, 2, 5, 6, 7]


def test_exporta_la_temporada_fria_y_borra_el_detalle(s, engine, monkeypatch, tmp_path):
    @contextmanager
    def scope():
        with Session(engine) as sess:
            yield sess
            sess.commit()

    monkeypatch.setattr(seasons, "get_engine", lambda: engine)
    monkeypatch.setattr(seasons, "session_scope", scope)
    monkeypatch.setattr(type(seasons.get_settings()), "archive_dir", property(lambda _self: tmp_path))
    mt = match(s, season_year=2022)
    p = m.Player(name="Viejo")
    s.add(p)
    s.flush()
    s.add_all([odd(1, mt, "closing", 5), m.Lineup(match_id=mt.id, team_id=mt.home_team_id, player_id=p.id,
                                                  status="confirmed", is_starter=True),
               m.TeamMatchStats(match_id=mt.id, team_id=mt.home_team_id, is_home=True, goals=2)])
    s.commit()
    out = seasons.export_cold(mt.season_id)
    assert out["odds_snapshot"] == 1 and out["lineup"] == 1 and out["match"] == 1
    folder = tmp_path / mt.season.label / "EPL"
    assert len(pd.read_parquet(folder / "lineup.parquet")) == 1
    s.expire_all()
    assert s.scalars(select(m.OddsSnapshot)).all() == [] and s.scalars(select(m.Lineup)).all() == []
    assert s.scalars(select(m.TeamMatchStats)).all() != [] and s.get(m.Season, mt.season_id).storage_tier == "cold"
