"""Comparar precios: cuotas de Betano por encima de la justa (sin margen) de Pinnacle, sin modelo."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.db import models as m
from apuestas.services import compare, picks

KICKOFF = datetime(2026, 10, 31, 20, tzinfo=UTC)


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(compare, "session_scope", scope)
        yield session


def match(s, status="scheduled", kickoff=KICKOFF):
    comp = s.query(m.Competition).first()
    if comp is None:
        comp = m.Competition(code="EPL", name="Premier League", country="England", tier="full")
        s.add(comp)
        s.flush()
        s.add_all([m.Season(competition_id=comp.id, start_year=2026, label="2026/2027"), m.Team(name="Arsenal"),
                   m.Team(name="Chelsea")])
        s.flush()
    season = s.query(m.Season).one()
    home, away = (s.query(m.Team).filter_by(name=n).one() for n in ("Arsenal", "Chelsea"))
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=kickoff, home_team_id=home.id,
                 away_team_id=away.id, status=status)
    s.add(mt)
    s.flush()
    return mt


def odds(s, mt, rows, hours=10):
    """rows: (casa, mercado, selección, línea, cuota), vistas `hours` antes del inicio."""
    start = s.query(m.OddsSnapshot).count() + 1
    s.add_all([m.OddsSnapshot(id=i, match_id=mt.id, bookmaker=book, market=mk, selection=sel, line=ln, price=p,
                              kind="live", source="oddspapi", captured_at=KICKOFF - timedelta(hours=hours))
               for i, (book, mk, sel, ln, p) in enumerate(rows, start=start)])
    s.flush()


def test_betano_por_encima_de_pinnacle(s):
    mt = match(s)
    odds(s, mt, [
        ("pinnacle", "ou_corners", "over", 9.5, 1.90), ("pinnacle", "ou_corners", "under", 9.5, 1.95),
        ("betano", "ou_corners", "over", 9.5, 2.10),  # justa de Pinnacle ~1,97: +6,5 %
        ("betano", "ou_corners", "under", 9.5, 1.70),  # por debajo: no sale
        ("betano", "ou_corners", "over", 10.5, 3.00),  # Pinnacle no tiene esa línea: no se compara
        ("pinnacle", "1x2", "home", None, 2.00), ("pinnacle", "1x2", "draw", None, 3.60),
        ("pinnacle", "1x2", "away", None, 3.90),
        ("betano", "1x2", "home", None, 2.02),  # justa ~2,08: por debajo
    ])
    rows = compare.match_edges(s, mt)
    p_over = oddsmath.devig([1.90, 1.95])[0]
    assert [(r["market"], r["selection"], r["line"]) for r in rows] == [("ou_corners", "over", 9.5)]
    r = rows[0]
    assert r["edge"] == pytest.approx(2.10 * p_over - 1, abs=1e-4) and r["edge"] > compare.MIN_EDGE
    assert r["fair_odds"] == pytest.approx(1 / p_over, abs=1e-3)
    assert r["group"] == "estadísticas" and r["label"] == "Córners: Más de 9.5"
    assert compare.match_edges(s, mt, min_edge=0.10) == []


def test_solo_la_ultima_descarga_de_cada_casa(s):
    mt = match(s)
    odds(s, mt, [("pinnacle", "ou_cards", "over", 4.5, 1.90), ("pinnacle", "ou_cards", "under", 4.5, 1.95),
                 ("betano", "ou_cards", "over", 4.5, 2.30), ("betano", "ou_cards", "over", 5.5, 1.20)], hours=34)
    # En la descarga del día siguiente Betano ya no ofrece Más de 4.5 (solo la 5.5): ese precio viejo no se compara
    s.add(m.OddsSnapshot(id=99, match_id=mt.id, bookmaker="betano", market="ou_cards", selection="over", line=5.5,
                         price=1.25, kind="live", source="oddspapi", captured_at=KICKOFF - timedelta(hours=10)))
    s.flush()
    assert compare.match_edges(s, mt) == []
    # La de Pinnacle de antes del partido (solo un mercado, 8 horas después) no deja fuera la de la mañana
    odds(s, mt, [("pinnacle", "btts", "yes", None, 1.80), ("pinnacle", "btts", "no", None, 2.05),
                 ("betano", "btts", "no", None, 2.30)], hours=10)
    odds(s, mt, [("pinnacle", "1x2", "home", None, 2.0)], hours=2)
    assert [r["market"] for r in compare.match_edges(s, mt)] == ["btts"]


def test_sin_pinnacle_no_hay_comparacion(s):
    mt = match(s)
    odds(s, mt, [("betano", "ou_corners", "over", 9.5, 2.10), ("betano", "ou_corners", "under", 9.5, 1.70)])
    assert compare.match_edges(s, mt) == []


def test_dia_solo_partidos_sin_empezar(s, monkeypatch):
    open_, done = match(s), match(s, "finished", KICKOFF - timedelta(hours=3))
    for mt in (open_, done):
        odds(s, mt, [("pinnacle", "btts", "yes", None, 1.80), ("pinnacle", "btts", "no", None, 2.05),
                     ("betano", "btts", "no", None, 2.30)])
    monkeypatch.setattr(picks, "matches_for_day", lambda _s, _d: [open_, done])
    out = compare.day_edges(KICKOFF.date())
    assert [r["match_id"] for r in out["rows"]] == [open_.id]
    assert out["rows"][0]["group"] == "goles" and out["rows"][0]["match"] == "Arsenal vs Chelsea"
    assert "no una apuesta segura" in out["note"]


def test_el_mcp_tiene_comparar_casas():
    from apuestas.mcp_server.server import build

    assert "comparar_casas" in {t.name for t in build()._tool_manager.list_tools()}
