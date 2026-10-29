"""Calibración de los empates: ¿el modelo de goles da empates de menos?

Corre el backtest de siempre (2024-26, cinco ligas) guardando de cada partido evaluado los goles esperados, el rho y el
resultado. Después, fuera de muestra: cada mes se elige con los meses anteriores el factor k que multiplica la
diagonal de la matriz de marcadores (todos los empates; la matriz se vuelve a normalizar) y se aplica a ese mes.
Compara la pérdida logarítmica 1X2 y de Más/Menos 2.5 con k = 1 (lo de ahora) y muestra la calibración del empate por
tramos (lo que da el modelo frente a lo que salió).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/empates.py (algo más de 1 min)
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from apuestas.backtest import engine
from apuestas.models import distributions as dist

GRID = np.round(np.arange(0.90, 1.31, 0.01), 2)
MIN_TRAIN = 600


def collect() -> list[dict]:
    rows: list[dict] = []
    orig = engine._evaluate_match

    def spy(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model=engine.W_MODEL, model_only=False):
        sharp = engine._book_probs(od, "pinnacle") or engine._book_probs(od, "betfair_ex")
        b365 = engine._book_probs(od, "bet365")
        if not model_only and sharp and b365 and r.home in gm.attack and r.away in gm.attack:
            lh, la = gm.expected(r.home, r.away, r.neutral, r.competition)
            rows.append({"day": r.day, "month": (r.day.year, r.day.month), "lh": lh, "la": la, "rho": rho,
                         "y": 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2), "over": r.hg + r.ag > 2.5,
                         "pin_draw": sharp[1]})
        return orig(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model, model_only=model_only)

    engine._evaluate_match = spy
    try:
        engine.run(date(2024, 8, 1), date(2026, 6, 30))
    finally:
        engine._evaluate_match = orig
    return rows


def probs(r: dict, k: float) -> tuple[list[float], float]:
    """1X2 y Más de 2.5 con la diagonal multiplicada por k."""
    mat = dist.dixon_coles_matrix(r["lh"], r["la"], r["rho"])
    mat[np.diag_indices_from(mat)] *= k
    mat /= mat.sum()
    p = [float(np.tril(mat, -1).sum()), float(np.trace(mat)), float(np.triu(mat, 1).sum())]
    return p, float(dist.over(dist.total_pmf_from_matrix(mat), 2.5).win)


def loss(r: dict, k: float) -> tuple[float, float]:
    p, over = probs(r, k)
    return -math.log(max(p[r["y"]], 1e-9)), -math.log(max(over if r["over"] else 1 - over, 1e-9))


def main() -> None:
    rows = collect()
    months = sorted({r["month"] for r in rows})
    ks = []
    for mo in months:
        train = [r for r in rows if r["month"] < mo]
        k = 1.0
        if len(train) >= MIN_TRAIN:
            k = float(GRID[np.argmin([sum(loss(r, g)[0] for r in train) for g in GRID])])
        ks.append(k)
        for r in rows:
            if r["month"] == mo:
                r["k"] = k
    print(f"{len(rows)} partidos. Factor del empate aprendido cada mes: {ks[0]:.2f} → {ks[-1]:.2f} "
          f"(media {np.mean(ks):.3f})")
    base = np.array([loss(r, 1.0) for r in rows])
    cal = np.array([loss(r, r["k"]) for r in rows])
    for j, name in ((0, "1X2"), (1, "Más/Menos 2.5")):
        d = cal[:, j] - base[:, j]
        print(f"  {name}: {base[:, j].mean():.4f} → {cal[:, j].mean():.4f} "
              f"({d.mean():+.4f} ± {1.96 * d.std(ddof=1) / math.sqrt(len(d)):.4f})")
    print("\nEmpate por tramos de probabilidad del modelo (k = 1): modelo, real, Pinnacle")
    pd_ = np.array([probs(r, 1.0)[0][1] for r in rows])
    real = np.array([r["y"] == 1 for r in rows])
    pin = np.array([r["pin_draw"] for r in rows])
    for lo, hi in ((0, 0.22), (0.22, 0.26), (0.26, 0.30), (0.30, 1)):
        m = (pd_ >= lo) & (pd_ < hi)
        if m.sum():
            print(f"  {lo:.2f}-{hi:.2f}: {m.sum():>5} partidos, modelo {pd_[m].mean():.3f}, real {real[m].mean():.3f}, "
                  f"Pinnacle {pin[m].mean():.3f}")


if __name__ == "__main__":
    main()
