"""Reparto de remates y córners movido hacia la diferencia de fuerza que ve la casa en el 1X2 (Betis-Feyenoord:
el modelo de goles veía a los dos casi iguales y Pinnacle, al Betis claro favorito)."""

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pytest

from apuestas.backtest import engine
from apuestas.models import fitting, market, ratings
from apuestas.models.fitting import MatchRow
from apuestas.models.ratings import MatchObs, RatingModel

TODAY = date(2026, 10, 22)


def _league() -> tuple[list[MatchObs], dict[int, float]]:
    """Diez equipos cuyos córners dependen de su fuerza: 0,6 × fuerza en ataque y en defensa."""
    rng = np.random.default_rng(7)
    strength = {t: 0.2 * (t - 5.5) for t in range(1, 11)}
    obs = []
    teams = list(strength)
    for w in range(40):
        rng.shuffle(teams)
        for h, a in zip(teams[::2], teams[1::2], strict=True):
            d = 0.6 * (strength[h] - strength[a])
            obs.append(MatchObs(int(h), int(a), TODAY - timedelta(days=7 * w + 1),
                                float(rng.poisson(np.exp(np.log(4.8) + 0.1 + d))), float(rng.poisson(np.exp(np.log(4.8) - d)))))
    return obs, strength


def test_fit_keeps_the_strength_coefficients():
    obs, strength = _league()
    cm = ratings.fit(obs, TODAY, prior_matches=20.0, strength=strength)
    assert cm.strength_coef is not None
    assert sum(cm.strength_coef) == pytest.approx(1.2, abs=0.25)
    assert ratings.fit(obs, TODAY, prior_matches=20.0).strength_coef is None
    # Se guarda en el paquete de modelos; los paquetes antiguos no lo traen
    assert RatingModel.from_dict(cm.to_dict()).strength_coef == pytest.approx(cm.strength_coef)
    old = cm.to_dict()
    del old["strength_coef"]
    assert RatingModel.from_dict(old).strength_coef is None


def test_strength_delta_and_shift():
    assert fitting.strength_delta((2.0, 1.0), (1.5, 1.5)) == pytest.approx(0.5 * np.log(2.0))
    assert fitting.strength_delta((1.5, 1.2), (1.5, 1.2)) == pytest.approx(0.0)
    cm = RatingModel(teams=[1, 2], mu=1.5, home_adv=0.2, attack={}, defence={}, strength_coef=(0.29, 0.30))
    # Betis-Feyenoord: el modelo 4,6-4,7 córners; Pinnacle ve al Betis 0,18 más fuerte que el modelo de goles
    mh, ma = fitting.strength_shift(cm, 4.6, 4.7, 0.18)
    assert mh / ma == pytest.approx(4.6 / 4.7 * np.exp(2 * fitting.COUNT_MARKET_SHIFT * 0.59 * 0.18))
    assert mh + ma == pytest.approx(9.3)  # el total no cambia
    assert mh == pytest.approx(5.0, abs=0.1)
    assert fitting.strength_shift(cm, 4.6, 4.7, 0.18, weight=0.0) == pytest.approx((4.6, 4.7))
    assert fitting.strength_shift(cm, 4.6, 4.7, 0.0) == (4.6, 4.7)
    plain = RatingModel(teams=[1, 2], mu=1.5, home_adv=0.2, attack={}, defence={})
    assert fitting.strength_shift(plain, 4.6, 4.7, 0.18) == (4.6, 4.7)  # sin fuerza (tarjetas, paquetes antiguos)


def _prices(book: str, lh: float, la: float, with_ou: bool = True) -> dict:
    ph, pd, pa, po = market.market_probs(np.array([lh]), np.array([la]))[0]
    out = {(book, "1x2", "home"): 1 / ph, (book, "1x2", "draw"): 1 / pd, (book, "1x2", "away"): 1 / pa}
    if with_ou:
        out |= {(book, "ou_goals", "over"): 1 / po, (book, "ou_goals", "under"): 1 / (1 - po)}
    return out


def test_prematch_market_goals_prefers_sharp_books():
    book, lh, la = fitting.prematch_market_goals(_prices("betano", 1.9, 1.0) | _prices("pinnacle", 1.8, 1.1))
    assert book == "pinnacle" and (lh, la) == pytest.approx((1.8, 1.1), rel=0.02)
    book, lh, la = fitting.prematch_market_goals(_prices("betano", 1.9, 1.0, with_ou=False))
    assert book == "betano" and lh / la == pytest.approx(1.9, rel=0.1)  # sin más/menos, solo el 1X2
    assert fitting.prematch_market_goals(_prices("william_hill", 1.9, 1.0)) is None
    assert fitting.prematch_market_goals({}) is None


def test_backtest_moves_dominance_stats_only():
    obs, strength = _league()
    corners = ratings.fit(obs, TODAY, prior_matches=20.0, strength=strength)
    cards = ratings.fit(obs, TODAY, prior_matches=10.0)
    row = MatchRow(1, "EPL", TODAY, 3, 8, False, 1, 1, None, {"corners": 6, "cards": 2}, {"corners": 3, "cards": 2})
    plain: dict = defaultdict(list)
    moved: dict = defaultdict(list)
    engine._evaluate_counts(row, {"corners": corners, "cards": cards}, plain)
    engine._evaluate_counts(row, {"corners": corners, "cards": cards}, moved, delta=0.3)
    assert moved["cards por equipo"] == plain["cards por equipo"]
    # La casa ve al local más fuerte y el local sacó más córners: mejora la verosimilitud por equipo
    assert moved["corners por equipo"][0][0] > plain["corners por equipo"][0][0]
