"""Prueba con datos reales de los cambios del 21 y 22 de octubre en los modelos de conteo de app-apuestas.

Variantes (reajuste mensual, 14 ligas, prueba 2021-07 a 2026-09):
  viejo     ratings.fit con L2 = 1 (antes del 21-10)
  nuevo     fitting.fit_counts: contracción en partidos y, en remates y córners, fuerza del modelo de goles (21-10)
  reparto   nuevo + fitting.strength_shift con el 1X2 PREVIO de bet365 del partido (22-10; el backtest del repo usa
            el cierre, que ya conoce las alineaciones)
  nivel     reparto + nivel de liga dinámico: factor (reales + K) / (esperados + K) con los errores fuera de muestra de
            los últimos 45 días de esa liga (se actualiza cada semana)
Métrica: log-verosimilitud de cada equipo (NB con la dispersión del modelo) y del total, frente a la media de la liga
de los últimos 365 días (local y visitante por separado). Sesgo de la media por temporada.
"""
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import SP, load, time_w  # noqa: E402

from apuestas.models import fitting, market, ratings  # noqa: E402
from apuestas.models.ratings import MatchObs  # noqa: E402

STATS = {"shots": ("HomeShots", "AwayShots"), "shots_on_target": ("HomeTarget", "AwayTarget"),
         "corners": ("HomeCorners", "AwayCorners"), "fouls": ("HomeFouls", "AwayFouls"), "cards": None}
LEVEL_DAYS, LEVEL_K = 45, 40.0

df = load()
df = df[df.season >= 2017].reset_index(drop=True)
df["cards_h"] = df.HomeYellow + df.HomeRed
df["cards_a"] = df.AwayYellow + df.AwayRed
for st, cols in STATS.items():
    if cols:
        df[f"{st}_h"], df[f"{st}_a"] = df[cols[0]], df[cols[1]]
