"""Goles de cada equipo y «Ambos marcan»: medición en el backtest y referencia de Pinnacle en el análisis."""

from types import SimpleNamespace

import numpy as np
import pytest

from apuestas.backtest import engine
from apuestas.betting import odds as oddsmath
from apuestas.models import distributions as dist
from apuestas.services import analysis
from apuestas.services.match_model import MatchModel


def test_team_goal_events_follow_the_score_matrix():
    mat = dist.dixon_coles_matrix(0.7, 2.1, -0.05)
    ev = engine._team_goal_events(mat, 0, 3)  # Parma 0-3 Roma
    probs = [p for p, _ in ev]
    assert len(ev) == 7 and all(0 < p < 1 for p in probs)
    assert probs[0] == pytest.approx(mat[0, :].sum())  # Parma menos de 0.5
    assert probs[5] == pytest.approx(mat[:, :3].sum())  # Roma menos de 2.5
    assert probs[6] == pytest.approx(mat[1:, 1:].sum())  # ambos marcan
    assert [h for _, h in ev] == [True, True, True, False, False, False, False]


def _row(market, selection, line, price, book="pinnacle"):
    return SimpleNamespace(bookmaker=book, market=market, selection=selection, line=line, price=price)


# Parma-Roma, 21-11-2026: Pinnacle tenía la línea de goles de Roma y el análisis no la usaba
PINNACLE = [
    _row("ou_goals_away", "over", 2.5, 1.84), _row("ou_goals_away", "under", 2.5, 2.00),
    _row("btts", "yes", None, 1.943), _row("btts", "no", None, 1.909),
    _row("eh", "home", 2.0, 2.29), _row("eh", "draw", 2.0, 4.28), _row("eh", "away", 2.0, 2.67),
    _row("1x2", "home", None, 12.09), _row("1x2", "draw", None, 6.91), _row("1x2", "away", None, 1.239),
]


def test_sharp_prob_reads_pinnacle_team_goals_btts_and_european_handicap():
    under = analysis._sharp_prob(PINNACLE, "ou_goals_away", "under", 2.5)
    assert under == pytest.approx(oddsmath.devig([1.84, 2.00])[1])
    assert analysis._sharp_prob(PINNACLE, "ou_goals_home", "under", 2.5) is None  # sin esa línea
    assert analysis._sharp_prob(PINNACLE, "btts", "no", None) == pytest.approx(oddsmath.devig([1.943, 1.909])[1])
    assert analysis._sharp_prob(PINNACLE, "eh", "draw", 2.0) == pytest.approx(oddsmath.devig([2.29, 4.28, 2.67])[1])


def test_sharp_prob_derives_double_chance_and_draw_no_bet_from_the_1x2():
    h, d, a = oddsmath.devig([12.09, 6.91, 1.239])
    assert analysis._sharp_prob(PINNACLE, "dc", "x2", None) == pytest.approx(d + a)
    assert analysis._sharp_prob(PINNACLE, "dc", "12", None) == pytest.approx(h + a)
    assert analysis._sharp_prob(PINNACLE, "dnb", "home", None) == pytest.approx(h / (h + a))


def test_roma_under_blends_with_pinnacle_and_loses_its_value():
    mm = MatchModel(101, 89, 0.72, 2.13, -0.05, {}, {})
    q = {"lineup_factor": 1.0, "sample_factor": 1.0, "lineup_status": "confirmed"}
    bet = analysis.evaluate_bet(mm, q, "baja", PINNACLE, "ou_goals_away", "under", 2.5, 1.91, "betano")
    assert bet.model_prob == pytest.approx(0.64, abs=0.01)
    assert bet.sharp_prob == pytest.approx(0.479, abs=0.001)
    assert bet.prob == pytest.approx(analysis.W_MODEL * bet.model_prob + (1 - analysis.W_MODEL) * bet.sharp_prob)
    assert bet.ev < 0.01  # antes, +22.7 %: la apuesta del día salía de un error del modelo
    assert "mercado afilado" in bet.reasons[-1]


def test_team_goal_events_of_an_implied_matrix_are_usable():
    lam, _ = engine.implied_goals(np.array([[0.08, 0.15, 0.77]]), np.array([0.66]))
    mat = dist.dixon_coles_matrix(lam[0, 0], lam[0, 1], engine.MARKET_RHO)
    assert lam[0, 1] > 2.0 and all(0 < p < 1 for p, _ in engine._team_goal_events(mat, 1, 1))
