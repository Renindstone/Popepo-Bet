"""Minutos esperados de cada jugador cuando el partido aún no tiene alineación.

Antes, cada jugador con 2 titularidades entraba con probabilidad de ser titular = titularidades / partidos que jugó (sin
contar los que no jugó) y los minutos del equipo sumaban ~1.260 en vez de ~988: los goles y remates de los jugadores
superaban en un 14-16 % lo esperado del equipo. Ahora son sus minutos en los últimos partidos del equipo, escalados a
lo que juega un equipo.
"""

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.models import fitting
from apuestas.models.fitting import ModelBundle
from apuestas.models.ratings import RatingModel
from apuestas.services import analysis

BEFORE = datetime(2026, 10, 1, tzinfo=UTC)
A, B = 1, 2  # equipos


def _ko(k: int) -> datetime:
    """Hora del partido que el equipo jugó hace k partidos (0 = el último)."""
    return BEFORE - timedelta(days=7 * k + 3)


def _players(**teams: int) -> dict[int, dict]:
    return {pid: {"team_id": team} for pid, team in ((int(k[1:]), t) for k, t in teams.items())}


def test_recent_minutes_counts_zero_when_he_did_not_play():
    apps = [(A, 100 + k, _ko(k), 1, 90, True) for k in range(10)]  # titular siempre
    apps += [(A, 100 + k, _ko(k), 2, 20, False) for k in range(0, 10, 2)]  # suplente uno de cada dos
    players = _players(p1=A, p2=A)
    fitting.recent_minutes(players, apps, n=8)
    assert players[1]["recent_minutes"] == pytest.approx(90.0)
    assert players[1]["recent_start_rate"] == pytest.approx(1.0)
    assert players[2]["recent_minutes"] == pytest.approx(10.0)  # 4 de los 8 últimos × 20'
    assert players[2]["recent_start_rate"] == 0.0


def test_recent_minutes_of_a_new_signing_count_from_his_first_match():
    apps = [(A, 100 + k, _ko(k), 1, 90, True) for k in range(10)]
    apps += [(A, 100 + k, _ko(k), 3, 90, True) for k in range(3)]  # llegó hace 3 partidos y fue titular en todos
    players = _players(p1=A, p3=A)
    fitting.recent_minutes(players, apps, n=8)
    assert players[3]["recent_minutes"] == pytest.approx(90.0)  # no 3 × 90 / 8


def test_recent_minutes_of_injured_or_departed_players():
    apps = [(A, 100 + k, _ko(k), 1, 90, True) for k in range(12)]
    apps += [(A, 100 + k, _ko(k), 4, 90, True) for k in range(9, 12)]  # titular hace 9-11 partidos, luego nada
    apps += [(A, 100 + k, _ko(k), 5, 90, True) for k in range(3, 12)]  # se fue al equipo B hace 2 partidos
    apps += [(B, 200 + k, _ko(k), 5, 90, True) for k in range(2)]
    players = _players(p1=A, p4=A, p5=B)
    fitting.recent_minutes(players, apps, n=8)
    assert players[4]["recent_minutes"] == 0.0
    assert players[5]["recent_minutes"] == pytest.approx(90.0)  # con el equipo B, su equipo actual


def _bundle_players(minutes: dict[int, float], team: int = A, starter_minutes: float = 85.0) -> ModelBundle:
    players = {pid: {"team_id": team, "name": f"J{pid}", "position": "MF", "recent_minutes": mi,
                     "recent_start_rate": 1.0 if mi > 45 else 0.0, "avg_starter_minutes": starter_minutes}
               for pid, mi in minutes.items()}
    return SimpleNamespace(players=players)


def test_minutes_without_lineup_add_up_to_what_a_team_plays():
    # 11 titulares de 80' y 4 suplentes de 22' = 968: se escala a TEAM_MINUTES
    minutes = {pid: 80.0 for pid in range(1, 12)} | {pid: 22.0 for pid in range(12, 16)}
    out = analysis._minutes_without_lineup(_bundle_players(minutes), A, set())
    assert sum(mi for mi, _ in out.values()) == pytest.approx(analysis.TEAM_MINUTES)
    assert out[1][0] == pytest.approx(80.0 * analysis.TEAM_MINUTES / 968)
    assert out[1][1] == 0.9  # probabilidad de ser titular, como mucho 0,9 sin alineación


def test_minutes_of_an_injured_player_go_to_the_rest_without_passing_a_full_match():
    minutes = {pid: 85.0 for pid in range(1, 12)} | {pid: 13.0 for pid in range(12, 16)}  # 987
    out = analysis._minutes_without_lineup(_bundle_players(minutes), A, {1})
    assert 1 not in out
    assert sum(mi for mi, _ in out.values()) == pytest.approx(analysis.TEAM_MINUTES)
    assert max(mi for mi, _ in out.values()) <= 85.0 + 1e-9  # los titulares ya estaban en lo que juegan de titular
    # los 85' del lesionado (y el minuto que faltaba hasta TEAM_MINUTES), entre los 4 suplentes
    assert out[12][0] == pytest.approx((analysis.TEAM_MINUTES - 10 * 85.0) / 4)


