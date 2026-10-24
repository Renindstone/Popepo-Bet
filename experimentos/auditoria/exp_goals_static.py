"""Walk-forward semanal del modelo de goles del repo y variantes (temporadas 2021-22 a 2025-26).

S0  repo sin mercado (goles, L2=2, ventaja local global, vida media 240 días)
S1  repo con mercado (observaciones de goles implícitos de las cuotas de partidos ya jugados, peso 128, 14 días)
S2  S1 + ventaja local propia de cada liga
S3  S2 + L2 hacia el nivel de cada liga (no hacia la media global)
"""
import sys
import time

import numpy as np
import pandas as pd

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import FULL, SP, dc_probs, fit_ext, fit_rho, load, predict_ext, time_w  # noqa: E402

from apuestas.models import market  # noqa: E402

df = load()
n = int(max(df.h.max(), df.a.max()) + 1)
nL = int(df.L.max() + 1)

# Goles implícitos de las cuotas (como fitting.load_market_goals, con bet365 previa en lugar del cierre de Pinnacle)
ok = df[["mH", "mD", "mA"]].notna().all(axis=1).to_numpy()
lam, rmse = market.implied_goals(df.loc[ok, ["mH", "mD", "mA"]].to_numpy(), df.loc[ok, "mOver"].to_numpy())
df["imp_h"], df["imp_a"] = np.nan, np.nan
good = np.where(ok)[0][rmse <= 0.02]
df.loc[good, "imp_h"] = lam[rmse <= 0.02, 0]
df.loc[good, "imp_a"] = lam[rmse <= 0.02, 1]
print(f"goles implícitos: {len(good)} de {ok.sum()} partidos con cuotas (RMSE<=0.02)", flush=True)

days = (df.date - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
H, A, HG, AG, LM = df.h.to_numpy(), df.a.to_numpy(), df.hg.to_numpy(float), df.ag.to_numpy(float), df.L.to_numpy()
IH, IA = df.imp_h.to_numpy(), df.imp_a.to_numpy()
full_mask = df["div"].isin(FULL).to_numpy()

VARIANTS = {
    "S0": dict(market=False, league_hfa=False, league_center=False),
    "S1": dict(market=True, league_hfa=False, league_center=False),
    "S2": dict(market=True, league_hfa=True, league_center=False),
    "S3": dict(market=True, league_hfa=True, league_center=True),
}
start, end = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2021-07-01"), pd.Timestamp(
    sys.argv[2] if len(sys.argv) > 2 else "2026-07-01")
out_rows = []
theta_prev = {k: None for k in VARIANTS}
cur = start
t0 = time.time()
while cur < end:
    nxt = cur + pd.Timedelta(days=7)
    c = (cur - pd.Timestamp("2000-01-01")).days
    tr = np.where((days < c) & (days >= c - 1100))[0]
    te = np.where((days >= c) & (days < c + 7))[0]
    if len(te) == 0:
        cur = nxt
        continue
    # Liga actual de cada equipo = la de su último partido antes del corte
    last = pd.Series(LM[tr]).groupby(np.concatenate([H[tr]])).last()
    last2 = pd.Series(LM[tr]).groupby(A[tr]).last()
    Lt = np.zeros(n, dtype=int)
    Lt[last2.index] = last2.values
    Lt[last.index] = last.values
    # Equipos de test sin pasado: su liga
    Lt[H[te]] = np.where(np.isin(H[te], tr_teams := np.union1d(H[tr], A[tr])), Lt[H[te]], LM[te])
    Lt[A[te]] = np.where(np.isin(A[te], tr_teams), Lt[A[te]], LM[te])
    age = c - days[tr]
    w_real = time_w(age, 240.0)
    mk = tr[np.isfinite(IH[tr])]
    w_mk = time_w(c - days[mk], 14.0) * 128.0
    rec = {"idx": te}
    for name, v in VARIANTS.items():
        if v["market"]:
            hi = np.concatenate([H[tr], H[mk]]); ai = np.concatenate([A[tr], A[mk]])
            yh = np.concatenate([HG[tr], IH[mk]]); ya = np.concatenate([AG[tr], IA[mk]])
            w = np.concatenate([w_real, w_mk]); lm = np.concatenate([LM[tr], LM[mk]])
        else:
            hi, ai, yh, ya, w, lm = H[tr], A[tr], HG[tr], AG[tr], w_real, LM[tr]
        params, theta_prev[name] = fit_ext(hi, ai, yh, ya, np.ones(len(hi)), w, lm, Lt, nL, n, l2=2.0,
                                           league_hfa=v["league_hfa"], league_center=v["league_center"],
                                           theta0=theta_prev[name])
        # rho como el repo: partidos de las ligas completas de los últimos 730 días
        rr = tr[(age <= 730) & full_mask[tr]]
        lh_tr, la_tr = predict_ext(params, H[rr], A[rr], LM[rr])
        rho = fit_rho(lh_tr, la_tr, HG[rr], AG[rr])
        lh, la = predict_ext(params, H[te], A[te], LM[te])
        pr = dc_probs(lh, la, rho)
        rec[f"{name}_lh"], rec[f"{name}_la"], rec[f"{name}_rho"] = lh, la, np.full(len(te), rho)
        rec[f"{name}_H"], rec[f"{name}_D"], rec[f"{name}_A"], rec[f"{name}_over"] = pr["H"], pr["D"], pr["A"], pr["over"]
        if name in ("S0", "S1", "S2"):
            rec[f"{name}_hfa"] = np.full(len(te), params[1])
        if v["league_hfa"]:
            rec[f"{name}_hfaL"] = params[1] + params[4][LM[te]]
    out_rows.append(pd.DataFrame(rec))
    if len(out_rows) % 10 == 0:
        print(f"{cur.date()} {len(out_rows)} semanas, {time.time() - t0:.0f}s", flush=True)
    cur = nxt

res = pd.concat(out_rows).set_index("idx")
res.to_parquet(f"{SP}/data/static_{start.date()}_{end.date()}.parquet")
print("listo", len(res), f"{time.time() - t0:.0f}s")
