import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.ingest import store


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.parametrize(
    ("fotmob", "fdco", "country"),
    [
        ("Heart of Midlothian", "Hearts", "Scotland"),
        ("Bodø/Glimt", "Bodo/Glimt", "Norway"),
        ("FC København", "FC Copenhagen", "Denmark"),
        ("Legia Warszawa", "Legia", "Poland"),
    ],
)
def test_fdco_name_resolves_to_fotmob_team(s, fotmob, fdco, country):
    """Un rival de copa europea (FotMob) y su liga (football-data) son el mismo equipo."""
    team = store.fotmob_team(s, 1, fotmob)
    same = store.resolve_team(s, "fdco", f"{country}:{fdco}", fdco, country)
    assert same.id == team.id
    assert (same.name, same.country) == (fotmob, country)


def test_similar_names_of_other_clubs_stay_apart(s):
    store.fotmob_team(s, 1, "Lausanne")
    store.fotmob_team(s, 2, "Universitatea Craiova")
    for name in ("Lausanne Ouchy", "U Craiova 1948"):
        store.resolve_team(s, "fdco", f"X:{name}", name, "X")
    assert s.scalar(select(func.count()).select_from(m.Team)) == 4


def test_calendar_year_season_label(s):
    comps = store.ensure_competitions(s)
    assert store.get_season(s, comps["NOR"], 2026).label == "2026"
    assert store.get_season(s, comps["AUT"], 2026).label == "2026-27"
