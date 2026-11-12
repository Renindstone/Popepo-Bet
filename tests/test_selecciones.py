"""UEFA Nations League y torneos de selecciones (10-11-2026): datos y análisis, sin apuesta del día ni mercados de
jugador; los clasificatorios, el Mundial y la Eurocopa solo dan historial."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apuestas.api import i18n
from apuestas.backtest import engine
from apuestas.core import names
from apuestas.core.competitions import COMPETITIONS, FULL, NATIONAL, NATIONAL_TEAM, fotmob_season
from apuestas.db import models as m
from apuestas.ingest import oddspapi, pipeline, store
from apuestas.ingest.fotmob import FMDetails, FMMatch, FMPlayer, FMUnavailable
from apuestas.models import fitting
from apuestas.services import analysis, picks, queries


@pytest.fixture
def s():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    with Session(db) as session:
        yield session


def test_nations_league_is_full_without_picks_and_the_rest_is_history():
    unl = COMPETITIONS["UNL"]
    assert unl in FULL and unl.national and not unl.picks and not unl.is_cup
    assert (unl.fotmob_id, unl.fotmob_more_ids, unl.fd_code, unl.understat) == (9806, (9807, 9808, 9809), None, None)
    assert {"UNL", "WCQ", "WC", "EURO"} == NATIONAL
    for code in ("WCQ", "WC", "EURO"):
        c = COMPETITIONS[code]
        assert c.tier == "light" and c.fotmob_stats and c.is_cup
    assert COMPETITIONS["WC"].neutral and COMPETITIONS["EURO"].neutral and not unl.neutral
    assert all(c.picks for c in FULL if c.code != "UNL")


def test_fotmob_seasons_only_the_editions_that_exist():
    """Con una temporada que no existe, FotMob devuelve la actual: no se pide."""
    unl = COMPETITIONS["UNL"]
    assert fotmob_season(2026, unl) == "2026/2027" and fotmob_season(2024, unl) == "2024/2025"
    assert fotmob_season(2025, unl) is None
    assert fotmob_season(2025, COMPETITIONS["WC"]) == "2026" and fotmob_season(2023, COMPETITIONS["EURO"]) == "2024"
    assert fotmob_season(2026, COMPETITIONS["EPL"]) == "2026/2027"


def test_sync_downloads_the_four_divisions_and_skips_missing_seasons(monkeypatch):
    asked = []
    monkeypatch.setattr(pipeline.fotmob, "league_matches", lambda lid, season, ttl=None: asked.append((lid, season)) or [])
    monkeypatch.setattr(pipeline, "_run", lambda source, task, fn: fn())
    monkeypatch.setattr(pipeline.store, "ensure_competitions", lambda s: {"UNL": None})
    monkeypatch.setattr(pipeline.store, "get_season", lambda s, comp, year: None)
    pipeline.sync_fotmob_leagues([2023, 2024, 2025, 2026], codes=["UNL"])
    assert asked == [(lid, season) for season in ("2024/2025", "2026/2027") for lid in (9806, 9807, 9808, 9809)]


def test_backtest_with_odds_leaves_the_nations_league_out():
    assert "UNL" not in engine.LEAGUES and "UCL" not in engine.LEAGUES and "TUR" in engine.LEAGUES
    assert not NATIONAL & fitting.GOALS_XG_SKIP  # el xG de las selecciones sí entra en su modelo de goles
    assert set(fitting.model_codes()) >= NATIONAL


def _match(s, code: str, fid: int = 1) -> m.Match:
    comp = store.ensure_competitions(s)[code]
    fm = FMMatch(fotmob_id=fid, kickoff_utc=datetime(2026, 11, 12, 19, 45, tzinfo=UTC), home_id=8491,
                 home_name="England", away_id=10155, away_name="Croatia", round="5", status="scheduled",
                 home_goals=None, away_goals=None)
    return store.upsert_fotmob_match(s, comp, store.get_season(s, comp, 2026), fm)


def test_national_teams_are_marked_and_never_match_a_club(s):
    club = store.resolve_team(s, "fdco", "Spain:Andorra", "Andorra", "Spain")
    comp = store.ensure_competitions(s)["UNL"]
    fm = FMMatch(fotmob_id=2, kickoff_utc=datetime(2026, 11, 13, 19, 45, tzinfo=UTC), home_id=8495,
                 home_name="Andorra", away_id=8496, away_name="Gibraltar", round="5", status="scheduled",
                 home_goals=None, away_goals=None)
    match = store.upsert_fotmob_match(s, comp, store.get_season(s, comp, 2026), fm)
    assert match.home_team_id != club.id
    assert match.home_team.country == NATIONAL_TEAM and match.home_team.name == "Andorra (Selección)"
    assert not match.neutral_venue
    wc = store.ensure_competitions(s)["WC"]
    final = FMMatch(fotmob_id=3, kickoff_utc=datetime(2026, 7, 19, 19, 0, tzinfo=UTC), home_id=8495,
                    home_name="Andorra", away_id=8496, away_name="Gibraltar", round="final", status="finished",
                    home_goals=1, away_goals=0)
    assert store.upsert_fotmob_match(s, wc, store.get_season(s, wc, 2025), final).neutral_venue


def test_playing_for_the_national_team_is_not_a_transfer(s):
    club = store.fotmob_team(s, 9823, "Bayern München")
    kane = store.resolve_player(s, 194165, "Harry Kane", club, "FW")
    match = _match(s, "UNL")
    det = FMDetails(fotmob_id=1, finished=False, cancelled=False, kickoff_utc=match.kickoff_utc, home_id=8491,
                    away_id=10155, home_goals=None, away_goals=None, home_goals_ht=None, away_goals_ht=None,
                    referee=None, referee_country=None, lineup_type="predicted",
                    players=[FMPlayer(194165, "Harry Kane", 8491, "FW", True, 9e7, 7.9),
                             FMPlayer(555, "Nuevo Sin Club", 8491, "MF", True, None, None)],
                    unavailable=[FMUnavailable(777, "Lesionado", 10155, "injury", "Knee", None, None, None)])
    store.apply_fotmob_details(s, match, det)
    assert kane.current_team_id == club.id
    assert s.scalar(select(m.Transfer.id)) is None
    new = s.scalar(select(m.Player).where(m.Player.name == "Nuevo Sin Club"))
    assert new.current_team_id is None
    assert s.scalar(select(m.Player).where(m.Player.name == "Lesionado")).current_team_id is None
    # La alineación y la baja sí quedan con la selección
    assert s.scalar(select(m.Lineup.team_id).where(m.Lineup.player_id == kane.id)) == match.home_team_id
    assert s.scalar(select(m.Availability.team_id)) == match.away_team_id


def test_player_model_ignores_national_team_matches(s):
    """Las proyecciones de jugador de los clubes no cambian por lo que hagan con su selección."""
    club = store.fotmob_team(s, 9823, "Bayern München")
    rival = store.fotmob_team(s, 9789, "Dortmund")
    kane = store.resolve_player(s, 194165, "Harry Kane", club, "FW")
    bun = store.ensure_competitions(s)["BUN"]
    league = m.Match(competition_id=bun.id, season_id=store.get_season(s, bun, 2026).id, home_team_id=club.id,
                     away_team_id=rival.id, kickoff_utc=datetime(2026, 10, 1, tzinfo=UTC), status="finished",
                     home_goals=2, away_goals=0)
    nations = _match(s, "UNL")
    nations.kickoff_utc, nations.status, nations.home_goals, nations.away_goals = (
        datetime(2026, 10, 6, tzinfo=UTC), "finished", 5, 0)
    s.add(league)
    s.flush()
    s.add(m.PlayerMatchStats(match_id=league.id, player_id=kane.id, team_id=club.id, minutes=90, goals=1, shots=4))
    s.add(m.PlayerMatchStats(match_id=nations.id, player_id=kane.id, team_id=nations.home_team_id, minutes=90,
                             goals=3, shots=9))
    s.flush()
    players, _ = fitting.fit_players(s, before=datetime(2026, 11, 1, tzinfo=UTC))
    assert players[kane.id]["apps"] == 1 and players[kane.id]["team_id"] == club.id
    assert players[kane.id]["per90"]["goals"] == pytest.approx(1.0)


def _bet(**kw) -> analysis.BetEval:
    base = dict(market="ou_goals", selection="over", line=1.5, bookmaker="betano", odds=1.6, model_prob=0.75,
                sharp_prob=None, prob=0.75, fair_odds=1.33, ev=0.2, stake_pct=1.0, confidence=0.9)
    return analysis.BetEval(**{**base, **kw})


def test_a_competition_without_picks_never_passes_the_cut():
    assert picks.qualifies(_bet())
    assert not picks.qualifies(_bet(eligible=False))
    assert queries.verdict_fields(_bet(eligible=False))["verdict"] == "valor pequeño o poca confianza"


@pytest.mark.parametrize(
    ("other", "fotmob"),
    [("España", "Spain"), ("Inglaterra", "England"), ("Países Bajos", "Netherlands"), ("Turquía", "Turkiye"),
     ("Türkiye", "Turkiye"), ("Turkey", "Turkiye"), ("Czech Republic", "Czechia"), ("República Checa", "Czechia"),
     ("Irlanda del Norte", "Northern Ireland"), ("Republic of Ireland", "Ireland"),
     ("Bosnia & Herzegovina", "Bosnia and Herzegovina"), ("Macedonia del Norte", "North Macedonia"),
     ("Islas Feroe", "Faroe Islands"), ("Andorra", "Andorra (Selección)")],
)
def test_national_team_names_in_spanish_and_other_spellings(other, fotmob):
    assert names.similarity(other, fotmob) == 100


def test_ireland_is_not_northern_ireland():
    assert names.similarity("Irlanda", "Northern Ireland") < 70
    assert names.similarity("Ireland", "Northern Ireland") < 90


def test_competition_code_and_oddspapi_tournament():
    for text in ("unl", "Nations League", "UEFA Nations League"):
        assert queries.competition_code(text) == "UNL"
    assert oddspapi.TOURNAMENTS["UNL"] == ("uefa-nations-league", "international")
    assert not {"WCQ", "WC", "EURO"} & set(oddspapi.TOURNAMENTS)


def test_notes_for_national_teams_are_translated():
    assert i18n.text(analysis.NO_PICKS_NOTE) != analysis.NO_PICKS_NOTE
    assert i18n.text(analysis.NO_MARKET_NATIONAL) != analysis.NO_MARKET_NATIONAL
    assert i18n.text(analysis.NO_PLAYERS_NOTE) != analysis.NO_PLAYERS_NOTE
    reason = f"Modelo 60% · cuota sin margen 55% · mezcla 56%: {analysis.NO_MARKET_NATIONAL}"
    assert "Selecciones" not in i18n.text(reason)
