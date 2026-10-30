"""Carga de partidos: rival anterior y siguiente, si son grandes o chicos, y el aviso de rival chico entre grandes."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.features import context as ctx

KO = datetime(2026, 11, 1, 15)  # sin zona: SQLite la pierde al leer


@pytest.fixture
def s():
    db = create_engine("sqlite://")
    m.Base.metadata.create_all(db)
    ctx._comp_teams.clear()
    with Session(db) as session:
        yield session
    ctx._comp_teams.clear()


def test_rival_chico_entre_grandes(s):
    comps = {c: m.Competition(code=c, name=c, country="x", tier="full", is_cup=c == "UCL") for c in ("EPL", "UCL")}
    s.add_all(comps.values())
    s.flush()
    seasons = {c: m.Season(competition_id=x.id, start_year=2026, label="2026/2027") for c, x in comps.items()}
    s.add_all(seasons.values())
    teams = [m.Team(name=f"T{i}") for i in range(10)] + [m.Team(name="Rival de Champions")]
    s.add_all(teams)
    s.flush()
    villa, small, city = teams[5], teams[0], teams[9]
    strength = {t.id: float(i) for i, t in enumerate(teams[:10])}  # T9 el más fuerte, T0 el más flojo

    def match(comp, home, away, when, status="finished"):
        mt = m.Match(competition_id=comps[comp].id, season_id=seasons[comp].id, kickoff_utc=when,
                     home_team_id=home.id, away_team_id=away.id, status=status)
        s.add(mt)
        return mt

    for i in range(10):  # la liga: todos juegan, para saber quién es grande y quién chico
        match("EPL", teams[i], teams[(i + 1) % 10], KO - timedelta(days=60 + i))
    match("EPL", villa, city, KO - timedelta(days=4))  # antes, contra el más fuerte
    today = match("EPL", villa, small, KO, "scheduled")  # hoy, contra el más flojo
    match("UCL", villa, teams[10], KO + timedelta(days=3), "scheduled")  # después, Champions
    s.flush()

    c = ctx.team_context(s, today, villa.id, 0.8, strength)
    assert c.opponent_tier == "chico"
    assert c.prev_match["opponent"] == "T9" and c.prev_match["tier"] == "grande" and c.prev_match["days"] == 4.0
    assert c.next_match["tier"] == "Champions" and c.next_match["days"] == 3.0
    assert any(n.startswith("Rival chico entre partidos grandes (T9, Rival de Champions)") for n in c.notes)
    # El rival chico no ve el aviso (su rival es grande), y sin fuerzas no se marca nada
    assert not any("Rival chico" in n for n in ctx.team_context(s, today, small.id, -0.8, strength).notes)
    assert ctx.team_context(s, today, villa.id, 0.8).opponent_tier is None


def test_titular_poco_habitual(s):
    from apuestas.features import lineup as lu

    comp = m.Competition(code="EPL", name="EPL", country="x", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    team, rival = m.Team(name="Fulham"), m.Team(name="Rival")
    fijo, nuevo = m.Player(name="Fijo"), m.Player(name="Nuevo")
    s.add_all([season, team, rival, fijo, nuevo])
    s.flush()
    for i in range(12):  # 12 onces confirmados: el fijo siempre, el nuevo solo en el más antiguo
        mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=KO - timedelta(days=7 * (i + 1)),
                     home_team_id=team.id, away_team_id=rival.id, status="finished")
        s.add(mt)
        s.flush()
        s.add(m.Lineup(match_id=mt.id, team_id=team.id, player_id=fijo.id, is_starter=True, status="confirmed"))
        if i == 11:
            s.add(m.Lineup(match_id=mt.id, team_id=team.id, player_id=nuevo.id, is_starter=True, status="confirmed"))
    s.flush()
    recent = lu.recent_starts(s, team.id, KO)
    assert recent == {fijo.id: 10}  # solo cuentan los 10 últimos: el nuevo, 0
    assert recent.get(nuevo.id, 0) <= lu.UNUSUAL_MAX_STARTS
    assert lu.recent_starts(s, rival.id, KO) is None  # sin onces suficientes, no se sabe
