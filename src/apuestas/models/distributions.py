"""Distribuciones de conteo y cálculo de probabilidades de mercados.

Convenciones de resultados de una apuesta (para líneas asiáticas):
    win, half_win, push, half_loss, loss
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import nbinom, poisson

MAX_GOALS = 10


def count_pmf(mean: float, dispersion: float = 0.0, max_k: int | None = None) -> np.ndarray:
    """PMF de Poisson (dispersion=0) o binomial negativa (Var = m + alfa m^2)."""
    mean = max(mean, 1e-6)
    if max_k is None:
        max_k = int(mean + 10 * math.sqrt(mean * (1 + dispersion * mean)) + 10)
    k = np.arange(max_k + 1)
    if dispersion <= 1e-6:
        pmf = poisson.pmf(k, mean)
    else:
        r = 1.0 / dispersion
        pmf = nbinom.pmf(k, r, r / (r + mean))
    pmf = np.asarray(pmf, dtype=float)
    return pmf / pmf.sum()


def dixon_coles_matrix(lh: float, la: float, rho: float = -0.05, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Matriz P[i, j] = P(local i goles, visitante j goles) con corrección Dixon-Coles para marcadores bajos."""
    ph = poisson.pmf(np.arange(max_goals + 1), lh)
    pa = poisson.pmf(np.arange(max_goals + 1), la)
    mat = np.outer(ph, pa)
    mat[0, 0] *= 1 - lh * la * rho
    mat[0, 1] *= 1 + lh * rho
    mat[1, 0] *= 1 + la * rho
    mat[1, 1] *= 1 - rho
    mat = np.clip(mat, 0, None)
    return mat / mat.sum()


def independent_matrix(pmf_h: np.ndarray, pmf_a: np.ndarray) -> np.ndarray:
    return np.outer(pmf_h, pmf_a)


@dataclass
class Outcome:
    win: float = 0.0
    half_win: float = 0.0
    push: float = 0.0
    half_loss: float = 0.0
    loss: float = 0.0

    def ev(self, odds: float) -> float:
        """Valor esperado por unidad apostada."""
        return (
            self.win * (odds - 1)
            + self.half_win * (odds - 1) / 2
            - self.half_loss / 2
            - self.loss
        )

    def fair_odds(self) -> float:
        """Cuota con EV = 0."""
        gain = self.win + self.half_win / 2
        lose = self.loss + self.half_loss / 2
        if gain <= 0:
            return float("inf")
        return 1 + lose / gain

    def decided(self) -> float:
        """Parte de la apuesta que se gana o se pierde de verdad: sin la devolución ni las medias devoluciones de las
        líneas de cuarto. (probabilidad equivalente × cuota − 1) × esto = valor esperado exacto."""
        return max(1e-9, 1 - self.push - (self.half_win + self.half_loss) / 2)

    def effective_prob(self) -> float:
        """Probabilidad equivalente sin empates (1 / cuota justa)."""
        fo = self.fair_odds()
        return 0.0 if math.isinf(fo) else 1 / fo


def _split_line(line: float) -> list[float]:
    """Líneas de cuarto (2.25, -0.75) se dividen en dos medias apuestas."""
    frac = round((line * 4) % 2, 6)
    if abs(frac - 1) < 1e-6:  # x.25 o x.75
        return [line - 0.25, line + 0.25]
    return [line]


def _sign(x: float) -> int:
    return 1 if x > 1e-9 else (-1 if x < -1e-9 else 0)


def line_outcome(diff_pmf: dict[int, float], line: float) -> Outcome:
    """Resultado de apostar a que `diff + line > 0` (sirve para hándicap y para over/under).

    - Hándicap asiático local: diff = goles_local - goles_visitante, line = hándicap.
    - Over L: diff = total, line = -L.   Under L: diff = -total, line = L.
    - Líneas de cuarto (x.25 / x.75) se dividen en dos medias apuestas.
    """
    parts = _split_line(line)
    out = Outcome()
    for d, p in diff_pmf.items():
        signs = [_sign(d + part) for part in parts]
        if len(signs) == 1:
            s = signs[0]
            if s > 0:
                out.win += p
            elif s < 0:
                out.loss += p
            else:
                out.push += p
            continue
        total = sum(signs)
        if total == 2:
            out.win += p
        elif total == 1:
            out.half_win += p
        elif total == 0:
            out.push += p
        elif total == -1:
            out.half_loss += p
        else:
            out.loss += p
    return out


def total_pmf_from_matrix(mat: np.ndarray) -> dict[int, float]:
    n, k = mat.shape
    out: dict[int, float] = {}
    for i in range(n):
        for j in range(k):
            out[i + j] = out.get(i + j, 0.0) + mat[i, j]
    return out


def diff_pmf_from_matrix(mat: np.ndarray) -> dict[int, float]:
    n, k = mat.shape
    out: dict[int, float] = {}
    for i in range(n):
        for j in range(k):
            out[i - j] = out.get(i - j, 0.0) + mat[i, j]
    return out


def pmf_to_dict(pmf: np.ndarray) -> dict[int, float]:
    return {i: float(p) for i, p in enumerate(pmf)}


def convolve(pmf_a: np.ndarray, pmf_b: np.ndarray) -> np.ndarray:
    return np.convolve(pmf_a, pmf_b)


def count_total_pmf(mh: float, ma: float, dispersion: float, total_dispersion: float | None = None,
                    max_k: int | None = None) -> np.ndarray:
    """Total de un conteo de los dos equipos. Con `total_dispersion`, binomial negativa con la dispersión propia del
    total, que recoge la correlación entre los dos (en córners y remates uno quita al otro; en tarjetas, el partido
    caliente sube a los dos); sin ella (paquetes antiguos), la suma de los dos como independientes."""
    if total_dispersion is None:
        return convolve(count_pmf(mh, dispersion, max_k), count_pmf(ma, dispersion, max_k))
    return count_pmf(mh + ma, total_dispersion, 2 * max_k if max_k else None)


def count_diff_dispersion(mh: float, ma: float, dispersion: float, total_dispersion: float) -> float:
    """Dispersión de cada equipo para la diferencia entre los dos (hándicaps de estadísticas), con la correlación que
    implica la dispersión del total: Var(local − visitante) = 2 (Var local + Var visitante) − Var total."""
    m2 = mh**2 + ma**2
    var_diff = 2 * (mh + ma + dispersion * m2) - (mh + ma + total_dispersion * (mh + ma) ** 2)
    return max(0.0, (var_diff - mh - ma) / m2)


def over(total_pmf: dict[int, float], line: float) -> Outcome:
    return line_outcome(total_pmf, -line)


def under(total_pmf: dict[int, float], line: float) -> Outcome:
    return line_outcome({-t: p for t, p in total_pmf.items()}, line)


def prob_outcome(p: float) -> Outcome:
    """Mercado binario sin empate (1X2, ambos marcan, tarjeta de jugador...)."""
    p = min(max(p, 0.0), 1.0)
    return Outcome(win=p, loss=1 - p)
