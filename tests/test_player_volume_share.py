"""Remates, a puerta y tarjetas de jugador: parte de los de su equipo por lo que se espera del equipo en el partido.

Antes se escalaban contra la media del equipo frente a un "rival promedio" de toda la BD (con ligas de segunda y
ligeras), que infla la media de los equipos de las ligas grandes: los remates de jugador salían ~15 % cortos.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.models import fitting
from apuestas.models.fitting import ModelBundle
from apuestas.models.ratings import RatingModel
from apuestas.services import analysis

BEFORE = datetime(2026, 10, 1, tzinfo=UTC)
# Por partido: (minutos, remates, a puerta, amarillas). El portero no remata y FotMob deja sus remates vacíos.
SQUAD = {"Kane": ("FW", 90, 6, 3, 1), "Musiala": ("MF", 90, 4, 1, 1), "Neuer": ("GK", 90, None, None, 0)}
TEAM_SHOTS, TEAM_SOT, TEAM_YELLOWS = 10, 4, 2


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _setup(s: Session) -> tuple[m.Match, dict[str, int]]:
    """Seis partidos jugados del Bayern y uno por jugar con su alineación confirmada."""
    comp = m.Competition(code="BUN", name="Bundesliga", country="Germany", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    bayern, dortmund = m.Team(name="Bayern"), m.Team(name="Dortmund")
    s.add_all([season, bayern, dortmund])
    s.flush()
    players = {name: m.Player(name=name, position=pos) for name, (pos, *_) in SQUAD.items()}
    s.add_all(players.values())
    s.flush()
    for k in range(6):
        mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=BEFORE - timedelta(days=7 * k + 3),
                     home_team_id=bayern.id, away_team_id=dortmund.id, status="finished", home_goals=2, away_goals=1)
        s.add(mt)
        s.flush()
        s.add(m.TeamMatchStats(match_id=mt.id, team_id=bayern.id, is_home=True, shots=TEAM_SHOTS,
                               shots_on_target=TEAM_SOT, yellow_cards=TEAM_YELLOWS, red_cards=0))
        for name, (_, mins, shots, sot, yellows) in SQUAD.items():
            s.add(m.PlayerMatchStats(match_id=mt.id, player_id=players[name].id, team_id=bayern.id, is_starter=True,
                                     minutes=mins, shots=shots, shots_on_target=sot, yellow_cards=yellows))
    nxt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=BEFORE + timedelta(days=2),
                  home_team_id=bayern.id, away_team_id=dortmund.id, status="scheduled")
    s.add(nxt)
    s.flush()
    for name, (pos, *_) in SQUAD.items():
        s.add(m.Lineup(match_id=nxt.id, team_id=bayern.id, player_id=players[name].id, status="confirmed",
                       is_starter=True, position=pos))
    s.flush()
    return nxt, {name: p.id for name, p in players.items()}


def _bundle(s: Session, mu_rival_promedio: float = 20.0) -> ModelBundle:
    players, priors = fitting.fit_players(s, before=BEFORE)

    def model(mean):  # media del Bayern "contra un rival promedio": exp(mu + ventaja local)
        return RatingModel(teams=[], mu=math.log(mean), home_adv=0.0, attack={}, defence={})

    counts = {"shots": model(mu_rival_promedio), "shots_on_target": model(7.0), "cards": model(3.0)}
    return ModelBundle(version="v1", as_of=BEFORE.date(), goals=model(1.6), rho=0.0, counts=counts, referees={},
                       players=players, priors=priors)


def test_team_volume_counts_red_cards_like_the_count_model():
    tms = m.TeamMatchStats(shots=12, shots_on_target=5, yellow_cards=3, red_cards=1)
    assert fitting._team_volume(tms) == {"shots": 12, "shots_on_target": 5, "yellow_cards": 4}
    assert fitting._team_volume(m.TeamMatchStats(shots=12, yellow_cards=None))["yellow_cards"] is None
    assert fitting._team_volume(None) == {}


def test_fit_players_keeps_each_players_share_of_the_team(s):
    _, ids = _setup(s)
    players, priors = fitting.fit_players(s, before=BEFORE)
    kane, musiala, neuer = (players[ids[n]] for n in ("Kane", "Musiala", "Neuer"))
    assert kane["volume_share"] == pytest.approx({"shots": 0.6, "shots_on_target": 0.75, "yellow_cards": 0.5})
    assert musiala["volume_share"] == pytest.approx({"shots": 0.4, "shots_on_target": 0.25, "yellow_cards": 0.5})
    # Sin remates el dato viene vacío: cuenta como 0, con la misma exposición (si no, su parte saldría inflada)
    assert neuer["volume_share"] == pytest.approx({"shots": 0.0, "shots_on_target": 0.0, "yellow_cards": 0.0})
    assert neuer["volume_team90"] == pytest.approx(kane["volume_team90"])
    assert kane["volume_team90"]["shots"] == pytest.approx(TEAM_SHOTS * kane["minutes90"], abs=0.01)
    assert priors["FW"]["shots_share"] == pytest.approx(0.6)
    assert priors["FW"]["shots_team90"] == pytest.approx(TEAM_SHOTS)


def test_projection_splits_the_expected_team_volume(s):
    match, ids = _setup(s)
    means = {"shots": (12.0, 9.0), "shots_on_target": (4.5, 3.0), "cards": (2.2, 2.0)}
    for mu in (20.0, 9.0):  # el "rival promedio" ya no cuenta
        proj = {p.player_id: p.lam for p in analysis._player_projections(
            s, _bundle(s, mu), match, match.home_team_id, True, means, 1.5)}
        assert sum(lam["shots"] for lam in proj.values()) == pytest.approx(12.0)
        assert sum(lam["shots_on_target"] for lam in proj.values()) == pytest.approx(4.5)
        assert sum(lam["yellow_cards"] for lam in proj.values()) == pytest.approx(2.2)
        assert proj[ids["Kane"]]["shots"] == pytest.approx(0.6 * 12.0)
        assert proj[ids["Neuer"]]["shots"] == pytest.approx(0.0)


def test_old_bundles_keep_the_previous_formula(s):
    """Un paquete de modelos sin las partes escala las tasas por 90' contra el rival promedio, como antes."""
    match, _ = _setup(s)
    bundle = _bundle(s, 20.0)
    new_keys = {f"{st}_{suf}" for st in fitting.VOLUME_SHARE_STATS for suf in ("share", "team90")}
    bundle.priors = {pos: {k: v for k, v in pr.items() if k not in new_keys} for pos, pr in bundle.priors.items()}
    means = {"shots": (12.0, 9.0), "shots_on_target": (4.5, 3.0), "cards": (2.2, 2.0)}
    proj = analysis._player_projections(s, bundle, match, match.home_team_id, True, means, 1.5)
    # 10 remates por 90' entre los tres × (12 esperados / 20 contra el rival promedio): el sesgo que se corrigió
    assert sum(p.lam["shots"] for p in proj) == pytest.approx(TEAM_SHOTS * 12.0 / 20.0)
