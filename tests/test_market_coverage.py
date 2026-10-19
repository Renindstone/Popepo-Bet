"""Equipos sin cuotas de su liga (p.ej. Bodø/Glimt): menos confianza y probabilidad anclada a la cuota."""

from datetime import date, timedelta

import pytest

from apuestas.models import ratings
from apuestas.models.ratings import MatchObs, RatingModel
from apuestas.services import analysis
from apuestas.services.match_model import MatchModel

TODAY = date(2026, 10, 19)


def test_fit_counts_recent_market_observations_per_team():
    obs = []
    for i in range(40):
        day = TODAY - timedelta(days=7 * i)
        obs.append(MatchObs(1, 2, day, 2, 1))
        obs.append(MatchObs(1, 2, day, 1.8, 1.1, market=True, weight=128))  # 1 y 2: liga con cuotas
        obs.append(MatchObs(3, 1, day, 0, 2))  # 3: solo partidos europeos, sin cuotas
    obs.append(MatchObs(2, 3, TODAY - timedelta(days=400), 1.5, 1.0, market=True))  # demasiado antigua
    model = ratings.fit(obs, TODAY, market_half_life_days=14)
    assert model.market_matches[1] == model.market_matches[2] > analysis.MARKET_COVERED
    assert model.market_matches[3] == 0
    again = RatingModel.from_dict(model.to_dict())
    assert again.market_matches == model.market_matches
    # Paquetes antiguos sin el dato: no se penaliza a nadie
    old = model.to_dict()
    del old["market_matches"]
    assert RatingModel.from_dict(old).market_matches == {}


def test_coverage_weight():
    assert analysis.market_coverage_weight(None) == 1.0
    assert analysis.market_coverage_weight(0) == analysis.W_MODEL
    assert analysis.market_coverage_weight(analysis.MARKET_COVERED) == 1.0
    assert analysis.W_MODEL < analysis.market_coverage_weight(5) < 1.0


def _quality(weight: float, factor: float) -> dict:
    return {"lineup_factor": 1.0, "sample_factor": 1.0, "lineup_status": "confirmed",
            "market_factor": factor, "market_weight": weight, "no_market_note": "Bodø casi sin cuotas"}


def test_goal_markets_blend_with_the_price_and_lose_confidence():
    mm = MatchModel(1, 2, 1.35, 1.25, -0.05, {"corners": (5.0, 4.5)}, {"corners": 0.05})  # el modelo ve parejo
    covered = analysis.evaluate_bet(mm, _quality(1.0, 1.0), "baja", [], "1x2", "away", None, 9.0, "betano")
    thin = analysis.evaluate_bet(mm, _quality(analysis.W_MODEL, 0.6), "baja", [], "1x2", "away", None, 9.0, "betano")
    book_p = 1 / (9.0 * (1 + analysis.BOOK_MARGIN))
    assert thin.prob == pytest.approx(analysis.W_MODEL * covered.model_prob + (1 - analysis.W_MODEL) * book_p)
    assert thin.ev < covered.ev / 3
    assert thin.confidence == pytest.approx(covered.confidence * 0.6)
    assert "Bodø" in thin.reasons[0]
    # Las estadísticas no dependen de la fuerza de goles: misma probabilidad, solo menos confianza
    c1 = analysis.evaluate_bet(mm, _quality(1.0, 1.0), "baja", [], "ou_corners", "over", 9.5, 1.9, "betano")
    c2 = analysis.evaluate_bet(mm, _quality(analysis.W_MODEL, 0.6), "baja", [], "ou_corners", "over", 9.5, 1.9, "betano")
    assert c2.prob == pytest.approx(c1.prob) and c2.confidence < c1.confidence
