"""Tarjetas: «Tarjeta al jugador» y nivel reciente de tarjetas de cada competición.

FotMob registra como mucho una amarilla por jugador y partido (la segunda cuenta como roja), y «Tarjeta al jugador»
se gana con amarilla o roja. El modelo de tarjetas del equipo (vida media 240 días) iba por detrás de las ligas que
bajan de nivel: en la Serie A esperaba 2,04 tarjetas por equipo y hubo 1,80 (enero de 2026).
"""

from collections import defaultdict
from datetime import date, timedelta

import pytest

from apuestas.backtest import engine
from apuestas.betting.settlement import PLAYER_COLUMNS
from apuestas.db import models as m
from apuestas.models import fitting
from apuestas.models.fitting import MatchRow, ModelBundle
from apuestas.models.ratings import RatingModel
from apuestas.services import analysis
from apuestas.services.match_model import MAX_CARD_PROB, MatchModel, PlayerProjection

TODAY = date(2026, 10, 22)


def _model(per_team: float) -> RatingModel:
    """Modelo de conteo sin equipos: cada equipo, `per_team` de media (sin ventaja local)."""
    import math

    return RatingModel(teams=[], mu=math.log(per_team), home_adv=0.0, attack={}, defence={})


def _row(mid: int, code: str, day: date, cards_h: int | None, cards_a: int | None) -> MatchRow:
    return MatchRow(mid, code, day, 1, 2, False, 1, 1, None, {"cards": cards_h}, {"cards": cards_a})


@pytest.mark.parametrize(("yellow", "red", "carded"), [(0, 0, 0.0), (1, 0, 1.0), (0, 1, 1.0), (1, 1, 1.0),
                                                       (None, None, 0.0)])
def test_player_card_counts_once_with_yellow_or_red(yellow, red, carded):
    """Roja directa o doble amarilla (1 amarilla + 1 roja en FotMob) cuentan como una tarjeta, igual que al liquidar."""
    pms = m.PlayerMatchStats(shots=None, shots_on_target=None, yellow_cards=yellow, red_cards=red)
    assert fitting._player_volume(pms) == {"shots": 0.0, "shots_on_target": 0.0, "yellow_cards": carded}
    assert PLAYER_COLUMNS["player_card"] == ("yellow_cards",)  # y la liquidación suma la roja aparte


def test_player_card_probability_is_the_expected_card():
    """La λ es la probabilidad de ver tarjeta (0 o 1 por partido): sin 1 − e^(−λ), que la dejaba ~7 % baja."""
    mm = MatchModel(1, 2, 1.5, 1.1, -0.05, {"cards": (2.0, 2.2)}, {"cards": 0.1})
    mm.players = {9: PlayerProjection(9, "Rodri", 1, "MF", 85, 1.0, {"yellow_cards": 0.18}),
                  4: PlayerProjection(4, "Raro", 1, "DF", 85, 1.0, {"yellow_cards": 1.4})}
    assert mm.outcome("player_card", "yes", None, 9).effective_prob() == pytest.approx(0.18)
    assert mm.outcome("player_card", "no", None, 9).effective_prob() == pytest.approx(0.82)
    assert mm.outcome("player_card", "sí", None, 4).effective_prob() == pytest.approx(MAX_CARD_PROB)


def test_level_follows_recent_cards_of_each_competition():
    cm = _model(2.0)  # 4 tarjetas por partido esperadas en todas las competiciones
    rows = [_row(k, "SA", TODAY - timedelta(days=3 + k), 2, 1) for k in range(30)]  # 3 por partido: 25 % menos
    rows += [_row(100 + k, "EPL", TODAY - timedelta(days=3 + k), 2, 2) for k in range(30)]  # lo esperado
    rows.append(_row(999, "SA", TODAY, None, 2))  # sin tarjetas de un equipo: no cuenta
    levels = fitting.fit_count_levels(rows, {"cards": cm}, TODAY)
    half_life, prior = fitting.COUNT_LEVEL["cards"]
    w = sum(0.5 ** ((3 + k) / half_life) for k in range(30))
    assert levels["cards"]["SA"] == pytest.approx((3 * w + 4 * prior) / (4 * w + 4 * prior), abs=1e-4)
    assert 0.75 < levels["cards"]["SA"] < 0.9  # entre lo visto (0,75) y 1 (el modelo): contraído con K partidos
    assert levels["cards"]["EPL"] == pytest.approx(1.0)
    # Lo de hace meses apenas pesa: tras el parón de verano el nivel vuelve casi al del modelo
    old = [_row(r.match_id, r.competition, r.day - timedelta(days=200), 2, 1) for r in rows[:30]]
    assert fitting.fit_count_levels(old, {"cards": cm}, TODAY)["cards"]["SA"] == pytest.approx(1.0, abs=0.01)
    # Solo las estadísticas de COUNT_LEVEL y solo si el paquete tiene su modelo
    assert set(fitting.fit_count_levels(rows, {"cards": cm, "fouls": cm}, TODAY)) == {"cards"}
    assert fitting.fit_count_levels(rows, {}, TODAY) == {}


def test_bundle_keeps_the_levels_and_old_bundles_use_one():
    goals = _model(1.4)
    bundle = ModelBundle(version="v1", as_of=TODAY, goals=goals, rho=0.0, counts={"cards": _model(2.0)}, referees={},
                         players={}, priors={}, count_levels={"cards": {"SA": 0.87}})
    back = ModelBundle.from_json(bundle.to_json())
    assert back.count_level("cards", "SA") == pytest.approx(0.87)
    assert back.count_level("cards", "EPL") == 1.0
    assert back.count_level("corners", "SA") == 1.0
    old = bundle.to_json()
    del old["count_levels"]
    assert ModelBundle.from_json(old).count_level("cards", "SA") == 1.0


