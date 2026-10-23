"""Datos y utilidades comunes de los experimentos de la auditoría (Matches.csv de xgabora: football-data + ClubElo).

Mismas ligas que el repo (3 completas + 11 ligeras con estadísticas). Cuotas: bet365 previas (1X2, más/menos 2,5,
hándicap asiático) y la máxima de ~17 casas. No hay Pinnacle, cierre, xG ni árbitro en este archivo.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

# Datos y resultados en var/experimentos/auditoria (var/ no se sube). Se puede cambiar con AUDIT_DIR.
SP = os.environ.get("AUDIT_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "var", "experimentos", "auditoria")
FULL = ["E0", "D1", "SP1"]
LIGHT = ["I1", "F1", "P1", "N1", "B1", "T1", "SC0", "G1", "E1", "D2", "SP2"]
DIVS = FULL + LIGHT
COUNTRY = {"E0": "ENG", "E1": "ENG", "D1": "GER", "D2": "GER", "SP1": "ESP", "SP2": "ESP", "I1": "ITA",
           "F1": "FRA", "P1": "POR", "N1": "NED", "B1": "BEL", "T1": "TUR", "SC0": "SCO", "G1": "GRE"}
MAXG = 10
_I, _J = np.indices((MAXG + 1, MAXG + 1))


def devig_power(o: np.ndarray) -> np.ndarray:
    """Método de potencia (como el repo) para filas de N x k cuotas."""
    p = 1.0 / o
    out = np.full_like(p, np.nan)
    for r in range(len(p)):
        if not np.all(np.isfinite(p[r])):
            continue
        lo, hi = 0.5, 3.0
        for _ in range(60):
            k = 0.5 * (lo + hi)
            s = np.sum(p[r] ** k)
            if s > 1:
                lo = k
            else:
                hi = k
        out[r] = p[r] ** k
        out[r] /= out[r].sum()
    return out


def load(start: str = "2013-07-01") -> pd.DataFrame:
    path = os.path.join(SP, "data", "matches_clean.parquet")
    os.makedirs(os.path.join(SP, "data"), exist_ok=True)
    if os.path.exists(path):
        return pd.read_parquet(path)
    df = pd.read_csv(os.path.join(SP, "data/xgabora/data/Matches.csv"), low_memory=False)
    df = df[df.Division.isin(DIVS)].copy()
    df["date"] = pd.to_datetime(df.MatchDate)
    df = df[(df.date >= start) & df.FTHome.notna() & df.FTAway.notna()].copy()
    df["country"] = df.Division.map(COUNTRY)
    # Clave de equipo: nombre; si el nombre aparece en dos países se añade el país
    names = pd.concat([df[["HomeTeam", "country"]].rename(columns={"HomeTeam": "t"}),
                       df[["AwayTeam", "country"]].rename(columns={"AwayTeam": "t"})])
    multi = names.groupby("t").country.nunique()
    multi = set(multi[multi > 1].index)
    key = lambda t, c: f"{t}|{c}" if t in multi else t  # noqa: E731
    df["hkey"] = [key(t, c) for t, c in zip(df.HomeTeam, df.country)]
    df["akey"] = [key(t, c) for t, c in zip(df.AwayTeam, df.country)]
    teams = sorted(set(df.hkey) | set(df.akey))
    tid = {t: i for i, t in enumerate(teams)}
    df["h"] = df.hkey.map(tid).astype(int)
    df["a"] = df.akey.map(tid).astype(int)
    df["div"] = df.Division
    df["L"] = df["div"].map({d: i for i, d in enumerate(DIVS)}).astype(int)
    df["hg"] = df.FTHome.astype(int)
    df["ag"] = df.FTAway.astype(int)
    df["season"] = np.where(df.date.dt.month >= 7, df.date.dt.year, df.date.dt.year - 1)
    df = df.sort_values(["date", "div", "h"]).reset_index(drop=True)
    # Probabilidades de bet365 sin margen
    o3 = df[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
    ok3 = np.all(o3 > 1.0, axis=1)
    p3 = np.full((len(df), 3), np.nan)
    p3[ok3] = devig_power(o3[ok3])
    df[["mH", "mD", "mA"]] = p3
    ou = df[["Over25", "Under25"]].to_numpy(float)
    okou = np.all(ou > 1.0, axis=1)
    pov = np.full(len(df), np.nan)
    pov[okou] = (1 / ou[okou, 0]) / ((1 / ou[okou]).sum(1))
    df["mOver"] = pov
    df["margin1x2"] = np.where(ok3, (1 / o3).sum(1) - 1, np.nan)
    df.to_parquet(path)
    return df


# --------------------------------------------------------------------------- probabilidades de un marcador

def dc_probs(lh: np.ndarray, la: np.ndarray, rho: float) -> dict[str, np.ndarray]:
    """1X2, más de 2,5 y matriz para vectores de medias (Dixon-Coles)."""
    lh, la = np.atleast_1d(lh).astype(float), np.atleast_1d(la).astype(float)
    k = np.arange(MAXG + 1)
    mat = poisson.pmf(k[None, :], lh[:, None])[:, :, None] * poisson.pmf(k[None, :], la[:, None])[:, None, :]
    mat[:, 0, 0] *= 1 - lh * la * rho
    mat[:, 0, 1] *= 1 + lh * rho
    mat[:, 1, 0] *= 1 + la * rho
    mat[:, 1, 1] *= 1 - rho
    mat = np.clip(mat, 0, None)
    mat /= mat.sum(axis=(1, 2), keepdims=True)
    return {"H": mat[:, _I > _J].sum(1), "D": mat[:, _I == _J].sum(1), "A": mat[:, _I < _J].sum(1),
            "over": mat[:, _I + _J >= 3].sum(1), "mat": mat}


def fit_rho(lh, la, hg, ag) -> float:
    lh, la, hg, ag = map(np.asarray, (lh, la, hg, ag))
    m00 = (hg == 0) & (ag == 0); m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0); m11 = (hg == 1) & (ag == 1)

    def nll(r):
        t = np.ones_like(lh)
        t[m00] = 1 - lh[m00] * la[m00] * r; t[m01] = 1 + lh[m01] * r
        t[m10] = 1 + la[m10] * r; t[m11] = 1 - r
        return -np.sum(np.log(np.clip(t, 1e-9, None)))
    from scipy.optimize import minimize_scalar
    return float(minimize_scalar(nll, bounds=(-0.25, 0.15), method="bounded").x)


# --------------------------------------------------------------------------- métricas

def logloss3(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, None))


def rps3(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    o = np.zeros_like(p); o[np.arange(len(y)), y] = 1
    cp, co = np.cumsum(p, 1)[:, :2], np.cumsum(o, 1)[:, :2]
    return ((cp - co) ** 2).sum(1) / 2


def brier3(p, y):
    o = np.zeros_like(p); o[np.arange(len(y)), y] = 1
    return ((p - o) ** 2).sum(1)


def logloss2(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired(d: np.ndarray, groups: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Media de una diferencia por partido y su error estándar con bootstrap por bloques (jornadas)."""
    d = np.asarray(d, float)
    g = pd.factorize(groups)[0]
    sums = np.bincount(g, weights=d); cnt = np.bincount(g)
    rng = np.random.default_rng(seed)
    G = len(sums)
    idx = rng.integers(0, G, size=(n_boot, G))
    boots = sums[idx].sum(1) / cnt[idx].sum(1)
    return float(d.mean()), float(boots.std(ddof=1))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return e


