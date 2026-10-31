"""La API traduce sus textos al inglés cuando el panel lo pide, sin tocar los valores que el panel usa como clave."""

import pytest
from fastapi.testclient import TestClient

from apuestas.api import i18n
from apuestas.api.app import app
from apuestas.services import analysis, radar


def test_every_market_label_has_its_english_name():
    assert set(i18n.MARKET_EN) == set(analysis.MARKET_LABELS)


@pytest.mark.parametrize(("es", "en"), [
    (analysis.bet_label("ou_corners_home", "over", 4.5, "Arsenal", "Chelsea"), "Corners (Arsenal): Over 4.5"),
    (analysis.bet_label("eh", "draw", 1, "Coventry City", "Leeds"), "Handicap (3-way): Draw (Coventry City +1)"),
    (analysis.bet_label("player_goal", "yes", None, "A", "B", "Kylian Mbappé"), "Player to score — Kylian Mbappé: Yes"),
    (analysis.bet_label("1x2", "away", None, "A", "Real Madrid"), "Match Result: Real Madrid"),
    ("sáb 01/11 12:00", "Sat 01/11 12:00"),
    ("Poco descanso (2.8 días)", "Little rest (2.8 days)"),
    ("Modelo 1% · cuota sin margen 8% · mezcla 2%: Troyes y Le Mans casi sin cuotas de su liga en nuestros datos; "
     "el modelo es poco fiable en este partido",
     "Model 1% · margin-free odds 8% · blend 2%: Troyes and Le Mans with almost no odds from their league in our "
     "data; the model is unreliable in this match"),
    ("aproximado: Tarjetas: Más de 4.5, Córners: Más de 9.5 se combina como si no dependiera del resultado",
     "approximate: Cards: Over 4.5, Corners: Over 9.5 combined as if it did not depend on the result"),
    (radar.NOTE, i18n.EXACT[radar.NOTE]),
])
def test_text_is_translated(es, en):
    assert i18n.text(es) == en


@pytest.mark.parametrize("key", ["APOSTAR", "NO apostar", "valor pequeño o poca confianza", "con valor", "racha",
                                 "baja", "Medianamente fácil", "goles", "muy tarjetero", "Liverpool", "Kylian Mbappé"])
def test_values_the_panel_uses_as_keys_stay(key):
    assert i18n.text(key) == key


def test_only_values_are_translated():
    assert i18n.translate({"Córners": ["Córners", 3, None]}) == {"Córners": ["Corners", 3, None]}


@pytest.mark.parametrize(("header", "detail"), [
    ("en", "Missing the X-API-Key header"),
    ("en-GB,en;q=0.9", "Missing the X-API-Key header"),
    ("es", "Falta la cabecera X-API-Key"),
    (None, "Falta la cabecera X-API-Key"),
])
def test_api_answers_in_the_language_asked(header, detail):
    # Por un túnel la API pide clave: un error que no necesita la BD
    headers = {"X-Forwarded-For": "190.12.3.4", **({"Accept-Language": header} if header else {})}
    r = TestClient(app).get("/status", headers=headers)
    assert r.status_code == 401
    assert r.json() == {"detail": detail}
    assert "Accept-Language" in r.headers["vary"]
