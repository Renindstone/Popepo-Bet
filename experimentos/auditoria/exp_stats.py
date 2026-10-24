"""Modelos de estadísticas (tarjetas, faltas, córners, remates, remates a puerta) con datos de 14 ligas.

C0  repo: ratings.fit con todas las ligas juntas (sin nivel de liga), NB con alfa por momentos, total = convolución
C1  + nivel y ventaja local de cada liga
C2  C1 + total con dispersión calibrada fuera de muestra (recoge la correlación entre los dos equipos)
C3  C2 + covariables del partido sacadas de las cuotas (superioridad y total esperado de goles)
GB  LightGBM (Poisson) por equipo con medias móviles, liga, cuotas y Elo; total NB calibrado fuera de muestra
Base: media de la liga (365 días) con NB.  Reajuste mensual. Test 2021-07 a 2026-06.
"""
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import FULL, SP, fit_ext, load, predict_ext, time_w  # noqa: E402

from apuestas.models import market, ratings  # noqa: E402
from apuestas.models.ratings import MatchObs  # noqa: E402

STATS = {"cards": ("HomeYellow", "AwayYellow", "HomeRed", "AwayRed"), "fouls": ("HomeFouls", "AwayFouls"),
         "corners": ("HomeCorners", "AwayCorners"), "shots": ("HomeShots", "AwayShots"),
         "sot": ("HomeTarget", "AwayTarget")}

df = load()
df = df[df.season >= 2017].reset_index(drop=True)
for st, cols in STATS.items():
    if st == "cards":
        df[f"{st}_h"] = df[cols[0]] + df[cols[2]]
        df[f"{st}_a"] = df[cols[1]] + df[cols[3]]
    else:
        df[f"{st}_h"], df[f"{st}_a"] = df[cols[0]], df[cols[1]]
