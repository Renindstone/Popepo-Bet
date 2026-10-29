"""Fuerza de goles dinámica (filtro de Kalman extendido, como `experimentos/auditoria/ekf.py`) frente a `ratings.fit`.

El filtro lleva ataque y defensa de cada equipo con un paseo aleatorio (varianza q por día, más b en el cambio de
temporada) y un nivel de goles y una ventaja local por competición que también se mueven (q_lg). Cada partido lo
actualiza con la verosimilitud de Poisson (85 % xG + 15 % goles, como `fitting.goals_obs`) y, después, con los goles
implícitos en el cierre de Pinnacle o bet365 como observación gaussiana de su logaritmo (desviación s_mkt), el
equivalente de `fitting.MARKET_WEIGHT`. Predice cada partido antes de verlo: todo es fuera de muestra.

Referencia: el backtest de siempre (`engine.run`, 2024-26, cinco ligas), con la media del modelo actual y su rho en
cada partido evaluado (los que tienen cuota previa de bet365 y Pinnacle). El filtro usa el mismo rho, así que solo
cambia la fuerza. Los parámetros se eligen con la pérdida logarítmica 1X2 de 2024-25 y la prueba honesta es 2025-26.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/fuerza_dinamica.py (unos 10 min)
"""

from __future__ import annotations

import math
import time
from datetime import UTC, date, datetime

import numpy as np

from apuestas.backtest import engine
from apuestas.core.competitions import season_start_year
from apuestas.db.session import _factory
from apuestas.models import fitting

SPLIT = date(2025, 7, 1)
DEFAULT = {"q": 3e-5, "b": 0.01, "s0": 0.3, "q_lg": 2e-6, "new_offset": -0.15, "s_mkt": 0.15, "league_level": True}


def reference() -> dict[int, dict]:
    """Partidos que evalúa el backtest, con la probabilidad 1X2 del modelo actual, su rho y las casas."""
    ref: dict[int, dict] = {}
    orig = engine._evaluate_match

    def spy(r, gm, rho, od, res, *a, model_only=False, **k):
        sharp = engine._book_probs(od, "pinnacle") or engine._book_probs(od, "betfair_ex")
        b365 = engine._book_probs(od, "bet365")
        if not model_only and sharp and b365 and r.home in gm.attack and r.away in gm.attack:
            y = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
            ref[r.match_id] = {"day": r.day, "rho": rho, "y": y, "modelo": engine._probs_1x2(
                *gm.expected(r.home, r.away, r.neutral), rho), "pinnacle": sharp, "bet365": b365}
        return orig(r, gm, rho, od, res, *a, model_only=model_only, **k)

    engine._evaluate_match = spy
    try:
        engine.run(start=date(2024, 8, 1), end=date(2026, 6, 30))
    finally:
        engine._evaluate_match = orig
    return ref


def ekf(rows, implied, q, b, s0, q_lg, new_offset, s_mkt, league_level) -> dict[int, tuple[float, float]]:
    """Goles esperados (local, visitante) de cada partido antes de jugarse: exp(eta + var / 2)."""
    teams = sorted({t for r in rows for t in (r.home, r.away)})
    comps = sorted({r.competition for r in rows}) if league_level else ["todas"]
    nt, nl = len(teams), len(comps)
    tpos, lpos = {t: i for i, t in enumerate(teams)}, {c: i for i, c in enumerate(comps)}
    dim = 2 * nt + 2 * nl  # ataque, defensa, nivel de goles y ventaja local de cada competición
    m, P = np.zeros(dim), np.zeros((dim, dim))
    m[2 * nt:2 * nt + nl] = math.log(1.35)
    m[2 * nt + nl:] = 0.25
    P[range(2 * nt, dim), range(2 * nt, dim)] = 0.05**2
    seen = np.zeros(nt, bool)
    last_t, last_season = np.zeros(nt), np.full(nt, -1)
    last_lg = np.full(nl, np.nan)
    in_comp: dict[int, str] = {}
    out = {}
    for r in rows:
        t, season = r.day.toordinal(), season_start_year(r.day)
        li = lpos[r.competition if league_level else "todas"]
        if not np.isnan(last_lg[li]):
            P[2 * nt + li, 2 * nt + li] += q_lg * (t - last_lg[li])
            P[2 * nt + nl + li, 2 * nt + nl + li] += q_lg * (t - last_lg[li])
        last_lg[li] = t
        for tm in (r.home, r.away):
            i = tpos[tm]
            if not seen[i]:  # equipo nuevo: la media de su competición (suelen ser ascendidos), varianza amplia
                same = [tpos[x] for x, c in in_comp.items() if c == r.competition]
                if len(same) >= 5:
                    m[i] = np.mean(m[same]) + new_offset
                    m[nt + i] = np.mean(m[[nt + j for j in same]]) + new_offset
                P[i, i] = P[nt + i, nt + i] = s0**2
                seen[i], last_t[i], last_season[i] = True, t, season
            else:
                extra = q * (t - last_t[i]) + (b if season != last_season[i] else 0.0)
                P[i, i] += extra
                P[nt + i, nt + i] += extra
                last_t[i], last_season[i] = t, season
            in_comp[tm] = r.competition
        hi, ai = tpos[r.home], tpos[r.away]
        home = 0.0 if r.neutral else 1.0
        sub = np.array(sorted({hi, ai, nt + hi, nt + ai, 2 * nt + li, 2 * nt + nl + li}))
        col = {c: k for k, c in enumerate(sub)}
        Hm = np.zeros((2, len(sub)))
        Hm[0, col[hi]], Hm[0, col[nt + ai]], Hm[0, col[2 * nt + li]] = 1.0, -1.0, 1.0
        Hm[0, col[2 * nt + nl + li]] = home
        Hm[1, col[ai]], Hm[1, col[nt + hi]], Hm[1, col[2 * nt + li]] = 1.0, -1.0, 1.0
        PHt = P[:, sub] @ Hm.T
        C = Hm @ PHt[sub]
        eta0 = Hm @ m[sub]
        out[r.match_id] = (math.exp(eta0[0] + C[0, 0] / 2), math.exp(eta0[1] + C[1, 1] / 2))
        xh, xa = r.stats_h.get("xg"), r.stats_a.get("xg")
        if xh is not None and xa is not None and r.competition not in fitting.GOALS_XG_SKIP:
            w = fitting.GOALS_XG_WEIGHT
            y = np.array([(1 - w) * r.hg + w * xh, (1 - w) * r.ag + w * xa])
        else:
            y = np.array([r.hg, r.ag], float)
        z = np.zeros(2)  # modo de Laplace: z = y − exp(eta0 + C z)
        for _ in range(20):
            lam = np.exp(eta0 + C @ z)
            dz = np.linalg.solve(np.eye(2) + lam[:, None] * C, z - y + lam)
            z -= dz
            if np.max(np.abs(dz)) < 1e-9:
                break
        lam = np.exp(eta0 + C @ z)
        m += PHt @ z
        P -= PHt @ np.linalg.inv(np.diag(1.0 / lam) + C) @ PHt.T
        if s_mkt and r.match_id in implied:  # el cierre de este partido, para los siguientes
            PHt = P[:, sub] @ Hm.T
            C = Hm @ PHt[sub]
            K = PHt @ np.linalg.inv(C + np.eye(2) * s_mkt**2)
            m += K @ (np.log(implied[r.match_id]) - Hm @ m[sub])
            P -= K @ PHt.T
        P = 0.5 * (P + P.T)
    return out


