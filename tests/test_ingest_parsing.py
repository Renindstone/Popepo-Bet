from datetime import UTC, date, datetime

import pytest

from apuestas.core import names
from apuestas.core.competitions import fd_season_code, fotmob_season, season_label, season_start_year
from apuestas.ingest import football_data, fotmob
from apuestas.models import ratings

CSV = (
    "﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HxG,AxG,HS,AS,HST,AST,HF,AF,HC,AC,"
    "HY,AY,HR,AR,B365H,B365D,B365A,BFEH,BFED,BFEA,B365>2.5,B365<2.5,AHh,B365AHH,B365AHA,B365CH,B365CD,B365CA\n"
    "E0,21/08/2026,20:00,Arsenal,Coventry,3,0,H,2,0,H,T Bramall,1.88,0.2,20,4,6,1,10,13,8,2,1,1,0,0,"
    "1.2,7,13,1.23,7.4,18,1.57,2.38,-2,2.03,1.78,1.18,7.5,13\n"
)


def test_football_data_parse():
    rows = football_data.parse_csv(CSV)
    assert len(rows) == 1
    r = rows[0]
    assert r.div == "E0"
    assert r.kickoff_utc == datetime(2026, 8, 21, 19, 0, tzinfo=UTC)  # 20:00 hora UK (BST) = 19:00 UTC
    assert r.stats["home"]["shots"] == 20 and r.stats["away"]["corners"] == 2
    assert r.stats["home"]["xg"] == pytest.approx(1.88)
    odds = {(o.bookmaker, o.market, o.selection, o.line, o.kind): o.price for o in r.odds}
    assert odds[("bet365", "1x2", "home", None, "opening")] == 1.2
    assert odds[("bet365", "1x2", "home", None, "closing")] == 1.18
    assert odds[("bet365", "ah", "home", -2.0, "opening")] == 2.03
    assert odds[("bet365", "ah", "away", 2.0, "opening")] == 1.78
    assert odds[("betfair_ex", "1x2", "away", None, "opening")] == 18


EXTRA_CSV = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,"
    "BFECH,BFECD,BFECA,B365CH,B365CD,B365CA\n"
    "Norway,Eliteserien,2025,26/10/2025,17:00,Bodo/Glimt,Ham-Kam,4,0,H,1.14,8.5,17,1.18,9,19,1.15,8,15,"
    "1.17,9.6,24,1.14,8,15\n"
    "Austria,Bundesliga,2026/2027,11/10/2026,16:00,LASK,SK Rapid,0,2,A,,,,1.91,4,3.7,1.88,3.8,3.37,"
    "1.99,4.1,3.75,1.86,3.75,3.7\n"
)


def test_football_data_extra_league_parse():
    nor, aut = football_data.parse_csv(EXTRA_CSV)
    assert (nor.season, aut.season) == (2025, 2026)  # año natural en Noruega, inicio de temporada en Austria
    assert nor.away == "HamKam"  # misma grafía en todas las temporadas
    assert (nor.home_goals, nor.away_goals) == (4, 0)
    assert aut.kickoff_utc == datetime(2026, 10, 11, 15, 0, tzinfo=UTC)
    odds = {(o.bookmaker, o.selection, o.kind): o.price for o in nor.odds if o.market == "1x2"}
    assert odds[("pinnacle", "home", "closing")] == 1.14
    assert odds[("bet365", "away", "closing")] == 15
    assert odds[("avg", "draw", "closing")] == 8
    assert all(o.kind == "closing" and o.market == "1x2" for o in nor.odds + aut.odds)
    assert not any(o.bookmaker == "pinnacle" for o in aut.odds)  # sin Pinnacle desde 2025-26


