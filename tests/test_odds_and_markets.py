from types import SimpleNamespace

import pytest

from apuestas.betting import odds as om
from apuestas.betting.settlement import profit, settle
from apuestas.models import distributions as dist
from apuestas.services.match_model import MatchModel


def test_devig_sums_to_one():
    for method in (om.devig_multiplicative, om.devig_power):
        p = method([1.9, 3.6, 4.2])
        assert sum(p) == pytest.approx(1.0, abs=1e-9)
    assert om.overround([1.9, 1.9]) == pytest.approx(0.0526, abs=1e-3)


def test_power_devig_shrinks_longshots_more():
    mult = om.devig_multiplicative([1.25, 6.0, 13.0])
    power = om.devig_power([1.25, 6.0, 13.0])
    assert power[2] < mult[2]
    assert power[0] > mult[0]


def test_ev_kelly_and_stake_cap():
    assert om.expected_value(0.55, 2.0) == pytest.approx(0.10)
    assert om.kelly(0.55, 2.0) == pytest.approx(0.10)
    assert om.stake_pct(0.55, 2.0, fraction=0.25, cap=0.03) == pytest.approx(0.025)
    assert om.stake_pct(0.9, 2.0, fraction=0.25, cap=0.03) == pytest.approx(0.03)
    assert om.stake_pct(0.4, 2.0, fraction=0.25, cap=0.03) == 0.0
    assert om.clv(2.10, 2.00) == pytest.approx(0.05)


@pytest.mark.parametrize(
    ("diff", "line", "expected"),
    [
        (0, -0.25, "half_loss"),  # empate con -0.25
        (1, -0.25, "win"),
        (0, 0.25, "half_win"),
        (1, -1.0, "push"),
        (1, -1.25, "half_loss"),
        (2, -1.75, "half_win"),
        (3, -1.75, "win"),
        (1, -1.75, "loss"),
        (1, -1.5, "loss"),
    ],
)
def test_asian_lines(diff, line, expected):
    o = dist.line_outcome({diff: 1.0}, line)
    assert getattr(o, expected) == pytest.approx(1.0)


def test_over_under_quarter_lines():
    assert dist.over({2: 1.0}, 2.25).half_loss == pytest.approx(1.0)
    assert dist.over({3: 1.0}, 2.25).win == pytest.approx(1.0)
    assert dist.under({2: 1.0}, 2.25).half_win == pytest.approx(1.0)
    assert dist.over({3: 1.0}, 3.0).push == pytest.approx(1.0)


def test_fair_odds_with_push():
    o = dist.Outcome(win=0.45, push=0.25, loss=0.30)
    assert o.ev(o.fair_odds()) == pytest.approx(0.0, abs=1e-9)


def test_dixon_coles_matrix_is_distribution():
    mat = dist.dixon_coles_matrix(1.6, 1.1, -0.05)
    assert mat.sum() == pytest.approx(1.0)
    assert (mat >= 0).all()


def _mm() -> MatchModel:
    return MatchModel(1, 2, 1.7, 1.0, -0.05, {"corners": (6.0, 4.0), "cards": (2.0, 2.2)}, {"corners": 0.05, "cards": 0.02})


def test_match_model_consistency():
    mm = _mm()
    p = mm.probs_1x2()
    assert sum(p.values()) == pytest.approx(1.0)
    assert mm.outcome("1x2", "home").win == pytest.approx(p["home"])
    # DNB == hándicap asiático 0
    assert mm.outcome("dnb", "home").effective_prob() == pytest.approx(mm.outcome("ah", "home", 0.0).effective_prob())
    # over/under complementarios en línea .5
    o, u = mm.outcome("ou_goals", "over", 2.5), mm.outcome("ou_goals", "under", 2.5)
    assert o.win + u.win == pytest.approx(1.0)
    # estadísticas: el local con más córners esperados gana la "carrera" de córners
    assert mm.outcome("1x2_corners", "home").win > mm.outcome("1x2_corners", "away").win
    assert mm.outcome("ou_corners_home", "over", 5.5).win > mm.outcome("ou_corners_away", "over", 5.5).win
    assert 0 < mm.outcome("ou_cards", "over", 3.5).win < 1


