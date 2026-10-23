"""EKF con los mejores hiperparámetros (validación 2016-21) y variante con observaciones del mercado."""
import sys, json, time
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from ekf_eval import *
from exp_common import fit_rho
from apuestas.models import market
df = load()
best = json.loads(open(f"{SP}/data/ekf_tune.log").read().split("BEST ")[1].splitlines()[0])
kw = {k: v for k, v in best.items() if k not in ("ll", "ll_ou", "ll_full")}
print("mejores", kw, flush=True)
pred = run_ekf(df, **kw)
pred.to_parquet(f"{SP}/data/ekf_best.parquet")
# rho estimado en validación con las medias del EKF
v = (df.date >= "2016-07-01") & (df.date < "2021-07-01")
lh = np.exp(pred.eta_h + 0.5 * pred.var_h)[v]; la = np.exp(pred.eta_a + 0.5 * pred.var_a)[v]
rho = fit_rho(lh.to_numpy(), la.to_numpy(), df.hg[v].to_numpy(), df.ag[v].to_numpy())
open(f"{SP}/data/ekf_rho.txt", "w").write(str(rho))
print("rho", rho, "valid", evaluate(df, pred, "2016-07-01", "2021-07-01", rho=rho), flush=True)
# goles implícitos de las cuotas previas (como observación de partidos ya jugados)
ok = df[["mH", "mD", "mA"]].notna().all(axis=1).to_numpy()
lam, rmse = market.implied_goals(df.loc[ok, ["mH", "mD", "mA"]].to_numpy(), df.loc[ok, "mOver"].to_numpy())
ih = np.full(len(df), np.nan); ia = np.full(len(df), np.nan)
good = np.where(ok)[0][rmse <= 0.02]
ih[good] = lam[rmse <= 0.02, 0]; ia[good] = lam[rmse <= 0.02, 1]
res = []
for s in [0.08, 0.15, 0.3]:
    t = time.time()
    p = run_ekf(df, **kw, s_mkt=s, imp_h=ih, imp_a=ia)
    ll = evaluate(df, p, "2016-07-01", "2021-07-01", rho=rho)
    res.append((ll[0], s, p))
    print("s_mkt", s, ll, round(time.time() - t), flush=True)
ll, s, p = min(res, key=lambda x: x[0])
p.to_parquet(f"{SP}/data/ekf_mkt_best.parquet")
open(f"{SP}/data/ekf_smkt.txt", "w").write(str(s))
print("mejor s_mkt", s)
