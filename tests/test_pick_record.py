"""Contador de aciertos de la apuesta del día desde el inicio."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apuestas.services.picks import record_from


def pick(status, result=None, odds=2.0, created=datetime(2026, 10, 20, 14, tzinfo=UTC), clv=None):
    return SimpleNamespace(status=status, result=result, odds=odds, created_at=created, clv=clv)


def test_empty_record():
    r = record_from([])
    assert r["settled"] == r["hits"] == r["pending"] == 0
    assert r["hit_rate"] is None and r["roi"] is None and r["since"] is None and r["avg_clv"] is None


def test_counts_hits_misses_pushes_and_pending():
    rows = [
        pick("settled", "win", 2.0, datetime(2026, 10, 19, 14, tzinfo=UTC), clv=0.04),
        pick("settled", "half_win", 1.9, clv=-0.02),
        pick("settled", "loss", 2.2),
        pick("settled", "push", 1.8),
        pick("open"),
    ]
    r = record_from(rows)
    assert (r["settled"], r["hits"], r["misses"], r["pushes"], r["pending"]) == (4, 2, 1, 1, 1)
    assert r["hit_rate"] == pytest.approx(2 / 3, abs=1e-3)  # la devuelta no cuenta
    # +1.0 (2.0) +0.45 (medio acierto a 1.9) −1 +0 = 0.45 unidades en 4 apuestas
    assert r["profit_units"] == pytest.approx(0.45) and r["roi"] == pytest.approx(0.1125)
    assert r["since"] == datetime(2026, 10, 19, 14, tzinfo=UTC)
    assert r["avg_clv"] == pytest.approx(0.01) and r["with_clv"] == 2  # solo las que tienen referencia