def _finished(hg: int, ag: int):
    return SimpleNamespace(status="finished", home_goals=hg, away_goals=ag, id=1, home_team_id=1, away_team_id=2,
                           details_fetched_at=None)


@pytest.mark.parametrize(
    ("score", "market", "sel", "line", "expected"),
    [
        ((2, 1), "1x2", "home", None, "win"),
        ((1, 1), "1x2", "home", None, "loss"),
        ((1, 1), "dnb", "home", None, "push"),
        ((1, 1), "dc", "1x", None, "win"),
        ((2, 1), "ah", "home", -0.75, "half_win"),
        ((2, 1), "ah", "away", 0.75, "half_loss"),
        ((2, 1), "ou_goals", "over", 2.5, "win"),
        ((1, 1), "ou_goals", "over", 2.25, "half_loss"),
        ((1, 0), "btts", "yes", None, "loss"),
        ((2, 0), "eh", "home", -1, "win"),
        ((1, 0), "eh", "draw", -1, "win"),
        # Tottenham 3-1 Coventry: "Coventry +2" normal (3 vías, línea del local -2) pierde; asiático +2 se devuelve
        ((3, 1), "eh", "away", -2, "loss"),
        ((3, 2), "eh", "away", -2, "win"),
        ((3, 1), "ah", "away", 2, "push"),
        ((2, 1), "ou_goals_home", "over", 1.5, "win"),
    ],
)
def test_settlement_goal_markets(score, market, sel, line, expected):
    assert settle(None, _finished(*score), market, sel, line) == expected


def test_profit():
    assert profit("win", 10, 2.5) == 15.0
    assert profit("half_win", 10, 2.0) == 5.0
    assert profit("half_loss", 10, 2.0) == -5.0
    assert profit("push", 10, 2.0) == 0.0


def test_bet_eval_is_json_serializable():
    """Regresión: los tipos numpy (numpy.bool) rompían GET /picks en la API."""
    import json

    from apuestas.services.analysis import evaluate_bet
    from apuestas.services.picks import qualifies

    quality = {"lineup_factor": 1.0, "sample_factor": 1.0, "lineup_status": "confirmed"}
    b = evaluate_bet(_mm(), quality, "baja", [], "ou_corners", "over", 9.5, 1.9, "betano")
    assert type(qualifies(b)) is bool
    assert all(type(getattr(b, f)) is float for f in ("odds", "model_prob", "prob", "ev", "confidence"))
    json.dumps({**b.to_dict(), "qualifies": qualifies(b)})


def test_three_way_handicap_label_shows_the_teams_own_line():
    from apuestas.services.analysis import BetEval

    def label(sel):
        return BetEval("eh", sel, -2.0, "betano", 1.57, .5, None, .5, 2, 0, 0, .5, None, []).label("Tottenham", "Coventry")

    assert label("away") == "Hándicap (3 vías): Coventry +2"
    assert label("home") == "Hándicap (3 vías): Tottenham -2"
    assert label("draw") == "Hándicap (3 vías): Empate (Tottenham -2)"


def test_stat_handicap_labels_have_names():
    """Las cuotas de Betano de hándicap de córners y tarjetas se muestran con nombre, no con el código."""
    from apuestas.services.analysis import bet_label

    assert bet_label("ah_corners", "home", -1.5, "Galatasaray", "Bodø/Glimt") == "Hándicap de córners: Galatasaray -1.5"
    assert bet_label("ah_cards", "away", 0.5, "Galatasaray", "Bodø/Glimt") == "Hándicap de tarjetas: Bodø/Glimt +0.5"


def test_valor_de_lineas_de_cuarto_cuenta_las_mitades():
    """En una línea de cuarto, el valor con la probabilidad equivalente tiene que dar lo mismo que el valor exacto."""
    from apuestas.models import distributions as dist

    out = dist.line_outcome({-1: 0.2, 0: 0.25, 1: 0.3, 2: 0.25}, -0.25)  # hándicap asiático −0.25
    assert out.half_loss > 0
    odds = 1.95
    approx = (out.effective_prob() * odds - 1) * out.decided()
    assert approx == pytest.approx(out.ev(odds), abs=1e-9)
