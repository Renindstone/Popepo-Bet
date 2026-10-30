"""¿El modelo de jugadores sobreestima los remates del titular poco habitual?

Cada mes de 2025-01 a 2026-10 se ajustan las partes de cada jugador (`fitting.fit_players`) solo con lo anterior y,
para los titulares de 60' o más del mes siguiente (sin porteros), lo esperado es la parte del jugador en los remates
de su equipo (contraída hacia su posición como `analysis._player_projections`) por sus minutos reales y por los
remates reales de su equipo ese día: así solo se mide la parte del jugador, no el modelo del equipo ni el de minutos.
Se agrupa por cuántas veces fue titular en los 10 partidos anteriores de su equipo. La escala absoluta de esta réplica no es
la del análisis (sale alta en todos los grupos): cuenta la diferencia entre grupos. La prueba honesta aprende la escala
general y el factor relativo del poco habitual antes de 2025-10 y los aplica después.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/titulares_modelo.py (unos 5 min)
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select, text

from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models import distributions as dist
from apuestas.models import fitting
from apuestas.services.analysis import VOLUME_SHARE_PRIOR_MATCHES

STATS = ("shots", "shots_on_target")
SPLIT = datetime(2025, 10, 1, tzinfo=UTC)
DISPERSION = 0.15  # la de los remates de jugador (match_model.PLAYER_COUNT_DISPERSION)


def group(starts: int) -> str:
    return "0-2 de 10" if starts <= 2 else "3-7 de 10" if starts <= 7 else "8-10 de 10"


def main() -> None:
    cutoffs = [datetime(y, mo, 1, tzinfo=UTC) for y in (2025, 2026) for mo in range(1, 13)
               if datetime(2025, 1, 1, tzinfo=UTC) <= datetime(y, mo, 1, tzinfo=UTC) <= datetime(2026, 10, 1, tzinfo=UTC)]
    out = []  # (fecha, grupo, estadística, real, esperado)
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = s.execute(
            select(m.PlayerMatchStats.player_id, m.PlayerMatchStats.team_id, m.PlayerMatchStats.match_id,
                   m.PlayerMatchStats.is_starter, m.PlayerMatchStats.minutes, m.PlayerMatchStats.shots,
                   m.PlayerMatchStats.shots_on_target, m.Player.position, m.Match.kickoff_utc)
            .join(m.Player, m.Player.id == m.PlayerMatchStats.player_id)
            .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
            .where(m.Match.status == "finished").order_by(m.Match.kickoff_utc)).all()
        team_stats = {(t, mid): (sh, sot) for t, mid, sh, sot in s.execute(
            select(m.TeamMatchStats.team_id, m.TeamMatchStats.match_id, m.TeamMatchStats.shots,
                   m.TeamMatchStats.shots_on_target))}
        # Titulares de los 10 partidos anteriores de cada equipo, partido a partido
        by_match = defaultdict(list)
        for r in rows:
            by_match[(r.team_id, r.match_id, r.kickoff_utc)].append(r)
        hist = defaultdict(lambda: deque(maxlen=10))
        starts_before = {}
        for (team, mid, _ko), ps in sorted(by_match.items(), key=lambda x: x[0][2]):
            for r in ps:
                starts_before[(r.player_id, mid)] = sum(r.player_id in h for h in hist[team])
            hist[team].append({r.player_id for r in ps if r.is_starter})

        for i, cut in enumerate(cutoffs[:-1]):
            players, priors = fitting.fit_players(s, before=cut)
            nxt = cutoffs[i + 1]
            for r in rows:
                if not (cut <= r.kickoff_utc < nxt) or not r.is_starter or (r.minutes or 0) < 60 or r.position == "GK":
                    continue
                if r.shots is None or len(hist) == 0:
                    continue
                team = team_stats.get((r.team_id, r.match_id))
                pr = players.get(r.player_id)
                prior = priors.get(r.position or "MF") or {}
                if not team or team[0] is None or not prior:
                    continue
                for j, st in enumerate(STATS):
                    if f"{st}_share" not in prior:
                        continue
                    exposure = ((pr or {}).get("volume_team90") or {}).get(st, 0.0)
                    obs = ((pr or {}).get("volume_share") or {}).get(st, 0.0)
                    k_vol = VOLUME_SHARE_PRIOR_MATCHES[st] * prior.get(f"{st}_team90", 0.0)
                    share = (obs * exposure + prior[f"{st}_share"] * k_vol) / (exposure + k_vol) if exposure + k_vol else 0.0
                    mu = share * r.minutes / 90 * (team[j] or 0)
                    real = r.shots if st == "shots" else (r.shots_on_target or 0)
                    if mu > 0:
                        out.append((r.kickoff_utc, group(starts_before.get((r.player_id, r.match_id), 0)), st, real, mu))
            print(f"  {cut:%Y-%m}: {len(out)} titularidades acumuladas", flush=True)

    print("\nModelo de jugadores fuera de muestra (con minutos y remates reales del equipo): real / esperado")
    for g in ("0-2 de 10", "3-7 de 10", "8-10 de 10"):
        cells = []
        for st in STATS:
            v = [(a, b) for _, gg, s_, a, b in out if gg == g and s_ == st]
            real, mu = (np.array(x) for x in zip(*v, strict=True))
            z = (real - mu) / np.sqrt(mu * (1 + DISPERSION * mu))
            cells.append(f"{st} {real.sum() / mu.sum():.3f} (z {z.mean():+.3f} ± {1.96 * z.std(ddof=1) / math.sqrt(len(z)):.3f})")
        print(f"  titular en {g} ({sum(1 for x in out if x[1] == g and x[2] == 'shots'):>6}): " + "; ".join(cells))

    print(f"\nPrueba honesta: escala general y factor relativo de los «0-2 de 10», aprendidos antes del {SPLIT:%Y-%m-%d};"
          " después, los «0-2 de 10» con la escala sola frente a escala × factor")
    for st in STATS:
        tr_all = [(a, b) for d, _g, s_, a, b in out if s_ == st and d < SPLIT]
        tr = [(a, b) for d, g, s_, a, b in out if g == "0-2 de 10" and s_ == st and d < SPLIT]
        te = [(a, b) for d, g, s_, a, b in out if g == "0-2 de 10" and s_ == st and d >= SPLIT]
        scale = sum(a for a, _ in tr_all) / sum(b for _, b in tr_all)
        f = (sum(a for a, _ in tr) / sum(b for _, b in tr)) / scale
        gain = []
        for real, mu in te:
            pf, p0 = dist.count_pmf(mu * scale * f, DISPERSION, 40), dist.count_pmf(mu * scale, DISPERSION, 40)
            gain.append(math.log(max(pf[int(real)], 1e-12)) - math.log(max(p0[int(real)], 1e-12)))
        g = np.array(gain)
        print(f"  {st:<16} factor relativo {f:.3f} ({len(tr)}): {g.mean():+.4f} ± "
              f"{1.96 * g.std(ddof=1) / math.sqrt(len(g)):.4f} en {len(g)}")

if __name__ == "__main__":
    main()