def test_backtest_applies_the_level_of_the_match_competition():
    cms = {"cards": _model(2.0)}
    row = _row(1, "SA", TODAY, 1, 2)
    plain: dict = defaultdict(list)
    lowered: dict = defaultdict(list)
    engine._evaluate_counts(row, cms, plain)
    engine._evaluate_counts(row, cms, lowered, levels={"cards": {"SA": 0.75, "EPL": 1.3}})
    # 3 tarjetas reales frente a 4 esperadas: con el nivel de la Serie A (3 esperadas) la verosimilitud mejora
    assert lowered["cards por equipo"][0][0] > plain["cards por equipo"][0][0]
    assert lowered["cards por equipo"][0][1] == plain["cards por equipo"][0][1]  # la media de la liga, igual
    other: dict = defaultdict(list)
    engine._evaluate_counts(row, cms, other, levels={"cards": {"EPL": 1.3}})
    assert other["cards por equipo"] == plain["cards por equipo"]


def test_substitutes_count_extra_minutes_in_their_card_share():
    """Un suplente ve más tarjetas por minuto (entra al final y juega el descuento): su exposición en tarjetas son
    sus minutos más CARD_SUB_EXTRA_MINUTES. En remates no cambia nada."""
    from datetime import UTC, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    before = datetime(2026, 10, 1, tzinfo=UTC)
    engine_db = create_engine("sqlite://")
    m.Base.metadata.create_all(engine_db)
    with Session(engine_db) as s:
        comp = m.Competition(code="SA", name="Serie A", country="Italy", tier="full")
        s.add(comp)
        s.flush()
        season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
        inter, milan = m.Team(name="Inter"), m.Team(name="Milan")
        starter, sub = m.Player(name="Barella", position="MF"), m.Player(name="Frattesi", position="MF")
        s.add_all([season, inter, milan, starter, sub])
        s.flush()
        for k in range(5):
            mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=before - timedelta(days=7 * k + 3),
                         home_team_id=inter.id, away_team_id=milan.id, status="finished", home_goals=1, away_goals=1)
            s.add(mt)
            s.flush()
            s.add(m.TeamMatchStats(match_id=mt.id, team_id=inter.id, is_home=True, shots=10, shots_on_target=4,
                                   yellow_cards=2, red_cards=0))
            s.add(m.PlayerMatchStats(match_id=mt.id, player_id=starter.id, team_id=inter.id, is_starter=True,
                                     minutes=90, shots=2, yellow_cards=1))
            s.add(m.PlayerMatchStats(match_id=mt.id, player_id=sub.id, team_id=inter.id, is_starter=False,
                                     minutes=25, shots=1, yellow_cards=1, red_cards=1))  # doble amarilla: 1 tarjeta
        s.flush()
        players, priors = fitting.fit_players(s, before=before)
        full, bench = players[starter.id], players[sub.id]
        extra = fitting.CARD_SUB_EXTRA_MINUTES
        assert bench["volume_team90"]["yellow_cards"] == pytest.approx(
            full["volume_team90"]["yellow_cards"] * (25 + extra) / 90, rel=1e-3)
        assert bench["volume_team90"]["shots"] == pytest.approx(full["volume_team90"]["shots"] * 25 / 90, rel=1e-3)
        assert bench["volume_share"]["yellow_cards"] == pytest.approx(0.5 * 90 / (25 + extra), rel=1e-3)
        # En el partido, el suplente del once confirmado cuenta también con esos minutos (si sale, el 55 %)
        nxt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=before + timedelta(days=2),
                      home_team_id=inter.id, away_team_id=milan.id, status="scheduled")
        s.add(nxt)
        s.flush()
        for pl, is_starter in ((starter, True), (sub, False)):
            s.add(m.Lineup(match_id=nxt.id, team_id=inter.id, player_id=pl.id, status="confirmed",
                           is_starter=is_starter, position="MF"))
        s.flush()
        bundle = ModelBundle(version="v1", as_of=before.date(), goals=_model(1.4), rho=0.0,
                             counts={"shots": _model(10.0), "shots_on_target": _model(4.0), "cards": _model(2.0)},
                             referees={}, players=players, priors=priors)
        means = {"shots": (10.0, 9.0), "shots_on_target": (4.0, 3.0), "cards": (2.0, 2.0)}
        proj = {pp.player_id: pp for pp in analysis._player_projections(s, bundle, nxt, inter.id, True, means, 1.4)}
    pb = proj[sub.id]
    assert pb.expected_minutes == pytest.approx(0.55 * 22)
    share = (bench["volume_share"]["yellow_cards"] * bench["volume_team90"]["yellow_cards"]
             + priors["MF"]["yellow_cards_share"] * analysis.VOLUME_SHARE_PRIOR_MATCHES["yellow_cards"]
             * priors["MF"]["yellow_cards_team90"]) / (bench["volume_team90"]["yellow_cards"]
                                                       + analysis.VOLUME_SHARE_PRIOR_MATCHES["yellow_cards"]
                                                       * priors["MF"]["yellow_cards_team90"])
    assert pb.lam["yellow_cards"] == pytest.approx(share * 0.55 * (22 + extra) / 90 * 2.0, rel=1e-3)
