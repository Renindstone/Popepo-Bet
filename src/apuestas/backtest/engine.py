"""Backtest "walk-forward": se reajusta el modelo cada semana usando SOLO datos anteriores y se
apuesta contra las cuotas de bet365 de ese momento. Mide si el modelo habría ganado dinero.

Métricas:
- Log-loss / Brier del 1X2: modelo vs probabilidades de bet365 vs Pinnacle (sin margen), en total y por liga. Por
  defecto se evalúan las ligas completas (`LEAGUES`: Premier, Bundesliga, LaLiga, Serie A, Ligue 1, Portugal y
  Bélgica; hasta el 21-10-2026 solo las tres primeras y hasta el 29-10-2026 las cinco primeras).
- ROI de apuestas con valor (1X2, más/menos 2.5 y hándicap asiático principal) a cuota previa de bet365.
- CLV medio: cuota tomada vs cuota de cierre de bet365 (indicador de ventaja real a corto plazo).
- Calibración de modelos de remates, córners y tarjetas (verosimilitud frente a la media de la liga), del total del
  partido y de cada equipo, en las ligas y en las copas con estadísticas (`extra_competitions`; solo la Champions).
  En la Champions se separan los partidos con un equipo de pocos datos (`:pocos_datos`) y, del resto, los de dos
  equipos de ligas distintas (`:entre_ligas`), que son los que dependen de comparar ligas.
- Log-loss del modelo por competición, también donde no hay cuotas (`extra_competitions`, p. ej. Champions).

Alineaciones (opción `lineups`): con los onces confirmados históricos de FotMob se mide, en los partidos
que los tienen, la log-loss del modelo con y sin el ajuste por alineación, y se estima por regresión
(Poisson con offset) cuánto cambian los goles/xG por cada punto de diferencia entre el once y el once típico.
Las apuestas siguen usando el modelo base: el once se publica ~1 h antes y la cuota previa es de días antes.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import numpy as np
from scipy.optimize import minimize
from scipy.stats import nbinom, poisson
from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.features import lineup as lu
from apuestas.models import distributions as dist
from apuestas.models import fitting, ratings
from apuestas.models.fitting import (
    COUNT_STATS,
    MatchRow,
    count_obs,
    fit_counts,
    fit_referees,
    fit_rho,
    goals_obs,
    load_market_goals,
    load_matches,
    market_obs,
    team_leagues,
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
    lineups: dict = field(default_factory=dict)
    ll_by_comp: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

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
            "logloss_1x2": {k: round(v, 4) for k, v in self.logloss.items() if ":" not in k},
            "logloss_1x2_por_competicion": _by_competition(self.logloss),
            "brier_1x2": {k: round(v, 4) for k, v in self.brier.items()},
            "logloss_modelo_por_competicion": {k: {"partidos": len(v), "logloss": round(float(np.mean(v)), 4)}
                                               for k, v in sorted(self.ll_by_comp.items())},
            "betting": {strat: {k: agg(v) for k, v in groups.items()} for strat, groups in by.items()},
            "count_models": self.count_calibration,
            **({"lineups": self.lineups} if self.lineups else {}),
        }


def _by_competition(logloss: dict[str, float]) -> dict[str, dict[str, float]]:
    """{"modelo:SA": x, "bet365:SA": y} -> {"SA": {"modelo": x, "bet365": y}}."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for k, v in logloss.items():
        if ":" in k:
            name, comp = k.split(":", 1)
            out[comp][name] = round(v, 4)
    return dict(sorted(out.items()))


def _profit(b: Bet) -> float:
    k = {"win": 1.0, "half_win": 0.5, "push": 0.0, "half_loss": -0.5, "loss": -1.0}[b.result]
    return k * (b.odds - 1) if k > 0 else k


def _odds_map(s: Session, match_ids: list[int]) -> dict[int, dict[tuple, float]]:
    out: dict[int, dict[tuple, float]] = defaultdict(dict)
    for r in s.scalars(select(m.OddsSnapshot).where(m.OddsSnapshot.match_id.in_(match_ids))):
        out[r.match_id][(r.bookmaker, r.market, r.selection, r.line, r.kind)] = r.price
    return out


