"""Banca inicial editable y banca actual (inicial + lo ganado o perdido)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import queries, tracker


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_current_bankroll_adds_all_settled_profit(s):
    user = m.User(username="ana", bankroll=500.0, currency="PEN")
    s.add(user)
    s.flush()
    old = datetime.now(UTC) - timedelta(days=30)  # fuera de la semana: solo cuenta para la banca actual
    for profit in (15.0, -10.0, None):  # la última sigue pendiente
        s.add(m.UserBet(user_id=user.id, match_id=1, placed_at=old, bookmaker="betano", market="1x2",
                        selection="home", odds=2.5, stake=10.0, profit=profit, result=None if profit is None else "x"))
    s.flush()
    b = tracker.bankroll_status(s, user)
    assert b["bankroll"] == 500.0 and b["total_profit"] == 5.0 and b["current"] == 505.0
    assert b["pending_bets"] == 1


@pytest.mark.parametrize("amount, currency", [(0, "PEN"), (-50, "PEN"), (100, "BTC")])
def test_set_bankroll_rejects_bad_values(amount, currency):
    with pytest.raises(ValueError):
        queries.set_bankroll("ana", amount, currency)
