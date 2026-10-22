"""Córners y demás conteos de equipos con pocos partidos (p. ej. Viking en la Champions): contracción hacia la
media en partidos equivalentes y, en sus mercados, mezcla con la probabilidad de la casa. Y córners entre ligas
(Betis-Feyenoord): contracción hacia la fuerza del modelo de goles."""

from collections import defaultdict
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from apuestas.backtest import engine
from apuestas.models import fitting, ratings
from apuestas.models.fitting import MatchRow
from apuestas.models.ratings import MatchObs
from apuestas.services import analysis
from apuestas.services.match_model import MatchModel, parse_market

TODAY = date(2026, 10, 21)
UNSEEN = 99  # rival europeo con solo dos partidos con córners


def _corners_obs() -> list[MatchObs]:
    """Liga de 6 equipos parejos (~5,5 córners en casa y ~4,5 fuera) más dos partidos del equipo 99 con muchos
    córners propios, como los 5 y 7 de Viking contra Stuttgart y el Bayern."""
    rng = np.random.default_rng(3)
    obs = []
    teams = list(range(1, 7))
    for w in range(60):
        day = TODAY - timedelta(days=7 * w + 1)
        rng.shuffle(teams)
        for h, a in zip(teams[::2], teams[1::2], strict=True):
            obs.append(MatchObs(int(h), int(a), day, float(rng.poisson(5.5)), float(rng.poisson(4.5))))
    obs.append(MatchObs(1, UNSEEN, TODAY - timedelta(days=40), 3.0, 9.0))
    obs.append(MatchObs(UNSEEN, 2, TODAY - timedelta(days=8), 11.0, 4.0))
    return obs


def test_prior_in_matches_shrinks_teams_with_few_matches():
    obs = _corners_obs()
    old = ratings.fit(obs, TODAY, l2=1.0)  # la L2 fija de antes: con conteos grandes apenas contrae
    new = ratings.fit(obs, TODAY, prior_matches=5.0)
    league_home = np.exp(new.mu + new.home_adv)
    assert old.expected(UNSEEN, 3)[0] / league_home > 1.6  # se cree lo que vio en dos partidos
    assert new.expected(UNSEEN, 3)[0] / league_home < 1.3
    # Los equipos con muchos partidos casi no cambian
    for h in range(1, 7):
        for a in range(1, 7):
            if h != a:
                assert new.expected(h, a) == pytest.approx(old.expected(h, a), rel=0.05)


def test_fit_counts_uses_the_prior_of_each_stat():
    assert set(fitting.COUNT_PRIOR_MATCHES) == set(fitting.COUNT_STATS)
    obs = _corners_obs()
    by_prior = ratings.fit(obs, TODAY, prior_matches=fitting.COUNT_PRIOR_MATCHES["corners"])
    assert fitting.fit_counts(obs, "corners", TODAY).attack == pytest.approx(by_prior.attack)
    fixed = ratings.fit(obs, TODAY, l2=1.0)  # la de antes, para el backtest (--count-l2 1)
    assert fitting.fit_counts(obs, "corners", TODAY, l2=1.0).attack == pytest.approx(fixed.attack)


def _two_leagues() -> tuple[list[MatchObs], dict[int, float], object]:
    """Liga fuerte (equipos 1-10) y liga floja (11-20) que solo se cruzan en tres partidos, como la Eredivisie y LaLiga
    en córners. Los córners de cada equipo dependen de su fuerza (0,6 × fuerza en ataque y en defensa)."""
    rng = np.random.default_rng(5)
    strength = {t: 0.3 + 0.2 * (t - 5.5) / 4.5 for t in range(1, 11)}
    strength |= {t: -0.3 + 0.2 * (t - 15.5) / 4.5 for t in range(11, 21)}

    def true(h: int, a: int) -> tuple[float, float]:
        return (float(np.exp(np.log(4.8) + 0.1 + 0.6 * (strength[h] - strength[a]))),
                float(np.exp(np.log(4.8) + 0.6 * (strength[a] - strength[h]))))

    obs = []

    def play(h: int, a: int, day: date) -> None:
        mh, ma = true(h, a)
        obs.append(MatchObs(h, a, day, float(rng.poisson(mh)), float(rng.poisson(ma))))

    for league in (range(1, 11), range(11, 21)):
        teams = list(league)
        for w in range(36):
            rng.shuffle(teams)
            for h, a in zip(teams[::2], teams[1::2], strict=True):
                play(int(h), int(a), TODAY - timedelta(days=7 * w + 1))
    for h, a, days in ((5, 18, 30), (17, 3, 60), (8, 12, 90)):
        play(h, a, TODAY - timedelta(days=days))
    return obs, strength, true