# Ligas con cuotas de football-data que se evalúan por defecto: las completas que no son copas
LEAGUES = tuple(c.code for c in FULL if not c.is_cup)


def run(
    start: date,
    end: date,
    competitions: tuple[str, ...] = LEAGUES,
    half_life_days: float = 240.0,
    xg_weight: float = 0.85,
    min_ev: float = 0.03,
    odds_range: tuple[float, float] = (1.4, 3.6),
    step_days: int = 7,
    w_model: float = W_MODEL,
    market_weight: float | None = None,
    market_half_life: float | None = None,
    lineups: bool = False,
    extra_competitions: tuple[str, ...] = (),
    count_l2: float | None = None,
    count_strength: bool = True,
    count_market: bool = True,
    count_level: bool = True,
) -> BacktestResult:
    """`extra_competitions`: competiciones donde solo se mide el modelo (sin cuotas ni apuestas).
    `count_l2`: L2 fija de los modelos de conteo (1,0 = la de antes del 21-10-2026) en vez de COUNT_PRIOR_MATCHES.
    `count_strength`: remates y córners guiados por la fuerza del modelo de goles (False = como antes).
    `count_market`: el reparto de remates y córners se mueve hacia la diferencia de fuerza del 1X2 de cierre del
    partido (fitting.strength_shift; False = como antes del 22-10-2026). Solo donde hay cuotas de cierre: las ligas.
    `count_level`: remates y a puerta con el nivel reciente de cada liga (fitting.count_levels; False = como antes
    del 22-10-2026)."""
    from apuestas.db.session import _factory

    market_weight = fitting.MARKET_WEIGHT if market_weight is None else market_weight
    market_half_life = fitting.MARKET_HALF_LIFE if market_half_life is None else market_half_life
    res = BacktestResult(params={"start": start.isoformat(), "end": end.isoformat(), "half_life": half_life_days,
                                 "xg_weight": xg_weight, "min_ev": min_ev, "odds_range": odds_range,
                                 "competitions": competitions, "w_model": w_model, "market_weight": market_weight,
                                 "market_half_life": market_half_life, "extra_competitions": extra_competitions,
                                 "count_l2": count_l2, "count_strength": count_strength,
                                 "count_market": count_market, "count_level": count_level})
    s = _factory()()
    try:
        before = datetime.combine(end, datetime.min.time(), UTC) + timedelta(days=1)
        since = datetime.combine(start, datetime.min.time(), UTC) - timedelta(days=1100)
        all_rows = load_matches(s, before=before, since=since)
        evaluated = set(competitions) | set(extra_competitions)
        odds = _odds_map(s, [r.match_id for r in all_rows if r.competition in evaluated and r.day >= start])
        # En el modelo de goles solo entran las cuotas de cierre de partidos ya jugados antes de cada reajuste
        # (train); en los conteos (count_market), la del propio partido, como las de antes del partido en el análisis
        implied = load_market_goals(s, before=before, since=since) if market_weight > 0 or count_market else {}
        xi_hist = lu.xi_history(s) if lineups else {}
    finally:
        s.close()

    ll: dict[str, list[float]] = defaultdict(list)
    br: dict[str, list[float]] = defaultdict(list)
    count_ll: dict[str, list[tuple[float, float]]] = defaultdict(list)
    xi_idx = {(mid, tid): xi for tid, hist in xi_hist.items() for _, mid, xi in hist}
    ll_lu: dict[str, list[float]] = defaultdict(list)
    lu_rows: list[tuple] = []

    cur = start
    while cur <= end:
        nxt = cur + timedelta(days=step_days)
        train = [r for r in all_rows if r.day < cur]
        test = [r for r in all_rows if cur <= r.day < nxt and r.competition in evaluated]
        if test and len(train) > 500:
            gm = ratings.fit(goals_obs(train, xg_weight) + market_obs(train, implied, market_weight), cur,
                             half_life_days=half_life_days, market_half_life_days=market_half_life)
            rho = fit_rho([r for r in train if (cur - r.day).days < 730], gm, set(competitions))
            cms = {}
            strength = fitting.count_strength(gm) if count_strength else None
            for stat in COUNT_STATS:
                obs = count_obs(train, stat)
                if len(obs) > 300:
                    cms[stat] = fit_counts(obs, stat, cur, half_life_days=half_life_days, l2=count_l2,
                                           strength=strength, rows=train if count_level else None)
            refs = fit_referees(train, cms["cards"], cms.get("fouls")) if "cards" in cms else {}
            leagues = team_leagues(train)
            for r in test:
                main = r.competition in competitions
                _evaluate_match(r, gm, rho, odds.get(r.match_id, {}), res, ll, br, min_ev, odds_range, w_model,
                                model_only=not main)
                delta = 0.0
                if count_market and r.match_id in implied and r.home in gm.attack and r.away in gm.attack:
                    delta = fitting.strength_delta(implied[r.match_id], gm.expected(r.home, r.away, r.neutral))
                _evaluate_counts(r, cms, count_ll, refs, "" if main else f":{r.competition}", leagues, delta)
                if lineups:
                    _evaluate_lineup(r, gm, rho, odds.get(r.match_id, {}), xi_hist, xi_idx, ll_lu, lu_rows)
        cur = nxt

    res.logloss = {k: float(np.mean(v)) for k, v in ll.items() if v}
    res.brier = {k: float(np.mean(v)) for k, v in br.items() if v}
    if lineups:
        res.lineups = {"betas": {"att": lu.BETA_ATT, "def": lu.BETA_DEF},
                       "matches": len(ll_lu["modelo"]),
                       "logloss_1x2": {k: round(float(np.mean(v)), 4) for k, v in ll_lu.items() if v and ":" not in k},
                       "logloss_modelo_por_competicion": {
                           k: {"partidos": len(v), "logloss": round(float(np.mean(v)), 4)}
                           for k, v in sorted(ll_lu.items()) if ":" in k},
                       "regresion": lineup_regression(lu_rows)}
    for stat, pairs in count_ll.items():
        model_ll = float(np.mean([p[0] for p in pairs]))
        naive_ll = float(np.mean([p[1] for p in pairs]))
        baseline = ("loglik_sin_arbitro" if stat.endswith("+arbitro") else "loglik_independientes"
                    if stat.endswith("+total") else "loglik_league_avg")
        diff = np.array([p[0] - p[1] for p in pairs])
        margin = 1.96 * float(diff.std(ddof=1)) / math.sqrt(len(diff)) if len(diff) > 1 else float("nan")
        res.count_calibration[stat] = {"matches": len(pairs), "loglik_model": round(model_ll, 4),
                                       baseline: round(naive_ll, 4), "improvement": round(model_ll - naive_ll, 4),
                                       "margin_95": round(margin, 4)}
    return res


