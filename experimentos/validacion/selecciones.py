"""Selecciones (UEFA Nations League, 10-11-2026): ¿cambian los modelos de clubes al entrenar con ellas? ¿Y qué tal
predice el modelo a las selecciones?

No hay cuotas históricas de selecciones (football-data no las cubre), así que no se puede medir contra bet365 como en
las ligas. Se mide:
- **clubes, antes y después**: el backtest de siempre (ligas con cuotas y copas europeas) sin las competiciones de
  selecciones en el entrenamiento y con ellas. Los equipos no se cruzan, pero comparten la media de goles, la ventaja
  local general, la dispersión y los árbitros;
- **selecciones**: log-loss 1X2 del modelo frente a la referencia más simple (los dos equipos como el equipo medio,
  con la ventaja local), en la ventana de siempre y desde julio de 2026 (la Nations League 2026-27, ya con el
  historial del Mundial y los clasificatorios), y remates, córners y tarjetas frente a la media;
- **xG de las selecciones**: lo mismo sin su xG en el modelo de goles (como la Europa League y la Conference).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/selecciones.py
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from apuestas.backtest import engine
from apuestas.core.competitions import COMPETITIONS, NATIONAL
from apuestas.models import fitting

EUROPE = ("UCL", "UEL", "UECL")
NATIONS = ("UNL", "WCQ", "WC", "EURO")
WINDOWS = {"2024-08 a 2026-06": (date(2024, 8, 1), date(2026, 6, 30)),
           "2026-07 a 2026-11": (date(2026, 7, 1), date(2026, 11, 10))}
CODES = fitting.model_codes()
XG_SKIP = fitting.GOALS_XG_SKIP


def run(window: str, national: bool = True, national_xg: bool = True) -> engine.BacktestResult:
    fitting.model_codes = lambda: CODES if national else [c for c in CODES if c not in NATIONAL]
    fitting.GOALS_XG_SKIP = XG_SKIP if national_xg else XG_SKIP | NATIONAL
    try:
        extra = (*EUROPE, *(NATIONS if national else ()))
        return engine.run(*WINDOWS[window], extra_competitions=extra)
    finally:
        fitting.model_codes, fitting.GOALS_XG_SKIP = (lambda: CODES), XG_SKIP


def clubs(res: dict) -> dict:
    out = {f"1X2 {k}": v for k, v in res["logloss_1x2"].items()}
    out.update({f"1X2 modelo {c}": v["logloss"] for c, v in res["logloss_modelo_por_competicion"].items()
                if c not in NATIONAL})
    for strat, groups in res["betting"].items():
        t = groups["total"]
        out[f"apuestas {strat}"] = f"{t['bets']} ap., ROI {t.get('roi', 0):+.4f}, CLV {t.get('avg_clv') or 0:+.4f}"
    for stat in ("shots", "corners", "cards", "fouls", "offsides"):
        for key in (stat, f"{stat}:UCL"):
            if key in res["count_models"]:
                out[f"{key} (mejora por partido)"] = res["count_models"][key]["improvement"]
    return out


def nations(res: dict) -> None:
    """Imprime el modelo frente a la referencia en cada torneo de selecciones (de `BacktestResult.summary()`)."""
    for c in NATIONS:
        v = res["logloss_modelo_por_competicion"].get(c)
        if v:
            print(f"  {c:5} {v['partidos']:4} partidos · modelo {v['logloss']:.4f} · equipos iguales "
                  f"{v['logloss_equipos_iguales']:.4f} · mejora {v['mejora']:+.4f} ± {v['margen_95']:.4f}")
    for stat in ("shots", "shots_on_target", "corners", "cards", "fouls"):
        v = res["count_models"].get(f"{stat}:UNL")
        if v:
            print(f"  UNL {stat:16} {v['matches']:4} partidos · mejora frente a la media {v['improvement']:+.4f} "
                  f"± {v['margin_95']:.4f}")


def paired(name: str, with_xg: list[float], without: list[float]) -> None:
    """Diferencia emparejada de log-loss 1X2 (los mismos partidos con y sin el xG de las selecciones)."""
    d = np.array(with_xg) - np.array(without)
    margin = 1.96 * float(d.std(ddof=1)) / math.sqrt(len(d))
    print(f"  {name:6} {len(d):4} partidos · con xG − sin xG = {d.mean():+.4f} ± {margin:.4f} (negativo: mejor con xG)")


def main() -> None:
    assert all(COMPETITIONS[c].national for c in NATIONS)
    std = "2024-08 a 2026-06"
    before, after = run(std, national=False), run(std)
    print(f"== Clubes, {std}: sin selecciones en el entrenamiento -> con ellas")
    cb, ca = clubs(before.summary()), clubs(after.summary())
    for k in cb:
        print(f"  {k:38} {cb[k]} -> {ca.get(k)}")
    with_xg: dict[str, list[float]] = {c: [] for c in NATIONS}
    without: dict[str, list[float]] = {c: [] for c in NATIONS}
    for window in WINDOWS:
        res = after if window == std else run(window)
        no_xg = run(window, national_xg=False)
        print(f"== Selecciones, {window} (con su xG)")
        nations(res.summary())
        print(f"== Selecciones, {window} (sin su xG)")
        nations(no_xg.summary())
        for c in NATIONS:
            with_xg[c] += res.ll_by_comp.get(c, [])
            without[c] += no_xg.ll_by_comp.get(c, [])
    print("== xG de las selecciones en el modelo de goles, las dos ventanas juntas")
    for c in NATIONS:
        if with_xg[c]:
            paired(c, with_xg[c], without[c])
    paired("todas", sum(with_xg.values(), []), sum(without.values(), []))


if __name__ == "__main__":
    main()
