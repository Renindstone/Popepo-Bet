"""Modelo bayesiano dinámico de fuerza (espacio de estados) con filtro de Kalman extendido para Poisson.

Por país (en estos datos no hay partidos entre países): estado = [ataque y defensa de cada equipo, nivel de goles
y ventaja local de cada liga]. Cada equipo hace un paseo aleatorio (varianza q por día) y en el parón de verano
recibe varianza extra b y se contrae hacia la media (r). Cada partido actualiza el estado con la verosimilitud de
Poisson exacta (modo de Laplace en 2 dimensiones). Opcional: las cuotas de partidos ya jugados como observación
gaussiana del log de los goles esperados (desviación s_mkt), el equivalente bayesiano de MARKET_WEIGHT.
Predice ANTES de actualizar con cada partido (sin fuga).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def run_ekf(df: pd.DataFrame, q: float = 3e-5, b: float = 0.01, r: float = 0.0, s0: float = 0.3,
            q_lg: float = 2e-6, s_mkt: float | None = None, new_offset: float = -0.15,
            imp_h=None, imp_a=None, y_obs: tuple | None = None) -> pd.DataFrame:
    days = (df.date - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
    out = np.full((len(df), 4), np.nan)  # eta_h, eta_a, var_h, var_a
    for country, g in df.groupby("country", sort=False):
        idx = g.index.to_numpy()
        teams = np.unique(np.concatenate([g.h.to_numpy(), g.a.to_numpy()]))
        divs = sorted(g["div"].unique())
        nt, nl = len(teams), len(divs)
        tpos = {t: i for i, t in enumerate(teams)}
        lpos = {d: i for i, d in enumerate(divs)}
        dim = 2 * nt + 2 * nl  # att, def, mu_L, h_L
        m = np.zeros(dim)
        P = np.zeros((dim, dim))
        m[2 * nt:2 * nt + nl] = np.log(1.3)
        m[2 * nt + nl:] = 0.25
        for k in range(2 * nt, dim):
            P[k, k] = 0.05 ** 2
        seen = np.zeros(nt, bool)
        last_t = np.zeros(nt)
        last_season = np.full(nt, -1)
        last_lg_t = np.full(nl, np.nan)
        H_, A_, HG, AG = g.h.to_numpy(), g.a.to_numpy(), g.hg.to_numpy(), g.ag.to_numpy()
        DV, SE, T = g["div"].to_numpy(), g.season.to_numpy(), days[idx]
        team_div = {}  # liga actual de cada equipo
        for row in range(len(g)):
            t = T[row]
            li = lpos[DV[row]]
            # ruido de las variables de liga
            if not np.isnan(last_lg_t[li]):
                dt = t - last_lg_t[li]
                P[2 * nt + li, 2 * nt + li] += q_lg * dt
                P[2 * nt + nl + li, 2 * nt + nl + li] += q_lg * dt
            last_lg_t[li] = t
            ids = []
            for tm in (H_[row], A_[row]):
                i = tpos[tm]
                ids.append(i)
                if not seen[i]:
                    # equipo nuevo: media de su liga + desplazamiento (suelen ser ascendidos), varianza amplia
                    same = [tpos[x] for x, d in team_div.items() if d == DV[row]]
                    if same and row > 300:
                        m[i] = np.mean(m[same]) + new_offset
                        m[nt + i] = np.mean(m[[nt + j for j in same]]) + new_offset
                    P[i, i] = s0 ** 2
                    P[nt + i, nt + i] = s0 ** 2
                    seen[i] = True
                    last_t[i] = t
                    last_season[i] = SE[row]
                else:
                    dt = t - last_t[i]
                    extra = q * dt
                    if SE[row] != last_season[i]:
                        extra += b
                        if r > 0:
                            same = [tpos[x] for x, d in team_div.items() if d == DV[row] and tpos[x] != i]
                            if same:
                                m[i] = (1 - r) * m[i] + r * np.mean(m[same])
                                m[nt + i] = (1 - r) * m[nt + i] + r * np.mean(m[[nt + j for j in same]])
                        last_season[i] = SE[row]
                    P[i, i] += extra
                    P[nt + i, nt + i] += extra
                    last_t[i] = t
                team_div[tm] = DV[row]
            hi, ai = ids
            # eta_h = mu_L + h_L + att_h - def_a ; eta_a = mu_L + att_a - def_h
            rows_h = (np.array([hi, nt + ai, 2 * nt + li, 2 * nt + nl + li]), np.array([1.0, -1.0, 1.0, 1.0]))
            rows_a = (np.array([ai, nt + hi, 2 * nt + li]), np.array([1.0, -1.0, 1.0]))
            sub = np.unique(np.concatenate([rows_h[0], rows_a[0]]))
            Hm = np.zeros((2, len(sub)))
            for rr, (cols, vals) in enumerate((rows_h, rows_a)):
                for c_, v_ in zip(cols, vals):
                    Hm[rr, np.searchsorted(sub, c_)] = v_
            PHt = P[:, sub] @ Hm.T  # dim x 2
            C = Hm @ PHt[sub]  # 2 x 2
            eta0 = Hm @ m[sub]
            out[idx[row]] = [eta0[0], eta0[1], C[0, 0], C[1, 1]]
            # actualización con los goles: z = y - exp(eta0 + C z)
            if y_obs is not None and np.isfinite(y_obs[0][idx[row]]):
                y = np.array([y_obs[0][idx[row]], y_obs[1][idx[row]]], float)
            else:
                y = np.array([HG[row], AG[row]], float)
            z = np.zeros(2)
            for _ in range(20):
                lam = np.exp(eta0 + C @ z)
                f = z - y + lam
                J = np.eye(2) + lam[:, None] * C
                dz = np.linalg.solve(J, f)
                z -= dz
                if np.max(np.abs(dz)) < 1e-9:
                    break
            lam = np.exp(eta0 + C @ z)
            m += PHt @ z
            K = PHt @ np.linalg.inv(np.diag(1.0 / lam) + C)
            P -= K @ PHt.T
            # observación del mercado (cuotas previas de este partido, usada solo para los siguientes)
            if s_mkt is not None and imp_h is not None and np.isfinite(imp_h[idx[row]]):
                PHt = P[:, sub] @ Hm.T
                C = Hm @ PHt[sub]
                eta = Hm @ m[sub]
                yv = np.log([imp_h[idx[row]], imp_a[idx[row]]])
                S = C + np.eye(2) * s_mkt ** 2
                K = PHt @ np.linalg.inv(S)
                m += K @ (yv - eta)
                P -= K @ PHt.T
            P = 0.5 * (P + P.T)
    return pd.DataFrame(out, index=df.index, columns=["eta_h", "eta_a", "var_h", "var_a"])