def outcome_index(hg, ag):
    hg, ag = np.asarray(hg), np.asarray(ag)
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


# --------------------------------------------------------------------------- modelo de fuerza ampliado

def fit_ext(hi, ai, yh, ya, hm, w, Lm, Lt, nL: int, n: int, l2: float = 2.0, league_hfa: bool = False,
            l2_hfa: float = 50.0, league_center: bool = False, theta0=None):
    """Modelo del repo (ratings.fit) con dos opciones:
    - league_hfa: ventaja local propia de cada liga (desviación de la global, penalizada con l2_hfa)
    - league_center: la L2 contrae a cada equipo hacia el nivel de SU liga (Lt = liga actual del equipo) en
      lugar de hacia 0 (nivel global). Los niveles de liga no se penalizan (ridge mínimo para identificarlos).
    """
    nh = nL if league_hfa else 0
    nc = nL if league_center else 0
    sz = 2 + 2 * n + nh + 2 * nc

    def unpack(t):
        mu, home = t[0], t[1]
        att, de = t[2:2 + n], t[2 + n:2 + 2 * n]
        hL = t[2 + 2 * n:2 + 2 * n + nh] if nh else None
        cA = t[2 + 2 * n + nh:2 + 2 * n + nh + nc] if nc else None
        cD = t[2 + 2 * n + nh + nc:] if nc else None
        return mu, home, att, de, hL, cA, cD

    def obj(t):
        mu, home, att, de, hL, cA, cD = unpack(t)
        hfa = home + (hL[Lm] if nh else 0.0)
        eh = mu + hfa * hm + att[hi] - de[ai]
        ea = mu + att[ai] - de[hi]
        lh, la = np.exp(eh), np.exp(ea)
        nll = np.sum(w * (lh - yh * eh)) + np.sum(w * (la - ya * ea))
        ra_, rd_ = (att - cA[Lt], de - cD[Lt]) if nc else (att, de)
        nll += 0.5 * l2 * (np.sum(ra_ ** 2) + np.sum(rd_ ** 2))
        rh, rr = w * (lh - yh), w * (la - ya)
        g = np.zeros_like(t)
        g[0] = rh.sum() + rr.sum()
        g[1] = (rh * hm).sum()
        g[2:2 + n] = np.bincount(hi, rh, n) + np.bincount(ai, rr, n) + l2 * ra_
        g[2 + n:2 + 2 * n] = -np.bincount(ai, rh, n) - np.bincount(hi, rr, n) + l2 * rd_
        if nh:
            nll += 0.5 * l2_hfa * np.sum(hL ** 2)
            g[2 + 2 * n:2 + 2 * n + nh] = np.bincount(Lm, rh * hm, nL) + l2_hfa * hL
        if nc:
            eps = 1e-3
            nll += 0.5 * eps * (np.sum(cA ** 2) + np.sum(cD ** 2))
            g[2 + 2 * n + nh:2 + 2 * n + nh + nc] = -l2 * np.bincount(Lt, ra_, nL) + eps * cA
            g[2 + 2 * n + nh + nc:] = -l2 * np.bincount(Lt, rd_, nL) + eps * cD
        return nll, g

    if theta0 is None or len(theta0) != sz:
        theta0 = np.zeros(sz)
        theta0[0] = math.log(max(np.average(np.concatenate([yh, ya]), weights=np.concatenate([w, w])), 1e-3))
        theta0[1] = 0.1
    res = minimize(obj, theta0, jac=True, method="L-BFGS-B", options={"maxiter": 3000})
    return unpack(res.x), res.x


def predict_ext(params, hi, ai, Lm, neutral=None):
    mu, home, att, de, hL, cA, cD = params
    hfa = home + (hL[Lm] if hL is not None else 0.0)
    return np.exp(mu + hfa + att[hi] - de[ai]), np.exp(mu + att[ai] - de[hi])


def time_w(days_ago: np.ndarray, half_life: float) -> np.ndarray:
    return np.power(0.5, np.clip(days_ago, 0, None) / half_life)
