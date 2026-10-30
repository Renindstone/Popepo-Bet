"""Antigüedad de las cuotas de cierre en días con partidos en vez de días de calendario (`ratings.fit`,
`market_matchdays`; fitting.MARKET_MATCHDAYS).

Con 14 días de calendario de vida media, tras el parón de verano las cuotas de mayo casi no pesan y el modelo arranca
la temporada con los goles y el xG. Contando solo días con partidos, el parón no envejece el mercado. Corre el
backtest (2024-08 a 2026-10, ligas) con las dos formas y varias vidas medias, y compara partido a partido la
pérdida logarítmica 1X2 del modelo, aparte en agosto-septiembre (inicio de temporada). La vida media se elige con
2024-25; 2025-26 y 2026-27 son la prueba.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/mercado_jornadas.py (unos 6 min)
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from apuestas.backtest import engine

VARIANTS = {"calendario 14": (14.0, False), "partidos 10": (10.0, True), "partidos 14": (14.0, True),
            "partidos 20": (20.0, True)}
SEASONS = {"2024-25": (date(2024, 8, 1), date(2025, 7, 1)), "2025-26": (date(2025, 7, 1), date(2026, 7, 1)),
           "2026-27": (date(2026, 7, 1), date(2026, 11, 1))}


def run(half_life: float, matchdays: bool) -> dict:
    out: dict = {}
    orig = engine._evaluate_match

    def spy(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model=engine.W_MODEL, model_only=False):
        if not model_only and r.home in gm.attack and r.away in gm.attack:
            p = engine._probs_1x2(*gm.expected(r.home, r.away, r.neutral, r.competition), rho)
            y = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
            out[r.match_id] = (r.day, -math.log(max(p[y], 1e-9)))
        return orig(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model, model_only=model_only)

    engine._evaluate_match = spy
    try:
        engine.run(date(2024, 8, 1), date(2026, 10, 28), market_half_life=half_life, market_matchdays=matchdays)
    finally:
        engine._evaluate_match = orig
    return out


def main() -> None:
    runs = {name: run(*v) for name, v in VARIANTS.items()}
    base = runs["calendario 14"]
    print("Pérdida log. 1X2 del modelo frente a 14 días de calendario (negativo = mejor; margen del 95 % pareado)")
    for name in list(VARIANTS)[1:]:
        cur = runs[name]
        for season, (lo, hi) in SEASONS.items():
            cells = []
            for label, months in (("ago-sep", (8, 9)), ("todo", tuple(range(1, 13)))):
                ids = [i for i, (d, _) in base.items() if lo <= d < hi and d.month in months and i in cur]
                d_ = np.array([cur[i][1] - base[i][1] for i in ids])
                cells.append(f"{label} ({len(ids)}) {d_.mean():+.4f} ± {1.96 * d_.std(ddof=1) / math.sqrt(len(d_)):.4f}")
            print(f"  {name:<12} {season}: " + "; ".join(cells))


if __name__ == "__main__":
    main()