def losses(ref: dict, pred: dict[int, tuple[float, float]] | None, key: str, ids: list[int]) -> np.ndarray:
    out = []
    for mid in ids:
        x = ref[mid]
        p = engine._probs_1x2(*pred[mid], x["rho"]) if pred is not None else x[key]
        out.append(-math.log(max(p[x["y"]], 1e-9)))
    return np.array(out)


def main() -> None:
    ref = reference()
    s = _factory()()
    try:
        before, since = datetime(2026, 7, 1, tzinfo=UTC), datetime(2023, 7, 1, tzinfo=UTC)
        rows = sorted(fitting.load_matches(s, before=before, since=since), key=lambda r: (r.day, r.match_id))
        implied = fitting.load_market_goals(s, before=before, since=since)
    finally:
        s.close()
    rows = [r for r in rows if r.competition in fitting.model_codes()]
    tune = [mid for mid, x in ref.items() if x["day"] < SPLIT]
    test = [mid for mid, x in ref.items() if x["day"] >= SPLIT]
    print(f"{len(rows)} partidos en el filtro; evaluados {len(tune)} (2024-25) y {len(test)} (2025-26)")

    cache: dict[tuple, dict] = {}

    def run(**kw) -> float:
        cfg = {**DEFAULT, **kw}
        k = tuple(sorted(cfg.items()))
        if k not in cache:
            t0 = time.time()
            cache[k] = ekf(rows, implied, **cfg)
            print(f"  {kw or 'base'}: 2024-25 {losses(ref, cache[k], '', tune).mean():.5f} ({time.time() - t0:.0f} s)",
                  flush=True)
        return float(losses(ref, cache[k], "", tune).mean())

    best: dict = {}
    for name, values in (("s_mkt", [0.04, 0.06, 0.08, 0.15, 0.0]), ("q", [3e-5, 1e-4, 3e-4]), ("b", [0.0, 0.01, 0.03]),
                         ("league_level", [True, False]), ("q_lg", [0.0, 2e-6, 1e-5]),
                         ("new_offset", [0.0, -0.15, -0.3]), ("s_mkt", [0.04, 0.06, 0.08])):
        best[name] = min(values, key=lambda v, n=name: run(**{**best, n: v}))
    pred = cache[tuple(sorted({**DEFAULT, **best}.items()))]
    print(f"\nMejores parámetros (2024-25): {best}")

    for label, ids in (("2024-25 (afinado)", tune), ("2025-26 (prueba honesta)", test), ("2024-26", tune + test)):
        base = losses(ref, None, "modelo", ids)
        print(f"\n{label}, {len(ids)} partidos. Pérdida log. 1X2 (frente al modelo actual, margen del 95 % pareado):")
        for name, v in (("modelo actual", base), ("fuerza dinámica", losses(ref, pred, "", ids)),
                        ("Pinnacle", losses(ref, None, "pinnacle", ids)), ("bet365", losses(ref, None, "bet365", ids))):
            d = v - base
            print(f"  {name:<16} {v.mean():.4f}  {d.mean():+.4f} ± {1.96 * d.std(ddof=1) / math.sqrt(len(d)):.4f}")


if __name__ == "__main__":
    main()