def test_strength_sets_the_level_of_leagues_that_barely_meet():
    obs, strength, true = _two_leagues()
    old = ratings.fit(obs, TODAY, prior_matches=5.0)
    new = ratings.fit(obs, TODAY, prior_matches=20.0, strength=strength)
    # El mejor de la liga floja en casa contra uno de mitad de tabla de la fuerte: saca menos córners que su rival
    real = true(20, 5)
    assert real[0] < real[1]
    assert old.expected(20, 5)[0] > old.expected(20, 5)[1]  # sin la fuerza, la L2 pone las dos ligas al mismo nivel
    got = new.expected(20, 5)
    assert got[0] < got[1]
    assert got == pytest.approx(real, rel=0.15)
    # Dentro de una liga casi no cambia
    for h, a in ((1, 10), (12, 19)):
        assert new.expected(h, a) == pytest.approx(old.expected(h, a), rel=0.1)


def test_strength_is_optional_and_centred():
    obs = _corners_obs()
    plain = ratings.fit(obs, TODAY, prior_matches=5.0)
    flat = ratings.fit(obs, TODAY, prior_matches=5.0, strength={t: 0.7 for t in range(1, 7)} | {UNSEEN: 0.7})
    assert flat.mu == pytest.approx(plain.mu)  # una fuerza igual para todos no cambia nada
    assert flat.expected(UNSEEN, 3) == pytest.approx(plain.expected(UNSEEN, 3))


def test_fit_counts_uses_strength_only_in_dominance_stats():
    obs, strength, _ = _two_leagues()
    corners = ratings.fit(obs, TODAY, prior_matches=fitting.COUNT_STRENGTH_PRIOR["corners"], strength=strength)
    assert fitting.fit_counts(obs, "corners", TODAY, strength=strength).attack == pytest.approx(corners.attack)
    cards = fitting.fit_counts(obs, "cards", TODAY)
    assert fitting.fit_counts(obs, "cards", TODAY, strength=strength).attack == pytest.approx(cards.attack)
    fixed = ratings.fit(obs, TODAY, l2=1.0)  # la L2 fija de antes, sin fuerza (--count-l2 1)
    assert fitting.fit_counts(obs, "corners", TODAY, l2=1.0, strength=strength).attack == pytest.approx(fixed.attack)
    goals = ratings.RatingModel(teams=[1, 2], mu=0.3, home_adv=0.2, attack={1: 0.4, 2: -0.1},
                                defence={1: 0.2, 2: 0.0})
    assert fitting.count_strength(goals) == pytest.approx({1: 0.6, 2: -0.1})


def test_parse_market():
    assert parse_market("ou_corners_away") == ("ou", "corners", "away")
    assert parse_market("ah_cards") == ("ah", "cards", "total")
    assert parse_market("ou_sot_home") == ("ou", "shots_on_target", "home")
    assert parse_market("1x2_corners") == ("1x2", "corners", "total")
    assert parse_market("ah") == ("ah", "goals", "total")
    assert parse_market("ou_goals_home") == ("ou", "goals", "home")


def _row(market, selection, line, price, book="betano"):
    return SimpleNamespace(bookmaker=book, market=market, selection=selection, line=line, price=price)


def _quality(n_corners: float | None) -> dict:
    q = {"lineup_factor": 1.0, "sample_factor": 1.0, "lineup_status": "confirmed"}
    if n_corners is not None:
        q["stat_matches_min"] = {"corners": n_corners}
        q["stat_thin_teams"] = {"corners": "Viking"} if n_corners < analysis.STAT_COVERED else {}
    return q


def test_stat_coverage_weight():
    assert analysis.stat_coverage_weight(None) == 1.0  # paquete de modelos sin el dato: no se toca
    assert analysis.stat_coverage_weight(0.0) == 0.0
    assert analysis.stat_coverage_weight(analysis.STAT_COVERED / 2) == pytest.approx(0.5)
    assert analysis.stat_coverage_weight(35.0) == 1.0


