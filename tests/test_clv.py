"""CLV: la cuota tomada frente a la justa (sin margen) de la referencia más afilada que haya antes del partido."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.db import models as m
from apuestas.ingest import oddspapi
from apuestas.jobs import scheduler
from apuestas.services import picks
from apuestas.services.analysis import book_fair_prob

KICKOFF = datetime(2026, 10, 25, 15, tzinfo=UTC)


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(picks, "session_scope", scope)
        yield session


def match(s):
    comp = m.Competition(code="LAL", name="LaLiga", country="Spain", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    home, away = m.Team(name="Barcelona"), m.Team(name="Real Madrid")
    s.add_all([season, home, away])
    s.flush()
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KICKOFF, home_team_id=home.id,
                 away_team_id=away.id, status="finished", home_goals=2, away_goals=1)
    s.add(mt)
    s.flush()
    return mt


def odds(s, mt, rows):
    """rows: (casa, tipo, selección, línea, cuota, minutos antes del inicio)."""
    start = s.query(m.OddsSnapshot).count() + 1
    s.add_all([m.OddsSnapshot(id=i, match_id=mt.id, bookmaker=book, market="ou_goals_home", selection=sel, line=ln,
                              price=p, kind=kind, source="x", captured_at=KICKOFF - timedelta(minutes=mins))
               for i, (book, kind, sel, ln, p, mins) in enumerate(rows, start=start)])
    s.flush()


def test_pinnacle_before_kickoff_without_margin(s):
    mt = match(s)
    odds(s, mt, [
        ("pinnacle", "live", "under", 2.5, 1.70, 600), ("pinnacle", "live", "over", 2.5, 2.10, 600),
        ("pinnacle", "live", "under", 2.5, 1.80, 14), ("pinnacle", "live", "over", 2.5, 2.00, 14),  # la última
        ("pinnacle", "live", "under", 2.5, 1.50, -30),  # ya empezado: no cuenta
        ("bet365", "closing", "under", 2.5, 1.75, 0), ("bet365", "closing", "over", 2.5, 2.00, 0),
    ])
    fair, book, at = picks.closing_reference(s, mt, "ou_goals_home", "under", 2.5)
    p_under = oddsmath.devig([1.80, 2.00])[0]
    assert book == "pinnacle" and fair == pytest.approx(1 / p_under, abs=1e-3)
    assert at.replace(tzinfo=UTC) == KICKOFF - timedelta(minutes=14)


def test_falls_back_when_a_side_is_missing(s):
    mt = match(s)
    # Pinnacle solo tiene un lado de esa línea: no se puede quitar el margen; queda el cierre de bet365
    odds(s, mt, [("pinnacle", "live", "under", 2.5, 1.80, 14), ("pinnacle", "live", "over", 1.5, 1.40, 14),
                 ("bet365", "closing", "under", 2.5, 1.75, 0), ("bet365", "closing", "over", 2.5, 2.00, 0)])
    assert picks.closing_reference(s, mt, "ou_goals_home", "under", 2.5)[1] == "bet365"
    assert picks.closing_reference(s, mt, "ou_goals_home", "under", 3.5) is None


def test_set_clv_on_a_settled_pick(s):
    mt = match(s)
    odds(s, mt, [("pinnacle", "live", "under", 2.5, 1.80, 14), ("pinnacle", "live", "over", 2.5, 2.00, 14)])
    pick = m.Pick(match_id=mt.id, pick_date=date(2026, 10, 25), stage="confirmed", market="ou_goals_home",
                  selection="under", line=2.5, bookmaker="betano", odds=1.93, model_prob=0.6, fair_odds=1.67,
                  ev=0.1, confidence=0.8, stake_pct=0.01, qualifies=True, status="settled", result="win",
                  announced_at=datetime(2026, 10, 25, 9, tzinfo=UTC), announced_odds=1.93)
    s.add(pick)
    s.flush()
    assert picks.set_clv(s, pick)
    assert pick.clv == pytest.approx(1.93 * oddsmath.devig([1.80, 2.00])[0] - 1, abs=1e-3)
    assert pick.closing_source == "pinnacle"
    s.flush()
    s.expire_all()  # como al leerlo de la BD
    out = picks.qualified_picks(days=10_000)
    row = out["picks"][0]
    assert row["clv_ref"] == {"book": "pinnacle", "kind": "live", "minutes_before": 14} and row["clv_note"] is None
    assert out["record"]["avg_clv"] == pytest.approx(pick.clv) and out["record"]["with_clv"] == 1


def test_settled_without_reference_says_why(s):
    mt = match(s)
    s.add(m.Pick(match_id=mt.id, pick_date=date(2026, 10, 25), stage="confirmed", market="dnb", selection="home",
                 bookmaker="betano", odds=1.5, model_prob=0.7, fair_odds=1.43, ev=0.05, confidence=0.8,
                 stake_pct=0.01, qualifies=True, status="settled", result="win",
                 announced_at=datetime(2026, 10, 25, 9, tzinfo=UTC), announced_odds=1.5))
    s.flush()
    row = picks.qualified_picks(days=10_000)["picks"][0]
    assert row["clv"] is None and row["clv_ref"] is None and "Pinnacle" in row["clv_note"]


def test_btts_without_margin():
    rows = [m.OddsSnapshot(bookmaker="pinnacle", market="btts", selection=sel, line=None, price=p)
            for sel, p in (("yes", 1.80), ("no", 2.05))]
    assert book_fair_prob(rows, "pinnacle", "btts", "no", None) == pytest.approx(oddsmath.devig([1.80, 2.05])[1])


@pytest.mark.parametrize("minutes, due", [(20, False), (17.4, True), (15, True), (12.6, True), (12.4, False)])
def test_closing_is_fetched_once_about_15_minutes_before(minutes, due):
    assert scheduler.closing_due(minutes) is due


def test_sync_closing_asks_only_pinnacle_for_those_competitions(monkeypatch):
    calls = []

    def fake_get(path, ttl, **params):
        calls.append((path, ttl, params))
        return {"markets": {}, "participants": {}}.get(path, [])

    monkeypatch.setattr(oddspapi, "_get", fake_get)
    monkeypatch.setattr(oddspapi, "tournament_ids", lambda: {"EPL": 17, "LAL": 8, "UCL": 7})
    assert oddspapi.sync_closing({"LAL"}) == 0
    odds_calls = [(ttl, p) for path, ttl, p in calls if path == "odds-by-tournaments"]
    assert [(p["bookmaker"], p["tournamentIds"]) for _, p in odds_calls] == [("pinnacle", "8")]
    assert odds_calls[0][0] <= 300  # sin la caché de 30 min: tiene que ser el precio de ahora
