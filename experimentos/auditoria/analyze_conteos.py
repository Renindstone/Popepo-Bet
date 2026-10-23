"""Tablas de exp_conteos_nuevos.py: mejora por equipo y del total, y sesgo de la media por temporada."""
import json
import sys

import numpy as np
import pandas as pd

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import SP, paired  # noqa: E402

r = pd.read_pickle(f"{SP}/data/conteos_nuevos.pkl")
r["week"] = pd.to_datetime(r.date).dt.strftime("%G-%V")
out = {"per_team": [], "total": [], "bias": []}
pairs = (("nuevo", "viejo"), ("reparto", "nuevo"), ("nivel", "reparto"), ("viejo", "base"), ("nivel", "base"))
for st, g in r.groupby("stat", sort=False):
    g = g[g.has_odds]
    for kind in ("side", "tot"):
        row = {"stat": st, "n": len(g)}
        for a, b in pairs:
            m, se = paired((g[f"{kind}_{a}"] - g[f"{kind}_{b}"]).to_numpy(), g.week.to_numpy())
            row[f"{a}-{b}"], row[f"{a}-{b}_se"] = m, se
        out["per_team" if kind == "side" else "total"].append(row)
    for season, gs in g.groupby("season"):
        out["bias"].append({"stat": st, "season": int(season), "n": len(gs), "real": gs.y.mean(),
                            **{f"{k}%": 100 * (gs[f"mu_{k}"].mean() / gs.y.mean() - 1)
                               for k in ("viejo", "nuevo", "reparto", "nivel")}})
json.dump(out, open(f"{SP}/data/conteos_nuevos.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print("== Log-verosimilitud por equipo (diferencia por partido, positivo = mejor)")
print(pd.DataFrame(out["per_team"]).round(4).to_string())
print("== Log-verosimilitud del total")
print(pd.DataFrame(out["total"]).round(4).to_string())
print("== Sesgo de la media del total por temporada (% sobre lo real)")
b = pd.DataFrame(out["bias"])
print(b[b.season >= 2023].round(1).to_string())
