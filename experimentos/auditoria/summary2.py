import sys, json
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from exp_common import *
from ekf import run_ekf
df = load()
best = json.loads(open(f"{SP}/data/ekf_tune.log").read().split("BEST ")[1].splitlines()[0])
kw = {k: v for k, v in best.items() if k not in ("ll", "ll_ou", "ll_full")}
rho = float(open(f"{SP}/data/ekf_rho.txt").read())
k = 0.3074
yh = 0.7 * df.hg.to_numpy() + 0.3 * k * df.HomeTarget.to_numpy(float)
ya = 0.7 * df.ag.to_numpy() + 0.3 * k * df.AwayTarget.to_numpy(float)
p3 = run_ekf(df, **kw, y_obs=(yh, ya))
st = pd.read_parquet(f"{SP}/data/static_2016-07-01_2026-07-01.parquet")
ek = pd.read_parquet(f"{SP}/data/ekf_probs.parquet")
ml = pd.read_parquet(f"{SP}/data/ml_preds.parquet")
lh = np.exp(p3.eta_h + 0.5 * p3.var_h).to_numpy(); la = np.exp(p3.eta_a + 0.5 * p3.var_a).to_numpy()
pr = dc_probs(np.nan_to_num(lh, nan=1.4), np.nan_to_num(la, nan=1.1), rho)
for c in "HDA":
    df[f"sot_{c}"] = pr[c]
df["sot_over"] = pr["over"]
d = df.join(st, how="inner").join(ek).join(ml)
d = d[(d.date >= "2021-07-01") & (d.date < "2026-07-01") & d.mH.notna() & d.mOver.notna() & d.gbm_H.notna()].copy()
d["week"] = d.date.dt.strftime("%G-%V")
y = outcome_index(d.hg, d.ag); yo = ((d.hg + d.ag) > 2.5).to_numpy().astype(float)
P = lambda n: d[[f"{n}_H", f"{n}_D", f"{n}_A"]].to_numpy()
ll = {n: logloss3(P(n), y) for n in ("S0", "S1", "S2", "S3", "ekf", "ekfm", "sot", "gbm", "stack_ekf")}
ll["m"] = logloss3(d[["mH", "mD", "mA"]].to_numpy(), y)
llo = {n: logloss2(d[f"{n}_over"].to_numpy(), yo) for n in ("S0", "S1", "ekf", "sot")}
llo["m"] = logloss2(d.mOver.to_numpy(), yo)
full = d["div"].isin(FULL).to_numpy()
out = {}
for name, a, b in (("ekf-S0", "ekf", "S0"), ("sot-ekf", "sot", "ekf"), ("sot-S0", "sot", "S0"), ("S2-S1", "S2", "S1"),
                   ("S3-S2", "S3", "S2"), ("gbm-ekf", "gbm", "ekf"), ("ekfm-S1", "ekfm", "S1")):
    for scope, mk in (("full", full), ("all", np.ones(len(d), bool))):
        out[f"{name}|{scope}"] = paired((ll[a] - ll[b])[mk], d.week.to_numpy()[mk])
for name, a, b in (("ou ekf-S0", "ekf", "S0"), ("ou sot-ekf", "sot", "ekf"), ("ou S1-m", "S1", "m"), ("ou sot-S0", "sot", "S0")):
    for scope, mk in (("full", full), ("all", np.ones(len(d), bool))):
        out[f"{name}|{scope}"] = paired((llo[a] - llo[b])[mk], d.week.to_numpy()[mk])
for dv in ("SP1", "SP2", "I1", "E0", "D1"):
    mk = (d["div"] == dv).to_numpy()
    out[f"S2-S1|{dv}"] = paired((ll["S2"] - ll["S1"])[mk], d.week.to_numpy()[mk])
by_season = {}
for s, g in d.groupby("season"):
    ix = d.index.get_indexer(g.index)
    by_season[int(s)] = {"ekf-S0": float((ll["ekf"] - ll["S0"])[ix].mean()), "sot-S0": float((ll["sot"] - ll["S0"])[ix].mean()), "n": len(g)}
out["by_season"] = by_season
out["sot_ll_full"] = float(ll["sot"][full].mean()); out["sot_ll_all"] = float(ll["sot"].mean())
out["sot_ou_all"] = float(llo["sot"].mean())
# EV anunciado vs realizado para el modelo del repo (S1) contra bet365
o1 = d[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
rows = []
for j in range(3):
    pj = P("S1")[:, j]; ev = pj * o1[:, j] - 1
    ok = (ev >= 0.03) & (o1[:, j] >= 1.4) & (o1[:, j] <= 3.6)
    rows.append(pd.DataFrame({"ev": ev[ok], "pl": np.where(y[ok] == j, o1[ok, j] - 1, -1.0), "week": d.week.to_numpy()[ok]}))
b = pd.concat(rows)
b["bin"] = pd.cut(b.ev, [0.03, 0.06, 0.10, 0.20, 10], labels=["3-6 %", "6-10 %", "10-20 %", ">20 %"])
evbins = []
for lab, g in b.groupby("bin", observed=True):
    r, se = paired(g.pl.to_numpy(), g.week.to_numpy())
    evbins.append({"bin": str(lab), "n": len(g), "ev": g.ev.mean(), "roi": r, "se": se})
out["ev_bins_S1_1x2"] = evbins
# Peso aprendido del modelo en el apilado: refit en todo el test para ver coeficientes
from sklearn.linear_model import LogisticRegression
X = np.log(np.column_stack([P("ekf"), d[["mH", "mD", "mA"]].to_numpy()]))
lr = LogisticRegression(C=1.0, max_iter=3000).fit(X, y)
out["stack_coef"] = lr.coef_.round(3).tolist()
json.dump(out, open(f"{SP}/data/summary2.json", "w"), indent=1, default=float)
for k_, v in out.items():
    print(k_, v if not isinstance(v, tuple) else (round(v[0], 4), round(v[1], 4)))