def _evaluate_match(r: MatchRow, gm, rho: float, od: dict, res: BacktestResult, ll, br, min_ev, odds_range,
                    w_model: float = W_MODEL, model_only: bool = False) -> None:
    if r.home not in gm.attack or r.away not in gm.attack:
        return
    lh, la = gm.expected(r.home, r.away, r.neutral)
    mat = dist.dixon_coles_matrix(lh, la, rho)
    p_model = [float(np.tril(mat, -1).sum()), float(np.trace(mat)), float(np.triu(mat, 1).sum())]
    outcome_idx = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
    res.ll_by_comp[r.competition].append(-math.log(max(p_model[outcome_idx], 1e-9)))
    if model_only:
        return  # competición sin cuotas (Champions...): solo cuenta la log-loss del modelo
    res.n_matches += 1

    sharp = _book_probs(od, "pinnacle") or _book_probs(od, "betfair_ex")
    b365 = _book_probs(od, "bet365")
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
        ll[f"{name}:{r.competition}"].append(ll[name][-1])
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
        no_push = out.decided()  # sin devolución ni medias devoluciones (líneas de cuarto)
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


def _book_probs(od: dict, book: str, kind: str = "opening") -> list[float] | None:
    o = [od.get((book, "1x2", sel, None, kind)) for sel in ("home", "draw", "away")]
    return oddsmath.devig(o) if all(o) else None


