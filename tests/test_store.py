from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from apuestas.core.competitions import LIGHT
from apuestas.db import models as m
from apuestas.ingest import fotmob, store


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


def _details(finished: bool = True) -> fotmob.FMDetails:
    det = fotmob.FMDetails(
        fotmob_id=99, finished=finished, cancelled=False, kickoff_utc=datetime(2025, 10, 2, 16, 45, tzinfo=UTC),
        home_id=1, away_id=2, home_goals=1, away_goals=1, home_goals_ht=0, away_goals_ht=1,
        referee="Nenad Minaković", referee_country="Serbia", lineup_type="confirmed",
    )
    det.players = [fotmob.FMPlayer(10, "Uno", 1, "FW", True, 1e6, 7.0), fotmob.FMPlayer(20, "Dos", 2, "DF", True, 2e6, 6.8)]
    det.player_stats = {10: {"team_fotmob_id": 1, "name": "Uno", "minutes": 90, "shots": 2.0},
                        20: {"team_fotmob_id": 2, "name": "Dos", "minutes": 90, "shots": 1.0}}
    det.team_stats = {1: {"shots": 8.0, "corners": 2.0, "xg": 0.79}, 2: {"shots": 12.0, "corners": 8.0, "xg": 2.08}}
    return det


def _cup_match(s, code: str) -> m.Match:
    comp = store.ensure_competitions(s)[code]
    home, away = store.fotmob_team(s, 1, "Bologna"), store.fotmob_team(s, 2, "Freiburg")
    match = m.Match(competition_id=comp.id, season_id=store.get_season(s, comp, 2025).id, fotmob_id=99,
                    kickoff_utc=datetime(2025, 10, 2, 16, 45, tzinfo=UTC), home_team_id=home.id, away_team_id=away.id)
    s.add(match)
    s.flush()
    return match


def test_stats_only_details_keep_team_stats_without_lineups(s):
    """Europa League: resultado, árbitro y estadísticas de equipo; ni once (cambiaría el once típico) ni jugadores."""
    match = _cup_match(s, "UEL")
    store.apply_fotmob_details(s, match, _details(), stats_only=True)
    stats = {t.is_home: t for t in s.scalars(select(m.TeamMatchStats).where(m.TeamMatchStats.match_id == match.id))}
    assert (stats[True].corners, stats[False].corners, stats[False].shots) == (2, 8, 12)
    assert stats[True].xg == pytest.approx(0.79)
    assert (match.status, match.home_goals, match.away_goals) == ("finished", 1, 1)
    assert match.referee.name == "Nenad Minaković"
    assert match.details_fetched_at is not None and match.lineup_status is None
    assert s.scalar(select(func.count()).select_from(m.Lineup)) == 0
    assert s.scalar(select(func.count()).select_from(m.PlayerMatchStats)) == 0


def test_full_details_store_lineups_and_players(s):
    match = _cup_match(s, "UCL")
    store.apply_fotmob_details(s, match, _details())
    assert match.lineup_status == "confirmed"
    assert s.scalar(select(func.count()).select_from(m.Lineup)) == 2
    assert s.scalar(select(func.count()).select_from(m.PlayerMatchStats)) == 2


def test_europa_and_conference_bring_stats():
    assert [c.code for c in LIGHT if c.fotmob_stats] == ["UEL", "UECL"]
