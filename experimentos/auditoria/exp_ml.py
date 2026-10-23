"""Gradient boosting (LightGBM), apilado con el mercado y comparación final contra bet365.

Entrada: predicciones previas al partido de los modelos estructurales (estático del repo y bayesiano dinámico).
Esquema: ventana creciente, se entrena con temporadas anteriores y se predice la siguiente (2021-22 a 2025-26).
"""
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import SP, dc_probs, load, outcome_index  # noqa: E402

df = load()
ekf = pd.read_parquet(f"{SP}/data/ekf_best.parquet")  # eta_h, eta_a, var_h, var_a (solo goles)
ekfm = pd.read_parquet(f"{SP}/data/ekf_mkt_best.parquet")  # con observaciones del mercado
rho = float(open(f"{SP}/data/ekf_rho.txt").read())

for name, p in (("ekf", ekf), ("ekfm", ekfm)):
    lh = np.exp(p.eta_h + 0.5 * p.var_h).to_numpy(); la = np.exp(p.eta_a + 0.5 * p.var_a).to_numpy()
    ok = np.isfinite(lh)
    pr = dc_probs(np.where(ok, lh, 1.4), np.where(ok, la, 1.1), rho)
    df[f"{name}_lh"], df[f"{name}_la"] = lh, la
    for k in ("H", "D", "A", "over"):
        df[f"{name}_{k}"] = np.where(ok, pr[k], np.nan)
    df[f"{name}_var"] = (p.var_h + p.var_a).to_numpy()

# Medias móviles por equipo (últimos 10 partidos del archivo, sin el actual)
cols = {"g": ("hg", "ag"), "s": ("HomeShots", "AwayShots"), "t": ("HomeTarget", "AwayTarget"),
        "c": ("HomeCorners", "AwayCorners")}
long = []
for side, opp in ((0, 1), (1, 0)):
    d = pd.DataFrame({"i": df.index, "team": df.h if side == 0 else df.a, "date": df.date})
    for k, (ch, ca) in cols.items():
        d[f"{k}_f"] = df[ch if side == 0 else ca].to_numpy(float)
        d[f"{k}_a"] = df[ca if side == 0 else ch].to_numpy(float)
    d["side"] = side
    long.append(d)
long = pd.concat(long).sort_values(["team", "date", "i"])
g = long.groupby("team")
feat_cols = []
for k in cols:
    for fa in ("f", "a"):
        c = f"{k}_{fa}"
        long[f"r_{c}"] = g[c].transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
long["rest"] = g["date"].diff().dt.days.clip(upper=30)
long["n_prev"] = g.cumcount()
for side, tag in ((0, "h"), (1, "a")):
    part = long[long.side == side].set_index("i")
    for c in [c for c in long.columns if c.startswith("r_")] + ["rest", "n_prev"]:
        df[f"{tag}_{c}"] = part[c].reindex(df.index).to_numpy()
df["elo_diff"] = df.HomeElo - df.AwayElo
df["form_diff"] = df.Form5Home - df.Form5Away
df["month"] = df.date.dt.month
df["y"] = outcome_index(df.hg, df.ag)
df["over"] = ((df.hg + df.ag) > 2.5).astype(int)

base_feats = (["ekf_lh", "ekf_la", "ekf_H", "ekf_D", "ekf_A", "ekf_var", "elo_diff", "HomeElo", "AwayElo",
               "Form3Home", "Form5Home", "Form3Away", "Form5Away", "form_diff", "L", "month"]
              + [c for c in df.columns if c.startswith(("h_r_", "a_r_"))] + ["h_rest", "a_rest", "h_n_prev", "a_n_prev"])
mkt_feats = ["mH", "mD", "mA", "mOver"]

pred = pd.DataFrame(index=df.index)
params = dict(objective="multiclass", num_class=3, learning_rate=0.03, num_leaves=15, min_data_in_leaf=200,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=0)
for s in range(2021, 2027):
    tr = df[(df.season >= 2017) & (df.season < s) & df.ekf_H.notna() & df.mH.notna()]
    te = df[(df.season == s) & df.ekf_H.notna() & df.mH.notna()]
    if te.empty:
        continue
    va = tr[tr.season == s - 1]; tr2 = tr[tr.season < s - 1]
    for tag, feats in (("gbm", base_feats), ("gbm_mkt", base_feats + mkt_feats)):
        dtr = lgb.Dataset(tr2[feats], tr2.y, categorical_feature=["L"])
        dva = lgb.Dataset(va[feats], va.y, categorical_feature=["L"])
        bst = lgb.train(params, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        nbest = bst.best_iteration
        bst = lgb.train(params, lgb.Dataset(tr[feats], tr.y, categorical_feature=["L"]), nbest)
        P = bst.predict(te[feats])
        pred.loc[te.index, [f"{tag}_H", f"{tag}_D", f"{tag}_A"]] = P
        pred.loc[te.index, f"{tag}_iters"] = nbest
    # Más/menos 2,5 con LightGBM binario
    pb = {**params, "objective": "binary"}; pb.pop("num_class")
    for tag, feats in (("gbm", base_feats), ("gbm_mkt", base_feats + mkt_feats)):
        dtr = lgb.Dataset(tr2[feats], tr2.over, categorical_feature=["L"])
        dva = lgb.Dataset(va[feats], va.over, categorical_feature=["L"])
        bst = lgb.train(pb, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        bst = lgb.train(pb, lgb.Dataset(tr[feats], tr.over, categorical_feature=["L"]), bst.best_iteration)
        pred.loc[te.index, f"{tag}_over"] = bst.predict(te[feats])
    # Apilado: logística multinomial sobre log-probabilidades del modelo y del mercado (aprende la mezcla)
    for tag, mcols in (("stack_ekf", ["ekf_H", "ekf_D", "ekf_A"]), ("stack_ekfm", ["ekfm_H", "ekfm_D", "ekfm_A"])):
        Xtr = np.log(np.column_stack([tr[mcols].to_numpy(), tr[["mH", "mD", "mA"]].to_numpy()]))
        Xte = np.log(np.column_stack([te[mcols].to_numpy(), te[["mH", "mD", "mA"]].to_numpy()]))
        lr = LogisticRegression(C=1.0, max_iter=2000).fit(Xtr, tr.y)
        pred.loc[te.index, [f"{tag}_H", f"{tag}_D", f"{tag}_A"]] = lr.predict_proba(Xte)
    print(s, len(tr), len(te), flush=True)

pred.to_parquet(f"{SP}/data/ml_preds.parquet")
df[[c for c in df.columns if c.startswith(("ekf_", "ekfm_"))]].to_parquet(f"{SP}/data/ekf_probs.parquet")
print("listo")