def _probs_1x2(lh: float, la: float, rho: float) -> list[float]:
    mat = dist.dixon_coles_matrix(lh, la, rho)
    return [float(np.tril(mat, -1).sum()), float(np.trace(mat)), float(np.triu(mat, 1).sum())]


def _evaluate_lineup(r: MatchRow, gm, rho: float, od: dict, xi_hist: dict, xi_idx: dict, ll_lu, lu_rows) -> None:
    """Partidos con once confirmado de ambos equipos: log-loss con/sin ajuste y datos para la regresión."""
    if r.home not in gm.attack or r.away not in gm.attack:
        return
    deltas = []
    for tid in (r.home, r.away):
        xi = xi_idx.get((r.match_id, tid))
        base = lu.baseline_from_history(xi_hist.get(tid, []), r.day)
        if xi is None or base is None:
            return
        deltas.append((xi.attack - base.attack, xi.defence - base.defence))
    (dah, ddh), (daa, dda) = deltas
    lh, la = gm.expected(r.home, r.away, r.neutral)
    # (partido, media del modelo, Δataque propio, Δdefensa rival, goles, xG)
    lu_rows.append((r.match_id, lh, dah, dda, r.hg, r.stats_h.get("xg")))
    lu_rows.append((r.match_id, la, daa, ddh, r.ag, r.stats_a.get("xg")))
    k = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
    variants = {
        "modelo": _probs_1x2(lh, la, rho),
        "modelo+alineacion": _probs_1x2(lh * math.exp(lu.BETA_ATT * dah - lu.BETA_DEF * dda),
                                        la * math.exp(lu.BETA_ATT * daa - lu.BETA_DEF * ddh), rho),
    }
    for name, p in variants.items():  # todas las competiciones, haya cuotas o no
        ll_lu[f"{r.competition}:{name}"].append(-math.log(max(p[k], 1e-9)))
    b365, sharp = _book_probs(od, "bet365"), _book_probs(od, "pinnacle") or _book_probs(od, "betfair_ex")
    if not (b365 and sharp):
        return
    variants |= {"bet365": b365, "pinnacle": sharp}
    closing = _book_probs(od, "pinnacle", "closing")
    if closing:
        variants["pinnacle_cierre"] = closing  # referencia: el cierre ya conoce las alineaciones
    for name, p in variants.items():
        ll_lu[name].append(-math.log(max(p[k], 1e-9)))


def lineup_regression(rows: list[tuple]) -> dict:
    """Poisson con offset: log E[y] = log(media del modelo) + c + b_att·Δataque − b_def·Δdefensa_rival.

    Errores estándar robustos agrupando por partido. Con y = goles y con y = xG (menos ruido).
    """
    out = {}
    for target, col in (("goles", 4), ("xg", 5)):
        data = [r for r in rows if r[col] is not None]
        if len(data) < 200:
            continue
        y = np.array([r[col] for r in data], dtype=float)
        off = np.log([r[1] for r in data])
        x = np.column_stack([np.ones(len(data)), [r[2] for r in data], [-r[3] for r in data]])

        def nll(b: np.ndarray, y=y, off=off, x=x) -> tuple[float, np.ndarray]:
            eta = off + x @ b
            mu = np.exp(eta)
            return float(np.sum(mu - y * eta)), x.T @ (mu - y)

        b = minimize(nll, np.zeros(3), jac=True, method="BFGS").x
        mu = np.exp(off + x @ b)
        h_inv = np.linalg.inv((x * mu[:, None]).T @ x)
        groups = np.unique([r[0] for r in data], return_inverse=True)[1]
        score = np.zeros((groups.max() + 1, 3))
        np.add.at(score, groups, x * (y - mu)[:, None])
        se = np.sqrt(np.diag(h_inv @ score.T @ score @ h_inv))
        out[target] = {"n": len(data), "intercept": round(float(b[0]), 4),
                       "beta_att": round(float(b[1]), 4), "se_att": round(float(se[1]), 4),
                       "beta_def": round(float(b[2]), 4), "se_def": round(float(se[2]), 4),
                       "sd_d_att": round(float(np.std(x[:, 1])), 4), "sd_d_def": round(float(np.std(x[:, 2])), 4)}
    return out


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


