"""Serie A y Ligue 1 (21-10-2026), Portugal y Bélgica (29-10-2026) y Turquía (30-10-2026) como ligas completas: fuentes, cuotas de
OddsPapi, backtest y consultas."""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.backtest import engine
from apuestas.core import names
from apuestas.core.competitions import COMPETITIONS, FULL, LIGHT
from apuestas.db import models as m
from apuestas.ingest import oddspapi, store
from apuestas.ingest.fotmob import FMMatch
from apuestas.services import queries


@pytest.fixture
def s():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    with Session(db) as session:
        yield session


def test_serie_a_and_ligue_1_are_full_with_all_sources():
    assert [c.code for c in FULL] == ["EPL", "BUN", "LAL", "SA", "L1", "POR", "BEL", "TUR", "UCL"]
    assert not {"SA", "L1", "POR", "BEL", "TUR"} & {c.code for c in LIGHT}
    sa, l1 = COMPETITIONS["SA"], COMPETITIONS["L1"]
    assert (sa.fd_code, sa.understat, sa.fotmob_id) == ("I1", "Serie_A", 55)
    assert (l1.fd_code, l1.understat, l1.fotmob_id) == ("F1", "Ligue_1", 53)
    # Understat no cubre Portugal ni Bélgica: su xG es solo el de FotMob
    por, bel = COMPETITIONS["POR"], COMPETITIONS["BEL"]
    assert (por.fd_code, por.understat, por.fotmob_id) == ("P1", None, 61)
    assert (bel.fd_code, bel.understat, bel.fotmob_id) == ("B1", None, 40)
    tur = COMPETITIONS["TUR"]
    assert (tur.fd_code, tur.understat, tur.fotmob_id) == ("T1", None, 71)


def test_backtest_evaluates_the_eight_leagues_by_default():
    assert engine.LEAGUES == ("EPL", "BUN", "LAL", "SA", "L1", "POR", "BEL", "TUR")


def test_backtest_logloss_by_competition():
    ll = {"modelo": 0.97, "modelo:SA": 0.9657, "bet365:SA": 0.96231, "modelo:L1": 0.9644}
    assert engine._by_competition(ll) == {"L1": {"modelo": 0.9644}, "SA": {"modelo": 0.9657, "bet365": 0.9623}}


def test_light_league_becomes_full_in_the_database(s):
    """La BD compartida ya tenía la Serie A como "light": al arrancar la nueva versión pasa a "full"."""
    s.add(m.Competition(code="SA", name="Serie A", country="Italy", tier="light", is_cup=False))
    s.add(m.Competition(code="BEL", name="Pro League", country="Belgium", tier="light", is_cup=False))
    s.flush()
    comps = store.ensure_competitions(s)
    assert comps["SA"].tier == "full" and comps["L1"].tier == "full" and comps["NED"].tier == "light"
    assert comps["BEL"].tier == "full" and comps["POR"].tier == "full"
    assert s.scalar(select(m.Competition.tier).where(m.Competition.code == "SA")) == "full"


@pytest.mark.parametrize(
    ("text", "code"),
    [("SA", "SA"), ("serie a", "SA"), ("Serie A", "SA"), ("ligue 1", "L1"), ("l1", "L1"),
     ("Premier League", "EPL"), ("laliga", "LAL"), ("ucl", "UCL"), ("Primeira Liga", "POR"), ("por", "POR"),
     ("Pro League", "BEL"), ("bel", "BEL"), ("Süper Lig", "TUR"), ("super lig", "TUR")],
)
def test_competition_code_accepts_code_or_name(text, code):
    assert queries.competition_code(text) == code


