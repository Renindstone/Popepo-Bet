"""Goles esperados implícitos en las cuotas ("ratings implícitos del mercado").

Las cuotas de cierre de una casa afilada (Pinnacle; si no hay, bet365), sin margen, resumen casi toda la
información disponible antes del partido. Se invierten a (goles esperados local, visitante): se buscan las
dos medias cuya matriz Dixon-Coles reproduce el 1X2 y el más/menos 2.5 del mercado (mínimos cuadrados con
Gauss-Newton, vectorizado para miles de partidos a la vez).

Esas medias se añaden al modelo de fuerza como observaciones extra (ver `fitting.market_obs`).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson

from apuestas.models.distributions import MAX_GOALS

MARKET_RHO = -0.05  # rho Dixon-Coles usado al invertir (el ajustado sobre los datos ronda este valor)
_K = np.arange(MAX_GOALS + 1)
_I, _J = np.indices((MAX_GOALS + 1, MAX_GOALS + 1))


def market_probs(lh: np.ndarray, la: np.ndarray, rho: float = MARKET_RHO) -> np.ndarray:
    """Probabilidades [local, empate, visitante, más de 2.5] para cada par de medias (N x 4)."""
    lh, la = np.atleast_1d(lh).astype(float), np.atleast_1d(la).astype(float)
    mat = poisson.pmf(_K[None, :], lh[:, None])[:, :, None] * poisson.pmf(_K[None, :], la[:, None])[:, None, :]
    mat[:, 0, 0] *= 1 - lh * la * rho
    mat[:, 0, 1] *= 1 + lh * rho
    mat[:, 1, 0] *= 1 + la * rho
    mat[:, 1, 1] *= 1 - rho
    mat = np.clip(mat, 0, None)
    mat /= mat.sum(axis=(1, 2), keepdims=True)
    return np.stack(
        [mat[:, _I > _J].sum(1), mat[:, _I == _J].sum(1), mat[:, _I < _J].sum(1), mat[:, _I + _J >= 3].sum(1)],
        axis=1,
    )


def implied_goals(p1x2: np.ndarray, p_over: np.ndarray, rho: float = MARKET_RHO,
                  iters: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Medias (N x 2) que mejor reproducen el 1X2 (N x 3) y P(más de 2.5) (N; NaN si no hay) y el error RMS."""
    p1x2 = np.atleast_2d(np.asarray(p1x2, dtype=float))
    p_over = np.atleast_1d(np.asarray(p_over, dtype=float))
    target = np.column_stack([p1x2, np.nan_to_num(p_over)])
    wts = np.ones_like(target)
    wts[np.isnan(p_over), 3] = 0.0  # sin más/menos: solo el 1X2 (el empate fija el total, peor)
    x = np.tile(np.log([1.45, 1.15]), (len(target), 1))
    eps = 1e-5
    for _ in range(iters):
        base = market_probs(np.exp(x[:, 0]), np.exp(x[:, 1]), rho)
        r = (base - target) * wts
        jac = np.empty((len(x), 4, 2))
        for k in range(2):
            xp = x.copy()
            xp[:, k] += eps
            jac[:, :, k] = (market_probs(np.exp(xp[:, 0]), np.exp(xp[:, 1]), rho) - base) * wts / eps
        jtj = np.einsum("nik,nil->nkl", jac, jac) + 1e-9 * np.eye(2)
        jtr = np.einsum("nik,ni->nk", jac, r)
        step = np.linalg.solve(jtj, jtr[:, :, None])[:, :, 0]
        step = np.clip(step, -0.5, 0.5)
        x = np.clip(x - step, np.log(0.05), np.log(6.0))
        if np.max(np.abs(step)) < 1e-8:
            break
    lam = np.exp(x)
    resid = (market_probs(lam[:, 0], lam[:, 1], rho) - target) * wts
    rmse = np.sqrt(np.sum(resid**2, axis=1) / wts.sum(axis=1))
    return lam, rmse
