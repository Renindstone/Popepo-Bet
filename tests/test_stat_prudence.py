"""Córners y tarjetas sin validar: fuera de la apuesta del día y con menos confianza si la casa discrepa mucho."""

from types import SimpleNamespace

import pytest

from apuestas.services import analysis, picks
from apuestas.services.analysis import BetEval
from apuestas.services.match_model import MatchModel


def _bet(market, odds=2.0, prob=0.6, conf=0.9):
    return BetEval(market, "over", 9.5, "betano", odds, prob, None, prob, 1 / prob, prob * odds - 1, 0.02, conf, None, [])


def test_pick_of_day_only_from_goal_markets():
    assert picks.qualifies(_bet("ou_goals"))
    assert picks.qualifies(_bet("ah"))
    assert not picks.qualifies(_bet("ou_corners"))  # mismos números, pero mercado sin validar
    assert not picks.qualifies(_bet("ah_cards"))
    assert not picks.qualifies(_bet("player_shots"))


def _row(market, selection, line, price, book="betano"):
    return SimpleNamespace(bookmaker=book, market=market, selection=selection, line=line, price=price)


def test_book_fair_prob_needs_every_side_of_the_line():
    rows = [_row("ou_corners", "over", 9.5, 1.82), _row("ou_corners", "under", 9.5, 1.95),
            _row("ah_corners", "home", -1.5, 1.85), _row("ah_corners", "away", 1.5, 1.95),
            _row("ou_cards", "over", 3.5, 1.72)]
    p_over = analysis.book_fair_prob(rows, "betano", "ou_corners", "over", 9.5)
    assert p_over == pytest.approx((1 / 1.82) / (1 / 1.82 + 1 / 1.95))
    p_away = analysis.book_fair_prob(rows, "betano", "ah_corners", "away", 1.5)
    assert p_away == pytest.approx((1 / 1.95) / (1 / 1.85 + 1 / 1.95))
    assert analysis.book_fair_prob(rows, "betano", "ou_cards", "over", 3.5) is None  # falta "menos"
    assert analysis.book_fair_prob(rows, "bet365", "ou_corners", "over", 9.5) is None  # otra casa


def test_disagreement_factor():
    assert analysis.stat_disagreement_factor(0.55, 0.52) == 1.0  # dentro de la tolerancia
    assert analysis.stat_disagreement_factor(0.62, 0.50) == pytest.approx(1 - 0.07 / 0.15)
    assert analysis.stat_disagreement_factor(0.80, 0.30) == analysis.STAT_DISAGREE_MIN_FACTOR


def test_stat_market_confidence_drops_when_the_house_disagrees():
    mm = MatchModel(1, 2, 1.5, 1.1, -0.05, {"corners": (7.0, 5.0)}, {"corners": 0.05})  # ~12 córners esperados
    quality = {"lineup_factor": 1.0, "sample_factor": 1.0, "lineup_status": "confirmed"}
    model_p = mm.outcome("ou_corners", "over", 10.5).effective_prob()
    agree = [_row("ou_corners", "over", 10.5, 1 / model_p), _row("ou_corners", "under", 10.5, 1 / (1 - model_p))]
    disagree = [_row("ou_corners", "over", 10.5, 4.0), _row("ou_corners", "under", 10.5, 1.22)]  # casa: ~23 %
    base = analysis.evaluate_bet(mm, quality, "baja", agree, "ou_corners", "over", 10.5, 2.0, "betano")
    low = analysis.evaluate_bet(mm, quality, "baja", disagree, "ou_corners", "over", 10.5, 4.0, "betano")
    assert low.confidence == pytest.approx(base.confidence * analysis.STAT_DISAGREE_MIN_FACTOR, rel=1e-6)
    assert "discrepan" in low.reasons[0]
    assert low.prob == pytest.approx(base.prob)  # solo baja la confianza; la probabilidad no cambia
