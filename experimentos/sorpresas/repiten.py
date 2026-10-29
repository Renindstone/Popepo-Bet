"""¿Se repiten las sorpresas? Mide si los equipos que el radar marcaría como «en racha» o «en baja» siguen
sorprendiendo a la casa en su partido siguiente o vuelven a lo esperado.

Para cada partido terminado de las seis competiciones desde 2023-07 calcula la puntuación por sorpresa de cada equipo
frente a la casa (resultado contra el 1X2 sin margen antes del partido y goles contra su línea; `weekly.team_items`, la
misma de Sorpresas). Después recorre cada equipo en orden: con los partidos de los 28 días anteriores decide si estaba
en racha, en baja o fuera del radar (`radar.classify`), y anota cómo le fue en el partido de ese día.

Si la casa ya recoge las rachas, el partido siguiente de los equipos en racha o en baja debería quedar en ~0. Si
siguen sorprendiendo en la misma dirección, el aviso podría bajar la confianza de las apuestas contra ellos.

Solo lee la base de datos (transacción de solo lectura). Uso: .venv/bin/python experimentos/sorpresas/repiten.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services import radar, weekly

SINCE = datetime(2023, 7, 1, tzinfo=UTC)
WINDOW = timedelta(days=radar.WINDOW_DAYS)


def scored_matches(s) -> list[dict]:
    codes = [c.code for c in FULL]
    matches = list(s.scalars(select(m.Match).join(m.Competition).where(
        m.Competition.code.in_(codes), m.Match.status == "finished", m.Match.home_goals.is_not(None),
        m.Match.kickoff_utc >= SINCE).order_by(m.Match.kickoff_utc)))
    ids = [mt.id for mt in matches]
    odds: dict[int, list] = defaultdict(list)
    for i in range(0, len(ids), 2000):
        for r in s.scalars(select(m.OddsSnapshot).where(m.OddsSnapshot.match_id.in_(ids[i:i + 2000]),
                                                        m.OddsSnapshot.market.in_(weekly.MARKETS))):
            odds[r.match_id].append(r)
    out = []
    for mt in matches:
        pk = weekly.pre_kickoff(odds.get(mt.id, []), weekly._aware(mt.kickoff_utc))
        for side, team in (("home", mt.home_team_id), ("away", mt.away_team_id)):
            items, _ = weekly.team_items(mt, side, pk, None, None, 0.0)
            res = next((i for i in items if i["item"] == "result"), None)
            if res is None:
                continue
            gf, ga = (mt.home_goals, mt.away_goals) if side == "home" else (mt.away_goals, mt.home_goals)
            out.append({"team": team, "at": weekly._aware(mt.kickoff_utc), "score": sum(i["score"] for i in items),
                        "result": res["score"], "p_win": res["p_over"], "gf": gf, "ga": ga})
    return out


def ci(xs: list[float]) -> str:
    if len(xs) < 2:
        return f"n={len(xs)}"
    mean, sd = statistics.fmean(xs), statistics.stdev(xs)
    half = 1.96 * sd / math.sqrt(len(xs))
    return f"{mean:+.3f} ± {half:.3f} (n={len(xs)})"


def main() -> None:
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = scored_matches(s)
    by_team: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_team[r["team"]].append(r)

    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for games in by_team.values():
        for k, g in enumerate(games):
            window = [p for p in games[:k] if g["at"] - p["at"] <= WINDOW]
            total = sum(p["score"] for p in window)
            upset = any(p["gf"] > p["ga"] and p["p_win"] <= radar.UPSET_MAX for p in window)
            flop = any(p["gf"] < p["ga"] and p["p_win"] >= radar.FLOP_MIN for p in window)
            kind = radar.classify(total, upset, flop) or "fuera"
            labels = [kind]
            if kind == "racha" and upset:
                labels.append("racha con batacazo")
            if kind == "baja" and flop:
                labels.append("baja con pinchazo")
            for label in labels:
                groups[label]["resultado"].append(g["result"])
                groups[label]["todo"].append(g["score"])
                groups[label]["gana"].append(1.0 if g["gf"] > g["ga"] else 0.0)
                groups[label]["p_casa"].append(g["p_win"])

    print(f"Partidos de equipo puntuados desde {SINCE:%Y-%m-%d}: {len(rows)}")
    print("Partido siguiente: puntuación del resultado frente a la casa (0 = lo que esperaba la casa)")
    for label in ("racha", "racha con batacazo", "fuera", "baja", "baja con pinchazo"):
        g = groups[label]
        if not g["resultado"]:
            continue
        won, p = statistics.fmean(g["gana"]), statistics.fmean(g["p_casa"])
        print(f"  {label:<20} resultado {ci(g['resultado'])}   resultado+goles {ci(g['todo'])}   "
              f"gana {won:.1%} frente a {p:.1%} de la casa")


if __name__ == "__main__":
    main()
