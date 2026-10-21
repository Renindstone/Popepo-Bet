"""Liquidación de combinadas y Bet Builders registrados desde el cupón del panel."""

import pytest

from apuestas.betting.settlement import combo_profit


def test_one_lost_selection_loses_even_with_matches_pending():
    assert combo_profit(10, 6.0, [("win", 2.0), ("loss", 1.5), (None, 2.0)]) == ("loss", -10)


def test_waits_until_every_selection_is_settled():
    assert combo_profit(10, 6.0, [("win", 2.0), (None, 3.0)]) is None


def test_all_won_pays_the_total_odds():
    # la cuota total puede no ser el producto (Bet Builder o cuota mejorada): se paga la total
    assert combo_profit(10, 5.5, [("win", 2.0), ("win", 3.0)]) == ("win", pytest.approx(45.0))


def test_void_selection_divides_its_odds_out():
    result, profit = combo_profit(10, 6.0, [("win", 2.0), ("void", 3.0)])
    assert result == "win" and profit == pytest.approx(10.0)  # 10 × 6 / 3 − 10


def test_half_results_and_all_void():
    _, profit = combo_profit(10, 4.0, [("win", 2.0), ("half_win", 2.0)])
    assert profit == pytest.approx(10 * 4.0 * (3 / 4) - 10)
    assert combo_profit(10, 4.0, [("void", 2.0), ("push", 2.0)]) == ("void", 0.0)
    result, profit = combo_profit(10, 3.0, [("half_loss", 3.0)])
    assert result == "half_loss" and profit == pytest.approx(-5.0)


def test_slip_needs_selections():
    from apuestas.services import queries

    with pytest.raises(ValueError):
        queries.evaluate_slip([])
    with pytest.raises(ValueError):
        queries.register_combo("ana", [{"match": "1", "legs": [{"market": "1x2", "selection": "home"}]}], 2.0, 10)
