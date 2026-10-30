"""Offsides: ¿un modelo como el de córners predice mejor que la media?

El modelo de conteo de siempre (`ratings.fit`, binomial negativa) aplicado a los offsides: el «ataque» de un equipo es
cuánto caen sus delanteros en fuera de juego y su «defensa», cuánto hace caer al rival (una línea adelantada, como la
del Barça, deja una defensa baja: el rival cae más). Se añade a `apuestas backtest` solo dentro de este script (los
offsides de `team_match_stats`, FotMob) y se compara la log-verosimilitud de cada equipo y del total con la media,
reajustando cada semana solo con lo anterior (2024-08 a 2026-10). Dos contracciones (K partidos). Además, si la
«trampa» de cada equipo se repite: correlación de su defensa entre 2024-25 y 2025-26.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/offsides.py (unos 4 min)
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
from sqlalchemy import select, text

from apuestas.backtest import engine
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models import fitting, ratings


def offsides() -> dict[tuple[int, int], int]:
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        return {(mid, t): o for mid, t, o in s.execute(select(
            m.TeamMatchStats.match_id, m.TeamMatchStats.team_id, m.TeamMatchStats.offsides).where(
            m.TeamMatchStats.offsides.is_not(None)))}


def main() -> None:
    off = offsides()
    orig_load = fitting.load_matches

    def load(*a, **k):
        rows = orig_load(*a, **k)
        for r in rows:
            r.stats_h["offsides"] = off.get((r.match_id, r.home))
            r.stats_a["offsides"] = off.get((r.match_id, r.away))
        return rows

    fitting.load_matches = engine.load_matches = load
    stats0, eng0, prior0 = fitting.COUNT_STATS, engine.COUNT_STATS, dict(fitting.COUNT_PRIOR_MATCHES)
    try:
        for k in (5.0, 10.0):
            fitting.COUNT_STATS = engine.COUNT_STATS = (*stats0, "offsides")
            fitting.COUNT_PRIOR_MATCHES = {**prior0, "offsides": k}
            res = engine.run(date(2024, 8, 1), date(2026, 10, 28)).summary()["count_models"]
            print(f"K = {k:g}")
            for key in ("offsides", "offsides por equipo", "corners", "corners por equipo"):
                print(f"  {key:<22} {res.get(key)}")
    finally:
        fitting.load_matches = engine.load_matches = orig_load
        fitting.COUNT_STATS, engine.COUNT_STATS, fitting.COUNT_PRIOR_MATCHES = stats0, eng0, prior0

    # ¿Se repite la «trampa»? La defensa de cada equipo en offsides al final de 2024-25 y de 2025-26
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = load(s, before=datetime(2026, 7, 1, tzinfo=UTC), since=datetime(2023, 7, 1, tzinfo=UTC))
    obs = fitting.count_obs(rows, "offsides")
    a = ratings.fit([o for o in obs if o.day < date(2025, 6, 1) and o.day >= date(2024, 7, 1)], date(2025, 6, 1),
                    half_life_days=10_000, prior_matches=5.0)
    b = ratings.fit([o for o in obs if o.day >= date(2025, 7, 1)], date(2026, 6, 1), half_life_days=10_000,
                    prior_matches=5.0)
    common = [t for t in a.defence if t in b.defence and a.n_matches.get(t, 0) >= 20 and b.n_matches.get(t, 0) >= 20]
    da, db = np.array([a.defence[t] for t in common]), np.array([b.defence[t] for t in common])
    aa, ab = np.array([a.attack[t] for t in common]), np.array([b.attack[t] for t in common])
    print(f"\nEntre 2024-25 y 2025-26 ({len(common)} equipos con 20 partidos o más en las dos): correlación de la "
          f"«trampa» (defensa) {np.corrcoef(da, db)[0, 1]:+.2f}; de caer en fuera de juego (ataque) "
          f"{np.corrcoef(aa, ab)[0, 1]:+.2f}")
    names = {}
    with session_scope() as s:
        names = {t.id: t.name for t in s.scalars(select(m.Team).where(m.Team.id.in_(common)))}
    trap = sorted(common, key=lambda t: b.defence[t])[:6]
    print("Los que más hacen caer al rival en 2025-26 (defensa más baja): " + ", ".join(
        f"{names[t]} (×{np.exp(-b.defence[t]):.2f}; antes ×{np.exp(-a.defence[t]):.2f})" for t in trap))


if __name__ == "__main__":
    main()
