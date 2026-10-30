"""Offsides como estadística del modelo: mercados Más/Menos del partido y de cada equipo, y su liquidación."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.betting.settlement import settle
from apuestas.db import models as m
from apuestas.models import fitting
from apuestas.services.match_model import MatchModel, parse_market


def test_mercados_de_offsides():
    assert parse_market("ou_offsides_home") == ("ou", "offsides", "home")
    assert parse_market("ou_fueras") == ("ou", "offsides", "total")
    assert "offsides" in fitting.COUNT_STATS
    mm = MatchModel(1, 2, 1.5, 1.1, -0.05, {"offsides": (2.5, 1.0)}, {"offsides": 0.05})
    over = mm.outcome("ou_offsides", "over", 3.5).effective_prob()
    home = mm.outcome("ou_offsides_home", "over", 1.5).effective_prob()
    assert 0.3 < over < 0.6 and home > mm.outcome("ou_offsides_away", "over", 1.5).effective_prob()


def test_liquidacion_de_offsides():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    with Session(db) as s:
        comp = m.Competition(code="LAL", name="LaLiga", country="Spain", tier="full")
        s.add(comp)
        s.flush()
        season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
        home, away = m.Team(name="Barcelona"), m.Team(name="Real Madrid")
        s.add_all([season, home, away])
        s.flush()
        mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=datetime(2026, 10, 25, 15),
                     home_team_id=home.id, away_team_id=away.id, status="finished", home_goals=1, away_goals=2)
        s.add(mt)
        s.flush()
        s.add_all([m.TeamMatchStats(match_id=mt.id, team_id=home.id, is_home=True, offsides=1),
                   m.TeamMatchStats(match_id=mt.id, team_id=away.id, is_home=False, offsides=6)])  # la trampa
        s.flush()
        assert settle(s, mt, "ou_offsides", "over", 6.5) == "win"
        assert settle(s, mt, "ou_offsides_away", "under", 4.5) == "loss"
        assert settle(s, mt, "ou_offsides_home", "over", 1.0) == "push"


@pytest.mark.parametrize("market", ["ou_offsides", "ou_offsides_home"])
def test_la_linea_hace_falta(market):
    from apuestas.betting.settlement import needs_line

    assert needs_line(market)