def test_fotmob_details_parse():
    data = {
        "general": {"matchId": "99", "matchTimeUTCDate": "2026-10-18T15:30:00.000Z"},
        "header": {"teams": [{"id": 10, "score": 2}, {"id": 20, "score": 1}],
                   "status": {"utcTime": "2026-10-18T15:30:00.000Z", "finished": True}},
        "content": {
            "matchFacts": {
                "infoBox": {"Referee": {"text": "Michael Oliver", "country": "England"}},
                "events": {"events": [
                    {"type": "Card", "playerId": 5, "card": "Yellow"},
                    {"type": "Half", "halfStrShort": "HT", "homeScore": 1, "awayScore": 0},
                ]},
            },
            "lineup": {"lineupType": "standard", "homeTeam": {
                "id": 10, "formation": "4-3-3", "coach": {"name": "Entrenador A"}, "starters": [
                {"id": 5, "name": "Jugador A", "positionId": 32, "usualPlayingPositionId": 1, "marketValue": 30000000,
                 "shirtNumber": "27", "verticalLayout": {"x": 0.125, "y": 0.292},
                 "performance": {"seasonRating": 7.1}}], "subs": [
                {"id": 7, "name": "Suplente", "usualPlayingPositionId": 3, "shirtNumber": "19"}], "unavailable": [
                {"id": 6, "name": "Lesionado", "unavailability": {"type": "injury", "expectedReturn": "Late October"}}]},
                       "awayTeam": {"id": 20, "starters": [], "subs": []}},
            "stats": {"Periods": {"All": {"stats": [{"stats": [
                {"key": "total_shots", "stats": [14, 9], "type": "text"},
                {"key": "corners", "stats": [8, 6], "type": "text"},
                {"key": "expected_goals", "stats": ["0.90", "1.14"], "type": "text"},
            ]}]}}},
            "playerStats": {"5": {"teamId": 10, "name": "Jugador A", "stats": [{"stats": {
                "Minutes played": {"key": "minutes_played", "stat": {"value": 90}},
                "Total shots": {"key": "total_shots", "stat": {"value": 3}}}}]}},
        },
    }
    det = fotmob.parse_match_details(data)
    assert det.finished and det.home_goals == 2 and det.home_goals_ht == 1
    assert det.referee == "Michael Oliver"
    assert det.lineup_type == "confirmed"
    assert det.players[0].position == "DF" and det.players[0].market_value == 30000000
    # lo necesario para dibujar la alineación como en FotMob
    assert (det.players[0].shirt, det.players[0].x, det.players[0].y) == (27, 0.125, 0.292)
    assert det.players[1].shirt == 19 and det.players[1].x is None  # suplente: sin posición en el campo
    assert det.team_info[10] == {"formation": "4-3-3", "coach": "Entrenador A"}
    assert det.unavailable[0].kind == "injury"
    assert det.team_stats[10]["shots"] == 14 and det.team_stats[20]["xg"] == pytest.approx(1.14)
    assert det.player_stats[5]["shots"] == 3 and det.player_stats[5]["yellow_cards"] == 1


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Man City", "Manchester City", True),
        ("Nott'm Forest", "Nottingham Forest", True),
        ("Ath Bilbao", "Athletic Club", True),
        ("Alaves", "Deportivo Alavés", True),
        ("Bayern Munich", "Bayern München", True),
        ("M'gladbach", "Borussia Mönchengladbach", True),
        ("Dundee", "Dundee United", False),
        ("Paris FC", "Paris Saint-Germain", False),
        ("Manchester City", "Manchester United", False),
        ("Real Madrid", "Real Sociedad", False),
        # Ligas extra de football-data frente a FotMob
        ("Bodo/Glimt", "Bodø/Glimt", True),
        ("Nordsjaelland", "Nordsjælland", True),
        ("Jagiellonia", "Jagiellonia Białystok", True),
        ("SK Rapid", "Rapid Wien", True),
        ("FC Copenhagen", "FC København", True),
        ("Lausanne", "Lausanne Ouchy", False),
        ("U Craiova 1948", "Universitatea Craiova", False),
    ],
)
def test_team_name_matching(a, b, same):
    assert (names.similarity(a, b) >= 90) is same


def test_person_similarity():
    assert names.person_similarity("T Bramall", "Thomas Bramall") >= 90
    assert names.person_similarity("J Smith", "Anthony Taylor") < 80


def test_season_helpers():
    assert season_start_year(date(2026, 10, 19)) == 2026
    assert season_start_year(date(2027, 3, 1)) == 2026
    assert fd_season_code(2026) == "2627"
    assert fotmob_season(2026) == "2026/2027"
    assert season_label(2026) == "2026-27"
    assert season_label(2026, calendar_year=True) == "2026"


def test_ratings_recover_strengths():
    import random

    random.seed(1)
    teams = list(range(6))
    true_att = {0: 0.5, 1: 0.2, 2: 0.0, 3: 0.0, 4: -0.2, 5: -0.5}
    obs = []
    for _k in range(400):
        h, a = random.sample(teams, 2)
        import math

        lh = math.exp(0.2 + 0.25 + true_att[h])
        la = math.exp(0.2 + true_att[a])
        obs.append(ratings.MatchObs(h, a, date(2026, 1, 1), lh, la))  # medias exactas (cuasi-Poisson)
    model = ratings.fit(obs, date(2026, 1, 2), half_life_days=10_000, l2=0.01)
    assert model.attack[0] > model.attack[2] > model.attack[5]
    assert model.home_adv == pytest.approx(0.25, abs=0.02)
