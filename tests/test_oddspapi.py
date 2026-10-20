"""OddsPapi: lectura de mercados y cuotas con respuestas de ejemplo de su documentación v4 (sin red)."""

from apuestas.ingest import oddspapi

MARKETS = [
    {"marketId": 101, "marketName": "Full Time Result", "marketType": "1x2", "handicap": 0, "period": "fulltime",
     "playerProp": False, "outcomes": [{"outcomeId": 101, "outcomeName": "1"}, {"outcomeId": 102, "outcomeName": "X"},
                                        {"outcomeId": 103, "outcomeName": "2"}]},
    {"marketId": 104, "marketName": "Both Teams To Score", "marketType": "totals", "handicap": 0,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 104, "outcomeName": "Yes"}, {"outcomeId": 105, "outcomeName": "No"}]},
    {"marketId": 1010, "marketName": "Over Under Full Time", "marketType": "totals", "handicap": 2.5,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1010, "outcomeName": "Over"}, {"outcomeId": 1011, "outcomeName": "Under"}]},
    {"marketId": 1068, "marketName": "Asian Handicap", "marketType": "spreads", "handicap": -0.75,
     "period": "fulltime", "playerProp": False,
     "outcomes": [{"outcomeId": 1068, "outcomeName": "1"}, {"outcomeId": 1069, "outcomeName": "2"}]},
    # No deben entrar: córners, primer tiempo y props de jugador
    {"marketId": 2000, "marketName": "Over Under Corners", "handicap": 9.5, "period": "fulltime",
     "outcomes": [{"outcomeId": 2000, "outcomeName": "Over"}, {"outcomeId": 2001, "outcomeName": "Under"}]},
    {"marketId": 2100, "marketName": "Over Under 1st Half", "handicap": 1.5, "period": "p1",
     "outcomes": [{"outcomeId": 2100, "outcomeName": "Over"}, {"outcomeId": 2101, "outcomeName": "Under"}]},
    {"marketId": 3000, "marketName": "Player Shots Over Under", "handicap": 1.5, "period": "fulltime",
     "playerProp": True, "outcomes": [{"outcomeId": 3000, "outcomeName": "Over"}]},
]


def _price(p, active=True):
    return {"players": {"0": {"price": p, "active": active, "playerName": None}}}


FIXTURE = {
    "fixtureId": "id1000001761301153", "participant1Id": 35, "participant2Id": 34, "startTime": "2026-10-24T14:00:00.000Z",
    "bookmakerOdds": {
        "betano": {"markets": {
            "101": {"outcomes": {"101": _price(1.45), "102": _price(4.75), "103": _price(6.5)}},
            "104": {"outcomes": {"104": _price(1.72), "105": _price(2.05)}},
            "1010": {"outcomes": {"1010": _price(1.62), "1011": _price(2.25, active=False)}},
            "1068": {"outcomes": {"1068": _price(1.95), "1069": _price(1.9)}},
            "2000": {"outcomes": {"2000": _price(1.8)}},
        }},
        "otra-casa": {"markets": {"101": {"outcomes": {"101": _price(1.5)}}}},
    },
}


def test_market_catalog_keeps_only_full_time_goal_markets():
    cat = oddspapi.market_catalog(MARKETS)
    assert cat["104"][0] == "btts"
    assert cat["1010"][:2] == ("ou_goals", 2.5)
    assert cat["1068"][:2] == ("ah", -0.75)
    assert {"2000", "2100", "3000", "101"}.isdisjoint(cat)


def test_parse_fixture_odds():
    prices = oddspapi.parse_fixture_odds(FIXTURE, oddspapi.market_catalog(MARKETS), ["betano"])
    got = {(p.market, p.selection, p.line): p.price for p in prices}
    assert got[("1x2", "home", None)] == 1.45 and got[("1x2", "away", None)] == 6.5
    assert got[("btts", "yes", None)] == 1.72
    assert got[("ou_goals", "over", 2.5)] == 1.62
    assert ("ou_goals", "under", 2.5) not in got  # inactiva
    assert got[("ah", "home", -0.75)] == 1.95 and got[("ah", "away", 0.75)] == 1.9  # línea del equipo elegido
    assert {p.bookmaker for p in prices} == {"betano"}  # solo las casas configuradas
    assert not any(p.market == "ou_corners" for p in prices)


def test_items_accepts_the_response_shapes():
    assert oddspapi._items([FIXTURE]) == [FIXTURE]
    assert oddspapi._items({"data": [FIXTURE]}) == [FIXTURE]
    assert oddspapi._items(FIXTURE) == [FIXTURE]
    assert oddspapi._items({"a": FIXTURE}) == [FIXTURE]
