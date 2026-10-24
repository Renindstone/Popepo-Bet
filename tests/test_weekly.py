"""Resumen de la semana: vara de la casa para equipos, previa del modelo para jugadores y sorpresa con margen."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.ingest import store
from apuestas.models import surprise as sp
from apuestas.services import weekly

KICKOFF = datetime(2026, 10, 20, 19, 0, tzinfo=UTC)  # martes
MONDAY = date(2026, 10, 19)


# --------------------------------------------------------------------------- sorpresa


def test_mid_pit_bounds_and_margin():
    pmf = sp.count_dist(sp.solve_mean(9.5, 0.5, 0.074), 0.074)
    assert sp.mid_pit(pmf, 0) < -0.99 and sp.mid_pit(pmf, 60) > 0.99
    assert sum(p * sp.mid_pit(pmf, k) for k, p in enumerate(pmf)) == pytest.approx(0, abs=1e-6)
    assert sp.mid_pit(pmf, 15) > sp.mid_pit(pmf, 10) > 0 > sp.mid_pit(pmf, 8)


def test_result_rewards_the_underdog():
    underdog, favourite = sp.result_score(3, 0.15, 0.25), sp.result_score(3, 0.75, 0.17)
    assert -1 <= favourite < underdog <= 1
    assert sp.result_score(1, 0.75, 0.17) < 0  # empatar siendo favorito resta


@pytest.mark.parametrize("line, p", [(9.5, 0.5), (10.0, 0.45), (9.75, 0.55), (2.5, 0.6)])
def test_solve_mean_reproduces_the_price(line, p):
    from apuestas.models import distributions as dist

    mu = sp.solve_mean(line, p, 0.074)
    assert dist.over(dist.pmf_to_dict(sp.count_dist(mu, 0.074)), line).effective_prob() == pytest.approx(p, abs=1e-3)
    assert sp.solve_mean(line, 1.0, 0.074) is None


# --------------------------------------------------------------------------- vara de la casa


def odd(book, market, sel, price, line=None, kind="live", at=KICKOFF - timedelta(hours=3)):
    return SimpleNamespace(bookmaker=book, market=market, selection=sel, line=line, price=price, kind=kind,
                           captured_at=at)


def test_pre_kickoff_ignores_prices_after_the_start_except_closing():
    rows = [odd("pinnacle", "1x2", "home", 2.0), odd("pinnacle", "1x2", "home", 9.0, at=KICKOFF + timedelta(minutes=30)),
            odd("bet365", "1x2", "home", 2.1, kind="closing", at=KICKOFF)]
    pk = weekly.pre_kickoff(rows, KICKOFF)
    assert pk["live"][("pinnacle", "1x2", "home", None)] == 2.0
    assert pk["closing"][("bet365", "1x2", "home", None)] == 2.1


def test_vara_prefers_closing_then_pinnacle():
    rows = [odd("pinnacle", "1x2", s, p) for s, p in (("home", 2.0), ("draw", 3.4), ("away", 3.9))]
    rows += [odd("bet365", "1x2", s, p, kind="closing", at=KICKOFF) for s, p in (("home", 1.8), ("draw", 3.6), ("away", 4.5))]
    vara = weekly.vara_1x2(weekly.pre_kickoff(rows, KICKOFF))
    assert vara["kind"] == "closing" and vara["book"] == "bet365"
    assert vara["home"] + vara["draw"] + vara["away"] == pytest.approx(1)


def test_main_line_is_the_closest_to_even():
    ladder = [(3.5, 1.30, 3.4), (4.5, 1.85, 1.95), (5.5, 2.9, 1.40)]
    rows = [odd("betano", "ou_corners_home", sel, p, line=ln) for ln, o, u in ladder for sel, p in (("over", o), ("under", u))]
    ml = weekly.main_line(weekly.pre_kickoff(rows, KICKOFF), "ou_corners_home")
    assert ml["line"] == 4.5 and ml["book"] == "betano" and 0.45 < ml["p_over"] < 0.55


# --------------------------------------------------------------------------- semana completa (SQLite)


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def build_week(s):
    comp = store.ensure_competitions(s)["EPL"]
    season = store.get_season(s, comp, 2026)
    teams = [m.Team(name=n) for n in ("Arsenal", "Chelsea", "Everton", "Fulham")]
    s.add_all(teams)
    s.flush()
    a, b, c, d = teams
    played = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KICKOFF, home_team_id=a.id,
                     away_team_id=b.id, status="finished", home_goals=2, away_goals=1)
    no_odds = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KICKOFF + timedelta(days=1),
                      home_team_id=c.id, away_team_id=d.id, status="finished", home_goals=0, away_goals=0)
    postponed = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KICKOFF + timedelta(days=2),
                        home_team_id=a.id, away_team_id=c.id, status="scheduled")
    s.add_all([played, no_odds, postponed])
    s.flush()
    striker = m.Player(name="Saka", position="FW")
    sub = m.Player(name="Suplente", position="MF")
    keeper = m.Player(name="Raya", position="GK")
    s.add_all([striker, sub, keeper])
    s.flush()
    odds = [("pinnacle", "1x2", sel, p, None) for sel, p in (("home", 2.0), ("draw", 3.5), ("away", 3.8))]
    odds += [("betano", "ou_corners_home", sel, p, 4.5) for sel, p in (("over", 1.9), ("under", 1.9))]
    odds += [("pinnacle", "ou_goals_home", sel, p, 1.5) for sel, p in (("over", 2.0), ("under", 1.8))]
    s.add_all([m.OddsSnapshot(id=i, match_id=played.id, bookmaker=bk, market=mk, selection=sel, line=ln, price=p,
                              kind="live", source="oddspapi", captured_at=KICKOFF - timedelta(hours=4))
               for i, (bk, mk, sel, p, ln) in enumerate(odds, start=1)])
    s.add_all([m.TeamMatchStats(match_id=played.id, team_id=a.id, is_home=True, goals=2, corners=8),
               m.TeamMatchStats(match_id=played.id, team_id=b.id, is_home=False, goals=1, corners=2)])
    lam = {"shots": 2.5, "shots_on_target": 1.0, "goals": 0.4, "assists": 0.2}
    payload = {"v": 1, "kickoff_utc": KICKOFF.isoformat(), "goals": {"home": 1.6, "away": 1.1, "rho": -0.01},
               "1x2": {"home": 0.5, "draw": 0.27, "away": 0.23},
               "counts": {"corners": {"home": 5.0, "away": 4.0, "dispersion": 0.074}},
               "player_dispersion": {"shots": 0.15, "shots_on_target": 0.15},
               "players": [{"player_id": striker.id, "side": "home", "position": "FW", "expected_minutes": 85.0,
                            "start_prob": 0.9, "lam": lam},
                           {"player_id": sub.id, "side": "home", "position": "MF", "expected_minutes": 20.0,
                            "start_prob": 0.1, "lam": lam},
                           {"player_id": keeper.id, "side": "home", "position": "GK", "expected_minutes": 90.0,
                            "start_prob": 1.0, "lam": {"shots": 0.0, "goals": 0.0}}]}
    s.add(m.Prediction(match_id=played.id, stage="confirmed", model_version="v1@2026-10-19", payload=payload,
                       updated_at=KICKOFF - timedelta(minutes=10), created_at=KICKOFF - timedelta(hours=8)))
    s.add_all([
        m.PlayerMatchStats(match_id=played.id, player_id=striker.id, team_id=a.id, minutes=90, goals=2, assists=0,
                           shots=5, shots_on_target=3),
        m.PlayerMatchStats(match_id=played.id, player_id=sub.id, team_id=a.id, minutes=20, goals=1, assists=0,
                           shots=1, shots_on_target=1),
        m.PlayerMatchStats(match_id=played.id, player_id=keeper.id, team_id=a.id, minutes=90, goals=0, assists=0,
                           shots=0, shots_on_target=0),
    ])
    s.flush()
    return played, a


def test_week_recap(s, monkeypatch):
    monkeypatch.setattr(weekly.fitting, "load_bundle", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    played, arsenal = build_week(s)
    r = weekly.recap(s, MONDAY, now=datetime(2026, 10, 27, tzinfo=UTC))  # el lunes 26 en Lima ya cerró la semana
    assert r["status"] == "cerrada" and r["history_since"] == "2026-10-20"  # la primera previa, en hora de Lima
    cov = r["coverage"]
    assert (cov["played"], cov["with_prediction"], cov["without_prediction"], cov["scheduled"]) == (2, 1, 1, 1)
    # Sin cuotas ni previa, el 0-0 no tiene vara: no cuenta
    assert [t["name"] for t in r["teams"]] == ["Arsenal", "Chelsea"]
    top = r["team_of_week"]
    items = {i["item"]: i for i in top["matches"][0]["items"]}
    assert set(items) == {"result", "goals", "corners"}
    assert items["corners"]["line"] == 4.5 and items["corners"]["source"] == "casa" and items["corners"]["score"] > 0.5
    assert items["result"]["book"] == "pinnacle" and items["result"]["score"] > 0
    # Jugadores: el suplente de 20 minutos no entra; el portero suma los goles recibidos
    assert [p["name"] for p in r["players"]] == ["Saka", "Raya"]
    raya = r["players"][1]
    assert any(i["item"] == "conceded" for i in raya["matches"][0]["items"])
    slots = r["eleven"]["slots"]
    assert slots[0]["line"] == "GK" and slots[0]["player"]["name"] == "Raya"
    fw = [sl["player"]["name"] if sl["player"] else None for sl in slots if sl["line"] == "FW"]
    assert fw == ["Saka", None, None]


def test_old_week_without_previas_has_no_players(s, monkeypatch):
    monkeypatch.setattr(weekly.fitting, "load_bundle", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    r = weekly.recap(s, MONDAY - timedelta(days=7))
    assert r["players"] == [] and r["player_of_week"] is None and r["team_of_week"] is None
    assert all(sl["player"] is None for sl in r["eleven"]["slots"])


def test_mcp_and_api_expose_the_week():
    from apuestas.api.app import app
    from apuestas.mcp_server.server import build

    assert "resumen_semana" in {t.name for t in build()._tool_manager.list_tools()}
    assert "/week" in {r.path for r in app.routes}