def test_stat_markets_of_teams_with_few_matches_blend_with_the_house():
    # Aston Villa-Viking: el modelo ve 4,2 córners de Viking; Betano, ~3
    mm = MatchModel(1, 2, 2.3, 0.8, -0.05, {"corners": (7.1, 4.2)}, {"corners": 0.07})
    rows = [_row("ou_corners_away", "over", 5.5, 6.5), _row("ou_corners_away", "under", 5.5, 1.10)]
    house = analysis.book_fair_prob(rows, "betano", "ou_corners_away", "over", 5.5)

    def ev(n):
        return analysis.evaluate_bet(mm, _quality(n), "baja", rows, "ou_corners_away", "over", 5.5, 6.5, "betano")

    known, viking, unseen, old_bundle = ev(30.0), ev(1.9), ev(0.0), ev(None)
    assert known.prob == pytest.approx(known.model_prob) and known.ev > 0.5  # equipos conocidos: solo el modelo
    assert old_bundle.prob == pytest.approx(known.prob)
    assert unseen.prob == pytest.approx(house) and unseen.ev < 0  # sin partidos: la casa, no puede salir valor
    assert viking.prob == pytest.approx(0.19 * known.model_prob + 0.81 * house)
    assert viking.model_prob == pytest.approx(known.model_prob)
    assert viking.ev < known.ev / 4
    assert "Viking" in viking.reasons[-1]


def test_blend_without_both_sides_uses_the_price_with_a_margin():
    mm = MatchModel(1, 2, 2.3, 0.8, -0.05, {"corners": (7.1, 4.2)}, {"corners": 0.07})
    only_over = [_row("ou_corners", "over", 13.5, 4.55)]
    bet = analysis.evaluate_bet(mm, _quality(0.0), "baja", only_over, "ou_corners", "over", 13.5, 4.55, "betano")
    assert bet.prob == pytest.approx(1 / (4.55 * (1 + analysis.BOOK_MARGIN)))
    assert bet.ev < 0


def test_goal_and_player_markets_ignore_the_stat_sample():
    mm = MatchModel(1, 2, 2.3, 0.8, -0.05, {"corners": (7.1, 4.2)}, {"corners": 0.07})
    q = _quality(0.0)
    q["stat_matches_min"]["goals"] = 0.0
    bet = analysis.evaluate_bet(mm, q, "baja", [], "ou_goals", "over", 2.5, 1.9, "betano")
    assert bet.prob == pytest.approx(bet.model_prob)


def test_backtest_counts_split_cups_and_teams_with_few_matches():
    cm = ratings.fit(_corners_obs(), TODAY, prior_matches=5.0)
    cup = MatchRow(1, "UCL", TODAY, 1, UNSEEN, False, 2, 1, None, {"corners": 7}, {"corners": 3})
    ll: dict = defaultdict(list)
    engine._evaluate_counts(cup, {"corners": cm}, ll, None, ":UCL")
    assert set(ll) == {"corners:UCL", "corners por equipo:UCL", "corners:UCL:pocos_datos",
                       "corners por equipo:UCL:pocos_datos"}
    league = MatchRow(2, "EPL", TODAY, 1, 2, False, 2, 1, None, {"corners": 7}, {"corners": 3})
    ll2: dict = defaultdict(list)
    engine._evaluate_counts(league, {"corners": cm}, ll2)
    assert set(ll2) == {"corners", "corners por equipo"}
    # Dos equipos conocidos de ligas distintas
    cross = MatchRow(3, "UCL", TODAY, 1, 2, False, 2, 1, None, {"corners": 7}, {"corners": 3})
    ll3: dict = defaultdict(list)
    engine._evaluate_counts(cross, {"corners": cm}, ll3, None, ":UCL", {1: "LAL", 2: "NED"})
    assert set(ll3) == {"corners:UCL", "corners por equipo:UCL", "corners:UCL:entre_ligas",
                        "corners por equipo:UCL:entre_ligas"}


def test_team_league_is_the_last_league_match():
    rows = [MatchRow(1, "ENG2", TODAY - timedelta(days=300), 1, 2, False, 1, 0, None, {}, {}),
            MatchRow(2, "EPL", TODAY - timedelta(days=30), 1, 3, False, 1, 0, None, {}, {}),
            MatchRow(3, "UCL", TODAY - timedelta(days=5), 1, 4, False, 1, 0, None, {}, {})]
    assert engine._team_leagues(rows) == {1: "EPL", 2: "ENG2", 3: "EPL"}
