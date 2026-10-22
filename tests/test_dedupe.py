"""Equipos duplicados entre fuentes: detección prudente y fusión con partidos duplicados (BD SQLite en memoria)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from apuestas.core import names
from apuestas.db import models as m
from apuestas.ingest import dedupe

T0 = datetime(2025, 9, 1, 15, tzinfo=UTC)


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def team(s, name, source, country=None):
    t = m.Team(name=name, country=country)
    s.add(t)
    s.flush()
    s.add(m.EntityAlias(entity_type="team", entity_id=t.id, source=source, source_key=f"{source}:{name}", source_name=name))
    return t


def game(s, comp, home, away, when, fotmob_id=None):
    season = s.scalar(select(m.Season).where(m.Season.competition_id == comp.id))
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=when, home_team_id=home.id,
                 away_team_id=away.id, fotmob_id=fotmob_id, status="finished", home_goals=1, away_goals=0)
    s.add(mt)
    s.flush()
    return mt


def comp(s, code):
    c = m.Competition(code=code, name=code, country="x", tier="light")
    s.add(c)
    s.flush()
    s.add(m.Season(competition_id=c.id, start_year=2025, label="2025/2026"))
    s.flush()
    return c


def test_names_known_variants():
    assert names.similarity("AEK", "AEK Athens") == 100
    assert names.similarity("Bodo/Glimt", "Bodø/Glimt") == 100
    assert names.similarity("St Etienne", "Saint-Étienne") == 100
    assert names.similarity("AEK", "AEK Larnaca") < 75  # otro club (Chipre)
    assert names.similarity("Dundee", "Dundee United") < 75
    # Nombres de OddsPapi en la Ligue 1 (22-10-2026)
    assert names.similarity("Stade Rennais FC", "Rennes") == 100
    assert names.similarity("Strasbourg Alsace", "Strasbourg") == 100


def test_detects_safe_pair_and_leaves_lookalikes_for_review(s):
    sa, gre, ucl = comp(s, "SA"), comp(s, "GRE"), comp(s, "UEL")
    verona_fm = team(s, "Hellas Verona", "fotmob")
    verona_fd = team(s, "Verona", "fdco", "Italy")
    rival = team(s, "Lecce", "fotmob")
    rival.country = "Italy"
    aek_fm, aek_fd = team(s, "AEK Athens", "fotmob"), team(s, "AEK", "fdco", "Greece")
    aris_cy, aris_gr = team(s, "Aris Limassol", "fotmob"), team(s, "Aris", "fdco", "Greece")
    other = team(s, "Panathinaikos", "fdco", "Greece")
    for i in range(3):  # la misma jornada, cargada por FotMob y por football-data
        game(s, sa, verona_fm, rival, T0 + timedelta(days=7 * i), fotmob_id=100 + i)
        game(s, sa, verona_fd, rival, T0 + timedelta(days=7 * i))
    game(s, ucl, aek_fm, aris_cy, T0 + timedelta(days=3), fotmob_id=500)
    game(s, gre, aek_fd, other, T0 + timedelta(days=5))
    game(s, gre, aris_gr, other, T0 + timedelta(days=6))

    found = {(c.keep_name, c.drop_name): c for c in dedupe.candidates(s)}
    assert found[("Hellas Verona", "Verona")].safe
    assert found[("Hellas Verona", "Verona")].duplicated_matches == 3
    assert found[("AEK Athens", "AEK")].safe
    aris = found.get(("Aris Limassol", "Aris")) or found.get(("Aris", "Aris Limassol"))
    assert aris is None or not aris.safe  # parecido, pero nunca se fusiona solo


def test_merge_moves_duplicate_matches_odds_and_aliases(s):
    sa = comp(s, "SA")
    keep, drop = team(s, "Hellas Verona", "fotmob"), team(s, "Verona", "fdco", "Italy")
    rival = team(s, "Lecce", "fotmob")
    a = game(s, sa, keep, rival, T0, fotmob_id=101)
    b = game(s, sa, drop, rival, T0 + timedelta(hours=1))  # hora de Londres frente a UTC
    lone = game(s, sa, rival, drop, T0 + timedelta(days=30))  # solo lo tiene football-data
    s.add_all([
        # En SQLite las claves BigInteger no se autoincrementan: id explícito
        m.OddsSnapshot(id=1, match_id=b.id, bookmaker="pinnacle", market="1x2", selection="home", price=2.1,
                       kind="closing", source="fdco", captured_at=T0),
        m.StatObservation(id=1, match_id=a.id, team_id=keep.id, stat="corners", source="fotmob", value=5),
        m.StatObservation(id=2, match_id=b.id, team_id=drop.id, stat="corners", source="fdco", value=5),
        m.StatObservation(id=3, match_id=b.id, team_id=rival.id, stat="corners", source="fdco", value=3),
    ])
    s.flush()

    out = dedupe.merge_teams(s, keep.id, drop.id)
    assert out["partidos_duplicados"] == 1
    assert s.get(m.Team, drop.id) is None
    assert s.get(m.Match, b.id) is None and s.get(m.Match, a.id) is not None
    assert s.scalar(select(m.OddsSnapshot.match_id)) == a.id  # las cuotas de cierre no se pierden
    obs = {(o.team_id, o.source) for o in s.scalars(select(m.StatObservation).where(m.StatObservation.match_id == a.id))}
    assert obs == {(keep.id, "fotmob"), (keep.id, "fdco"), (rival.id, "fdco")}
    assert s.get(m.Match, lone.id).away_team_id == keep.id
    aliases = set(s.scalars(select(m.EntityAlias.entity_id).where(m.EntityAlias.entity_type == "team",
                                                                  m.EntityAlias.source == "fdco")))
    assert aliases == {keep.id}  # la próxima ingesta de "Verona" ya cae en el equipo bueno
    assert s.scalar(select(func.count()).select_from(m.TeamMatchStats).where(m.TeamMatchStats.match_id == a.id)) == 2


def test_merge_refuses_teams_that_played_each_other(s):
    sco = comp(s, "SCO")
    d, du = team(s, "Dundee", "fdco", "Scotland"), team(s, "Dundee United", "fotmob", "Scotland")
    game(s, sco, d, du, T0)
    with pytest.raises(ValueError, match="se enfrentaron"):
        dedupe.merge_teams(s, du.id, d.id)