ok = df[["mH", "mD", "mA"]].notna().all(axis=1).to_numpy()
lam, rmse = market.implied_goals(df.loc[ok, ["mH", "mD", "mA"]].to_numpy(), df.loc[ok, "mOver"].to_numpy())
df["imp_h"], df["imp_a"] = np.nan, np.nan
good = np.where(ok)[0][rmse <= fitting.MARKET_MAX_RMSE]
df.loc[good, "imp_h"] = lam[rmse <= fitting.MARKET_MAX_RMSE, 0]
df.loc[good, "imp_a"] = lam[rmse <= fitting.MARKET_MAX_RMSE, 1]
days = (df.date - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
H, A, LM, HG, AG = df.h.to_numpy(), df.a.to_numpy(), df.L.to_numpy(), df.hg.to_numpy(float), df.ag.to_numpy(float)
IH, IA = df.imp_h.to_numpy(), df.imp_a.to_numpy()
dates = df.date.dt.date.to_numpy()


def logpmf(k, m, a):
    m = np.maximum(m, 1e-6)
    if a <= 1e-6:
        return poisson.logpmf(k, m)
    r = 1 / a
    return nbinom.logpmf(k, r, r / (r + m))


def total_logpmf(y, mh, ma, a, kmax=120):
    k = np.arange(kmax)
    if a <= 1e-6:
        ph, pa = poisson.pmf(k[None, :], mh[:, None]), poisson.pmf(k[None, :], ma[:, None])
    else:
        r = 1 / a
        ph = nbinom.pmf(k[None, :], r, r / (r + mh[:, None])); pa = nbinom.pmf(k[None, :], r, r / (r + ma[:, None]))
    out = np.empty(len(y))
    for i in range(len(y)):
        out[i] = np.log(max(np.convolve(ph[i], pa[i])[int(y[i])], 1e-12))
    return out


months = pd.date_range("2021-07-01", "2026-10-01", freq="MS")
blocks = []
t0 = time.time()
oos = {st: [] for st in STATS}  # (día, liga, total real, total esperado por "reparto") para el nivel dinámico
for mi in range(len(months) - 1):
    cur, nxt = months[mi], months[mi + 1]
    c, cn = (cur - pd.Timestamp("2000-01-01")).days, (nxt - pd.Timestamp("2000-01-01")).days
    tr = np.where((days < c) & (days >= c - 1100))[0]
    te_all = np.where((days >= c) & (days < cn))[0]
    if len(te_all) == 0:
        continue
    # modelo de goles como en producción (goles + observaciones del mercado de partidos jugados), para la fuerza
    mk = tr[np.isfinite(IH[tr])]
    gobs = [MatchObs(int(H[i]), int(A[i]), dates[i], HG[i], AG[i]) for i in tr]
    gobs += [MatchObs(int(H[i]), int(A[i]), dates[i], IH[i], IA[i], weight=fitting.MARKET_WEIGHT, market=True)
             for i in mk]
    gm = ratings.fit(gobs, cur.date(), half_life_days=240.0, market_half_life_days=fitting.MARKET_HALF_LIFE)
    strength = fitting.count_strength(gm)
    for st in STATS:
        yh, ya = df[f"{st}_h"].to_numpy(float), df[f"{st}_a"].to_numpy(float)
        has_tr = tr[np.isfinite(yh[tr]) & np.isfinite(ya[tr])]
        te = te_all[np.isfinite(yh[te_all]) & np.isfinite(ya[te_all])]
        if len(te) == 0 or len(has_tr) < 1000:
            continue
        obs = [MatchObs(int(H[i]), int(A[i]), dates[i], yh[i], ya[i]) for i in has_tr]
        old = fitting.fit_counts(obs, st, cur.date(), l2=1.0)
        new = fitting.fit_counts(obs, st, cur.date(), strength=strength)
        e_old = np.array([old.expected(int(H[i]), int(A[i])) for i in te])
        e_new = np.array([new.expected(int(H[i]), int(A[i])) for i in te])
        e_sh = e_new.copy()
        for j, i in enumerate(te):
            if np.isfinite(IH[i]) and int(H[i]) in gm.attack and int(A[i]) in gm.attack:
                delta = fitting.strength_delta((IH[i], IA[i]), gm.expected(int(H[i]), int(A[i])))
                e_sh[j] = fitting.strength_shift(new, e_new[j, 0], e_new[j, 1], delta)
        # nivel dinámico por liga, actualizado cada semana con los errores fuera de muestra
        lvl = np.ones(len(te))
        hist = pd.DataFrame(oos[st], columns=["day", "L", "y", "yhat"]) if oos[st] else None
        cache = {}
        for j, i in enumerate(te):
            if hist is None:
                break
            week_start = days[i] - ((days[i] - c) % 7)
            key = (LM[i], week_start)
            if key not in cache:
                h = hist[(hist.L == LM[i]) & (hist.day < week_start) & (hist.day >= week_start - LEVEL_DAYS)]
                cache[key] = 1.0
                if len(h):
                    mbar = h.yhat.mean()
                    cache[key] = (h.y.sum() + LEVEL_K * mbar) / (h.yhat.sum() + LEVEL_K * mbar)
            lvl[j] = cache[key]
        e_lv = e_sh * lvl[:, None]
        # base: media de la liga, local y visitante, últimos 365 días
        rec = has_tr[(c - days[has_tr]) <= 365]
        bh = pd.Series(yh[rec]).groupby(LM[rec]).mean().reindex(LM[te]).to_numpy()
        ba = pd.Series(ya[rec]).groupby(LM[rec]).mean().reindex(LM[te]).to_numpy()
        mh_rec = pd.Series(yh[rec]).groupby(LM[rec]).transform("mean").to_numpy()
        ma_rec = pd.Series(ya[rec]).groupby(LM[rec]).transform("mean").to_numpy()
        yy, mm = np.concatenate([yh[rec], ya[rec]]), np.concatenate([mh_rec, ma_rec])
        a_base = max(float(np.sum((yy - mm) ** 2 - mm) / np.sum(mm ** 2)), 0.0)
        yt_h, yt_a = yh[te].astype(int), ya[te].astype(int)
        block = {"stat": st, "i": te, "div": df["div"].to_numpy()[te], "date": df.date.to_numpy()[te],
                 "season": df.season.to_numpy()[te], "y": yt_h + yt_a, "has_odds": np.isfinite(IH[te])}
        for name, e, a in (("viejo", e_old, old.dispersion), ("nuevo", e_new, new.dispersion),
                           ("reparto", e_sh, new.dispersion), ("nivel", e_lv, new.dispersion),
                           ("base", np.column_stack([bh, ba]), a_base)):
            block[f"side_{name}"] = logpmf(yt_h, e[:, 0], a) + logpmf(yt_a, e[:, 1], a)
            block[f"tot_{name}"] = total_logpmf(yt_h + yt_a, e[:, 0], e[:, 1], a)
            block[f"mu_{name}"] = e[:, 0] + e[:, 1]
        blocks.append(pd.DataFrame(block))
        oos[st] += list(zip(days[te], LM[te], yt_h + yt_a, e_sh[:, 0] + e_sh[:, 1]))
    print(cur.date(), f"{time.time() - t0:.0f}s", flush=True)

res = pd.concat(blocks, ignore_index=True)
res.to_pickle(f"{SP}/data/conteos_nuevos.pkl")
print("listo", len(res))
