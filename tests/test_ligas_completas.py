"""Serie A y Ligue 1 como ligas completas (21-10-2026): fuentes, cuotas de OddsPapi, backtest y consultas."""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.backtest import engine
from apuestas.core.competitions import COMPETITIONS, FULL, LIGHT
from apuestas.db import models as m
from apuestas.ingest import oddspapi, store
from apuestas.services import queries


@pytest.fixture
def s():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    with Session(db) as session:
        yield session


def test_serie_a_and_ligue_1_are_full_with_all_sources():
    assert [c.code for c in FULL] == ["EPL", "BUN", "LAL", "SA", "L1", "UCL"]
    assert not {"SA", "L1"} & {c.code for c in LIGHT}
    sa, l1 = COMPETITIONS["SA"], COMPETITIONS["L1"]
    assert (sa.fd_code, sa.understat, sa.fotmob_id) == ("I1", "Serie_A", 55)
    assert (l1.fd_code, l1.understat, l1.fotmob_id) == ("F1", "Ligue_1", 53)


def test_backtest_evaluates_the_five_leagues_by_default():
    assert engine.LEAGUES == ("EPL", "BUN", "LAL", "SA", "L1")


def test_backtest_logloss_by_competition():
    ll = {"modelo": 0.97, "modelo:SA": 0.9657, "bet365:SA": 0.96231, "modelo:L1": 0.9644}
    assert engine._by_competition(ll) == {"L1": {"modelo": 0.9644}, "SA": {"modelo": 0.9657, "bet365": 0.9623}}


def test_light_league_becomes_full_in_the_database(s):
    """La BD compartida ya tenía la Serie A como "light": al arrancar la nueva versión pasa a "full"."""
    s.add(m.Competition(code="SA", name="Serie A", country="Italy", tier="light", is_cup=False))
    s.flush()
    comps = store.ensure_competitions(s)
    assert comps["SA"].tier == "full" and comps["L1"].tier == "full" and comps["NED"].tier == "light"
    assert s.scalar(select(m.Competition.tier).where(m.Competition.code == "SA")) == "full"


@pytest.mark.parametrize(
    ("text", "code"),
    [("SA", "SA"), ("serie a", "SA"), ("Serie A", "SA"), ("ligue 1", "L1"), ("l1", "L1"),
     ("Premier League", "EPL"), ("laliga", "LAL"), ("ucl", "UCL")],
)
def test_competition_code_accepts_code_or_name(text, code):
    assert queries.competition_code(text) == code


def test_oddspapi_requests_per_bookmaker_with_six_competitions(s, monkeypatch):
    """Cada llamada cuenta 1 en el cupo y admite 5 torneos: con las cinco ligas, 1 por casa; con la Champions, 2."""
    tournaments = [
        {"tournamentId": 17, "tournamentSlug": "premier-league", "categorySlug": "england"},
        {"tournamentId": 35, "tournamentSlug": "bundesliga", "categorySlug": "germany"},
        {"tournamentId": 8, "tournamentSlug": "laliga", "categorySlug": "spain"},
        {"tournamentId": 23, "tournamentSlug": "serie-a", "categorySlug": "italy"},
        {"tournamentId": 34, "tournamentSlug": "ligue-1", "categorySlug": "france"},
        {"tournamentId": 7, "tournamentSlug": "uefa-champions-league", "categorySlug": "international-clubs"},
        {"tournamentId": 99, "tournamentSlug": "serie-b", "categorySlug": "italy"},
    ]
    calls = []

    def fake_get(path, ttl, **params):
        calls.append((path, params))
        return {"tournaments": tournaments, "markets": [], "participants": {}}.get(path, [])

    @contextmanager
    def same_session():
        yield s

    monkeypatch.setattr(oddspapi, "_get", fake_get)
    monkeypatch.setattr(oddspapi, "bookmakers", lambda: ["betano.pe", "pinnacle"])
    monkeypatch.setattr(oddspapi, "session_scope", same_session)
    assert oddspapi.tournament_ids() == {"EPL": 17, "BUN": 35, "LAL": 8, "SA": 23, "L1": 34, "UCL": 7}

    # Fin de semana: juegan las cinco ligas y no la Champions
    monkeypatch.setattr(oddspapi, "playing_soon", lambda days, now=None: {"EPL", "BUN", "LAL", "SA", "L1"})
    calls.clear()
    oddspapi.sync_upcoming()
    odds_calls = [p for path, p in calls if path == "odds-by-tournaments"]
    assert [p["bookmaker"] for p in odds_calls] == ["betano.pe", "pinnacle"]
    assert all(p["tournamentIds"] == "17,35,8,23,34" for p in odds_calls)

    # Semana de Champions con liga entre semana: las seis, en dos peticiones por casa
    monkeypatch.setattr(oddspapi, "playing_soon", lambda days, now=None: {"EPL", "BUN", "LAL", "SA", "L1", "UCL"})
    calls.clear()
    oddspapi.sync_upcoming()
    odds_calls = [p["tournamentIds"] for path, p in calls if path == "odds-by-tournaments"]
    assert odds_calls == ["17,35,8,23,34", "7", "17,35,8,23,34", "7"]
