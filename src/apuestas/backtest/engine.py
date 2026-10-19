"""Backtest "walk-forward": se reajusta el modelo cada semana usando SOLO datos anteriores y se
apuesta contra las cuotas de bet365 de ese momento. Mide si el modelo habría ganado dinero.

Métricas:
- Log-loss / Brier del 1X2: modelo vs probabilidades de bet365 vs Pinnacle (sin margen).
- ROI de apuestas con valor (1X2, más/menos 2.5 y hándicap asiático principal) a cuota previa de bet365.
- CLV medio: cuota tomada vs cuota de cierre de bet365 (indicador de ventaja real a corto plazo).
- Calibración de modelos de remates, córners y tarjetas (verosimilitud frente a la media de la liga).

Limitación honesta: el backtest no usa alineaciones (no hay alineaciones previstas históricas), así que
mide el modelo base; los ajustes por alineación/bajas solo se podrán evaluar con los picks reales.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import numpy as np
from scipy.stats import nbinom, poisson
from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.db import models as m
from apuestas.models import distributions as dist
from apuestas.models import ratings
from apuestas.models.fitting import (
    COUNT_STATS,
    MatchRow,
    count_obs,
    fit_referees,
    fit_rho,
    goals_obs,
    load_matches,
)

W_MODEL = 0.25


@dataclass
class Bet:
    day: date
    competition: str
    market: str
    selection: str
    line: float | None
    odds: float
    closing: float | None
    prob: float
    ev: float
    result: str
    strategy: str


@dataclass
class BacktestResult:
    params: dict
    n_matches: int = 0
    logloss: dict[str, float] = field(default_factory=dict)
    brier: dict[str, float] = field(default_factory=dict)
    bets: list[Bet] = field(default_factory=list)
    count_calibration: dict[str, dict] = field(default_factory=dict)

    def summary(self) -> dict:
        def agg(items: list[Bet]) -> dict:
            if not items:
                return {"bets": 0}
            pl = sum(_profit(b) for b in items)
            clv = [b.odds / b.closing - 1 for b in items if b.closing]
            return {"bets": len(items), "profit_units": round(pl, 2), "roi": round(pl / len(items), 4),
                    "hit_rate": round(sum(b.result in ("win", "half_win") for b in items) / len(items), 3),
                    "avg_odds": round(float(np.mean([b.odds for b in items])), 2),
                    "avg_clv": round(float(np.mean(clv)), 4) if clv else None,
                    "beat_closing_pct": round(sum(c > 0 for c in clv) / len(clv), 3) if clv else None}

        by: dict[str, dict[str, list[Bet]]] = defaultdict(lambda: defaultdict(list))
        for b in self.bets:
            by[b.strategy]["total"].append(b)
            by[b.strategy][b.market].append(b)
            by[b.strategy][b.competition].append(b)
        return {
            "params": self.params,
            "matches_evaluated": self.n_matches,
            "logloss_1x2": {k: round(v, 4) for k, v in self.logloss.items()},
            "brier_1x2": {k: round(v, 4) for k, v in self.brier.items()},
            "betting": {strat: {k: agg(v) for k, v in groups.items()} for strat, groups in by.items()},
            "count_models": self.count_calibration,
        }


def _profit(b: Bet) -> float:
    k = {"win": 1.0, "half_win": 0.5, "push": 0.0, "half_loss": -0.5, "loss": -1.0}[b.result]
    return k * (b.odds - 1) if k > 0 else k


def _odds_map(s: Session, match_ids: list[int]) -> dict[int, dict[tuple, float]]:
    out: dict[int, dict[tuple, float]] = defaultdict(dict)
    for r in s.scalars(select(m.OddsSnapshot).where(m.OddsSnapshot.match_id.in_(match_ids))):
        out[r.match_id][(r.bookmaker, r.market, r.selection, r.line, r.kind)] = r.price
    return out


def run(
    start: date,
    end: date,
    competitions: tuple[str, ...] = ("EPL", "BUN", "LAL"),
    half_life_days: float = 240.0,
    xg_weight: float = 0.85,
    min_ev: float = 0.03,
    odds_range: tuple[float, float] = (1.4, 3.6),
    step_days: int = 7,
    w_model: float = W_MODEL,
) -> BacktestResult:
    from apuestas.db.session import _factory

    res = BacktestResult(params={"start": start.isoformat(), "end": end.isoformat(), "half_life": half_life_days,
                                 "xg_weight": xg_weight, "min_ev": min_ev, "odds_range": odds_range,
                                 "competitions": competitions, "w_model": w_model})
    s = _factory()()
    try:
        all_rows = load_matches(s, before=datetime.combine(end, datetime.min.time(), UTC) + timedelta(days=1),
                                since=datetime.combine(start, datetime.min.time(), UTC) - timedelta(days=1100))
        odds = _odds_map(s, [r.match_id for r in all_rows if r.competition in competitions and r.day >= start])
    finally:
        s.close()

    ll: dict[str, list[float]] = defaultdict(list)
    br: dict[str, list[float]] = defaultdict(list)
    count_ll: dict[str, list[tuple[float, float]]] = defaultdict(list)

    cur = start
    while cur <= end:
        nxt = cur + timedelta(days=step_days)
        train = [r for r in all_rows if r.day < cur]
        test = [r for r in all_rows if cur <= r.day < nxt and r.competition in competitions]
        if test and len(train) > 500:
            gm = ratings.fit(goals_obs(train, xg_weight), cur, half_life_days=half_life_days)
            rho = fit_rho([r for r in train if (cur - r.day).days < 730], gm, set(competitions))
            cms = {}
            for stat in COUNT_STATS:
                obs = count_obs(train, stat)
                if len(obs) > 300:
                    cms[stat] = ratings.fit(obs, cur, half_life_days=half_life_days, l2=1.0)
            refs = fit_referees(train, cms["cards"], cms.get("fouls")) if "cards" in cms else {}
            for r in test:
                _evaluate_match(r, gm, rho, odds.get(r.match_id, {}), res, ll, br, min_ev, odds_range, w_model)
                _evaluate_counts(r, cms, count_ll, refs)
        cur = nxt

    res.logloss = {k: float(np.mean(v)) for k, v in ll.items() if v}
    res.brier = {k: float(np.mean(v)) for k, v in br.items() if v}
    for stat, pairs in count_ll.items():
        model_ll = float(np.mean([p[0] for p in pairs]))
        naive_ll = float(np.mean([p[1] for p in pairs]))
        baseline = "loglik_sin_arbitro" if stat.endswith("+arbitro") else "loglik_league_avg"
        res.count_calibration[stat] = {"matches": len(pairs), "loglik_model": round(model_ll, 4),
                                       baseline: round(naive_ll, 4), "improvement": round(model_ll - naive_ll, 4)}
    return res


def _evaluate_match(r: MatchRow, gm, rho: float, od: dict, res: BacktestResult, ll, br, min_ev, odds_range,
                    w_model: float = W_MODEL) -> None:
    if r.home not in gm.attack or r.away not in gm.attack:
        return
    lh, la = gm.expected(r.home, r.away, r.neutral)
    mat = dist.dixon_coles_matrix(lh, la, rho)
    p_model = [float(np.tril(mat, -1).sum()), float(np.trace(mat)), float(np.triu(mat, 1).sum())]
    outcome_idx = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
    res.n_matches += 1

    def book_probs(book: str) -> list[float] | None:
        o = [od.get((book, "1x2", sel, None, "opening")) for sel in ("home", "draw", "away")]
        return oddsmath.devig(o) if all(o) else None

    sharp = book_probs("pinnacle") or book_probs("betfair_ex")
    b365 = book_probs("bet365")
    variants = {"modelo": p_model}
    if b365:
        variants["bet365"] = b365
    if sharp:
        variants["pinnacle"] = sharp
        variants["mezcla"] = [w_model * a + (1 - w_model) * b for a, b in zip(p_model, sharp, strict=True)]
    if not (b365 and sharp):
        return  # comparamos solo partidos con todas las referencias
    for name, p in variants.items():
        ll[name].append(-math.log(max(p[outcome_idx], 1e-9)))
        br[name].append(sum((p[i] - (1.0 if i == outcome_idx else 0.0)) ** 2 for i in range(3)))

    diff = dist.diff_pmf_from_matrix(mat)
    total = dist.total_pmf_from_matrix(mat)

    def sharp_two_way(market: str, sel_a: str, sel_b: str, line_a, line_b) -> tuple[float, float] | None:
        for book in ("pinnacle", "betfair_ex"):
            a = od.get((book, market, sel_a, line_a, "opening"))
            b = od.get((book, market, sel_b, line_b, "opening"))
            if a and b:
                pa, pb = oddsmath.devig([a, b])
                return pa, pb
        return None

    candidates = []
    for i, sel in enumerate(("home", "draw", "away")):
        o = od.get(("bet365", "1x2", sel, None, "opening"))
        if o:
            candidates.append(("1x2", sel, None, o, od.get(("bet365", "1x2", sel, None, "closing")),
                               dist.prob_outcome(p_model[i]), sharp[i]))
    sh_ou = sharp_two_way("ou_goals", "over", "under", 2.5, 2.5)
    for j, sel in enumerate(("over", "under")):
        o = od.get(("bet365", "ou_goals", sel, 2.5, "opening"))
        if o:
            out = dist.over(total, 2.5) if sel == "over" else dist.under(total, 2.5)
            candidates.append(("ou_goals", sel, 2.5, o, od.get(("bet365", "ou_goals", sel, 2.5, "closing")),
                               out, sh_ou[j] if sh_ou else None))
    ah_lines = {k[3] for k in od if k[0] == "bet365" and k[1] == "ah" and k[2] == "home" and k[4] == "opening"}
    for line in ah_lines:
        sh_ah = sharp_two_way("ah", "home", "away", line, -line)
        for j, (sel, ln) in enumerate((("home", line), ("away", -line))):
            o = od.get(("bet365", "ah", sel, ln, "opening"))
            if not o:
                continue
            d = diff if sel == "home" else {-k: v for k, v in diff.items()}
            out = dist.line_outcome(d, ln)
            # Cierre: la línea puede moverse; solo se usa si es la misma
            closing = od.get(("bet365", "ah", sel, ln, "closing"))
            candidates.append(("ah", sel, ln, o, closing, out, sh_ah[j] if sh_ah else None))

    for market, sel, line, o, closing, out, sharp_p in candidates:
        if not (odds_range[0] <= o <= odds_range[1]):
            continue
        result = _settle(r, market, sel, line)
        no_push = max(1e-9, 1 - out.push)
        p_m = out.effective_prob()
        ev_m = (p_m * o - 1) * no_push
        if ev_m >= min_ev:
            res.bets.append(Bet(r.day, r.competition, market, sel, line, o, closing, p_m, ev_m, result, "solo_modelo"))
        if sharp_p is not None:
            p_b = w_model * p_m + (1 - w_model) * sharp_p
            ev_b = (p_b * o - 1) * no_push
            if ev_b >= min_ev:
                res.bets.append(Bet(r.day, r.competition, market, sel, line, o, closing, p_b, ev_b, result,
                                    "modelo+mercado"))
            ev_s = (sharp_p * o - 1) * no_push
            if ev_s >= min_ev:
                res.bets.append(Bet(r.day, r.competition, market, sel, line, o, closing, sharp_p, ev_s, result,
                                    "solo_mercado_afilado"))


def _settle(r: MatchRow, market: str, sel: str, line: float | None) -> str:
    diff, total = r.hg - r.ag, r.hg + r.ag
    if market == "1x2":
        res = "home" if diff > 0 else ("away" if diff < 0 else "draw")
        return "win" if res == sel else "loss"
    if market == "ou_goals":
        out = dist.over({total: 1.0}, line) if sel == "over" else dist.under({total: 1.0}, line)
    else:
        out = dist.line_outcome({diff if sel == "home" else -diff: 1.0}, line)
    for name in ("win", "half_win", "push", "half_loss", "loss"):
        if getattr(out, name) > 0.5:
            return name
    return "push"


def _evaluate_counts(r: MatchRow, cms: dict, count_ll, refs: dict | None = None) -> None:
    refs = refs or {}
    for stat, cm in cms.items():
        vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
        if vh is None or va is None or r.home not in cm.attack or r.away not in cm.attack:
            continue
        mh, ma = cm.expected(r.home, r.away, r.neutral)
        a = cm.dispersion
        total = int(vh + va)
        pmf = dist.convolve(dist.count_pmf(mh, a, 80), dist.count_pmf(ma, a, 80))
        p_model = pmf[total] if total < len(pmf) else 1e-9
        ref = refs.get(r.referee_id) if r.referee_id else None
        if stat in ("cards", "fouls") and ref:
            f = ref["cards_factor"] if stat == "cards" else ref.get("fouls_factor", 1.0)
            pmf_ref = dist.convolve(dist.count_pmf(mh * f, a, 80), dist.count_pmf(ma * f, a, 80))
            p_ref = pmf_ref[total] if total < len(pmf_ref) else 1e-9
            count_ll[f"{stat}+arbitro"].append((math.log(max(p_ref, 1e-9)), math.log(max(p_model, 1e-9))))
        naive_mean = math.exp(cm.mu) * (1 + math.exp(cm.home_adv))
        if a > 1e-6:
            rr = 1 / (a / 2)
            p_naive = nbinom.pmf(total, rr, rr / (rr + naive_mean))
        else:
            p_naive = poisson.pmf(total, naive_mean)
        count_ll[stat].append((math.log(max(p_model, 1e-9)), math.log(max(p_naive, 1e-9))))
