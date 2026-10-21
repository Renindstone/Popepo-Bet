"""Goles y asistencias de jugadores: probabilidad sola, junto con el marcador (Bet Builder) y liquidación."""

from types import SimpleNamespace

import numpy as np
import pytest

from apuestas.betting.settlement import settle
from apuestas.services import captures
from apuestas.services.match_model import MatchModel, PlayerProjection

KANE, MUSIALA, SAKA = 9, 42, 7


def model() -> MatchModel:
    mm = MatchModel(1, 2, 2.1, 1.0, -0.05, {"corners": (6.5, 4.0)}, {"corners": 0.05})
    mm.players = {
        KANE: PlayerProjection(KANE, "Harry Kane", 1, "FW", 85, 1.0,
                               {"goals": 0.75, "assists": 0.22, "shots": 4.0, "shots_on_target": 1.8}),
        MUSIALA: PlayerProjection(MUSIALA, "Jamal Musiala", 1, "MF", 80, 1.0,
                                  {"goals": 0.35, "assists": 0.30, "shots": 2.5, "shots_on_target": 1.0}),
        SAKA: PlayerProjection(SAKA, "Bukayo Saka", 2, "FW", 85, 1.0,
                               {"goals": 0.30, "assists": 0.25, "shots": 2.6, "shots_on_target": 1.0}),
    }
    return mm


def alone(mm, market, pid, sel="yes", line=None):
    return mm.outcome(market, sel, line, pid).effective_prob()


def test_single_player_markets():
    mm = model()
    goal, assist, ga = (alone(mm, k, KANE) for k in ("player_goal", "player_assist", "player_goal_assist"))
    assert goal == pytest.approx(1 - np.exp(-0.75))
    assert ga == pytest.approx(1 - np.exp(-0.97))  # gol o asistencia: goles + asistencias esperadas
    assert ga > goal > assist
    two = alone(mm, "player_goal", KANE, "over", 1.5)
    assert two == pytest.approx(1 - np.exp(-0.75) * (1 + 0.75))


def test_joint_with_one_player_matches_the_single_market():
    """Repartir los goles del equipo entre sus jugadores da la misma probabilidad que el mercado solo."""
    mm = model()
    for market in ("player_goal", "player_assist", "player_goal_assist"):
        assert mm.joint_prob([(market, "yes", None, KANE)]) == pytest.approx(alone(mm, market, KANE), abs=0.01)
    assert mm.joint_prob([("player_goal", "over", 1.5, KANE)]) == pytest.approx(
        alone(mm, "player_goal", KANE, "over", 1.5), abs=0.01)


def test_player_and_result_are_correlated():
    mm = model()
    win = mm.probs_1x2()["home"]
    joint = mm.joint_prob([("1x2", "home", None, None), ("player_goal_assist", "yes", None, KANE)])
    assert joint > win * alone(mm, "player_goal_assist", KANE)  # si Kane participa, el Bayern gana más
    assert joint < win
    # el rival marca: Saka y "gana el Bayern" van en contra
    against = mm.joint_prob([("1x2", "home", None, None), ("player_goal", "yes", None, SAKA)])
    assert against < win * alone(mm, "player_goal", SAKA)


def test_yes_and_no_add_up_and_two_players_fit_inside_each():
    mm = model()
    win = mm.probs_1x2()["home"]
    yes = mm.joint_prob([("1x2", "home", None, None), ("player_goal", "yes", None, KANE)])
    no = mm.joint_prob([("1x2", "home", None, None), ("player_goal", "no", None, KANE)])
    assert yes + no == pytest.approx(win, abs=1e-9)
    both = mm.joint_prob([("player_goal", "yes", None, KANE), ("player_goal", "yes", None, MUSIALA)])
    assert 0 < both < min(alone(mm, "player_goal", KANE), alone(mm, "player_goal", MUSIALA))
    # Kane marca y Musiala asiste no puede ser más probable que cada una por separado
    combo = mm.joint_prob([("player_goal", "yes", None, KANE), ("player_assist", "yes", None, MUSIALA)])
    assert combo < alone(mm, "player_assist", MUSIALA)


def test_lines_that_cannot_be_combined():
    mm = model()
    assert mm.joint_prob([("player_goal", "over", 1.5, KANE), ("player_goal", "yes", None, MUSIALA)]) is None
    assert mm.joint_prob([("player_goal", "yes", None, 999)]) is None  # jugador sin proyección
    assert not mm.combinable("ou_corners", "over", 9.5)


def leg(market, selection, line=None, player_id=None, label=None):
    return {"market": market, "selection": selection, "line": line, "player": None, "text": label,
            "player_id": player_id, "label": label or f"{market} {selection}"}


def test_block_with_players_and_approximate_corners():
    mm = model()
    p, why, approx = captures.block_probability(mm, [leg("1x2", "home"), leg("player_goal_assist", "yes", None, KANE)])
    assert why is None and approx == [] and p > 0
    p2, why, approx = captures.block_probability(mm, [leg("1x2", "home"), leg("player_goal_assist", "yes", None, KANE),
                                                      leg("ou_corners", "over", 8.5, label="Más de 8.5 córners")])
    assert why is None and approx == ["Más de 8.5 córners"]
    assert p2 == pytest.approx(p * alone(mm, "ou_corners", None, "over", 8.5))
    p, why, _ = captures.block_probability(mm, [leg("1x2", "home"), leg("player_goal", "yes", None, 999, "Nadie")])
    assert p is None and "Nadie" in why
    # una línea entera de goles depende del marcador: no se aproxima
    p, why, _ = captures.block_probability(mm, [leg("1x2", "home"), leg("ou_goals", "over", 2.0, label="Más de 2")])
    assert p is None and "Más de 2" in why


class FakeSession:
    def __init__(self, row):
        self.row = row

    def scalar(self, _query):
        return self.row


def finished():
    return SimpleNamespace(status="finished", home_goals=2, away_goals=1, details_fetched_at=True, id=1)


@pytest.mark.parametrize(("goals", "assists", "market", "sel", "line", "expected"), [
    (0, 1, "player_goal_assist", "yes", None, "win"),
    (1, 0, "player_goal_assist", "yes", None, "win"),
    (0, 0, "player_goal_assist", "yes", None, "loss"),
    (0, 1, "player_assist", "yes", None, "win"),
    (1, 0, "player_assist", "no", None, "win"),
    (2, 0, "player_goal", "over", 1.5, "win"),
    (1, 3, "player_goal", "over", 1.5, "loss"),
])
def test_settle_goal_and_assist_markets(goals, assists, market, sel, line, expected):
    row = SimpleNamespace(goals=goals, assists=assists, yellow_cards=0, red_cards=0)
    assert settle(FakeSession(row), finished(), market, sel, line, player_id=KANE) == expected