def test_oddspapi_requests_per_bookmaker_with_eight_competitions(s, monkeypatch):
    """Cada llamada cuenta 1 en el cupo y admite 5 torneos: hasta 5 competiciones, 1 por casa; de 6 a 9, 2."""
    tournaments = [
        {"tournamentId": 17, "tournamentSlug": "premier-league", "categorySlug": "england"},
        {"tournamentId": 35, "tournamentSlug": "bundesliga", "categorySlug": "germany"},
        {"tournamentId": 8, "tournamentSlug": "laliga", "categorySlug": "spain"},
        {"tournamentId": 23, "tournamentSlug": "serie-a", "categorySlug": "italy"},
        {"tournamentId": 34, "tournamentSlug": "ligue-1", "categorySlug": "france"},
        {"tournamentId": 238, "tournamentSlug": "liga-portugal", "categorySlug": "portugal"},
        {"tournamentId": 38, "tournamentSlug": "pro-league", "categorySlug": "belgium"},
        {"tournamentId": 52, "tournamentSlug": "super-lig", "categorySlug": "turkiye"},
        {"tournamentId": 7, "tournamentSlug": "uefa-champions-league", "categorySlug": "international-clubs"},
        {"tournamentId": 99, "tournamentSlug": "serie-b", "categorySlug": "italy"},
        {"tournamentId": 239, "tournamentSlug": "liga-portugal-2", "categorySlug": "portugal"},
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
    assert oddspapi.tournament_ids() == {"EPL": 17, "BUN": 35, "LAL": 8, "SA": 23, "L1": 34, "POR": 238, "BEL": 38,
                                         "TUR": 52, "UCL": 7}

    # Fin de semana: juegan las cinco ligas y no la Champions
    monkeypatch.setattr(oddspapi, "playing_soon", lambda days, now=None: {"EPL", "BUN", "LAL", "SA", "L1"})
    calls.clear()
    oddspapi.sync_upcoming()
    odds_calls = [p for path, p in calls if path == "odds-by-tournaments"]
    assert [p["bookmaker"] for p in odds_calls] == ["betano.pe", "pinnacle"]
    assert all(p["tournamentIds"] == "17,35,8,23,34" for p in odds_calls)

    # Fin de semana con las ocho ligas: dos peticiones por casa
    eight = {"EPL", "BUN", "LAL", "SA", "L1", "POR", "BEL", "TUR"}
    monkeypatch.setattr(oddspapi, "playing_soon", lambda days, now=None: eight)
    calls.clear()
    oddspapi.sync_upcoming()
    odds_calls = [p["tournamentIds"] for path, p in calls if path == "odds-by-tournaments"]
    assert odds_calls == ["17,35,8,23,34", "238,38,52", "17,35,8,23,34", "238,38,52"]

    # Semana de Champions con liga entre semana: seis, en dos peticiones por casa
    monkeypatch.setattr(oddspapi, "playing_soon", lambda days, now=None: {"EPL", "BUN", "LAL", "SA", "L1", "UCL"})
    calls.clear()
    oddspapi.sync_upcoming()
    odds_calls = [p["tournamentIds"] for path, p in calls if path == "odds-by-tournaments"]
    assert odds_calls == ["17,35,8,23,34", "7", "17,35,8,23,34", "7"]


def test_fotmob_adopts_the_football_data_match_of_a_league_that_was_light(s):
    """Portugal y Bélgica eran "light" sin FotMob: football-data creó sus partidos y sus equipos. Al bajar la liga de
    FotMob, el partido se reutiliza (con sus cuotas de cierre y estadísticas) en vez de duplicarse."""
    comp = store.ensure_competitions(s)["BEL"]
    season = store.get_season(s, comp, 2025)
    home = store.resolve_team(s, "fdco", "Belgium:Oud-Heverlee Leuven", "Oud-Heverlee Leuven", "Belgium")
    away = store.resolve_team(s, "fdco", "Belgium:Standard", "Standard", "Belgium")
    kickoff = datetime(2025, 9, 13, 18, 45, tzinfo=UTC)
    old = store.create_light_match(s, comp, season, kickoff, home, away, 2, 1)
    fm = FMMatch(fotmob_id=4818355, kickoff_utc=kickoff, home_id=1773, home_name="OH Leuven", away_id=9985,
                 away_name="Standard Liège", round="7", status="finished", home_goals=2, away_goals=1)
    match = store.upsert_fotmob_match(s, comp, season, fm)
    assert match.id == old.id and match.fotmob_id == 4818355
    assert (match.home_team_id, match.away_team_id) == (home.id, away.id)
    assert s.scalar(select(m.Match.id).where(m.Match.competition_id == comp.id).offset(1)) is None
    assert home.name == "OH Leuven" and away.name == "Standard Liège"  # FotMob tiene los nombres más completos
    # La final del playoff europeo solo la trae FotMob: partido nuevo
    final = FMMatch(fotmob_id=5268800, kickoff_utc=datetime(2026, 5, 29, 16, 30, tzinfo=UTC), home_id=1773,
                    home_name="OH Leuven", away_id=9985, away_name="Standard Liège", round="final",
                    status="finished", home_goals=0, away_goals=1)
    assert store.upsert_fotmob_match(s, comp, season, final).id != old.id


@pytest.mark.parametrize(
    ("other", "fotmob"),
    [("AVS", "AVS Futebol SAD"), ("Estrela", "Estrela da Amadora"), ("Beerschot VA", "Beerschot"),
     ("Dender", "FCV Dender EH"), ("Mechelen", "KV Mechelen"), ("Oud-Heverlee Leuven", "OH Leuven"),
     ("RWD Molenbeek", "RWDM Brussels"), ("Standard", "Standard Liège"), ("Waregem", "Zulte Waregem"),
     ("Royal Charleroi SC", "Sporting Charleroi"), ("Charleroi", "Sporting Charleroi"),
     ("Ad. Demirspor", "Adana Demirspor"), ("Amedspor", "Amed Sportif"), ("Bodrumspor", "Bodrum FK"),
     ("Karagumruk", "Fatih Karagümrük")],
)
def test_portuguese_belgian_and_turkish_names_match_fotmob(other, fotmob):
    """Nombres de football-data y OddsPapi que no llegaban al umbral de `store.resolve_team` (90)."""
    assert names.similarity(other, fotmob) >= 90
