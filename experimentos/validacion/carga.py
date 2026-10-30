"""Carga de partidos: ¿cambian los remates, córners, faltas, tarjetas y goles de un equipo con el calendario?

Corre el backtest (2024-08 a 2026-10, las ocho ligas) guardando, para cada equipo de cada partido, lo que el modelo
esperaba de él antes del partido (faltas y tarjetas con el árbitro y el factor de clásico, como el análisis) y lo
que hizo. Con el calendario de cada equipo (ligas y copas europeas de la BD; las copas nacionales no están) se
agrupan los partidos por:
- días de descanso desde su partido anterior;
- partidos jugados en los 14 días anteriores;
- «rival chico entre grandes» (la idea del dueño): el rival está entre el 40 % más flojo de su liga y el partido
  anterior o el siguiente del equipo (a 4 días o menos) es contra un grande (el 20 % más fuerte) o de Champions.
La fuerza es ataque + defensa del modelo de goles en ese momento. Para cada grupo: real / esperado y el residuo
estandarizado medio z = (real − esperado) / desviación esperada, con su margen del 95 %.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/carga.py (unos 3 min)
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import defaultdict
from datetime import UTC, date, datetime

import numpy as np

from apuestas.backtest import engine
from apuestas.db.session import _factory
from apuestas.models import distributions as dist
from apuestas.models import fitting

START, END = date(2024, 8, 1), date(2026, 10, 28)
STATS = ("shots", "shots_on_target", "corners", "fouls", "cards", "goals")
SPLIT = date(2025, 7, 1)


def collect() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    strength: dict = {}  # (día, equipo) -> fuerza
    orig_c, orig_m = engine._evaluate_counts, engine._evaluate_match

    def spy_m(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model=engine.W_MODEL, model_only=False):
        if not model_only and r.home in gm.attack and r.away in gm.attack:
            if (r.day, "_") not in strength:  # una vez por día: la fuerza de todos los equipos
                strength[(r.day, "_")] = {t: gm.attack[t] + gm.defence[t] for t in gm.attack}
            lh, la = gm.expected(r.home, r.away, r.neutral, r.competition)
            for side, team, opp, lam, goals in (("h", r.home, r.away, lh, r.hg), ("a", r.away, r.home, la, r.ag)):
                rows.append({"mid": r.match_id, "day": r.day, "comp": r.competition, "team": team, "opp": opp,
                             "side": side, "goals": (goals, lam, lam)})
        return orig_m(r, gm, rho, od, res, ll, br, min_ev, odds_range, w_model, model_only=model_only)

    def spy_c(r, cms, count_ll, refs=None, suffix="", leagues=None, delta=0.0, derby=False):
        if not suffix:
            ref = (refs or {}).get(r.referee_id) if r.referee_id else None
            mine = [x for x in rows[-2:] if x["mid"] == r.match_id]
            for stat, cm in cms.items():
                vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
                if vh is None or va is None or len(mine) != 2:
                    continue
                mh, ma = cm.expected(r.home, r.away, r.neutral, r.competition)
                if stat in fitting.COUNT_STRENGTH_PRIOR:
                    mh, ma = fitting.strength_shift(cm, mh, ma, delta)
                f = 1.0
                if ref and stat in ("cards", "fouls"):
                    f = ref["cards_factor"] if stat == "cards" else ref.get("fouls_factor", 1.0)
                k = fitting.DERBY_FACTOR.get(stat, 1.0) if derby else 1.0
                for x, real, mu in ((mine[0], vh, mh * f * k), (mine[1], va, ma * f * k)):
                    x[stat] = (real, mu, mu + cm.dispersion * mu**2)
        return orig_c(r, cms, count_ll, refs, suffix, leagues, delta, derby)

    engine._evaluate_counts, engine._evaluate_match = spy_c, spy_m
    try:
        engine.run(START, END)
    finally:
        engine._evaluate_counts, engine._evaluate_match = orig_c, orig_m
    return rows, strength


def main() -> None:
    rows, strength = collect()
    s = _factory()()
    try:
        allm = fitting.load_matches(s, before=datetime(2026, 11, 1, tzinfo=UTC), since=datetime(2023, 7, 1, tzinfo=UTC))
    finally:
        s.close()
    sched = defaultdict(list)  # equipo -> [(día, rival, competición)]
    for r in allm:
        sched[r.home].append((r.day, r.away, r.competition))
        sched[r.away].append((r.day, r.home, r.competition))
    for v in sched.values():
        v.sort()
    days = sorted(d for d, k in strength if k == "_")

    def tier(day, team, comp):
        """grande / chico / medio dentro de su liga, por la fuerza del modelo de goles ese día."""
        st = strength[(days[min(bisect_left(days, day), len(days) - 1)], "_")]
        rivals = [st[t] for t, c in league.items() if c == comp and t in st]
        if team not in st or len(rivals) < 8:
            return None
        q = sum(v < st[team] for v in rivals) / len(rivals)
        return "grande" if q >= 0.8 else "chico" if q < 0.4 else "medio"

    league = {}  # equipo -> su liga (última de liga en los datos)
    for r in allm:
        if r.competition not in ("UCL", "UEL", "UECL"):
            for t in (r.home, r.away):
                league[t] = r.competition

    groups = defaultdict(list)
    for x in rows:
        sc = sched[x["team"]]
        i = bisect_left(sc, (x["day"],))
        prev = sc[i - 1] if i > 0 else None
        nxt = sc[i + 1] if i + 1 < len(sc) else None
        rest = (x["day"] - prev[0]).days if prev else None
        last14 = sum(1 for d, _, _ in sc[max(0, i - 8):i] if 0 < (x["day"] - d).days <= 14)
        x["short_rest"] = rest is not None and rest <= 3
        x["sandwich"] = False
        if rest is not None:
            groups["descanso " + ("≤ 3 días" if rest <= 3 else "4-5 días" if rest <= 5 else "≥ 6 días")].append(x)
        groups["partidos en 14 días: " + ("≥ 4" if last14 >= 4 else "3" if last14 == 3 else "≤ 2")].append(x)
        if tier(x["day"], x["opp"], x["comp"]) == "chico":
            def big(game, day=x["day"]):
                return game is not None and abs((game[0] - day).days) <= 4 and (
                    game[2] == "UCL" or tier(game[0], game[1], league.get(game[1], "")) == "grande")
            x["sandwich"] = big(prev) or big(nxt)
            groups["rival chico, entre grandes" if x["sandwich"] else "rival chico, sin grandes al lado"].append(x)

    print(f"{len(rows)} equipo-partido. Real / esperado y residuo estandarizado medio (margen del 95 %)")
    for name in sorted(groups):
        xs = groups[name]
        cells = []
        for stat in STATS:
            v = [x[stat] for x in xs if stat in x]
            if len(v) < 30:
                continue
            real, mu, var = (np.array(t) for t in zip(*v, strict=True))
            z = (real - mu) / np.sqrt(np.maximum(var, 1e-9))
            cells.append(f"{stat} {real.sum() / mu.sum():.3f} ({z.mean():+.2f}±{1.96 * z.std(ddof=1) / math.sqrt(len(z)):.2f})")
        print(f"  {name:<36} ({len(xs):>5}): " + "; ".join(cells))


    print(f"\nFactor estimado con antes del {SPLIT}, probado después (log-verosimilitud del equipo por partido frente a"
          " sin factor; margen del 95 % pareado)")
    for flag, stat in (("sandwich", "cards"), ("sandwich", "fouls"), ("short_rest", "cards"), ("short_rest", "fouls")):
        tr = [x[stat] for x in rows if x.get(flag) and stat in x and x["day"] < SPLIT]
        te = [x[stat] for x in rows if x.get(flag) and stat in x and x["day"] >= SPLIT]
        f = sum(v[0] for v in tr) / sum(v[1] for v in tr)
        gain = []
        for real, mu, var in te:
            a = max((var - mu) / mu**2, 0.0)
            pf, p0 = dist.count_pmf(mu * f, a, 60), dist.count_pmf(mu, a, 60)
            gain.append(math.log(max(pf[int(real)], 1e-12)) - math.log(max(p0[int(real)], 1e-12)))
        g = np.array(gain)
        full = [x[stat] for x in rows if x.get(flag) and stat in x]
        print(f"  {flag:<10} {stat:<6} factor {f:.3f} ({len(tr)}; con todo, {sum(v[0] for v in full) / sum(v[1] for v in full):.3f})"
              f": {g.mean():+.4f} ± {1.96 * g.std(ddof=1) / math.sqrt(len(g)):.4f} en {len(g)}")


if __name__ == "__main__":
    main()
