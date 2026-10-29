"""Ventaja local propia de cada competición en el modelo de goles (`ratings.fit(home_l2=...)`, fitting.GOALS_HOME_L2).

Corre el backtest de siempre (2024-26, cinco ligas) con una sola ventaja local y con un desvío por competición
contraído con varias L2, y compara partido a partido la pérdida logarítmica 1X2 del modelo y de la mezcla con
Pinnacle (25/75), en los partidos con cuota previa de bet365 y Pinnacle. La L2 se elige con 2024-25; 2025-26 es la
prueba honesta. Muestra además el desvío de cada liga en el último ajuste y las apuestas del backtest.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/ventaja_local.py (unos 6 min)
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from apuestas.backtest import engine

GRID = [None, 300.0, 1000.0, 3000.0, 10000.0, 30000.0]
SPLIT = date(2025, 7, 1)
LEAGUES = ("EPL", "BUN", "LAL", "SA", "L1")


def run(home_l2: float | None) -> tuple[dict, dict, dict]:
    """Pérdida por partido {match_id: (día, liga, modelo, mezcla)}, desvíos del último ajuste y resumen."""
    out: dict = {}
    last: dict = {}
    orig = engine._evaluate_match

    def spy(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model=engine.W_MODEL, model_only=False):
        sharp = engine._book_probs(od, "pinnacle") or engine._book_probs(od, "betfair_ex")
        b365 = engine._book_probs(od, "bet365")
        if not model_only and sharp and b365 and r.home in gm.attack and r.away in gm.attack:
            p = engine._probs_1x2(*gm.expected(r.home, r.away, r.neutral, r.competition), rho)
            y = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
            mix = w_model * p[y] + (1 - w_model) * sharp[y]
            out[r.match_id] = (r.day, r.competition, -math.log(max(p[y], 1e-9)), -math.log(max(mix, 1e-9)))
        last["home"] = (gm.home_adv, dict(gm.home_by_comp))
        return orig(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model, model_only=model_only)

    engine._evaluate_match = spy
    try:
        res = engine.run(date(2024, 8, 1), date(2026, 6, 30), home_by_league=home_l2 is not None, home_l2=home_l2)
    finally:
        engine._evaluate_match = orig
    return out, last["home"], res.summary()["betting"]


def diff(a: dict, b: dict, ids: list[int], k: int) -> str:
    d = np.array([b[i][k] - a[i][k] for i in ids])
    return f"{d.mean():+.4f} ± {1.96 * d.std(ddof=1) / math.sqrt(len(d)):.4f}"


def main() -> None:
    runs = {}
    for l2 in GRID:
        runs[l2] = run(l2)
        home, by_comp = runs[l2][1]
        print(f"L2 {l2}: local {home:.3f}; " + ", ".join(f"{c} {v:+.3f}" for c, v in sorted(by_comp.items())
                                                       if c in LEAGUES), flush=True)
    base = runs[None][0]
    ids = sorted(base)
    tune = [i for i in ids if base[i][0] < SPLIT]
    test = [i for i in ids if base[i][0] >= SPLIT]
    print(f"\nPartidos: {len(tune)} en 2024-25 y {len(test)} en 2025-26. Pérdida log. 1X2, diferencia frente a una "
          "sola ventaja (negativo = mejor; margen del 95 % pareado)")
    for l2 in GRID[1:]:
        cur = runs[l2][0]
        print(f"  L2 {l2:>7}: modelo 2024-25 {diff(base, cur, tune, 2)}, 2025-26 {diff(base, cur, test, 2)}, "
              f"todo {diff(base, cur, ids, 2)} | mezcla todo {diff(base, cur, ids, 3)}")
    best = min(GRID[1:], key=lambda x: np.mean([runs[x][0][i][2] for i in tune]))
    print(f"\nMejor L2 en 2024-25: {best}. Por liga (2024-26):")
    for lg in LEAGUES:
        lid = [i for i in ids if base[i][1] == lg]
        print(f"  {lg}: {len(lid)} partidos, modelo {diff(base, runs[best][0], lid, 2)}")
    for name, l2 in (("una sola", None), (f"L2 {best}", best)):
        b = runs[l2][2]
        print(f"  Apuestas con {name}: " + "; ".join(
            f"{k} {v['total']['bets']} ({v['total']['roi']:+.1%}, CLV {v['total']['avg_clv']:+.2%})"
            for k, v in b.items()))


if __name__ == "__main__":
    main()
