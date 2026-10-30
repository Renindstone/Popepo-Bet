"""Comparar precios: ¿cuántas veces paga Betano más que la cuota justa de Pinnacle, y qué pasa con esas apuestas?

Con las cuotas de OddsPapi guardadas desde el 19-10-2026, para cada partido terminado:
- en cada descarga de Betano (hora t), la probabilidad sin margen de Pinnacle con lo que se sabía en ese momento
  (su última foto hasta t + 15 min, con todos los lados de la misma línea: `analysis.book_fair_prob`);
- valor = cuota de Betano × esa probabilidad − 1. Cuenta cada selección una vez, la primera vez que lo pasa;
- resultado de la apuesta (`settlement.settle`) y CLV frente a Pinnacle sin margen en su última foto antes del
  inicio, solo cuando esa foto es posterior a t (si no, no hay con qué medir el cierre).

El mercado de referencia es el mismo que hace la apuesta del día con 75 % de peso, pero aquí sin modelo: es comparar
precios. Con pocas semanas de cuotas la muestra es corta: mira el intervalo y el CLV, no solo el rendimiento.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/betano_pinnacle.py
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta

import numpy as np
from sqlalchemy import select, text

from apuestas.betting.settlement import RESULT_PROFIT, settle
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.services import weekly
from apuestas.services.analysis import book_fair_prob

THRESHOLDS = (0.0, 0.02, 0.05)
GOALS = ("1x2", "dc", "dnb", "btts", "ah", "eh", "ou_goals", "ou_goals_home", "ou_goals_away")
LAG = timedelta(minutes=15)


def latest(rows: list[m.OddsSnapshot], until) -> list[m.OddsSnapshot]:
    """La última foto de cada (mercado, selección, línea) hasta `until`. Solo se guarda una foto cuando el precio
    cambia, así que no se sabe si una línea dejó de ofrecerse (`last_seen_at` lo apunta desde el 29-10-2026)."""
    out: dict[tuple, m.OddsSnapshot] = {}
    for r in sorted(rows, key=lambda r: weekly._aware(r.captured_at)):
        if weekly._aware(r.captured_at) <= until:
            out[(r.market, r.selection, r.line)] = r
    return list(out.values())


def main() -> None:
    bets: dict[tuple, dict] = {}
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        matches = s.scalars(select(m.Match).where(m.Match.status == "finished", m.Match.id.in_(
            select(m.OddsSnapshot.match_id).where(m.OddsSnapshot.bookmaker.like("betano%"))))).all()
        for mt in matches:
            ko = weekly._aware(mt.kickoff_utc)
            rows = [r for r in s.scalars(select(m.OddsSnapshot).where(
                m.OddsSnapshot.match_id == mt.id, m.OddsSnapshot.kind == "live",
                (m.OddsSnapshot.bookmaker.like("betano%")) | (m.OddsSnapshot.bookmaker == "pinnacle")))
                if weekly._aware(r.captured_at) < ko]
            betano = [r for r in rows if r.bookmaker.startswith("betano")]
            pin = [r for r in rows if r.bookmaker == "pinnacle"]
            if not betano or not pin:
                continue
            pin_close = latest(pin, ko)
            close_at = max(weekly._aware(r.captured_at) for r in pin_close)
            for t in sorted({weekly._aware(r.captured_at) for r in betano}):
                pin_t = latest(pin, t + LAG)
                for b in latest(betano, t):
                    key = (mt.id, b.market, b.selection, b.line)
                    if key in bets or weekly._aware(b.captured_at) != t:
                        continue
                    p = book_fair_prob(pin_t, "pinnacle", b.market, b.selection, b.line)
                    if not p:
                        continue
                    ev = b.price * p - 1
                    if ev < min(THRESHOLDS):
                        continue
                    res = settle(s, mt, b.market, b.selection, b.line)
                    if res is None or res == "void":
                        continue
                    k = RESULT_PROFIT[res]
                    p_close = book_fair_prob(pin_close, "pinnacle", b.market, b.selection, b.line)
                    clv = b.price * p_close - 1 if p_close and close_at > t + LAG else None
                    bets[key] = {"market": b.market, "ev": ev, "profit": k * (b.price - 1) if k > 0 else k,
                                 "clv": clv, "odds": b.price}

    print(f"Partidos terminados con Betano y Pinnacle: {len({k[0] for k in bets})} con alguna selección")
    groups = defaultdict(list)
    for b in bets.values():
        groups["goles" if b["market"] in GOALS else "estadísticas"].append(b)
    for name, items in groups.items():
        for th in THRESHOLDS:
            sel = [b for b in items if b["ev"] >= th]
            if not sel:
                continue
            pr = np.array([b["profit"] for b in sel])
            clv = np.array([b["clv"] for b in sel if b["clv"] is not None])
            half = 1.96 * pr.std(ddof=1) / math.sqrt(len(pr)) if len(pr) > 1 else float("nan")
            clv_text = (f"CLV {clv.mean():+.2%} en {len(clv)} ({(clv > 0).mean():.0%} positivos)" if len(clv)
                        else "sin cierre posterior")
            print(f"  {name:<13} valor ≥ {th:.0%}: {len(sel):>4} apuestas, cuota media {np.mean([b['odds'] for b in sel]):.2f}, "
                  f"valor anunciado {np.mean([b['ev'] for b in sel]):+.1%}, rendimiento {pr.mean():+.1%} ± {half:.1%}; "
                  f"{clv_text}")


if __name__ == "__main__":
    main()
