"""Combinadas y Bet Builders: probabilidad conjunta con la matriz de marcadores y total de la combinada."""

import numpy as np
import pytest

from apuestas.services import captures
from apuestas.services.match_model import MatchModel

CITY = MatchModel(1, 2, 2.4, 0.6, -0.05, {"corners": (8.0, 3.0)}, {"corners": 0.05})


def _leg(market, selection, line=None, label=None):
    return {"market": market, "selection": selection, "line": line, "player": None, "text": label,
            "label": label or f"{market} {selection} {line}"}


def test_joint_probability_accounts_for_correlation():
    mat = CITY.matrix / CITY.matrix.sum()
    i, j = np.indices(mat.shape)
    expected = mat[(i > j) & (i + j >= 3)].sum()
    joint = CITY.joint_goal_prob([("1x2", "home", None), ("ou_goals", "over", 2.5)])
    assert joint == pytest.approx(expected)
    independent = CITY.probs_1x2()["home"] * CITY.outcome("ou_goals", "over", 2.5).effective_prob()
    assert joint > independent  # si el City gana, es más probable que haya goles
    # "Roma gana y Roma más de 1.5" = el local gana marcando 2 o más
    assert CITY.joint_goal_prob([("1x2", "home", None), ("ou_goals_home", "over", 1.5)]) == pytest.approx(
        mat[(i > j) & (i >= 2)].sum())


def test_joint_probability_refuses_what_it_cannot_combine():
    assert CITY.joint_goal_prob([("1x2", "home", None), ("ou_corners", "over", 6.5)]) is None
    assert CITY.joint_goal_prob([("ou_goals", "over", 2.0)]) is None  # línea entera: puede devolverse
    assert CITY.joint_goal_prob([("ah", "home", -1.0)]) is None
    assert CITY.joint_goal_prob([("ah", "home", -1.5), ("btts", "no", None)]) is not None


def test_block_probability():
    p, why = captures.block_probability(CITY, [_leg("1x2", "home"), _leg("ou_goals", "over", 2.5)])
    assert why is None and 0 < p < 1
    p, why = captures.block_probability(CITY, [_leg("ou_corners", "over", 6.5)])  # sola: su propia probabilidad
    assert why is None and p == pytest.approx(CITY.outcome("ou_corners", "over", 6.5).effective_prob())
    p, why = captures.block_probability(CITY, [_leg("1x2", "home"), _leg("ou_corners", "over", 6.5, "Más de 6.5 córners")])
    assert p is None and "Más de 6.5 córners" in why
    p, why = captures.block_probability(CITY, [_leg("1x2", "away"), _leg("otro", "", None, "Safonov 3+ atajadas")])
    assert p is None and why == "fuera del modelo: Safonov 3+ atajadas"


def test_combo_summary_multiplies_matches():
    blocks = [{"prob": 0.5, "odds": 2.0}, {"prob": 0.8, "odds": 1.3}]
    s = captures.combo_summary(blocks, 2.75)
    assert s["prob"] == pytest.approx(0.4) and s["ev"] == pytest.approx(0.1) and s["verdict"] == "con valor"
    assert captures.combo_summary(blocks, None)["total_odds"] == 2.6  # sin cuota total: producto de los bloques
    s = captures.combo_summary([{"prob": None, "odds": 6.7}, {"prob": 0.8, "odds": 1.35}], 11.03)
    assert not s["evaluable"] and s["verdict"] == "no evaluable" and s["prob"] is None


def test_final_status_distinguishes_unreadable_from_engine_errors():
    assert captures.final_status("evaluada", {}) == ("lista", None, None)
    assert captures.final_status("procesando", {"error": "La IA tardó más de 300 s"})[0] == "error"
    status, error, reason = captures.final_status("procesando", {"result": "Es una combinada de 3 Bet Builders…"})
    assert (status, error) == ("no_evaluable", None) and reason.startswith("Es una combinada")
    assert captures.final_status("no_evaluable", {"result": "x"}) == ("no_evaluable", None, None)
