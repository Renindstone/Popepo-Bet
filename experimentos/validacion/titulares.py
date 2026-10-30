"""Quién juega: ¿el titular poco habitual remata más de lo normal para probarse?

Con las estadísticas de jugador de la BD (desde 2023-24): para cada titularidad de 60 minutos o más (sin porteros), lo
esperado es su ritmo anterior de remates por 90 minutos en sus titularidades de 60' o más (de suplente se remata
más por minuto; contraído hacia la media de su posición con 4 partidos, como el modelo; hacen falta unas 4 antes) por los minutos que jugó, corregido por cuánto remató su equipo ese día frente a su media reciente (así un
partido de copa contra un rival flojo no cuenta como «probarse»). Se agrupan por cuántas veces fue titular en los 10
partidos anteriores de su equipo y por los minutos que llevaba antes. Real / esperado y residuo estandarizado medio
(margen del 95 %).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/titulares.py
"""

from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
from sqlalchemy import select, text

from apuestas.db import models as m
from apuestas.db.session import session_scope

PRIOR_MATCHES = 4
MIN_PREV_MINUTES = 4 * 60  # al menos unas 4 titularidades antes, para tener su ritmo propio
STATS = ("shots", "shots_on_target")


def main() -> None:
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        q = (select(m.PlayerMatchStats.player_id, m.PlayerMatchStats.team_id, m.PlayerMatchStats.match_id,
                    m.PlayerMatchStats.is_starter, m.PlayerMatchStats.minutes, m.PlayerMatchStats.shots,
                    m.PlayerMatchStats.shots_on_target, m.Player.position, m.Match.kickoff_utc)
             .join(m.Player, m.Player.id == m.PlayerMatchStats.player_id)
             .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
             .where(m.Match.status == "finished", m.PlayerMatchStats.shots.is_not(None))
             .order_by(m.Match.kickoff_utc))
        rows = s.execute(q).all()
    # Media por posición (por 90') y remates del equipo por partido
    pos_sum = defaultdict(lambda: [0.0, 0.0, 0.0])
    team_match = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if r.is_starter and (r.minutes or 0) >= 60:  # solo titularidades: de suplente se remata más por minuto
            pos_sum[r.position][0] += r.shots
            pos_sum[r.position][1] += r.shots_on_target or 0
            pos_sum[r.position][2] += r.minutes
        team_match[(r.team_id, r.match_id)][0] += r.shots
        team_match[(r.team_id, r.match_id)][1] += r.shots_on_target or 0
    pos_rate = {p: (v[0] / v[2] * 90, v[1] / v[2] * 90) for p, v in pos_sum.items() if v[2]}

    player_prev = defaultdict(lambda: [0.0, 0.0, 0.0])  # remates, a puerta, minutos antes
    team_hist = defaultdict(lambda: deque(maxlen=10))  # últimos 10 partidos del equipo: (partido, titulares, remates, a puerta)
    by_match = defaultdict(list)
    for r in rows:
        by_match[(r.team_id, r.match_id, r.kickoff_utc)].append(r)
    groups = defaultdict(lambda: {st: [] for st in STATS})
    for (team, mid, _ko), players in sorted(by_match.items(), key=lambda x: x[0][2]):
        hist = team_hist[team]
        if len(hist) >= 5:
            avg_team = (np.mean([h[2] for h in hist]), np.mean([h[3] for h in hist]))
            today = team_match[(team, mid)]
            for r in players:
                if not r.is_starter or (r.minutes or 0) < 60 or r.position == "GK" or r.position not in pos_rate:
                    continue
                starts = sum(r.player_id in h[1] for h in hist)
                prev = player_prev[r.player_id]
                if prev[2] < MIN_PREV_MINUTES:
                    continue
                key_start = "titular en 0-2 de 10" if starts <= 2 else "titular en 3-7 de 10" if starts <= 7 else "titular en 8-10 de 10"
                key_min = "con < 8 titularidades antes" if prev[2] < 8 * 75 else None
                for i, st in enumerate(STATS):
                    prior = pos_rate[r.position][i]
                    rate = (prev[i] + prior * PRIOR_MATCHES) / (prev[2] / 90 + PRIOR_MATCHES)
                    team_f = (today[i] / avg_team[i]) if avg_team[i] > 0 else 1.0
                    mu = rate * r.minutes / 90 * team_f
                    real = r.shots if st == "shots" else (r.shots_on_target or 0)
                    for key in (key_start, key_min):
                        if key:
                            groups[key][st].append((real, mu))
        for r in players:  # después de medir: el partido entra en lo «anterior» (solo titularidades de 60' o más)
            if r.is_starter and (r.minutes or 0) >= 60:
                p = player_prev[r.player_id]
                p[0] += r.shots
                p[1] += r.shots_on_target or 0
                p[2] += r.minutes
        t = team_match[(team, mid)]
        hist.append((mid, {r.player_id for r in players if r.is_starter}, t[0], t[1]))

    print("Titulares de 60' o más: real / esperado (ritmo propio anterior, corregido por el equipo) y residuo z")
    for name in sorted(groups):
        cells = []
        for st in STATS:
            v = groups[name][st]
            real, mu = (np.array(x) for x in zip(*v, strict=True))
            z = (real - mu) / np.sqrt(np.maximum(mu * (1 + 0.15 * mu), 1e-9))
            cells.append(f"{st} {real.sum() / mu.sum():.3f} (z {z.mean():+.3f} ± {1.96 * z.std(ddof=1) / math.sqrt(len(z)):.3f})")
        print(f"  {name:<22} ({len(groups[name]['shots']):>6}): " + "; ".join(cells))


if __name__ == "__main__":
    main()
