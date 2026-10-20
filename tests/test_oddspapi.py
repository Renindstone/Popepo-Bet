"""OddsPapi: lectura de mercados y cuotas con respuestas de ejemplo de su documentación v4 (sin red)."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.ingest import oddspapi, store

MARKETS = [  # formas reales del catálogo /v4/markets
    {"marketId": 101, "marketName": "Full Time Result", "marketType": "1x2", "handicap": 0, "period": "fulltime",
     "playerProp": False, "outcomes": [{"outcomeId": 101, "outcomeName": "1"}, {"outcomeId": 102, "outcomeName": "X"},
                                        {"outcomeId": 103, "outcomeName": "2"}]},
    {"marketId": 104, "marketName": "Both Teams To Score", "marketType": "bothteamsscore", "handicap": 0,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 105, "outcomeName": "No"}, {"outcomeId": 104, "outcomeName": "Yes"}]},
    {"marketId": 1010, "marketName": "Over Under Full Time", "marketType": "totals", "handicap": 2.5,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1011, "outcomeName": "Under"}, {"outcomeId": 1010, "outcomeName": "Over"}]},
    {"marketId": 1068, "marketName": "Asian Handicap", "marketType": "spreads", "handicap": -0.75,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1069, "outcomeName": "2"}, {"outcomeId": 1068, "outcomeName": "1"}]},
    {"marketId": 1060, "marketName": "Asian Handicap", "marketType": "spreads", "handicap": -1.5,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1060, "outcomeName": "1"}, {"outcomeId": 1061, "outcomeName": "2"}]},
    {"marketId": 1084, "marketName": "Asian Handicap", "marketType": "spreads", "handicap": 1.5,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1084, "outcomeName": "1"}, {"outcomeId": 1085, "outcomeName": "2"}]},
    {"marketId": 10118, "marketName": "European Handicap", "marketType": "spreads-european", "handicap": -2.0,
     "period": "fulltime", "playerProp": False, "outcomes": [{"outcomeId": 10118, "outcomeName": "1"},
                                                             {"outcomeId": 10119, "outcomeName": "X"},
                                                             {"outcomeId": 10120, "outcomeName": "2"}]},
    {"marketId": 10829, "marketName": "Corners - Over Under Full Time", "marketType": "totals-corners",
     "handicap": 9.5, "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 10829, "outcomeName": "Over"}, {"outcomeId": 10830, "outcomeName": "Under"}]},
    {"marketId": 10930, "marketName": "Bookings - Over Under Full Time", "marketType": "totals-bookings",
     "handicap": 4.5, "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 10930, "outcomeName": "Over"}, {"outcomeId": 10931, "outcomeName": "Under"}]},
    {"marketId": 10845, "marketName": "Corners - Handicap", "marketType": "spreads-corners", "handicap": -1.5,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 10845, "outcomeName": "1"}, {"outcomeId": 10846, "outcomeName": "2"}]},
    # No deben entrar: primer tiempo y props de jugador
    {"marketId": 2100, "marketName": "Corners - Over Under First Half", "marketType": "totals-corners",
     "handicap": 4.5, "period": "p1",
     "outcomes": [{"outcomeId": 2100, "outcomeName": "Over"}, {"outcomeId": 2101, "outcomeName": "Under"}]},
    {"marketId": 3000, "marketName": "Player Shots", "marketType": "totals", "handicap": 1.5, "period": "fulltime",
     "playerProp": True, "outcomes": [{"outcomeId": 3000, "outcomeName": "Over"}]},
]


def _price(p, active=True):
    return {"players": {"0": {"price": p, "active": active, "playerName": None}}}


FIXTURE = {
    "fixtureId": "id1000001761301153", "participant1Id": 35, "participant2Id": 34, "startTime": "2026-10-24T14:00:00.000Z",
    "bookmakerOdds": {
        "betano.pe": {"markets": {
            "101": {"outcomes": {"101": _price(1.45), "102": _price(4.75), "103": _price(6.5)}},
            "104": {"outcomes": {"104": _price(1.72), "105": _price(2.05)}},
            "1010": {"outcomes": {"1010": _price(1.62), "1011": _price(2.25, active=False)}},
            "1068": {"outcomes": {"1068": _price(1.95), "1069": _price(1.9)}},
            "10118": {"outcomes": {"10118": _price(3.1), "10119": _price(3.9), "10120": _price(1.57)}},
            "10829": {"outcomes": {"10829": _price(1.8), "10830": _price(1.95)}},
            "10930": {"outcomes": {"10930": _price(1.9)}},
            "10845": {"outcomes": {"10845": _price(1.85), "10846": _price(1.95)}},
            "2100": {"outcomes": {"2100": _price(1.7)}},
        }},
        "otra-casa": {"markets": {"101": {"outcomes": {"101": _price(1.5)}}}},
    },
}


def test_market_catalog_keeps_only_full_time_goal_markets():
    cat = oddspapi.market_catalog(MARKETS)
    assert cat["104"][:2] == ("btts", None)
    assert cat["1010"][:2] == ("ou_goals", 2.5)
    assert cat["1068"][:2] == ("ah", -0.75)
    assert cat["10118"][:2] == ("eh", -2.0)
    assert cat["10829"][:2] == ("ou_corners", 9.5) and cat["10930"][:2] == ("ou_cards", 4.5)
    assert {"2100", "3000", "101"}.isdisjoint(cat)


def test_parse_fixture_odds():
    prices = oddspapi.parse_fixture_odds(FIXTURE, oddspapi.market_catalog(MARKETS), ["betano.pe"])
    got = {(p.market, p.selection, p.line): p.price for p in prices}
    assert got[("1x2", "home", None)] == 1.45 and got[("1x2", "away", None)] == 6.5
    assert got[("btts", "yes", None)] == 1.72
    assert got[("ou_goals", "over", 2.5)] == 1.62
    assert ("ou_goals", "under", 2.5) not in got  # inactiva
    assert got[("ah", "home", -0.75)] == 1.95 and got[("ah", "away", 0.75)] == 1.9  # línea del equipo elegido
    assert {p.bookmaker for p in prices} == {"betano"}  # solo las configuradas, con nuestro nombre
    # Hándicap 3 vías: la línea sigue siendo la del local ("Coventry +2" = eh away con línea -2)
    assert got[("eh", "away", -2.0)] == 1.57 and got[("eh", "draw", -2.0)] == 3.9
    assert got[("ou_corners", "over", 9.5)] == 1.8 and got[("ou_cards", "over", 4.5)] == 1.9
    assert got[("ah_corners", "home", -1.5)] == 1.85 and got[("ah_corners", "away", 1.5)] == 1.95
    assert not any(p.price == 1.7 for p in prices)  # primer tiempo


def test_items_accepts_the_response_shapes():
    assert oddspapi._items([FIXTURE]) == [FIXTURE]
    assert oddspapi._items({"data": [FIXTURE]}) == [FIXTURE]
    assert oddspapi._items(FIXTURE) == [FIXTURE]
    assert oddspapi._items({"a": FIXTURE}) == [FIXTURE]


# Betano en Atlético - Deportivo (24-10-2026) tal como lo devolvió OddsPapi: el 1X2 y los hándicaps positivos
# vienen de un evento con local y visitante invertidos; los hándicaps negativos, del partido bien orientado.
REVERSED_BETANO = {"markets": {
    "101": {"outcomes": {"101": _price(14.5), "102": _price(6.0), "103": _price(1.18)}},
    "1060": {"outcomes": {"1060": _price(1.72), "1061": _price(2.18)}},  # Atlético -1,5 / Deportivo +1,5: bien
    "1084": {"outcomes": {"1084": _price(2.32), "1085": _price(1.57)}},  # "Atlético +1,5 @2,32": es de Deportivo
}}
PINNACLE = {"markets": {"101": {"outcomes": {"101": _price(1.287), "102": _price(5.95), "103": _price(10.05)}}}}
PINNACLE_1X2 = {"home": 1.287, "draw": 5.95, "away": 10.05}


def _prices(book_odds, book="betano.pe"):
    return oddspapi.parse_fixture_odds({"bookmakerOdds": {book: book_odds}}, oddspapi.market_catalog(MARKETS), [book])


def test_reversed_event_is_rejected_with_and_without_pinnacle():
    prices = _prices(REVERSED_BETANO)
    assert "1X2 al revés que Pinnacle" in oddspapi.rejection_reason(prices, PINNACLE_1X2)
    # Sin Pinnacle lo delatan los hándicaps: "local +1,5" no puede pagar más que "local -1,5"
    assert oddspapi.rejection_reason(prices, None) == "líneas incoherentes, ah home: -1.5 @1.72 y +1.5 @2.32"


def test_coherent_odds_are_kept():
    prices = oddspapi.parse_fixture_odds(FIXTURE, oddspapi.market_catalog(MARKETS), ["betano.pe"])
    assert oddspapi.rejection_reason(prices, {"home": 1.5, "draw": 4.5, "away": 6.0}) is None
    assert oddspapi.rejection_reason(prices, None) is None
    # Partido igualado (PSG - Barça): el favorito cambia según la casa, pero por poco
    close = [oddspapi.Price("betano", "1x2", s, None, p) for s, p in (("home", 2.42), ("draw", 3.5), ("away", 2.47))]
    assert not oddspapi.reversed_1x2(close, {"home": 2.5, "draw": 3.6, "away": 2.49})


def test_incoherent_lines_in_over_under_and_european_handicap():
    def lines(market, sel, pts):
        return [oddspapi.Price("betano", market, sel, ln, p) for ln, p in pts]

    ok = (lines("ou_goals", "over", [(1.5, 1.2), (2.5, 1.8), (3.5, 3.0)])
          + lines("ou_goals", "under", [(1.5, 4.0), (2.5, 2.0), (3.5, 1.35)])
          + lines("eh", "home", [(-2.0, 3.1), (-1.0, 1.75), (1.0, 1.07)])
          + lines("eh", "away", [(-2.0, 2.1), (-1.0, 3.85), (1.0, 30.0)])
          + lines("eh", "draw", [(-2.0, 4.4), (-1.0, 4.5), (1.0, 12.7)]))  # el empate no es monótono
    assert oddspapi.incoherent_lines(ok) is None
    # Goles del equipo 1 de dos eventos distintos (Atlético - Deportivo en Betano)
    mixed = lines("ou_goals_home", "over", [(0.5, 2.55), (1.5, 7.9), (3.5, 3.4)])
    assert oddspapi.incoherent_lines(mixed) == "ou_goals_home over: +1.5 @7.9 y +3.5 @3.4"


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _sync(s, monkeypatch, odds_by_book: dict, existing: list[tuple]) -> tuple[int, list, set]:
    """sync_upcoming con Atlético - Deportivo en una BD SQLite y las respuestas de OddsPapi simuladas.

    existing: cuotas ya guardadas (casa, mercado, selección, línea, cuota, fuente, día de captura).
    Devuelve (cuotas nuevas, cuotas que se guardarían, (casa, fuente) que quedan en la BD).
    """
    comp = store.ensure_competitions(s)["LAL"]
    home, away = m.Team(name="Atlético Madrid"), m.Team(name="Deportivo A Coruña")
    s.add_all([home, away])
    s.flush()
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=2)
    match = m.Match(competition_id=comp.id, season_id=store.get_season(s, comp, 2026).id, kickoff_utc=start,
                    home_team_id=home.id, away_team_id=away.id)
    s.add(match)
    s.flush()
    # En SQLite las claves BigInteger no se autoincrementan: id explícito
    s.add_all([m.OddsSnapshot(id=i, match_id=match.id, bookmaker=book, market=mk, selection=sel, line=ln, price=p,
                              source=src, captured_at=datetime(2026, 10, day, tzinfo=UTC))
               for i, (book, mk, sel, ln, p, src, day) in enumerate(existing, start=1)])
    s.flush()

    responses = {
        "tournaments": [{"tournamentId": 8, "tournamentSlug": "laliga", "categorySlug": "spain"}],
        "markets": MARKETS,
        "participants": {"2836": "Atletico Madrid", "2832": "RC Deportivo de A Coruna"},
    }
    fixtures = {book: [{"fixtureId": "id1000000872478650", "participant1Id": 2836, "participant2Id": 2832,
                        "tournamentId": 8, "startTime": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        "bookmakerOdds": {book: odds}}]
                for book, odds in odds_by_book.items()}

    @contextmanager
    def same_session():
        yield s

    stored = []
    monkeypatch.setattr(oddspapi, "bookmakers", lambda: list(odds_by_book))
    monkeypatch.setattr(oddspapi, "_get", lambda path, ttl, **params: fixtures.get(params.get("bookmaker"),
                                                                                  responses.get(path)))
    monkeypatch.setattr(oddspapi, "session_scope", same_session)
    monkeypatch.setattr(store, "find_match", lambda *a, **k: match)  # en SQLite las fechas pierden la zona horaria
    monkeypatch.setattr(store, "store_odds", lambda s, match, prices, source: stored.extend(prices) or len(prices))
    n = oddspapi.sync_upcoming()
    left = {(r.bookmaker, r.source) for r in s.scalars(select(m.OddsSnapshot))}
    return n, stored, left


def test_sync_upcoming_drops_the_reversed_bookmaker_only(s, monkeypatch):
    # Ya había: Betano al revés de una descarga anterior, y Pinnacle y bet365 de football-data
    existing = [("betano", "ah", "home", 1.5, 2.32, "oddspapi", 18), ("pinnacle", "1x2", "home", None, 1.3, "fdco", 18),
                ("bet365", "1x2", "home", None, 1.3, "fdco", 18)]
    n, stored, left = _sync(s, monkeypatch, {"betano.pe": REVERSED_BETANO, "pinnacle": PINNACLE}, existing)
    assert n == 3 and {p.bookmaker for p in stored} == {"pinnacle"}  # solo el 1X2 de Pinnacle
    assert left == {("pinnacle", "fdco"), ("bet365", "fdco")}  # las de Betano por OddsPapi, borradas


def test_sync_upcoming_falls_back_to_stored_pinnacle(s, monkeypatch):
    """Sin Pinnacle en la descarga, la referencia es su último 1X2 guardado (p. ej. de football-data)."""
    only_1x2 = {"markets": {"101": REVERSED_BETANO["markets"]["101"]}}  # sin hándicaps que lo delaten
    old = [("pinnacle", "1x2", sel, None, p, "fdco", 17) for sel, p in (("home", 3.8), ("draw", 3.4), ("away", 2.0))]
    new = [("pinnacle", "1x2", sel, None, p, "fdco", 18) for sel, p in (("home", 1.3), ("draw", 5.9), ("away", 10.0))]
    assert _sync(s, monkeypatch, {"betano.pe": only_1x2}, new + old)[:2] == (0, [])


def test_latest_1x2_is_the_last_capture(s):
    match = m.Match(id=1)
    s.add_all([m.OddsSnapshot(id=i, match_id=1, bookmaker="pinnacle", market="1x2", selection=sel, price=p,
                              kind=kind, source="fdco", captured_at=datetime(2026, 10, day, tzinfo=UTC))
               for i, (sel, p, kind, day) in enumerate([("home", 1.3, "live", 18), ("home", 2.0, "live", 17),
                                                        ("home", 1.25, "closing", 19)], start=1)])
    s.flush()
    assert store.latest_1x2(s, match, "pinnacle") == {"home": 1.3}  # la de cierre no cuenta
    assert store.latest_1x2(s, match, "betano") == {}
