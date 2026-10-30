"""Comparar precios: cuotas de Betano por encima de la justa (sin margen) de Pinnacle, sin modelo."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.db import models as m
from apuestas.ingest.store import store_odds
from apuestas.services import compare, picks

KICKOFF = datetime(2026, 10, 31, 20, tzinfo=UTC)


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    ids = count(1000)

    def give_id(_mapper, _conn, row):  # en SQLite las claves BigInteger no se autoincrementan
        row.id = row.id or next(ids)

    event.listen(m.OddsSnapshot, "before_insert", give_id)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(compare, "session_scope", scope)
        yield session
    event.remove(m.OddsSnapshot, "before_insert", give_id)


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


def download(s, mt, rows, hours):
    """Una descarga de OddsPapi por la ingesta real: solo guarda los precios que cambian y apunta los que vuelve a ver."""
    store_odds(s, mt, [SimpleNamespace(bookmaker=b, market=mk, selection=sel, line=ln, price=p, kind="live")
                       for b, mk, sel, ln, p in rows], "oddspapi", captured_at=KICKOFF - timedelta(hours=hours))


def test_solo_lineas_que_la_casa_sigue_ofreciendo(s):
    mt = match(s)
    pin = [("pinnacle", "ou_cards", "over", 4.5, 1.90), ("pinnacle", "ou_cards", "under", 4.5, 1.95),
           ("pinnacle", "btts", "yes", None, 1.80), ("pinnacle", "btts", "no", None, 2.05)]
    download(s, mt, pin + [("betano", "ou_cards", "over", 4.5, 2.30), ("betano", "btts", "no", None, 2.30)], hours=34)
    # Al día siguiente, los mismos precios (no se guarda fila nueva) salvo que Betano ya no ofrece Más de 4.5
    download(s, mt, pin + [("betano", "btts", "no", None, 2.30)], hours=10)
    assert [r["market"] for r in compare.match_edges(s, mt)] == ["btts"]  # sin cambiar de precio, sigue vigente
    # La de Pinnacle de antes del partido (solo el 1X2) no deja fuera lo visto por la mañana
    download(s, mt, [("pinnacle", "1x2", "home", None, 2.0)], hours=2)
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


def test_el_analisis_tampoco_usa_cuotas_que_ya_no_se_ofrecen(s):
    # «Con valor» y la apuesta del día leen las cuotas con `_latest_odds`
    from apuestas.services import analysis

    mt = match(s)
    download(s, mt, [("betano", "ou_corners", "over", 8.5, 1.60), ("betano", "ou_corners", "over", 9.5, 2.00)], hours=34)
    download(s, mt, [("betano", "ou_corners", "over", 9.5, 2.00)], hours=10)  # la 8.5 ya no sale
    odds(s, mt, [("bet365", "1x2", "home", None, 1.90)], hours=60)  # fila de antes del 29-10: sin last_seen_at
    rows = analysis._latest_odds(s, mt.id)
    assert sorted((r.bookmaker, r.line, r.price) for r in rows) == [("bet365", None, 1.90), ("betano", 9.5, 2.00)]
    assert s.query(m.OddsSnapshot).filter_by(bookmaker="betano").count() == 2  # la 9.5 no se guardó dos veces
