"""Córners y tarjetas del modelo frente a las cuotas de Betano guardadas (OddsPapi), para decidir si pueden entrar en
la apuesta del día (hoy `pick_allow_stat_markets=False`).

Para cada partido terminado con la previa guardada (`prediction.payload`, desde el 24-10-2026) y cuotas de Betano
antes del inicio:
- probabilidad del modelo de Más de cada línea (binomial negativa con la media y la dispersión de la previa; el total
  es la suma de los dos equipos);
- probabilidad de Betano sin margen (las dos cuotas de la línea, método potencia);
- lo que pasó (córners; tarjetas = amarillas + rojas, como se liquida).

Compara la pérdida logarítmica de los dos (menos es mejor) y el rendimiento de apostar 1 unidad a cada selección con
valor ≥ 3 % según el modelo. Con pocas semanas de cuotas la muestra es corta: mira el intervalo, no solo la media.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/estadisticas_betano.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

import numpy as np
from sqlalchemy import select, text

from apuestas.betting import odds as oddsmath
from apuestas.betting.settlement import RESULT_PROFIT
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models import distributions as dist
from apuestas.models import surprise as sp
from apuestas.services import weekly

MARKETS = {  # mercado → (estadística, alcance)
    "ou_corners": ("corners", "total"), "ou_corners_home": ("corners", "home"), "ou_corners_away": ("corners", "away"),
    "ou_cards": ("cards", "total"), "ou_cards_home": ("cards", "home"), "ou_cards_away": ("cards", "away"),
}
MIN_EV = 0.03


def pmf_for(payload: dict, stat: str, scope: str) -> dict[int, float] | None:
    c = payload.get("counts", {}).get(stat)
    if not c:
        return None
    alpha = c.get("dispersion", 0.0)
    home, away = sp.count_dist(c["home"], alpha), sp.count_dist(c["away"], alpha)
    arr = home if scope == "home" else away if scope == "away" else np.convolve(home, away)
    return {k: float(v) for k, v in enumerate(arr)}


def actual(stats: dict[str, m.TeamMatchStats], stat: str, scope: str) -> int | None:
    def one(st):
        if st is None:
            return None
        return st.corners if stat == "corners" else (
            None if st.yellow_cards is None else st.yellow_cards + (st.red_cards or 0))
    h, a = one(stats.get("home")), one(stats.get("away"))
    if scope == "home":
        return h
    if scope == "away":
        return a
    return None if h is None or a is None else h + a


def main() -> None:
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = s.execute(select(m.Match, m.Prediction).join(m.Prediction, m.Prediction.match_id == m.Match.id)
                         .where(m.Match.status == "finished", m.Match.home_goals.is_not(None))).all()
        loss = defaultdict(lambda: {"modelo": [], "betano": []})
        bets = defaultdict(list)
        n_matches = 0
        for mt, pred in rows:
            odds_rows = list(s.scalars(select(m.OddsSnapshot).where(
                m.OddsSnapshot.match_id == mt.id, m.OddsSnapshot.bookmaker.like("betano%"),
                m.OddsSnapshot.market.in_(list(MARKETS)))))
            if not odds_rows:
                continue
            n_matches += 1
            pk = weekly.pre_kickoff(odds_rows, weekly._aware(mt.kickoff_utc))
            prices = {}
            for kind in ("live", "opening"):  # el último precio antes del inicio
                for (_book, market, sel, line), price in pk.get(kind, {}).items():
                    prices.setdefault((market, line), {})[sel] = price
            stats = {("home" if st.team_id == mt.home_team_id else "away"): st for st in s.scalars(
                select(m.TeamMatchStats).where(m.TeamMatchStats.match_id == mt.id))}
            for (market, line), sel in prices.items():
                if "over" not in sel or "under" not in sel or line is None:
                    continue
                stat, scope = MARKETS[market]
                value, pmf = actual(stats, stat, scope), pmf_for(pred.payload, stat, scope)
                if value is None or pmf is None:
                    continue
                p_model = dist.over(pmf, line).effective_prob()
                p_book = oddsmath.devig_power([sel["over"], sel["under"]])[0]
                o = dist.over({value: 1.0}, line)
                if o.push > 0.5:  # línea entera que cae justo: no informa
                    continue
                hit = 1.0 if (o.win + o.half_win) > 0.5 else 0.0
                for who, p in (("modelo", p_model), ("betano", p_book)):
                    p = min(max(p, 1e-4), 1 - 1e-4)
                    loss[stat][who].append(-(hit * math.log(p) + (1 - hit) * math.log(1 - p)))
                for side, p_side, price in (("over", p_model, sel["over"]), ("under", 1 - p_model, sel["under"])):
                    if p_side * price - 1 >= MIN_EV:
                        res = dist.over({value: 1.0}, line) if side == "over" else dist.under({value: 1.0}, line)
                        name = next(k for k in ("win", "half_win", "push", "half_loss", "loss") if getattr(res, k) > 0.5)
                        k = RESULT_PROFIT[name]
                        bets[stat].append(k * (price - 1) if k > 0 else k)

    print(f"Partidos con previa y cuotas de Betano: {n_matches}")
    for stat in ("corners", "cards"):
        lm, lb = loss[stat]["modelo"], loss[stat]["betano"]
        if not lm:
            continue
        diff = [a - b for a, b in zip(lm, lb, strict=True)]
        half = 1.96 * statistics.stdev(diff) / math.sqrt(len(diff)) if len(diff) > 1 else float("nan")
        b = bets[stat]
        roi = statistics.fmean(b) if b else float("nan")
        roi_half = 1.96 * statistics.stdev(b) / math.sqrt(len(b)) if len(b) > 1 else float("nan")
        print(f"  {stat:<8} líneas {len(lm):>4}: pérdida log. modelo {statistics.fmean(lm):.4f}, Betano "
              f"{statistics.fmean(lb):.4f} (modelo − Betano {statistics.fmean(diff):+.4f} ± {half:.4f}); "
              f"apuestas con valor ≥3 %: {len(b)}, rendimiento {roi:+.1%} ± {roi_half:.1%}")


if __name__ == "__main__":
    main()