# goles implícitos de las cuotas del propio partido (covariables previas al partido)
ok = df[["mH", "mD", "mA"]].notna().all(axis=1).to_numpy()
lam, rmse = market.implied_goals(df.loc[ok, ["mH", "mD", "mA"]].to_numpy(), df.loc[ok, "mOver"].to_numpy())
df["imp_h"], df["imp_a"] = np.nan, np.nan
df.loc[np.where(ok)[0], "imp_h"] = lam[:, 0]
df.loc[np.where(ok)[0], "imp_a"] = lam[:, 1]
n = int(max(df.h.max(), df.a.max()) + 1)
nL = int(df.L.max() + 1)
days = (df.date - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
H, A, LM = df.h.to_numpy(), df.a.to_numpy(), df.L.to_numpy()


def nb_pmf_total(mean, alpha, kmax=120):
    k = np.arange(kmax)
    if alpha <= 1e-6:
        return poisson.pmf(k[None, :], mean[:, None])
    r = 1 / alpha
    return nbinom.pmf(k[None, :], r, r / (r + mean[:, None]))


def conv_total(mh, ma, alpha, kmax=120):
    """Total como suma de dos NB independientes (lo que hace el repo)."""
    k = np.arange(kmax)
    if alpha <= 1e-6:
        ph = poisson.pmf(k[None, :], mh[:, None]); pa = poisson.pmf(k[None, :], ma[:, None])
    else:
        r = 1 / alpha
        ph = nbinom.pmf(k[None, :], r, r / (r + mh[:, None])); pa = nbinom.pmf(k[None, :], r, r / (r + ma[:, None]))
    out = np.zeros((len(mh), kmax))
    for i in range(len(mh)):
        out[i] = np.convolve(ph[i], pa[i])[:kmax]
    return out


def alpha_moments(y, mu):
    return max(float(np.sum((y - mu) ** 2 - mu) / max(np.sum(mu ** 2), 1e-9)), 0.0)


def team_rolling(df, st, nwin=10):
    """Medias móviles por equipo (últimos n partidos, sin el actual) de lo que genera y concede."""
    rows = pd.concat([
        pd.DataFrame({"i": df.index, "team": df.h, "date": df.date, "f": df[f"{st}_h"], "c": df[f"{st}_a"],
                      "gf": df.hg, "ga": df.ag}),
        pd.DataFrame({"i": df.index, "team": df.a, "date": df.date, "f": df[f"{st}_a"], "c": df[f"{st}_h"],
                      "gf": df.ag, "ga": df.hg})]).sort_values(["team", "date", "i"])
    g = rows.groupby("team")
    for col in ("f", "c", "gf", "ga"):
        rows[f"r_{col}"] = g[col].transform(lambda s: s.shift(1).rolling(nwin, min_periods=3).mean())
    rows["n_prev"] = g.cumcount()
    return rows


results = []
LINES = {'cards': [2.5, 3.5, 4.5, 5.5, 6.5], 'fouls': [18.5, 20.5, 22.5, 24.5, 26.5, 28.5], 'corners': [7.5, 8.5, 9.5, 10.5, 11.5, 12.5], 'shots': [20.5, 22.5, 24.5, 26.5, 28.5, 30.5], 'sot': [6.5, 7.5, 8.5, 9.5, 10.5, 11.5]}
t0 = time.time()
months = pd.date_range("2019-07-01", "2026-07-01", freq="MS")
for st in STATS:
    yh_all, ya_all = df[f"{st}_h"].to_numpy(float), df[f"{st}_a"].to_numpy(float)
    has = np.isfinite(yh_all) & np.isfinite(ya_all)
    oos_hist = {"C1": [], "C3": []}  # (media, total) fuera de muestra para calibrar la dispersión del total
    theta_prev = None
    for mi in range(len(months) - 1):
        cur, nxt = months[mi], months[mi + 1]
        c = (cur - pd.Timestamp("2000-01-01")).days
        cn = (nxt - pd.Timestamp("2000-01-01")).days
        tr = np.where(has & (days < c) & (days >= c - 1100))[0]
        te = np.where(has & (days >= c) & (days < cn))[0]
        if len(te) == 0 or len(tr) < 1000:
            continue
        age = c - days[tr]
        # --- C0: código del repo
        obs = [MatchObs(int(H[i]), int(A[i]), df.date.iat[i].date(), yh_all[i], ya_all[i]) for i in tr]
        rm = ratings.fit(obs, cur.date(), half_life_days=240.0, l2=1.0)
        mh0 = np.array([rm.expected(int(H[i]), int(A[i]))[0] for i in te])
        ma0 = np.array([rm.expected(int(H[i]), int(A[i]))[1] for i in te])
        # --- C1: nivel y ventaja local por liga
        Lt = np.zeros(n, dtype=int)
        s_last = pd.Series(np.concatenate([LM[tr], LM[tr]]),
                           index=np.concatenate([H[tr], A[tr]]))
        order = np.argsort(np.concatenate([days[tr], days[tr]]), kind="stable")
        s_last = s_last.iloc[order]
        lastL = s_last.groupby(level=0).last()
        Lt[lastL.index] = lastL.values
        new_h = ~np.isin(H[te], lastL.index); new_a = ~np.isin(A[te], lastL.index)
        Lt[H[te][new_h]] = LM[te][new_h]; Lt[A[te][new_a]] = LM[te][new_a]
        w = time_w(age, 240.0)
        params, theta_prev = fit_ext(H[tr], A[tr], yh_all[tr], ya_all[tr], np.ones(len(tr)), w, LM[tr], Lt, nL, n,
                                     l2=1.0, league_hfa=True, league_center=True, theta0=theta_prev)
        mh1, ma1 = predict_ext(params, H[te], A[te], LM[te])
        lh_tr, la_tr = predict_ext(params, H[tr], A[tr], LM[tr])
        a_team = alpha_moments(np.concatenate([yh_all[tr], ya_all[tr]]), np.concatenate([lh_tr, la_tr]))
        # --- C3: covariables de las cuotas (superioridad y total) con offset del modelo C1
        def cov(ix, home):
            ih, ia = df.imp_h.to_numpy()[ix], df.imp_a.to_numpy()[ix]
            sup = (ih - ia) if home else (ia - ih)
            tot = np.log((ih + ia) / 2.7)
            X = np.column_stack([sup, np.abs(sup), tot])
            return np.nan_to_num(X)
        Xtr = np.vstack([cov(tr, True), cov(tr, False)])
        off = np.log(np.concatenate([lh_tr, la_tr]))
        ytr = np.concatenate([yh_all[tr], ya_all[tr]])
        wtr = np.concatenate([w, w])
        beta = np.zeros(3)
        for _ in range(25):
            mu = np.exp(off + Xtr @ beta)
            g = Xtr.T @ (wtr * (ytr - mu)); Hs = (Xtr * (wtr * mu)[:, None]).T @ Xtr + 1e-6 * np.eye(3)
            step = np.linalg.solve(Hs, g); beta += step
            if np.max(np.abs(step)) < 1e-8:
                break
        mh3 = mh1 * np.exp(cov(te, True) @ beta); ma3 = ma1 * np.exp(cov(te, False) @ beta)
        # --- dispersión del total calibrada fuera de muestra (o en muestra si aún no hay historial)
        def alpha_total(key, fallback_mu, fallback_y):
            hist = oos_hist[key][-1500:]
            if len(hist) >= 500:
                mu_, y_ = np.array(hist).T
                return alpha_moments(y_, mu_)
            return alpha_moments(fallback_y, fallback_mu)
        ytot_tr = yh_all[tr] + ya_all[tr]
        aT1 = alpha_total("C1", lh_tr + la_tr, ytot_tr)
        mu3_tr = lh_tr * np.exp(cov(tr, True) @ beta) + la_tr * np.exp(cov(tr, False) @ beta)
        aT3 = alpha_total("C3", mu3_tr, ytot_tr)
        # --- base: media de la liga en 365 días
        base_mu = np.zeros(len(te)); rec_tr = tr[age <= 365]
        lg_mean = pd.Series(ytot_tr[age <= 365]).groupby(LM[rec_tr]).mean()
        base_mu = lg_mean.reindex(LM[te]).to_numpy()
        base_mu = np.where(np.isfinite(base_mu), base_mu, ytot_tr.mean())
        a_base = alpha_moments(ytot_tr[age <= 365], lg_mean.reindex(LM[rec_tr]).to_numpy())
        ytot = (yh_all[te] + ya_all[te]).astype(int)
        pm = {
            "C0": conv_total(mh0, ma0, rm.dispersion),
            "C1": conv_total(mh1, ma1, a_team),
            "C2": nb_pmf_total(mh1 + ma1, aT1),
            "C3": nb_pmf_total(mh3 + ma3, aT3),
            "base": nb_pmf_total(base_mu, a_base),
        }
        rng = np.random.default_rng(mi)
        u = rng.random(len(te))
        block = {"stat": np.full(len(te), st), "i": te, "div": df["div"].to_numpy()[te], "date": df.date.to_numpy()[te],
                 "y": ytot}
        kk = np.arange(120)
        for k, v in pm.items():
            cdf = v.cumsum(1)
            block[f"mu_{k}"] = (kk * v).sum(1)
            block[f"ll_{k}"] = np.log(np.clip(v[np.arange(len(te)), ytot], 1e-12, None))
            lo = np.where(ytot > 0, cdf[np.arange(len(te)), np.maximum(ytot - 1, 0)], 0.0)
            block[f"pit_{k}"] = lo + u * (cdf[np.arange(len(te)), ytot] - lo)
            for L in LINES[st]:
                block[f"ov{L}_{k}"] = 1 - cdf[:, int(L)]
        results.append(pd.DataFrame(block))
        oos_hist["C1"] += list(zip(mh1 + ma1, ytot))
        oos_hist["C3"] += list(zip(mh3 + ma3, ytot))
    print(st, f"{time.time() - t0:.0f}s", flush=True)

res = pd.concat(results, ignore_index=True)
res.to_pickle(f"{SP}/data/stats_results.pkl")
print("listo", len(res))