def test_too_many_minutes_scale_down_everybody():
    # Un fichaje que ocupa el sitio de alguien que se fue a una liga sin datos: 12 jugadores de 90'
    minutes = {pid: 90.0 for pid in range(1, 13)}
    out = analysis._minutes_without_lineup(_bundle_players(minutes, starter_minutes=90.0), A, set())
    assert all(mi == pytest.approx(analysis.TEAM_MINUTES / 12) for mi, _ in out.values())


def test_old_bundles_without_recent_minutes_give_nothing():
    bundle = SimpleNamespace(players={1: {"team_id": A, "starts": 10, "apps": 12}})
    assert analysis._minutes_without_lineup(bundle, A, set()) == {}


# --------------------------------------------------------------------------- con la BD


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _setup(s: Session) -> tuple[SimpleNamespace, int]:
    """Diez partidos del Bayern: 10 fijos de 90', dos delanteros que se turnan y un suplente de 20' en cada uno."""
    comp = m.Competition(code="BUN", name="Bundesliga", country="Germany", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    bayern, dortmund = m.Team(name="Bayern"), m.Team(name="Dortmund")
    s.add_all([season, bayern, dortmund])
    s.flush()
    players = [m.Player(name=f"J{k}", position="FW" if k >= 10 else "MF") for k in range(13)]
    s.add_all(players)
    s.flush()
    for k in range(10):
        mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=_ko(k), home_team_id=bayern.id,
                     away_team_id=dortmund.id, status="finished", home_goals=2, away_goals=1)
        s.add(mt)
        s.flush()
        s.add(m.TeamMatchStats(match_id=mt.id, team_id=bayern.id, is_home=True, shots=14, shots_on_target=4,
                               yellow_cards=0, red_cards=0))
        striker = players[10 + k % 2]
        for p, mins, starter in [*((p, 90, True) for p in players[:10]), (striker, 70, True), (players[12], 20, False)]:
            s.add(m.PlayerMatchStats(match_id=mt.id, player_id=p.id, team_id=bayern.id, is_starter=starter,
                                     minutes=mins, goals=1 if p is striker else 0, shots=3 if p is striker else 1))
    s.flush()
    fake = SimpleNamespace(id=-1, home_team_id=bayern.id, away_team_id=dortmund.id)  # sin alineación
    return fake, bayern.id


def _bundle(s: Session) -> ModelBundle:
    players, priors = fitting.fit_players(s, before=BEFORE)

    def model(mean):
        return RatingModel(teams=[], mu=math.log(mean), home_adv=0.0, attack={}, defence={})

    return ModelBundle(version="v1", as_of=BEFORE.date(), goals=model(1.6), rho=0.0,
                       counts={"shots": model(12.0), "shots_on_target": model(4.0), "cards": model(2.0)},
                       referees={}, players=players, priors=priors)


MEANS = {"shots": (12.0, 9.0), "shots_on_target": (4.0, 3.0), "cards": (2.0, 2.0)}


def test_projection_without_lineup_uses_the_team_minutes(s):
    match, team = _setup(s)
    proj = analysis._player_projections(s, _bundle(s), match, team, True, MEANS, 1.5)
    assert sum(p.expected_minutes for p in proj) == pytest.approx(analysis.TEAM_MINUTES)
    by_name = {p.name: p for p in proj}
    # Los delanteros se turnan: medio partido de titular cada uno, no 0,9 de probabilidad
    assert by_name["J10"].start_prob == pytest.approx(0.5)
    assert by_name["J10"].expected_minutes == pytest.approx(35.0 * analysis.TEAM_MINUTES / 990, rel=0.01)
    # Los remates de los jugadores suman lo esperado del equipo (antes, con más minutos, lo superaban)
    assert sum(p.lam["shots"] for p in proj) == pytest.approx(12.0, rel=0.05)


def test_projection_without_lineup_with_an_old_bundle_keeps_the_previous_rule(s):
    match, team = _setup(s)
    bundle = _bundle(s)
    for pr in bundle.players.values():
        del pr["recent_minutes"], pr["recent_start_rate"]
    proj = {p.name: p for p in analysis._player_projections(s, bundle, match, team, True, MEANS, 1.5)}
    # Titular en todos los partidos que jugó: casi seguro titular, aunque solo juega uno de cada dos
    assert proj["J10"].start_prob == 0.9
    assert proj["J10"].expected_minutes == pytest.approx(0.9 * 70)
    assert "J12" not in proj  # nunca fue titular
