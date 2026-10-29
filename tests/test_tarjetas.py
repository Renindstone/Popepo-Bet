"""Tarjetas: «Tarjeta al jugador» y nivel reciente de tarjetas de cada competición.

FotMob registra como mucho una amarilla por jugador y partido (la segunda cuenta como roja), y «Tarjeta al jugador»
se gana con amarilla o roja. El modelo de tarjetas del equipo (vida media 240 días) iba por detrás de las ligas que
bajan de nivel: en la Serie A esperaba 2,04 tarjetas por equipo y hubo 1,80 (enero de 2026).
"""

from datetime import date, timedelta

import pytest

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


SA, EPL = list(range(1, 9)), list(range(11, 19))


def _card_rows() -> list[MatchRow]:
    """Serie A con un 25 % menos de tarjetas en los últimos 60 días, Premier igual que siempre y una copa entre equipos
    de las dos ligas con un 20 % menos de las que dicen sus ligas (arbitrada con otros criterios)."""
    import numpy as np

    rng = np.random.default_rng(3)
    rows, mid = [], 0
    for comp, teams in (("SA", list(SA)), ("EPL", list(EPL))):
        for w in range(150):
            day = TODAY - timedelta(days=7 * w + 1)
            f = 0.75 if comp == "SA" and (TODAY - day).days <= 60 else 1.0
            rng.shuffle(teams)
            for h, a in zip(teams[::2], teams[1::2], strict=True):
                mid += 1
                rows.append(MatchRow(mid, comp, day, int(h), int(a), False, 1, 1, 50 + mid % 6,
                                     {"cards": float(rng.poisson(2.1 * f))}, {"cards": float(rng.poisson(2.3 * f))}))
    for w in range(60):
        mid += 1
        rows.append(MatchRow(mid, "UCL", TODAY - timedelta(days=4 * w + 2), SA[w % 8], EPL[w % 8], False, 1, 1, None,
                             {"cards": float(rng.poisson(2.1 * 0.8))}, {"cards": float(rng.poisson(2.3 * 0.8))}))
    return rows


def test_cards_follow_the_recent_level_of_each_league():
    rows = _card_rows()
    obs = fitting.count_obs(rows, "cards")
    old = fitting.fit_counts(obs, "cards", TODAY)
    cm = fitting.fit_counts(obs, "cards", TODAY, rows=rows)
    assert old.level == {}
    assert cm.level[SA[0]] < cm.level[EPL[0]] - 0.05  # la Serie A, con menos tarjetas que lo que dice el modelo
    assert cm.attack == old.attack and cm.defence == old.defence  # el nivel va aparte
    # En la copa solo cuenta el nivel de la copa, no la media de las ligas de los dos equipos
    assert cm.cup_alone and cm.cup_level["UCL"] < 0
    assert cm.level_for(SA[0], EPL[0], "UCL") == pytest.approx(cm.cup_level["UCL"])
    assert cm.level_for(SA[0], SA[1], "SA") == pytest.approx(cm.level[SA[0]])
    # En remates, la copa sigue tomando la media de las ligas más su desvío
    assert not fitting.COUNT_LEVEL_PARAMS.get("shots", {}).get("cup_alone", False)


def test_referees_are_fitted_without_the_level():
    """El factor del árbitro se mide frente al modelo sin el nivel de hoy, que no vale para partidos de hace años."""
    rows = _card_rows()
    obs = fitting.count_obs(rows, "cards")
    plain = fitting.fit_counts(obs, "cards", TODAY)
    leveled = fitting.fit_counts(obs, "cards", TODAY, rows=rows)
    assert fitting.fit_referees(rows, leveled, None) == fitting.fit_referees(rows, plain, None)
    eh, ea = leveled.expected(SA[0], SA[1], False, "SA")
    assert (eh, ea) != pytest.approx(leveled.expected(SA[0], SA[1], False, "SA", level=False))
    assert leveled.expected(SA[0], SA[1], False, "SA", level=False) == pytest.approx(plain.expected(SA[0], SA[1]))


def test_cup_alone_survives_the_model_bundle():
    cm = fitting.fit_counts(fitting.count_obs(_card_rows(), "cards"), "cards", TODAY, rows=_card_rows())
    back = RatingModel.from_dict(cm.to_dict())
    assert back.cup_alone and back.level_for(SA[0], EPL[0], "UCL") == pytest.approx(cm.cup_level["UCL"])
    d = cm.to_dict()
    del d["cup_alone"]
    assert not RatingModel.from_dict(d).cup_alone  # paquetes anteriores: como los remates


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
        # En el partido, el suplente del once confirmado cuenta también con esos minutos (si sale, el 44,3 %)
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
    assert pb.expected_minutes == pytest.approx(analysis.SUB_PLAY_RATE * analysis.SUB_MINUTES)
    share = (bench["volume_share"]["yellow_cards"] * bench["volume_team90"]["yellow_cards"]
             + priors["MF"]["yellow_cards_share"] * analysis.VOLUME_SHARE_PRIOR_MATCHES["yellow_cards"]
             * priors["MF"]["yellow_cards_team90"]) / (bench["volume_team90"]["yellow_cards"]
                                                       + analysis.VOLUME_SHARE_PRIOR_MATCHES["yellow_cards"]
                                                       * priors["MF"]["yellow_cards_team90"])
    assert pb.lam["yellow_cards"] == pytest.approx(
        share * analysis.SUB_PLAY_RATE * (analysis.SUB_MINUTES + extra) / 90 * 2.0, rel=1e-3)
