import sys, json
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from exp_common import FULL, SP, paired
r = pd.read_pickle(f"{SP}/data/stats_results.pkl")
r = r[(r.date >= "2021-07-01") & (r.date < "2026-07-01")].copy()
r["week"] = pd.to_datetime(r.date).dt.strftime("%G-%V")
LINES = {'cards': [2.5, 3.5, 4.5, 5.5, 6.5], 'fouls': [18.5, 20.5, 22.5, 24.5, 26.5, 28.5], 'corners': [7.5, 8.5, 9.5, 10.5, 11.5, 12.5], 'shots': [20.5, 22.5, 24.5, 26.5, 28.5, 30.5], 'sot': [6.5, 7.5, 8.5, 9.5, 10.5, 11.5]}
out = {"ll": [], "tails": [], "pit": [], "league_bias": []}
M = ["C0", "C1", "C2", "C3"]
for st, g in r.groupby("stat"):
    for scope, gg in (("full", g[g["div"].isin(FULL)]), ("all", g)):
        row = {"stat": st, "scope": scope, "n": len(gg)}
        for k in M:
            dm, se = paired((gg[f"ll_{k}"] - gg["ll_base"]).to_numpy(), gg.week.to_numpy())
            row[f"{k}_vs_base"], row[f"{k}_se"] = dm, se
        for a, b in (("C1", "C0"), ("C2", "C1"), ("C3", "C2")):
            dm, se = paired((gg[f"ll_{a}"] - gg[f"ll_{b}"]).to_numpy(), gg.week.to_numpy())
            row[f"{a}-{b}"], row[f"{a}-{b}_se"] = dm, se
        out["ll"].append(row)
        # PIT: fracción en el 10 % más bajo y más alto (ideal 0,10)
        for k in M + ["base"]:
            p = gg[f"pit_{k}"].to_numpy()
            out["pit"].append({"stat": st, "scope": scope, "model": k, "low10": (p < 0.1).mean(), "high10": (p > 0.9).mean()})
    # colas: para cada partido, la línea cuya prob. de "más" en C0 está más cerca de 20 % y la de "menos" más cerca de 20 %
    for k in M:
        P = np.column_stack([g[f"ov{L}_{k}"].to_numpy() for L in LINES[st]])
        y = g.y.to_numpy()
        hi = np.argmin(np.abs(P - 0.2), axis=1); lo = np.argmin(np.abs((1 - P) - 0.2), axis=1)
        Lv = np.array(LINES[st])
        ph = P[np.arange(len(g)), hi]; yh = (y > Lv[hi]).astype(float)
        pl = 1 - P[np.arange(len(g)), lo]; yl = (y < Lv[lo]).astype(float)
        sel_h = np.abs(ph - 0.2) < 0.07; sel_l = np.abs(pl - 0.2) < 0.07
        out["tails"].append({"stat": st, "model": k, "over_pred": ph[sel_h].mean(), "over_obs": yh[sel_h].mean(), "n_over": int(sel_h.sum()),
                             "under_pred": pl[sel_l].mean(), "under_obs": yl[sel_l].mean(), "n_under": int(sel_l.sum())})
    for dv, gg in g.groupby("div"):
        out["league_bias"].append({"stat": st, "div": dv, "n": len(gg), "obs": gg.y.mean(), **{f"mu_{k}": gg[f"mu_{k}"].mean() for k in M + ["base"]}})
json.dump(out, open(f"{SP}/data/stats_summary.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print(pd.DataFrame(out["ll"]).round(4).to_string())
print(pd.DataFrame(out["tails"]).round(3).to_string())
pit = pd.DataFrame(out["pit"]); print(pit[pit.scope == "all"].round(3).to_string())
lb = pd.DataFrame(out["league_bias"])
lb["C0_bias%"] = 100 * (lb.mu_C0 / lb.obs - 1); lb["C1_bias%"] = 100 * (lb.mu_C1 / lb.obs - 1)
print(lb.pivot(index="div", columns="stat", values="C0_bias%").round(1).to_string())
print(lb.pivot(index="div", columns="stat", values="C1_bias%").round(1).to_string())
