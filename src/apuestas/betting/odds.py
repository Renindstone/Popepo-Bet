"""Matemática de cuotas: probabilidad implícita, quitar el margen de la casa, valor esperado y Kelly."""

from __future__ import annotations

from scipy.optimize import brentq


def implied(odds: list[float]) -> list[float]:
    return [1 / o for o in odds]


def overround(odds: list[float]) -> float:
    """Margen de la casa: 0.05 = 5%."""
    return sum(implied(odds)) - 1


def devig_multiplicative(odds: list[float]) -> list[float]:
    p = implied(odds)
    total = sum(p)
    return [x / total for x in p]


def devig_power(odds: list[float]) -> list[float]:
    """Método de potencia: corrige el sesgo favorito-sorpresa mejor que el multiplicativo."""
    p = implied(odds)
    if abs(sum(p) - 1) < 1e-9:
        return p

    def f(k: float) -> float:
        return sum(x**k for x in p) - 1

    try:
        k = brentq(f, 0.5, 3.0)
    except ValueError:
        return devig_multiplicative(odds)
    return [x**k for x in p]


def devig(odds: list[float]) -> list[float]:
    return devig_power(odds) if len(odds) >= 3 else devig_multiplicative(odds)


def expected_value(prob: float, odds: float) -> float:
    return prob * odds - 1


def kelly(prob: float, odds: float) -> float:
    """Fracción de Kelly completa (puede ser negativa = no apostar)."""
    b = odds - 1
    if b <= 0:
        return 0.0
    return (prob * b - (1 - prob)) / b


def stake_pct(prob: float, odds: float, fraction: float, cap: float) -> float:
    """Kelly fraccional con tope. Devuelve % de la banca (0-1)."""
    return round(max(0.0, min(kelly(prob, odds) * fraction, cap)), 4)


def clv(odds_taken: float, closing_odds: float) -> float:
    """Closing Line Value: >0 significa que conseguiste mejor cuota que la de cierre."""
    return odds_taken / closing_odds - 1
