"""Mezcla aprendida con el mercado (en lugar de W_MODEL = 0,25 fijo) y elegir por la probabilidad de que haya valor.

Corre el backtest de siempre (2024-26, las cinco ligas, cuota previa de bet365) guardando todas las selecciones
candidatas (1X2, más/menos 2,5 y hándicap asiático) con la probabilidad del modelo, la de Pinnacle sin margen y el
cierre de bet365. Después, fuera de muestra:

1. Peso del modelo por mercado aprendido cada mes con los meses anteriores (mínima pérdida logarítmica de la mezcla
   lineal, como la de `analysis.W_MODEL`), frente al 0,25 fijo y al mercado solo.
2. Apuestas con valor ≥ 3 % con cada mezcla: número, rendimiento y CLV (cuota tomada / cierre de bet365 − 1).
3. Probabilidad de valor: P(p > 1/cuota) con p ~ Normal(mezcla, σ²), σ = desviación de (cierre sin margen − mezcla)
   en los meses anteriores de ese mercado. Se apuesta si P ≥ umbral.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/apilado.py (algo más de 1 min)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.stats import norm

from apuestas.backtest import engine
from apuestas.betting import odds as oddsmath
from apuestas.betting.settlement import RESULT_PROFIT

MIN_EV = 0.03
GRID = np.round(np.arange(0.0, 0.51, 0.01), 2)
MIN_TRAIN = 300  # candidatas de ese mercado antes de aprender el peso; antes, 0,25
FIXED = 0.25
Y = {"win": (1.0, 1.0), "half_win": (1.0, 0.5), "loss": (0.0, 1.0), "half_loss": (0.0, 0.5)}  # (acierto, peso)


def collect() -> list[dict]:
    cur: dict = {}
    rows: list[dict] = []
    orig_eval, orig_bet = engine._evaluate_match, engine.Bet

    def spy_eval(r, *a, **k):
        cur["id"] = r.match_id
        return orig_eval(r, *a, **k)

    def spy_bet(*args):
        b = orig_bet(*args)
        if b.strategy == "solo_modelo":
            den = b.prob * b.odds - 1
            rows.append({"mid": cur["id"], "day": b.day, "market": b.market, "sel": b.selection, "line": b.line,
                         "odds": b.odds, "closing": b.closing, "p_m": b.prob, "result": b.result,
                         "decided": b.ev / den if abs(den) > 1e-6 else 1.0, "p_s": None})
        elif b.strategy == "solo_mercado_afilado":
            rows[-1]["p_s"] = b.prob
        return b

    engine._evaluate_match, engine.Bet = spy_eval, spy_bet
    try:  # w_model = 0 y min_ev = −10: todas las candidatas, y «modelo+mercado» = Pinnacle
        engine.run(start=date(2024, 8, 1), end=date(2026, 6, 30), w_model=0.0, min_ev=-10.0)
    finally:
        engine._evaluate_match, engine.Bet = orig_eval, orig_bet
    return [r for r in rows if r["p_s"] is not None]


def add_closing(rows: list[dict]) -> None:
    """Probabilidad del cierre de bet365 sin margen (las dos o tres selecciones del mismo mercado y línea)."""
    groups = defaultdict(list)
    for r in rows:
        line = -r["line"] if r["market"] == "ah" and r["sel"] == "away" else r["line"]
        groups[(r["mid"], r["market"], line)].append(r)
    for g in groups.values():
        need = 3 if g[0]["market"] == "1x2" else 2
        if len(g) == need and all(x["closing"] for x in g):
            for x, p in zip(g, oddsmath.devig([x["closing"] for x in g]), strict=True):
                x["p_close"] = p


def logloss(p, y, w) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))))


def profit(r: dict) -> float:
    k = RESULT_PROFIT[r["result"]]
    return k * (r["odds"] - 1) if k > 0 else k


def report(name: str, bets: list[dict]) -> None:
    if not bets:
        print(f"    {name:<34} 0 apuestas")
        return
    pr = np.array([profit(b) for b in bets])
    clv = np.array([b["odds"] / b["closing"] - 1 for b in bets if b["closing"]])
    half = 1.96 * pr.std(ddof=1) / math.sqrt(len(pr)) if len(pr) > 1 else float("nan")
    clv_text = f"CLV {clv.mean():+.2%} ({(clv > 0).mean():.0%} ganan al cierre)" if len(clv) else "sin cierre"
    print(f"    {name:<34} {len(bets):>5} apuestas, rendimiento {pr.mean():+.1%} ± {half:.1%}, {clv_text}")


def main() -> None:
    rows = collect()
    add_closing(rows)
    for r in rows:
        r["month"] = (r["day"].year, r["day"].month)
    months = sorted({r["month"] for r in rows})
    print(f"Candidatas con Pinnacle: {len(rows)}")

    for market in ("1x2", "ou_goals", "ah"):
        mk = [r for r in rows if r["market"] == market]
        trail = []
        for mo in months:
            train = [r for r in mk if r["month"] < mo and r["result"] in Y]
            test = [r for r in mk if r["month"] == mo]
            if len(train) >= MIN_TRAIN:
                pm, ps = np.array([r["p_m"] for r in train]), np.array([r["p_s"] for r in train])
                y, w = (np.array(v) for v in zip(*(Y[r["result"]] for r in train), strict=True))
                wt = float(GRID[np.argmin([logloss(g * pm + (1 - g) * ps, y, w) for g in GRID])])
                res = np.array([r["p_close"] - (wt * r["p_m"] + (1 - wt) * r["p_s"]) for r in train if "p_close" in r])
                sigma = float(res.std()) if len(res) > 50 else None
            else:
                wt, sigma = FIXED, None
            trail.append(wt)
            for r in test:
                r["w"], r["sigma"] = wt, sigma

        print(f"\n{market}: peso aprendido del modelo por mes {trail[0]:.2f} → {trail[-1]:.2f} "
              f"(media {np.mean(trail):.2f})")
        ev_rows = [r for r in mk if r["result"] in Y]
        y, w = (np.array(v) for v in zip(*(Y[r["result"]] for r in ev_rows), strict=True))
        lls = {}
        for name, p in (("fija 0,25", [FIXED * r["p_m"] + (1 - FIXED) * r["p_s"] for r in ev_rows]),
                        ("aprendida", [r["w"] * r["p_m"] + (1 - r["w"]) * r["p_s"] for r in ev_rows]),
                        ("Pinnacle sola", [r["p_s"] for r in ev_rows]), ("modelo solo", [r["p_m"] for r in ev_rows])):
            p = np.clip(np.array(p), 1e-6, 1 - 1e-6)
            lls[name] = -w * (y * np.log(p) + (1 - y) * np.log(1 - p))
        base = lls["fija 0,25"]
        for name, v in lls.items():
            d = v - base
            print(f"    pérdida log. {name:<14} {v.sum() / w.sum():.5f}  (frente a la fija {d.sum() / w.sum():+.5f} ± "
                  f"{1.96 * d.std(ddof=1) * math.sqrt(len(d)) / w.sum():.5f})")

        def ev(r, p):
            return (p * r["odds"] - 1) * r["decided"]

        report("valor ≥3 % con la mezcla fija", [r for r in mk if ev(r, FIXED * r["p_m"] + (1 - FIXED) * r["p_s"]) >= MIN_EV])
        report("valor ≥3 % con la aprendida", [r for r in mk if ev(r, r["w"] * r["p_m"] + (1 - r["w"]) * r["p_s"]) >= MIN_EV])
        report("valor ≥3 % con Pinnacle sola", [r for r in mk if ev(r, r["p_s"]) >= MIN_EV])
        for q in (0.6, 0.75, 0.9):
            sel = []
            for r in mk:
                if r["sigma"]:
                    p = r["w"] * r["p_m"] + (1 - r["w"]) * r["p_s"]
                    if norm.cdf((p - 1 / r["odds"]) / r["sigma"]) >= q:
                        sel.append(r)
            report(f"P(valor) ≥ {q:.0%} (aprendida)", sel)


if __name__ == "__main__":
    main()
