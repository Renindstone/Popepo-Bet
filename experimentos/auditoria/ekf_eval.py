import sys, time
import numpy as np, pandas as pd
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_common import *
from ekf import run_ekf

def evaluate(df, pred, lo, hi, rho=-0.06, divs=None):
    m = (df.date >= lo) & (df.date < hi)
    if divs is not None:
        m &= df["div"].isin(divs)
    d, p = df[m], pred[m]
    lh = np.exp(p.eta_h + 0.5 * p.var_h); la = np.exp(p.eta_a + 0.5 * p.var_a)
    pr = dc_probs(lh.to_numpy(), la.to_numpy(), rho)
    y = outcome_index(d.hg, d.ag)
    P = np.column_stack([pr["H"], pr["D"], pr["A"]])
    return logloss3(P, y).mean(), logloss2(pr["over"], ((d.hg + d.ag) > 2.5).to_numpy().astype(float)).mean(), len(d)
