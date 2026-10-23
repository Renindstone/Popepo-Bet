"""¿Mejora la fuerza si se observa algo más que los goles? Objetivo = (1-w)·goles + w·k·remates a puerta
(el equivalente, sin xG, a lo que hace el repo con 85 % xG + 15 % goles)."""
import sys, json
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from ekf_eval import *
df = load()
best = json.loads(open(f"{SP}/data/ekf_tune.log").read().split("BEST ")[1].splitlines()[0])
kw = {k: v for k, v in best.items() if k not in ("ll", "ll_ou", "ll_full")}
rho = float(open(f"{SP}/data/ekf_rho.txt").read())
pre = df[(df.date < "2016-07-01") & df.HomeTarget.notna()]
k = (pre.hg.sum() + pre.ag.sum()) / (pre.HomeTarget.sum() + pre.AwayTarget.sum())
print("goles por remate a puerta", round(k, 4), flush=True)
sh, sa = df.HomeTarget.to_numpy(float), df.AwayTarget.to_numpy(float)
for w in (0.3, 0.5, 0.7, 0.85):
    yh = (1 - w) * df.hg.to_numpy() + w * k * sh
    ya = (1 - w) * df.ag.to_numpy() + w * k * sa
    p = run_ekf(df, **kw, y_obs=(yh, ya))
    v = evaluate(df, p, "2016-07-01", "2021-07-01", rho=rho)
    t = evaluate(df, p, "2021-07-01", "2026-07-01", rho=rho)
    print(json.dumps({"w": w, "valid_ll": v[0], "valid_ou": v[1], "test_ll": t[0], "test_ou": t[1]}), flush=True)
    if w == 0.5:
        p.to_parquet(f"{SP}/data/ekf_sot05.parquet")
p0 = pd.read_parquet(f"{SP}/data/ekf_best.parquet")
print(json.dumps({"w": 0, "valid": evaluate(df, p0, "2016-07-01", "2021-07-01", rho=rho), "test": evaluate(df, p0, "2021-07-01", "2026-07-01", rho=rho)}, default=float))
