"""Dispersión del total de los conteos (fitting.COUNT_TOTAL_DISPERSION), medida fuera de muestra en el backtest
2024-26, y una prueba honesta: alfa estimada en 2024-25 y evaluada en 2025-26, frente a sumar los dos equipos como
independientes (lo de antes del 29-10-2026).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/dispersion_total.py (unos 40 s)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

import numpy as np

from apuestas.backtest import engine
from apuestas.models import distributions as dist
from apuestas.models import fitting

CUT = date(2025, 7, 1)
rec = defaultdict(list)
orig = engine._evaluate_counts


def spy(r, cms, count_ll, refs=None, suffix="", leagues=None, delta=0.0, derby=False):
    """Guarda las medias fuera de muestra de cada partido de liga y sigue con la evaluación de siempre."""
    if not suffix:
        for stat, cm in cms.items():
            vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
            if vh is None or va is None:
                continue
            mh, ma = cm.expected(r.home, r.away, r.neutral, r.competition)
            if stat in fitting.COUNT_STRENGTH_PRIOR:
                mh, ma = fitting.strength_shift(cm, mh, ma, delta)
            rec[stat].append((r.day, mh, ma, vh, va, cm.dispersion))
    return orig(r, cms, count_ll, refs, suffix, leagues, delta, derby)


def mom(y, m) -> float:
    """Alfa por momentos: Var = m + alfa m²."""
    return float(np.sum((y - m) ** 2 - m) / np.sum(m**2))


def ll(pmf, k: int) -> float:
    return math.log(max(pmf[k] if k < len(pmf) else 1e-9, 1e-9))


def main() -> None:
    engine._evaluate_counts = spy
    engine.run(start=date(2024, 8, 1), end=date(2026, 6, 30))
    print("Fuera de muestra, 2024-26 (alfa del total = la que va en COUNT_TOTAL_DISPERSION)")
    for stat, rows in rec.items():
        mh, ma, vh, va, a = np.array([x[1:] for x in rows], float).T
        print(f"  {stat:<16} alfa equipo: ajuste {a.mean():.4f}, fuera {mom(np.r_[vh, va], np.r_[mh, ma]):.4f} | "
              f"alfa total fuera {mom(vh + va, mh + ma):.4f} | corr. residuos {np.corrcoef(vh - mh, va - ma)[0, 1]:+.3f}")

    print(f"\nAlfa estimada antes del {CUT}, evaluada después (mejora por partido frente a sumar independientes)")
    for stat, rows in rec.items():
        tr = np.array([x[1:] for x in rows if x[0] < CUT], float)
        alpha = max(mom(tr[:, 2] + tr[:, 3], tr[:, 0] + tr[:, 1]), 0.0)
        gain = np.array([ll(dist.count_total_pmf(mh, ma, a, alpha, 80), int(vh + va))
                         - ll(dist.count_total_pmf(mh, ma, a, None, 80), int(vh + va))
                         for day, mh, ma, vh, va, a in rows if day >= CUT])
        print(f"  {stat:<16} alfa {alpha:.4f}: {gain.mean():+.4f} ± {1.96 * gain.std(ddof=1) / math.sqrt(len(gain)):.4f}"
              f" ({len(gain)} partidos)")


if __name__ == "__main__":
    main()
