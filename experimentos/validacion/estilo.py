"""Plan probable: ¿cada equipo tiene su forma propia de jugar contra los grandes, y la repite?

Con lo que el modelo esperaba de cada equipo y lo que hizo (`carga.collect`, 2024-08 a 2026-10), en los partidos de
liga contra un grande (rival en el 20 % más fuerte de su liga), de local y de visitante por separado: cuánto se sale
cada equipo de lo esperado, por encima de cómo se sale en el resto de sus partidos. Si esa forma propia se repite de
2024-25 a lo de después, sirve; si no, es ruido. Dos pruebas:
1. Correlación, entre equipos, de su desvío propio contra grandes en las dos mitades.
2. Prueba honesta: el desvío de 2024-25, contraído hacia 0 con K partidos, como factor en los partidos contra grandes
   de después, frente a sin factor (log-verosimilitud del equipo por partido).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/estilo.py (unos 3 min)
"""

from __future__ import annotations

import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import date

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from carga import collect  # noqa: E402

from apuestas.models import distributions as dist  # noqa: E402

SPLIT = date(2025, 7, 1)
STATS = ("shots", "shots_on_target", "corners", "fouls", "cards", "goals")
K = 10.0  # partidos contra grandes para fiarse a medias del desvío propio
CUPS = ("UCL", "UEL", "UECL")


def main() -> None:
    rows, strength = collect()
    days = sorted(d for d, k in strength if k == "_")
    league = {}
    for x in rows:
        if x["comp"] not in CUPS:
            league[x["team"]] = x["comp"]
    teams_of = defaultdict(set)
    for t, c in league.items():
        teams_of[c].add(t)

    def tier(day, team, comp):
        st = strength[(days[min(bisect_left(days, day), len(days) - 1)], "_")]
        vals = [st[t] for t in teams_of[comp] if t in st]
        if team not in st or len(vals) < 8:
            return None
        q = sum(v < st[team] for v in vals) / len(vals)
        return "grande" if q >= 0.8 else "chico" if q < 0.4 else "medio"

    for x in rows:
        x["big"] = x["comp"] not in CUPS and tier(x["day"], x["opp"], x["comp"]) == "grande"

    for side_name, side in (("de local", "h"), ("de visitante", "a")):
        print(f"\nContra grandes {side_name}")
        for stat in STATS:
            per = {"A": defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0]), "B": defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])}
            test = []  # (equipo, real, esperado, varianza) contra grandes después
            for x in rows:
                if stat not in x or x["comp"] in CUPS:
                    continue
                real, mu, var = x[stat]
                half = "A" if x["day"] < SPLIT else "B"
                acc = per[half][x["team"]]
                if x["big"] and x["side"] == side:
                    acc[0] += real
                    acc[1] += mu
                    acc[4] += 1
                    if half == "B":
                        test.append((x["team"], real, mu, var))
                else:
                    acc[2] += real
                    acc[3] += mu

            def own(acc):
                """Desvío propio contra grandes: (real / esperado contra grandes) / (real / esperado en el resto)."""
                if acc[4] < 3 or acc[1] <= 0 or acc[3] <= 0 or acc[2] <= 0:
                    return None
                return (acc[0] / acc[1]) / (acc[2] / acc[3])

            pairs = [(own(per["A"][t]), own(per["B"][t])) for t in per["A"] if t in per["B"]]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if len(pairs) < 10:
                continue
            a, b = (np.log(np.array(v)) for v in zip(*pairs, strict=True))
            r = float(np.corrcoef(a, b)[0, 1])
            half = 1.96 / math.sqrt(len(a) - 3)
            lo, hi = math.tanh(math.atanh(r) - half), math.tanh(math.atanh(r) + half)
            gain = []
            for team, real, mu, var in test:
                acc = per["A"].get(team)
                f = own(acc) if acc else None
                if f is None:
                    continue
                f = 1 + acc[4] / (acc[4] + K) * (f - 1)
                al = max((var - mu) / mu**2, 0.0)
                pf, p0 = dist.count_pmf(mu * f, al, 60), dist.count_pmf(mu, al, 60)
                gain.append(math.log(max(pf[int(real)], 1e-12)) - math.log(max(p0[int(real)], 1e-12)))
            g = np.array(gain)
            print(f"  {stat:<16} {len(pairs):>3} equipos: correlación {r:+.2f} [{lo:+.2f}, {hi:+.2f}]; prueba honesta "
                  f"{g.mean():+.4f} ± {1.96 * g.std(ddof=1) / math.sqrt(len(g)):.4f} en {len(g)} partidos")


if __name__ == "__main__":
    main()
