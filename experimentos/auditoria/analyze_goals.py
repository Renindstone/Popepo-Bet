"""Tablas de resultados de goles y resultado (test 2021-07 a 2026-07) y simulación de apuestas."""
import json
import sys

import numpy as np
import pandas as pd

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import FULL, SP, brier3, ece, load, logloss2, logloss3, outcome_index, paired, rps3  # noqa: E402

df = load()
st = pd.read_parquet(f"{SP}/data/static_2016-07-01_2026-07-01.parquet")
ml = pd.read_parquet(f"{SP}/data/ml_preds.parquet")
ek = pd.read_parquet(f"{SP}/data/ekf_probs.parquet")
d = df.join(st, how="inner").join(ml, how="left").join(ek, how="left")
d = d[(d.date >= "2021-07-01") & (d.date < "2026-07-01") & d.mH.notna() & d.mOver.notna() & d.ekfm_H.notna()
      & d.gbm_H.notna()].copy()
d["week"] = d.date.dt.strftime("%G-%V")
y = outcome_index(d.hg, d.ag)
yo = ((d.hg + d.ag) > 2.5).to_numpy().astype(float)

# Mezcla fija del repo (25 % modelo + 75 % mercado), con bet365 como "mercado" (no hay Pinnacle aquí)
for k in "HDA":
    d[f"blend_{k}"] = 0.25 * d[f"S1_{k}"] + 0.75 * d[f"m{k}"]
d["blend_over"] = 0.25 * d.S1_over + 0.75 * d.mOver

MODELS = {"S0": "Repo sin mercado", "S1": "Repo con mercado (como producción)", "S2": "S1 + ventaja local por liga",
          "S3": "S2 + nivel por liga", "ekf": "Bayesiano dinámico (solo goles)", "ekfm": "Bayesiano dinámico + mercado",
          "gbm": "LightGBM sin cuotas", "gbm_mkt": "LightGBM con cuotas", "blend": "Mezcla fija 25/75 del repo",
          "stack_ekf": "Apilado aprendido (dinámico + mercado)", "stack_ekfm": "Apilado aprendido (dinámico+M + mercado)",
          "m": "bet365 sin margen"}


def probs(name):
    if name == "m":
        return d[["mH", "mD", "mA"]].to_numpy()
    return d[[f"{name}_H", f"{name}_D", f"{name}_A"]].to_numpy()


def over(name):
    if name == "m":
        return d.mOver.to_numpy()
    c = f"{name}_over"
    return d[c].to_numpy() if c in d else None


out = {"n_all": int(len(d)), "n_full": int(d["div"].isin(FULL).sum()), "tables": {}}
for scope, mask in (("full", d["div"].isin(FULL).to_numpy()), ("all", np.ones(len(d), bool))):
    rows = []
    ref_ll = logloss3(probs("m"), y)
    rep_ll = logloss3(probs("S1"), y)
    for k, label in MODELS.items():
        P = probs(k)
        ll = logloss3(P, y)
        dm, se = paired((ll - ref_ll)[mask], d.week.to_numpy()[mask])
        dr, ser = paired((ll - rep_ll)[mask], d.week.to_numpy()[mask])
        po = over(k)
        row = {"modelo": label, "key": k, "n": int(mask.sum()), "logloss": ll[mask].mean(), "rps": rps3(P, y)[mask].mean(),
               "brier": brier3(P, y)[mask].mean(), "vs_bet365": dm, "se_vs_bet365": se, "vs_repo": dr, "se_vs_repo": ser,
               "ece_home": ece(P[mask, 0], (y[mask] == 0).astype(float)), "draw_pred": P[mask, 1].mean(),
               "draw_obs": (y[mask] == 1).mean()}
        if po is not None:
            llo = logloss2(po, yo)
            dmo, seo = paired((llo - logloss2(over("m"), yo))[mask], d.week.to_numpy()[mask])
            row.update({"logloss_ou": llo[mask].mean(), "ou_vs_bet365": dmo, "se_ou": seo, "over_pred": po[mask].mean(),
                        "over_obs": yo[mask].mean()})
        rows.append(row)
    out["tables"][scope] = rows

# Sesgo por liga: goles totales esperados vs reales, más de 2,5 previsto vs real, ventaja local
bias = []
for dv, g in d.groupby("div"):
    yy = ((g.hg + g.ag) > 2.5).mean()
    bias.append({"div": dv, "n": len(g), "goals_obs": (g.hg + g.ag).mean(),
                 "S0_goals": (g.S0_lh + g.S0_la).mean(), "S1_goals": (g.S1_lh + g.S1_la).mean(),
                 "S3_goals": (g.S3_lh + g.S3_la).mean(), "ekf_goals": (g.ekf_lh + g.ekf_la).mean(),
                 "over_obs": yy, "S0_over": g.S0_over.mean(), "S1_over": g.S1_over.mean(), "S3_over": g.S3_over.mean(),
                 "m_over": g.mOver.mean(),
                 "home_ratio_obs": g.hg.sum() / max(g.ag.sum(), 1), "S1_home_ratio": g.S1_lh.sum() / g.S1_la.sum(),
                 "S2_home_ratio": g.S2_lh.sum() / g.S2_la.sum(), "S1_hfa": g.S1_hfa.mean(), "S2_hfaL": g.S2_hfaL.mean()})
