"""Plan probable con el entrenador: ¿se repite la forma de jugar contra los grandes mientras sigue el mismo técnico?

Con lo que el modelo esperaba de cada equipo y lo que hizo (`carga.collect`, 2024-08 a 2026-10) y el entrenador de
cada partido (`match.lineup_info`, de FotMob). En orden de fecha, para cada partido de liga contra un grande (rival
en el 20 % más fuerte de su liga): el desvío propio del equipo contra grandes con ESE entrenador en sus partidos
anteriores (real / esperado contra grandes, entre real / esperado en el resto), contraído hacia 1 con K partidos,
como factor; frente a sin factor (log-verosimilitud del equipo por partido, margen del 95 %). Solo con lo de antes de
cada partido: es una prueba honesta. Aparte, de visitante, que es el caso del Madrid en el Camp Nou.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/estilo_entrenador.py (unos 3 min)
"""

from __future__ import annotations

import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict

import numpy as np
from sqlalchemy import select, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from carga import collect  # noqa: E402

from apuestas.db import models as m  # noqa: E402
from apuestas.db.session import session_scope  # noqa: E402
from apuestas.models import distributions as dist  # noqa: E402

STATS = ("shots", "shots_on_target", "corners", "fouls", "cards", "goals")
CUPS = ("UCL", "UEL", "UECL")
MIN_PREV = 3


def main() -> None:
    rows, strength = collect()
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        info = dict(s.execute(select(m.Match.id, m.Match.lineup_info).where(m.Match.lineup_info.is_not(None))).all())
    days = sorted(d for d, k in strength if k == "_")
    league = {x["team"]: x["comp"] for x in rows if x["comp"] not in CUPS}
    teams_of = defaultdict(set)
    for t, c in league.items():
        teams_of[c].add(t)

    def big(day, team, comp):
        st = strength[(days[min(bisect_left(days, day), len(days) - 1)], "_")]
        vals = [st[t] for t in teams_of[comp] if t in st]
        return team in st and len(vals) >= 8 and sum(v < st[team] for v in vals) / len(vals) >= 0.8

    rows = [x for x in rows if x["comp"] not in CUPS]
    for x in rows:
        x["coach"] = ((info.get(x["mid"]) or {}).get(str(x["team"])) or {}).get("coach")
        x["big"] = big(x["day"], x["opp"], x["comp"])
    rows.sort(key=lambda x: x["day"])
    with_coach = sum(1 for x in rows if x["coach"])
    print(f"{len(rows)} equipo-partido de liga, {with_coach} con entrenador; contra grandes: {sum(x['big'] for x in rows)}")

    for k_prior in (5.0, 10.0):
        for label, sides in (("local y visitante", ("h", "a")), ("solo de visitante", ("a",))):
            print(f"\nK = {k_prior:g}, contra grandes {label}")
            for stat in STATS:
                acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])  # (equipo, entrenador) -> sumas antes del partido
                gain = []
                for x in rows:
                    if stat not in x or not x["coach"]:
                        continue
                    real, mu, var = x[stat]
                    a = acc[(x["team"], x["coach"], x["side"] if len(sides) == 1 else "")]
                    if x["big"] and x["side"] in sides:
                        if a[4] >= MIN_PREV and a[1] > 0 and a[2] > 0 and a[3] > 0:
                            own = (a[0] / a[1]) / (a[2] / a[3])
                            f = 1 + a[4] / (a[4] + k_prior) * (own - 1)
                            al = max((var - mu) / mu**2, 0.0)
                            pf, p0 = dist.count_pmf(mu * f, al, 60), dist.count_pmf(mu, al, 60)
                            gain.append(math.log(max(pf[int(real)], 1e-12)) - math.log(max(p0[int(real)], 1e-12)))
                        a[0] += real
                        a[1] += mu
                        a[4] += 1
                    else:
                        a[2] += real
                        a[3] += mu
                g = np.array(gain)
                if len(g) > 10:
                    print(f"  {stat:<16} {g.mean():+.4f} ± {1.96 * g.std(ddof=1) / math.sqrt(len(g)):.4f} en {len(g)} partidos")


if __name__ == "__main__":
    main()
