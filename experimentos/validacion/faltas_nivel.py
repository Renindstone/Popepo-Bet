"""Faltas con el nivel reciente de cada liga, solo en las ligas (`fitting.count_levels`, `leagues_only`).

Corre el backtest (2024-08 a 2026-10, ligas y copas europeas) sin nivel en faltas (lo de antes) y con él en dos
vidas medias, y compara partido a partido la log-verosimilitud de las faltas de cada equipo y la del total con el
factor del árbitro (lo que usa el análisis). La vida media se elige con 2024-25; 2025-26 y 2026-27 son la prueba.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/faltas_nivel.py (unos 5 min)
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from apuestas.backtest import engine
from apuestas.models import distributions as dist
from apuestas.models import fitting

VARIANTS = {"sin nivel": None, "ligas, 30 días": {"leagues_only": True},
            "ligas, 60 días": {"leagues_only": True, "half_life": 60.0}}
SEASONS = {"2024-25": (date(2024, 8, 1), date(2025, 7, 1)), "2025-26": (date(2025, 7, 1), date(2026, 7, 1)),
           "2026-27": (date(2026, 7, 1), date(2026, 11, 1))}


def run(params: dict | None) -> dict:
    out: dict = {}
    orig = engine._evaluate_counts

    def spy(r, cms, count_ll, refs=None, suffix="", leagues=None, delta=0.0):
        cm = cms.get("fouls")
        vh, va = r.stats_h.get("fouls"), r.stats_a.get("fouls")
        if cm is not None and vh is not None and va is not None:
            mh, ma = cm.expected(r.home, r.away, r.neutral, r.competition)
            team = engine._count_logpmf(int(vh), mh, cm.dispersion) + engine._count_logpmf(int(va), ma, cm.dispersion)
            ref = (refs or {}).get(r.referee_id) if r.referee_id else None
            f = ref.get("fouls_factor", 1.0) if ref else 1.0
            pmf = dist.count_total_pmf(mh * f, ma * f, cm.dispersion, cm.total_dispersion, 80)
            k = int(vh + va)
            out[r.match_id] = (r.day, "copas" if suffix else "ligas", team, math.log(max(pmf[k] if k < len(pmf) else 0, 1e-9)))
        return orig(r, cms, count_ll, refs, suffix, leagues, delta)

    stats, prm = fitting.COUNT_LEVEL_STATS, dict(fitting.COUNT_LEVEL_PARAMS)
    if params is not None:
        fitting.COUNT_LEVEL_STATS = (*stats, "fouls")
        fitting.COUNT_LEVEL_PARAMS = {**prm, "fouls": params}
    engine._evaluate_counts = spy
    try:
        engine.run(date(2024, 8, 1), date(2026, 10, 28), extra_competitions=("UCL", "UEL", "UECL"))
    finally:
        engine._evaluate_counts = orig
        fitting.COUNT_LEVEL_STATS, fitting.COUNT_LEVEL_PARAMS = stats, prm
    return out


def main() -> None:
    runs = {name: run(p) for name, p in VARIANTS.items()}
    base = runs["sin nivel"]
    print("Log-verosimilitud por partido frente a sin nivel (positivo = mejor; margen del 95 % pareado)")
    for name in list(VARIANTS)[1:]:
        cur = runs[name]
        for scope in ("ligas", "copas"):
            for season, (lo, hi) in SEASONS.items():
                ids = [i for i, x in base.items() if x[1] == scope and lo <= x[0] < hi and i in cur]
                if len(ids) < 20:
                    continue
                cells = []
                for k, label in ((2, "por equipo"), (3, "total con árbitro")):
                    d = np.array([cur[i][k] - base[i][k] for i in ids])
                    cells.append(f"{label} {d.mean():+.4f} ± {1.96 * d.std(ddof=1) / math.sqrt(len(d)):.4f}")
                print(f"  {name:<15} {scope:<5} {season} ({len(ids):>4}): " + "; ".join(cells))


if __name__ == "__main__":
    main()
