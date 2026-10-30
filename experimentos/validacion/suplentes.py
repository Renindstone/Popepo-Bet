"""Props de suplentes: las apuestas a un jugador que no sale se anulan, así que su probabilidad debe ser la de si
juega (`PlayerProjection.play_prob`).

Con las previas guardadas con el once confirmado (desde el 24-10-2026), para cada suplente: su tasa por minuto de la
previa (λ / minutos esperados) por los minutos que juega un suplente que sale (`analysis.SUB_MINUTES`) es la λ
condicionada a que juegue. Se compara con lo que hicieron los suplentes que salieron (suma de λ frente a lo real y
P(al menos 1) frente a la frecuencia real), y la λ sin condicionar con todos los suplentes (los que no salieron,
con 0).

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/suplentes.py
"""

from __future__ import annotations

import math

from sqlalchemy import select, text

from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services.analysis import SUB_MINUTES, SUB_PLAY_RATE

STATS = {"shots": "shots", "shots_on_target": "shots_on_target", "goals": "goals"}


def main() -> None:
    rows = []
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        q = (select(m.Prediction, m.Match).join(m.Match, m.Match.id == m.Prediction.match_id)
             .where(m.Prediction.stage == "confirmed", m.Match.status == "finished"))
        for pred, mt in s.execute(q):
            played = {r.player_id: r for r in s.scalars(select(m.PlayerMatchStats).where(
                m.PlayerMatchStats.match_id == mt.id))}
            for p in pred.payload.get("players", []):
                if p.get("start_prob", 1) > 0 or not p.get("expected_minutes"):
                    continue
                st = played.get(p["player_id"])
                mins = (st.minutes or 0) if st else 0
                per_min = {k: p["lam"].get(k, 0.0) / p["expected_minutes"] for k in STATS}
                rows.append((mins, per_min, st))
    played = [(mi, pm, st) for mi, pm, st in rows if mi > 0]
    print(f"Suplentes con previa del once confirmado: {len(rows)}; salieron {len(played)} "
          f"({len(played) / max(len(rows), 1):.1%}; el modelo supone {SUB_PLAY_RATE:.1%}), "
          f"{sum(mi for mi, _, _ in played) / max(len(played), 1):.1f} min de media (supone {SUB_MINUTES})")
    for k, col in STATS.items():
        lam_c = [pm[k] * SUB_MINUTES for _, pm, _ in played]
        real = [getattr(st, col) or 0 for _, _, st in played]
        p_any = sum(1 - math.exp(-x) for x in lam_c)
        uncond = sum(pm[k] * SUB_MINUTES * SUB_PLAY_RATE for _, pm, _ in rows)
        real_all = sum((getattr(st, col) or 0) if st else 0 for _, _, st in rows)
        print(f"  {k:<16} si juega: esperado {sum(lam_c):6.1f}, real {sum(real):4d}; al menos 1: esperado "
              f"{p_any:5.1f}, real {sum(1 for x in real if x > 0):3d} | sin condicionar (todos): esperado "
              f"{uncond:6.1f}, real {real_all:4d}")


if __name__ == "__main__":
    main()
