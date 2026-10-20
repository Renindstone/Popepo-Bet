from datetime import date, timedelta

import numpy as np
import pytest

from apuestas.backtest.engine import lineup_regression
from apuestas.features import lineup as lu
from apuestas.models import fitting, market, ratings
from apuestas.models.fitting import MatchRow, market_obs
from apuestas.models.ratings import MatchObs


def test_implied_goals_recovers_means():
    lh = np.array([0.6, 1.4, 2.7, 1.1])
    la = np.array([2.2, 1.1, 0.5, 1.1])
    p = market.market_probs(lh, la)
    assert p[:, :3].sum(axis=1) == pytest.approx(np.ones(4))
    lam, rmse = market.implied_goals(p[:, :3], p[:, 3])
    assert lam[:, 0] == pytest.approx(lh, abs=1e-6)
    assert lam[:, 1] == pytest.approx(la, abs=1e-6)
    assert rmse.max() < 1e-6
    # Sin más/menos: el 1X2 solo (el empate fija el total) también basta si las cuotas son coherentes
    lam2, _ = market.implied_goals(p[:, :3], np.full(4, np.nan))
    assert lam2[:, 0] == pytest.approx(lh, abs=1e-4)


def _row(mid: int, home: int, away: int, day: date) -> MatchRow:
    return MatchRow(mid, "EPL", day, home, away, False, 1, 1, None, {}, {})


def test_market_obs_pull_ratings_but_do_not_count_as_matches():
    rng = np.random.default_rng(1)
    start = date(2025, 1, 1)
    teams = [1, 2, 3, 4]
    rows, real = [], []
    for k in range(240):
        h, a = rng.choice(teams, 2, replace=False)
        day = start + timedelta(days=k)
        rows.append(_row(k, int(h), int(a), day))
        real.append(MatchObs(int(h), int(a), day, float(rng.poisson(1.3)), float(rng.poisson(1.3))))
    # El mercado dice que el equipo 1 es mucho mejor que los demás
    implied = {r.match_id: ((2.4, 0.7) if r.home == 1 else (0.7, 2.4) if r.away == 1 else (1.3, 1.1)) for r in rows}
    as_of = start + timedelta(days=241)
    base = ratings.fit(real, as_of)
    mixed = ratings.fit(real + market_obs(rows, implied, weight=4.0), as_of, market_half_life_days=60)
    assert mixed.attack[1] - mixed.defence[2] > base.attack[1] - base.defence[2]
    assert mixed.attack[1] > max(mixed.attack[t] for t in (2, 3, 4))
    assert mixed.n_matches == pytest.approx(base.n_matches)
    assert market_obs(rows, implied, weight=0.0) == []


def test_baseline_from_history_uses_only_previous_matches():
    d0 = date(2025, 8, 1)
    hist = [(d0 + timedelta(days=7 * i), i, lu.XIStrength(float(i), -float(i))) for i in range(12)]
    base = lu.baseline_from_history(hist, d0 + timedelta(days=7 * 10), n=4)
    assert base.attack == pytest.approx((6 + 7 + 8 + 9) / 4)
    assert base.defence == pytest.approx(-(6 + 7 + 8 + 9) / 4)
    assert lu.baseline_from_history(hist, d0) is None


def test_lineup_regression_recovers_betas():
    rng = np.random.default_rng(7)
    rows = []
    for mid in range(3000):
        for _ in range(2):
            lam = rng.uniform(0.8, 2.2)
            d_att, d_def = rng.normal(0, 0.4), rng.normal(0, 0.4)
            mu = lam * np.exp(0.25 * d_att - 0.15 * d_def)
            rows.append((mid, lam, d_att, d_def, int(rng.poisson(mu)), float(rng.gamma(4.0, mu / 4.0))))
    reg = lineup_regression(rows)
    for target in ("goles", "xg"):
        assert reg[target]["beta_att"] == pytest.approx(0.25, abs=3 * reg[target]["se_att"])
        assert reg[target]["beta_def"] == pytest.approx(0.15, abs=3 * reg[target]["se_def"])
    assert reg["xg"]["se_att"] < reg["goles"]["se_att"]


def test_extra_leagues_only_in_model_when_enabled(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(fitting, "get_settings", lambda: SimpleNamespace(extra_leagues_in_model=False))
    codes = fitting.model_codes()
    assert {"EPL", "SA", "UCL", "UECL"} <= set(codes) and not {"NOR", "AUT", "SUI"} & set(codes)
    monkeypatch.setattr(fitting, "get_settings", lambda: SimpleNamespace(extra_leagues_in_model=True))
    assert {"NOR", "AUT", "SUI", "EPL"} <= set(fitting.model_codes())
