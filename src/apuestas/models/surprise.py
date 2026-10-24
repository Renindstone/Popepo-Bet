"""Sorpresa de un dato frente a lo esperado, de −1 a +1 (resumen de la semana, `services/weekly.py`).

`mid_pit`: P(X < real) − P(X > real) con la distribución esperada. 0 = lo esperado, +1 = muy por encima y −1 = muy
por debajo. Tiene en cuenta el margen: con 9,9 córners esperados, 10 suma +0,09, 12 suma +0,43 y 15 suma +0,77.
El resultado se mide en puntos frente a los puntos esperados: ganar de punto suma más que ganar de favorito.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from apuestas.models import distributions as dist


def count_dist(mean: float, dispersion: float = 0.0) -> np.ndarray:
    """Poisson (dispersión 0) o binomial negativa, como los mercados del modelo."""
    return dist.count_pmf(mean, dispersion)


def mid_pit(pmf: np.ndarray, actual: int) -> float:
    a = max(int(actual), 0)
    n = len(pmf)
    below = float(pmf[: min(a, n)].sum())
    at = float(pmf[a]) if a < n else 0.0
    above = max(0.0, 1.0 - below - at)
    return max(-1.0, min(1.0, below - above))


def points(goals_for: int, goals_against: int) -> int:
    return 3 if goals_for > goals_against else 1 if goals_for == goals_against else 0


def result_score(pts: int, p_win: float, p_draw: float) -> float:
    """(puntos − puntos esperados) / 3: ganar con un 15 % suma +0,77; ganar con un 75 %, +0,19; empatarlo, −0,47."""
    return max(-1.0, min(1.0, (pts - (3 * p_win + p_draw)) / 3))


def solve_mean(line: float, p_over: float, dispersion: float, lo: float = 0.05, hi: float = 80.0) -> float | None:
    """Media con la que P(más de `line`) es `p_over` (la cuota sin margen de la casa). Vale para líneas .5,
    enteras y de cuarto (la devolución cuenta como en el mercado). None si no hay ninguna media que la cumpla."""
    if not 0.0 < p_over < 1.0:
        return None

    def gap(mu: float) -> float:
        return dist.over(dist.pmf_to_dict(count_dist(mu, dispersion)), line).effective_prob() - p_over

    try:
        if gap(lo) * gap(hi) > 0:
            return None
        return float(brentq(gap, lo, hi, xtol=1e-4))
    except ValueError:
        return None
