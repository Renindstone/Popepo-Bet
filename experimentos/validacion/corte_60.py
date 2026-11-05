"""Mínimo de 60 % de probabilidad en el corte: ¿qué pasa con las apuestas que quedan?

Mismo backtest de siempre (`apuestas backtest`, valor ≥ 3 %) con el rango de cuotas del corte (1,50-2,60), separando las
apuestas por probabilidad. Compara lo que el modelo esperaba acertar con lo que acertó, el ROI y el CLV. La confianza
del corte no se puede replicar en el backtest, así que no se filtra por ella.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/corte_60.py (unos 4 min)
"""

from __future__ import annotations

from datetime import date

import numpy as np

from apuestas.backtest import engine


def row(name: str, bets: list[engine.Bet]) -> None:
    if not bets:
        print(f"  {name:<12} sin apuestas")
        return
    decided = [b for b in bets if b.result != "push"]
    profit = np.array([engine._profit(b) for b in bets])
    clv = [b.odds / b.closing - 1 for b in bets if b.closing]
    print(f"  {name:<12} {len(bets):>6} apuestas · cuota {np.mean([b.odds for b in bets]):.2f} · "
          f"esperado {np.mean([b.prob for b in decided]):.1%} · acierto "
          f"{np.mean([b.result in ('win', 'half_win') for b in decided]):.1%} · ROI {profit.mean():+.1%} "
          f"± {1.96 * profit.std(ddof=1) / np.sqrt(len(profit)):.1%} · CLV {np.mean(clv) if clv else 0:+.1%}")


def main() -> None:
    res = engine.run(date(2024, 8, 1), date(2026, 10, 28), odds_range=(1.5, 2.6))
    for strategy in ("solo_modelo", "modelo+mercado"):
        bets = [b for b in res.bets if b.strategy == strategy]
        print(strategy)
        row("todas", bets)
        row("menos de 60", [b for b in bets if b.prob < 0.60])
        row("60 o más", [b for b in bets if b.prob >= 0.60])


if __name__ == "__main__":
    main()
