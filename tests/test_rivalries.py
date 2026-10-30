"""Clásicos y derbis: el registro en la BD, el historial de la rivalidad y su factor en faltas y tarjetas."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.backtest import engine
from apuestas.db import models as m
from apuestas.ingest import store
from apuestas.models import fitting, ratings
from apuestas.models.fitting import MatchRow
from apuestas.models.ratings import MatchObs
from apuestas.services import rivalries

T0 = datetime(2026, 10, 25, 15, tzinfo=UTC)


@pytest.fixture
def s():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    with Session(db) as session:
        yield session


def teams(s, *names):
    rows = [m.Team(name=n) for n in names]
    s.add_all(rows)
    s.flush()
    return rows


def test_se_registran_los_clasicos_cuyos_equipos_existen(s):
    real, barca, _ = teams(s, "Real Madrid", "Barcelona", "Liverpool")  # sin Everton: su derbi espera
    assert store.ensure_rivalries(s) == 1
    assert rivalries.name_for(s, barca.id, real.id) == rivalries.name_for(s, real.id, barca.id) == "El Clásico"
    assert store.ensure_rivalries(s) == 0  # no se duplica
    (everton,) = teams(s, "Everton")  # sube de categoría: se enlaza en la siguiente sincronización
    assert store.ensure_rivalries(s) == 1
    assert rivalries.index(s)[frozenset((everton.id, s.scalar(select(m.Team.id).where(m.Team.name == "Liverpool"))))] \
        == "Derbi de Merseyside"


def test_historial_de_la_rivalidad(s):
    real, barca = teams(s, "Real Madrid", "Barcelona")
    comp = m.Competition(code="LAL", name="LaLiga", country="Spain", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    s.add(season)
    s.flush()
    for i, (h, a, hg, ag) in enumerate([(barca, real, 1, 2), (real, barca, 2, 1)]):
        mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=T0 - timedelta(days=200 * (i + 1)),
                     home_team_id=h.id, away_team_id=a.id, status="finished", home_goals=hg, away_goals=ag)
        s.add(mt)
        s.flush()
        s.add_all([m.TeamMatchStats(match_id=mt.id, team_id=h.id, is_home=True, fouls=14, yellow_cards=3, red_cards=1,
                                    shots=18, offsides=2),
                   m.TeamMatchStats(match_id=mt.id, team_id=a.id, is_home=False, fouls=12, yellow_cards=2,
                                    shots=10, offsides=None)])
    s.flush()
    out = rivalries.history(s, real.id, barca.id, T0)
    assert [x["score"] for x in out["matches"]] == ["1-2", "2-1"]  # el más reciente primero
    assert out["matches"][0]["cards"] == [4, 2] and out["matches"][0]["offsides"] == [2, None]
    assert out["averages"] == {"fouls": 26.0, "cards": 6.0, "shots": 28.0, "offsides": None}


def test_el_backtest_aplica_el_factor_de_clasico_en_faltas_y_tarjetas():
    day0 = date(2026, 10, 1)
    obs = [MatchObs(i % 6, (i + 1) % 6, day0 - timedelta(days=i), 2.0, 2.0) for i in range(300)]
    cm = ratings.fit(obs, day0, prior_matches=10.0)
    cm.total_dispersion = 0.0
    row = MatchRow(1, "LAL", day0, 0, 1, False, 1, 1, None, {"cards": 6}, {"cards": 4})
    plain, derby = defaultdict(list), defaultdict(list)
    engine._evaluate_counts(row, {"cards": cm}, plain)
    engine._evaluate_counts(row, {"cards": cm}, derby, derby=True)
    assert "cards+clasico" not in plain
    with_k, without = derby["cards+clasico"][0]
    assert without == pytest.approx(plain["cards"][0][0])  # sin factor, lo mismo que un partido normal
    assert with_k > without  # 10 tarjetas: más probables con el factor de 1,25
    assert fitting.DERBY_FACTOR == {"fouls": 1.08, "cards": 1.25}
