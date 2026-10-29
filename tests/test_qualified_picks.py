"""Apuestas que pasan el corte: se marcan al guardarse, salen primero y tienen su propio contador de aciertos."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import picks, queries


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session

        monkeypatch.setattr(picks, "session_scope", scope)
        monkeypatch.setattr(queries, "session_scope", scope)
        yield session


def bet(**kw):
    """Apuesta con valor que pasa el corte por defecto (goles, cuota 2,0, 55 %, +10 %, confianza 0,8)."""
    base = dict(market="ou_goals", selection="over", line=2.5, bookmaker="bet365", odds=2.0, prob=0.55,
                fair_odds=1.82, ev=0.10, confidence=0.8, stake_pct=0.01, reasons=[])
    return SimpleNamespace(**{**base, **kw})


def match(s, kickoff=datetime(2026, 10, 20, 19, tzinfo=UTC)):
    comp = m.Competition(code="EPL", name="Premier League", country="England", tier="full")
    s.add(comp)
    s.flush()
    season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
    home, away = m.Team(name="Arsenal"), m.Team(name="Chelsea")
    s.add_all([season, home, away])
    s.flush()
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=kickoff, home_team_id=home.id,
                 away_team_id=away.id, status="finished", home_goals=2, away_goals=1)
    s.add(mt)
    s.flush()
    return mt


@pytest.mark.parametrize("change, passes", [
    ({}, True),
    ({"confidence": 0.4}, False),  # poca confianza
    ({"odds": 3.5, "ev": 0.2}, False),  # cuota fuera del rango de la apuesta del día
    ({"market": "ou_corners"}, False),  # córners: aún no entran en la apuesta del día
])
def test_upsert_marks_whether_it_passes(s, change, passes):
    mt = match(s)
    p = picks._upsert_pick(s, mt, bet(**change), date(2026, 10, 20), "pre_lineup")
    assert p.qualifies is passes


def test_recalculation_can_take_it_out_of_the_cut(s):
    mt = match(s)
    day = date(2026, 10, 20)
    p = picks._upsert_pick(s, mt, bet(), day, "pre_lineup")
    s.flush()
    again = picks._upsert_pick(s, mt, bet(confidence=0.5), day, "confirmed")  # con la alineación baja la confianza
    assert again.id == p.id and again.qualifies is False


def test_qualified_record_counts_only_those_that_passed(s):
    mt = match(s)
    day = date(2026, 10, 20)
    rows = [
        dict(selection="over", qualifies=True, status="settled", result="win", odds=2.0, is_pick_of_day=True),
        dict(selection="under", qualifies=True, status="settled", result="loss", odds=1.9),
        dict(selection="yes", qualifies=True, status="open", result=None, odds=1.8),
        dict(selection="no", qualifies=True, status="withdrawn", result=None, odds=2.1),  # retirada sin anunciar
        dict(selection="home", qualifies=False, status="settled", result="win", odds=2.5),  # no pasó el corte
    ]
    for r in rows:
        # Anunciadas: las que pasaron el corte y no se retiraron (lo que la migración rellena con los datos viejos)
        shown = r["qualifies"] and r["status"] != "withdrawn"
        s.add(m.Pick(match_id=mt.id, pick_date=day, stage="pre_lineup", market="ou_goals", line=2.5,
                     bookmaker="bet365", model_prob=0.55, fair_odds=1.8, ev=0.1, confidence=0.8, stake_pct=0.01,
                     created_at=datetime(2026, 10, 20, 14, tzinfo=UTC),
                     announced_at=datetime(2026, 10, 20, 14, tzinfo=UTC) if shown else None,
                     announced_odds=r["odds"] if shown else None, was_pick_of_day=r.get("is_pick_of_day", False), **r))
    s.flush()
    out = picks.qualified_picks(days=10_000)
    rec = out["record"]
    assert (rec["settled"], rec["hits"], rec["misses"], rec["pending"]) == (2, 1, 1, 1)
    assert rec["profit_units"] == pytest.approx(0.0)  # +1 a 2,0 y −1
    assert rec["since"] == "2026-10-20"
    listed = {p["selection"]: p for p in out["picks"]}
    assert set(listed) == {"over", "under", "yes"}
    assert listed["over"]["is_pick_of_day"] and listed["over"]["profit_units"] == 1.0
    assert listed["yes"]["profit_units"] is None


def test_past_day_lists_the_ones_that_passed_first(s):
    mt = match(s, kickoff=datetime.now(UTC) - timedelta(days=3))
    day = picks.today_local() - timedelta(days=3)
    for sel, ev, passed, status, odds in (("a", 0.30, False, "settled", 2.0), ("b", 0.05, True, "settled", 2.0),
                                          ("c", 0.20, True, "withdrawn", 2.0), ("d", 0.08, True, "settled", 2.0),
                                          ("e", 0.01, False, "settled", 1.15)):  # cuota de menos de 1.20: no sale
        s.add(m.Pick(match_id=mt.id, pick_date=day, stage="pre_lineup", market="1x2", selection=sel,
                     bookmaker="bet365", odds=odds, model_prob=0.5, fair_odds=2.0, ev=ev, confidence=0.8,
                     stake_pct=0.01, qualifies=passed, status=status))
    s.flush()
    rows = queries.pick_of_day(day.isoformat())["value_bets"]
    # Pasan el corte (d, b por valor) y después el resto, incluida la retirada aunque pasara el corte
    assert [r["selection"] for r in rows] == ["d", "b", "a", "c"]
    assert rows[0]["qualifies"] is True and rows[2]["qualifies"] is False
    # Probabilidad y confianza guardadas, para poder ordenar por ellas en el panel
    assert rows[0]["prob"] == 0.5 and rows[0]["confidence"] == 0.8


# --------------------------------------------------------------------------- copia fija de lo anunciado


def test_lo_anunciado_no_se_sobrescribe(s):
    mt = match(s)
    day = date(2026, 10, 20)
    p = picks._upsert_pick(s, mt, bet(odds=2.0, ev=0.10, prob=0.55), day, "pre_lineup")
    s.flush()
    assert (p.announced_odds, p.announced_ev, p.announced_prob) == (2.0, 0.10, 0.55) and p.announced_at is not None
    picks._upsert_pick(s, mt, bet(odds=1.8, ev=0.05, prob=0.58), day, "confirmed")  # recálculo
    assert (p.odds, p.announced_odds, p.announced_ev) == (1.8, 2.0, 0.10)


def test_lo_que_no_pasa_el_corte_no_se_anuncia(s):
    p = picks._upsert_pick(s, match(s), bet(confidence=0.4), date(2026, 10, 20), "pre_lineup")
    assert p.announced_at is None and p.announced_odds is None


def test_retirada_que_vuelve_se_reabre_sin_duplicar(s):
    mt = match(s)
    day = date(2026, 10, 20)
    p = picks._upsert_pick(s, mt, bet(), day, "pre_lineup")
    s.flush()
    p.status = "withdrawn"
    s.flush()
    again = picks._upsert_pick(s, mt, bet(odds=2.1), day, "confirmed")
    assert again.id == p.id and again.status == "open"


def test_la_apuesta_del_dia_queda_marcada_aunque_la_cambien(s):
    mt = match(s)
    p = picks._upsert_pick(s, mt, bet(), date(2026, 10, 20), "pre_lineup")
    picks._announce_pod(p)
    p.is_pick_of_day = False  # el recálculo eligió otra
    assert p.was_pick_of_day is True


def test_el_contador_cuenta_la_anunciada_aunque_se_retire(s, monkeypatch):
    monkeypatch.setattr(picks, "fill_missing_clv", lambda _s: 0)
    monkeypatch.setattr(picks, "closing_reference", lambda *a: (1.9, "pinnacle", datetime(2026, 10, 20, 18, tzinfo=UTC)))
    mt = match(s)  # 2-1: Más de 2.5 gana
    p = picks._upsert_pick(s, mt, bet(odds=2.0), date(2026, 10, 20), "pre_lineup")
    picks._announce_pod(p)
    p.is_pick_of_day = True
    s.flush()
    picks._upsert_pick(s, mt, bet(odds=1.7), date(2026, 10, 20), "confirmed")
    p.status, p.is_pick_of_day = "withdrawn", False  # se retiró antes del partido
    s.flush()
    picks.settle_all()
    assert p.result == "win" and p.status == "withdrawn"
    rec = picks.pick_record()
    assert (rec["settled"], rec["hits"], rec["profit_units"]) == (1, 1, 1.0)  # con la cuota anunciada, 2.0
    assert p.clv == pytest.approx(2.0 / 1.9 - 1, abs=1e-4)  # CLV con la cuota anunciada