out["league_bias"] = bias

# Calibración del empate por tramos
cal = []
for k in ("S1", "ekfm", "m"):
    P = probs(k)[:, 1]
    edges = np.quantile(P, np.linspace(0, 1, 6))
    idx = np.clip(np.searchsorted(edges, P, side="right") - 1, 0, 4)
    for b in range(5):
        mm = idx == b
        cal.append({"model": k, "bin": b, "pred": P[mm].mean(), "obs": (y[mm] == 1).mean(), "n": int(mm.sum())})
out["draw_calibration"] = cal

# --------------------------------------------------------------------------- apuestas contra bet365
o1 = d[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
oou = d[["Over25", "Under25"]].to_numpy(float)
mx1 = d[["MaxHome", "MaxDraw", "MaxAway"]].to_numpy(float)
mxou = d[["MaxOver25", "MaxUnder25"]].to_numpy(float)


def bets_for(name, odds1, oddsou, min_ev=0.03, lo=1.4, hi=3.6):
    P = probs(name); po = over(name)
    rec = []
    for j in range(3):
        ev = P[:, j] * odds1[:, j] - 1
        ok = (ev >= min_ev) & (odds1[:, j] >= lo) & (odds1[:, j] <= hi)
        win = (y == j)
        rec.append(pd.DataFrame({"i": np.where(ok)[0], "ev": ev[ok], "odds": odds1[ok, j], "prob": P[ok, j],
                                 "pl": np.where(win[ok], odds1[ok, j] - 1, -1.0), "mkt": "1x2"}))
    if po is not None:
        for j, pp in enumerate((po, 1 - po)):
            ev = pp * oddsou[:, j] - 1
            ok = (ev >= min_ev) & (oddsou[:, j] >= lo) & (oddsou[:, j] <= hi)
            win = (yo == 1) if j == 0 else (yo == 0)
            rec.append(pd.DataFrame({"i": np.where(ok)[0], "ev": ev[ok], "odds": oddsou[ok, j], "prob": pp[ok],
                                     "pl": np.where(win[ok], oddsou[ok, j] - 1, -1.0), "mkt": "ou25"}))
    b = pd.concat(rec)
    b["week"] = d.week.to_numpy()[b.i]
    b["date"] = d.date.to_numpy()[b.i]
    b["full"] = d["div"].isin(FULL).to_numpy()[b.i]
    return b


bet_rows = []
for name in ("S1", "blend", "ekfm", "stack_ekfm", "gbm", "gbm_mkt"):
    for book, odds1, oddsou in (("bet365", o1, oou), ("max", mx1, mxou)):
        b = bets_for(name, odds1, oddsou)
        if b.empty:
            continue
        roi, se = paired(b.pl.to_numpy(), b.week.to_numpy())
        bet_rows.append({"model": name, "book": book, "bets": len(b), "roi": roi, "se": se, "avg_ev": b.ev.mean(),
                         "avg_odds": b.odds.mean()})
        # Apuesta del día: la de mayor EV por día con las reglas de producción (cuota 1,5-2,6, prob>=0,42, EV>=3 %)
        p = b[(b.odds >= 1.5) & (b.odds <= 2.6) & (b.prob >= 0.42)]
        pod = p.sort_values("ev").groupby("date").tail(1)
        if len(pod):
            r2, s2 = paired(pod.pl.to_numpy(), pod.week.to_numpy())
            bet_rows.append({"model": name + " (apuesta del día)", "book": book, "bets": len(pod), "roi": r2, "se": s2,
                             "avg_ev": pod.ev.mean(), "avg_odds": pod.odds.mean()})
out["betting"] = bet_rows
json.dump(out, open(f"{SP}/data/goals_results.json", "w"), indent=1, default=float)

pd.set_option("display.width", 220)
for scope in ("full", "all"):
    t = pd.DataFrame(out["tables"][scope]).set_index("modelo")
    print(f"\n== {scope} (n={t.n.iloc[0]})")
    print(t[["logloss", "rps", "vs_bet365", "se_vs_bet365", "vs_repo", "se_vs_repo", "logloss_ou", "ou_vs_bet365",
             "se_ou", "draw_pred", "draw_obs", "over_pred", "over_obs"]].round(4).to_string())
print(pd.DataFrame(bias).round(3).to_string())
print(pd.DataFrame(cal).round(3).to_string())
print(pd.DataFrame(bet_rows).round(4).to_string())
