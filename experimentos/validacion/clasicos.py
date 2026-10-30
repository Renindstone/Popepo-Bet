"""¿Se salen los clásicos y derbis de lo que espera el modelo? Faltas, tarjetas, remates, a puerta, córners, goles y
offsides.

Corre el backtest (2024-08 a 2026-10, las ocho ligas) guardando lo que el modelo esperaba de cada partido antes de
jugarse (faltas y tarjetas con el factor del árbitro, como el análisis) y compara con lo que pasó, en los clásicos
de la lista y en el resto. Para cada estadística: real / esperado y el residuo estandarizado medio
z = (real − esperado) / desviación esperada, con su margen del 95 %, y su dispersión (si los clásicos van a veces muy
por debajo y a veces muy por encima, la desviación de z pasa de 1). Los offsides no están en el modelo: se comparan con
la media de offsides de los dos equipos en esa temporada fuera de los clásicos.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/clasicos.py (unos 2 min)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

import numpy as np
from sqlalchemy import select, text

from apuestas.backtest import engine
from apuestas.core.competitions import season_start_year
from apuestas.core.rivalries import RIVALRIES
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models import distributions as dist

RIVALS = [(a, b) for a, b, _ in RIVALRIES]
STATS = ("fouls", "cards", "shots", "shots_on_target", "corners")
SPLIT = date(2025, 7, 1)


def collect() -> dict[int, dict]:
    out: dict[int, dict] = {}
    orig_c, orig_m = engine._evaluate_counts, engine._evaluate_match

    def spy_c(r, cms, count_ll, refs=None, suffix="", leagues=None, delta=0.0, derby=False):
        if not suffix:
            row = out.setdefault(r.match_id, {"day": r.day, "comp": r.competition, "home": r.home, "away": r.away})
            ref = (refs or {}).get(r.referee_id) if r.referee_id else None
            for stat, cm in cms.items():
                vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
                if vh is None or va is None:
                    continue
                mh, ma = cm.expected(r.home, r.away, r.neutral, r.competition)
                f = 1.0
                if ref and stat == "cards":
                    f = ref["cards_factor"]
                elif ref and stat == "fouls":
                    f = ref.get("fouls_factor", 1.0)
                mu = (mh + ma) * f
                at = cm.total_dispersion if cm.total_dispersion is not None else cm.dispersion / 2
                row[stat] = (vh + va, mu, mu + at * mu**2)
        return orig_c(r, cms, count_ll, refs, suffix, leagues, delta, derby)

    def spy_m(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model=engine.W_MODEL, model_only=False):
        if not model_only and r.home in gm.attack and r.away in gm.attack:
            lh, la = gm.expected(r.home, r.away, r.neutral, r.competition)
            out.setdefault(r.match_id, {"day": r.day, "comp": r.competition, "home": r.home, "away": r.away})[
                "goals"] = (r.hg + r.ag, lh + la, lh + la)
        return orig_m(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model, model_only=model_only)

    engine._evaluate_counts, engine._evaluate_match = spy_c, spy_m
    try:
        engine.run(date(2024, 8, 1), date(2026, 10, 28))
    finally:
        engine._evaluate_counts, engine._evaluate_match = orig_c, orig_m
    return out


def add_offsides(rows: dict[int, dict], derby_ids: set[int]) -> None:
    """Offsides reales y, como «esperado», la media de los dos equipos esa temporada fuera de los clásicos."""
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        q = select(m.TeamMatchStats.match_id, m.TeamMatchStats.team_id, m.TeamMatchStats.offsides).where(
            m.TeamMatchStats.match_id.in_(list(rows)), m.TeamMatchStats.offsides.is_not(None))
        off = defaultdict(dict)
        for mid, tid, o in s.execute(q):
            off[mid][tid] = o
    sums = defaultdict(lambda: [0.0, 0])
    for mid, r in rows.items():
        if mid in derby_ids or len(off.get(mid, {})) < 2:
            continue
        for tid in (r["home"], r["away"]):
            k = (tid, season_start_year(r["day"]))
            sums[k][0] += off[mid][tid]
            sums[k][1] += 1
    for mid, r in rows.items():
        if len(off.get(mid, {})) < 2:
            continue
        season = season_start_year(r["day"])
        means = [sums[(t, season)][0] / sums[(t, season)][1] for t in (r["home"], r["away"]) if sums[(t, season)][1] >= 5]
        if len(means) == 2:
            mu = sum(means)
            r["offsides"] = (off[mid][r["home"]] + off[mid][r["away"]], mu, mu * 1.3)  # algo más que Poisson


def main() -> None:
    rows = collect()
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        names = {t.id: t.name for t in s.scalars(select(m.Team))}
    pairs = {frozenset(p) for p in RIVALS}
    derby = {mid for mid, r in rows.items() if frozenset((names[r["home"]], names[r["away"]])) in pairs}
    add_offsides(rows, derby)
    print(f"Partidos: {len(rows)}; clásicos: {len(derby)} de {len(pairs)} rivalidades")
    print("Clásicos frente al resto: real / esperado; residuo estandarizado medio (margen 95 %); desviación de z")
    for stat in (*STATS, "goals", "offsides"):
        cells = []
        for label, ids in (("clásicos", [i for i in rows if i in derby]), ("resto", [i for i in rows if i not in derby])):
            v = [rows[i][stat] for i in ids if stat in rows[i]]
            if not v:
                continue
            real, mu, var = (np.array(x) for x in zip(*v, strict=True))
            z = (real - mu) / np.sqrt(np.maximum(var, 1e-9))
            cells.append(f"{label} ({len(v)}) {real.sum() / mu.sum():.3f}, z {z.mean():+.2f} ± "
                         f"{1.96 * z.std(ddof=1) / math.sqrt(len(z)):.2f}, sd {z.std(ddof=1):.2f}")
        print(f"  {stat:<16} " + " | ".join(cells))
    print(f"\nFactor de clásico estimado con los de antes del {SPLIT}, probado con los de después (log-verosimilitud del"
          " total por partido frente a sin factor; margen del 95 % pareado)")
    for stat in ("fouls", "cards"):
        tr = [rows[i][stat] for i in derby if stat in rows[i] and rows[i]["day"] < SPLIT]
        te = [rows[i][stat] for i in derby if stat in rows[i] and rows[i]["day"] >= SPLIT]
        f = sum(x[0] for x in tr) / sum(x[1] for x in tr)
        gain = []
        for real, mu, var in te:
            at = max((var - mu) / mu**2, 0.0)
            pmf_f, pmf_0 = dist.count_pmf(mu * f, at, 120), dist.count_pmf(mu, at, 120)
            k = int(real)
            gain.append(math.log(max(pmf_f[k], 1e-12)) - math.log(max(pmf_0[k], 1e-12)))
        g = np.array(gain)
        print(f"  {stat:<6} factor {f:.3f} ({len(tr)} clásicos): {g.mean():+.4f} ± "
              f"{1.96 * g.std(ddof=1) / math.sqrt(len(g)):.4f} en {len(g)} clásicos")
    print("\nPor rivalidad (≥ 3 partidos): faltas, tarjetas, remates y offsides, real / esperado")
    by_pair = defaultdict(list)
    for mid in derby:
        r = rows[mid]
        by_pair[" - ".join(sorted((names[r["home"]], names[r["away"]])))].append(r)
    for pair, rs in sorted(by_pair.items(), key=lambda x: -len(x[1])):
        if len(rs) < 3:
            continue

        def ratio(stat, rs=rs):
            v = [r[stat] for r in rs if stat in r]
            return f"{sum(x[0] for x in v) / sum(x[1] for x in v):.2f}" if v else "  - "

        print(f"  {pair:<45} {len(rs)} partidos: faltas {ratio('fouls')}, tarjetas {ratio('cards')}, "
              f"remates {ratio('shots')}, offsides {ratio('offsides')}")


if __name__ == "__main__":
    main()