# Por debajo de estos partidos (ponderados) de un equipo, el partido se cuenta además en el grupo "pocos datos"
FEW_COUNT_MATCHES = 10


def _evaluate_counts(r: MatchRow, cms: dict, count_ll, refs: dict | None = None, suffix: str = "",
                     leagues: dict[int, str] | None = None, delta: float = 0.0) -> None:
    """Log-verosimilitud del total y de cada equipo (`<stat> por equipo`) frente a la media de la liga. En las
    copas (`suffix` = ":UCL") se separan los partidos con un equipo de pocos datos (rivales de ligas sin descargar)
    y, entre los demás, los de equipos de dos ligas distintas (`leagues`: liga de cada equipo). `delta`: fuerza que
    la casa suma al local frente al modelo de goles (fitting.strength_delta), para las estadísticas de dominio."""
    refs = refs or {}
    leagues = leagues or {}
    for stat, cm in cms.items():
        vh, va = r.stats_h.get(stat), r.stats_a.get(stat)
        if vh is None or va is None:
            continue
        groups = [suffix]
        if suffix and min(cm.n_matches.get(r.home, 0.0), cm.n_matches.get(r.away, 0.0)) < FEW_COUNT_MATCHES:
            groups.append(f"{suffix}:pocos_datos")
        elif suffix and leagues.get(r.home) and leagues.get(r.away) and leagues[r.home] != leagues[r.away]:
            groups.append(f"{suffix}:entre_ligas")
        mh, ma = cm.expected(r.home, r.away, r.neutral, r.competition)
        if stat in fitting.COUNT_STRENGTH_PRIOR:
            mh, ma = fitting.strength_shift(cm, mh, ma, delta)
        a, at = cm.dispersion, cm.total_dispersion
        total = int(vh + va)
        pmf = dist.count_total_pmf(mh, ma, a, at, 80)
        p_model = pmf[total] if total < len(pmf) else 1e-9
        if at is not None and not suffix:  # frente a sumar los dos equipos como independientes
            conv = dist.count_total_pmf(mh, ma, a, None, 80)
            p_conv = conv[total] if total < len(conv) else 1e-9
            count_ll[f"{stat}+total"].append((math.log(max(p_model, 1e-9)), math.log(max(p_conv, 1e-9))))
        ref = refs.get(r.referee_id) if r.referee_id else None
        if stat in ("cards", "fouls") and ref and not suffix:
            f = ref["cards_factor"] if stat == "cards" else ref.get("fouls_factor", 1.0)
            pmf_ref = dist.count_total_pmf(mh * f, ma * f, a, at, 80)
            p_ref = pmf_ref[total] if total < len(pmf_ref) else 1e-9
            count_ll[f"{stat}+arbitro"].append((math.log(max(p_ref, 1e-9)), math.log(max(p_model, 1e-9))))
        naive_mean = math.exp(cm.mu) * (1 + math.exp(cm.home_adv))
        if a > 1e-6:
            rr = 1 / (a / 2)
            p_naive = nbinom.pmf(total, rr, rr / (rr + naive_mean))
        else:
            p_naive = poisson.pmf(total, naive_mean)
        naive_h, naive_a = math.exp(cm.mu + (0.0 if r.neutral else cm.home_adv)), math.exp(cm.mu)
        side_model = _count_logpmf(int(vh), mh, a) + _count_logpmf(int(va), ma, a)
        side_naive = _count_logpmf(int(vh), naive_h, a) + _count_logpmf(int(va), naive_a, a)
        for g in groups:
            count_ll[f"{stat}{g}"].append((math.log(max(p_model, 1e-9)), math.log(max(p_naive, 1e-9))))
            count_ll[f"{stat} por equipo{g}"].append((side_model, side_naive))


def _count_logpmf(k: int, mean: float, dispersion: float) -> float:
    mean = max(mean, 1e-6)
    if dispersion <= 1e-6:
        return float(poisson.logpmf(k, mean))
    rr = 1 / dispersion
    return float(nbinom.logpmf(k, rr, rr / (rr + mean)))
