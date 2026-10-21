"""Motor local de capturas: reglas que pasan la transcripción de la IA a mercados, plan y resumen por plantilla.

Las transcripciones son las que devolvió qwen2.5vl:7b con dos capturas reales de Betano y bet365.
"""

import pytest

from apuestas.services import capture_reader as cr

MATCHES = {
    "lille": (4815, "Lille", "Galatasaray"),
    "galatasaray": (4815, "Lille", "Galatasaray"),
    "betis": (4820, "Real Betis", "Feyenoord"),
    "feyenoord": (4820, "Real Betis", "Feyenoord"),
    "bayern": (4817, "Bayern München", "Arsenal"),
    "madrid": (4821, "Real Madrid", "RB Leipzig"),
    "como": (4814, "Como", "Manchester United"),
}


def resolve(text):
    t = text.lower()
    return next((v for k, v in MATCHES.items() if k in t), None)


@pytest.mark.parametrize(("title", "selection", "home", "away", "expected"), [
    # Betano, doble con Bet Builder (captura 10)
    ("Menos 1.5", "Lille OSC - Goles totales Más/Menos", "Lille", "Galatasaray", ("ou_goals_home", "under", 1.5, None)),
    ("Hándicap", "Galatasaray SK +1", "Lille", "Galatasaray", ("eh", "away", -1.0, None)),
    ("Hándicap", "Feyenoord Rotterdam +2", "Real Betis", "Feyenoord", ("eh", "away", -2.0, None)),
    # bet365, combinada de 4 (captura 7): a veces título y selección vienen cambiados
    ("Empate o Arsenal", "Doble oportunidad", "Bayern München", "Arsenal", ("dc", "x2", None, None)),
    ("Harry Kane anotará o asistirá", "Jugador - Anotará o conseguirá una asistencia", "Bayern München", "Arsenal",
     ("player_goal_assist", "yes", None, "Harry Kane")),
    ("Resultado final: Real Madrid", "Resultado final", "Real Madrid", "RB Leipzig", ("1x2", "home", None, None)),
    ("Kylian Mbappe - Anotará", "Anotará en cualquier momento", "Real Madrid", "RB Leipzig",
     ("player_goal", "yes", None, "Kylian Mbappe")),
    ("Como o Empate", "Doble oportunidad", "Como", "Manchester United", ("dc", "1x", None, None)),
    ("Resultado final", "Real Betis", "Real Betis", "Feyenoord", ("1x2", "home", None, None)),
    # otros mercados habituales
    ("Total de goles", "Más de 2.5", "Real Madrid", "RB Leipzig", ("ou_goals", "over", 2.5, None)),
    ("Ambos equipos marcan", "No", "Real Madrid", "RB Leipzig", ("btts", "no", None, None)),
    ("Total de córners", "Más de 9.5", "Como", "Manchester United", ("ou_corners", "over", 9.5, None)),
    ("Resultado final", "Empate", "Como", "Manchester United", ("1x2", "draw", None, None)),
    ("Hándicap asiático", "Arsenal -0.75", "Bayern München", "Arsenal", ("ah", "away", -0.75, None)),
    ("Kane 2 o más goles", "Anotará", "Bayern München", "Arsenal", ("player_goal", "over", 1.5, "Kane")),
    ("Safonov", "3+ atajadas", "PSG", "Barcelona", ("otro", "", None, None)),
])
def test_parse_selection(title, selection, home, away, expected):
    got = cr.parse_selection(title, selection, home, away)
    assert (got["mercado"], got["seleccion"], got["linea"], got["jugador"]) == expected


def test_plan_betano_double_with_bet_builder():
    tr = {"partidos": [
        {"partido": "Lille OSC vs Galatasaray SK", "cuota_bet_builder": 2.27, "selecciones": [
            {"mercado": "Menos 1.5", "seleccion": "Lille OSC - Goles totales Más/Menos", "cuota": None},
            {"mercado": "Hándicap", "seleccion": "Galatasaray SK +1", "cuota": None}]},
        {"partido": "Feyenoord Rotterdam vs Real Betis Balompié", "cuota_bet_builder": 1.6, "selecciones": [
            {"mercado": "Hándicap", "seleccion": "Feyenoord Rotterdam +2", "cuota": None}]}],
        "cuota_total": 3.63, "importe": None}
    p = cr.plan(tr, resolve)
    assert p["tipo"] == "combinada" and p["cuota_total"] == 3.63
    assert [b["partido"] for b in p["bloques"]] == ["4815", "4820"]
    assert [b["cuota"] for b in p["bloques"]] == [2.27, 1.6]


def test_plan_fixes_a_total_odds_smaller_than_one_block():
    # bet365: la IA leyó 4.30 (la del primer bloque) como total; con 4 partidos la total es el producto
    tr = {"partidos": [
        {"partido": "Bayern München vs Arsenal", "cuota_bet_builder": 4.3, "selecciones": [
            {"mercado": "Empate o Arsenal", "seleccion": "Doble oportunidad", "cuota": None}]},
        {"partido": "Real Madrid vs RB Leipzig", "cuota_bet_builder": 1.43, "selecciones": [
            {"mercado": "Resultado final", "seleccion": "Real Madrid", "cuota": None}]},
        {"partido": "Como vs Man Utd", "cuota_bet_builder": 1.35, "selecciones": [
            {"mercado": "Como o Empate", "seleccion": "Doble oportunidad", "cuota": None}]},
        {"partido": "Real Betis vs Feyenoord", "cuota_bet_builder": 1.52, "selecciones": [
            {"mercado": "Resultado final", "seleccion": "Real Betis", "cuota": None}]}],
        "cuota_total": 4.3, "importe": 15.0}
    p = cr.plan(tr, resolve)
    assert p["cuota_total"] == pytest.approx(12.62) and p["importe"] == 15.0


def test_plan_single_odds_and_nothing():
    tr = {"partidos": [{"partido": "Real Madrid - RB Leipzig", "cuota_bet_builder": None, "selecciones": [
        {"mercado": "Resultado final", "seleccion": "Real Madrid", "cuota": 1.4},
        {"mercado": "Total de goles", "seleccion": "Más de 2.5", "cuota": 1.62}]}], "cuota_total": None, "importe": 10}
    p = cr.plan(tr, resolve)
    assert p["tipo"] == "cuotas" and p["partido"] == "4821" and len(p["lineas"]) == 2
    assert p["lineas"][1]["mercado"] == "ou_goals" and p["lineas"][1]["cuota"] == 1.62
    assert cr.plan({"partidos": []}, resolve)["tipo"] == "nada"
    missing = {"partidos": [{"partido": "Equipo X vs Equipo Y", "cuota_bet_builder": None,
                             "selecciones": [{"mercado": "1X2", "seleccion": "Equipo X", "cuota": 2.0}]}]}
    assert cr.plan(missing, resolve)["tipo"] == "nada"


def test_summaries_only_use_the_models_numbers():
    combo = {"bloques": [
        {"partido": "Lille vs Galatasaray", "selecciones": ["Goles (Lille): Menos de 1.5", "Hándicap: Galatasaray +1"],
         "cuota": 2.27, "prob_modelo": "55.6%", "valor_esperado": "+26.2%"},
        {"partido": "PSG vs Barcelona", "selecciones": ["Safonov 3+ atajadas"], "cuota": 2.0,
         "no_evaluable": "fuera del modelo: Safonov 3+ atajadas"}],
        "total": {"cuota": 4.54, "prob_modelo": None, "veredicto": "no evaluable"}}
    text = cr.summary_combo(combo)
    assert "no se puede evaluar entera" in text and "55.6%" in text and "fuera del modelo" in text
    lines = {"partido": "Real Madrid vs RB Leipzig", "alineaciones": "predicted", "lineas": [
        {"apuesta": "Resultado: Real Madrid", "cuota": 1.4, "prob_modelo": "73.3%", "valor_esperado": "+2.6%",
         "veredicto": "valor pequeño o poca confianza"},
        {"apuesta": "Goles: Más de 2.5", "cuota": 1.62, "prob_modelo": "58.0%", "valor_esperado": "-6.0%",
         "veredicto": "NO apostar"}]}
    text = cr.summary_lines(lines)
    assert "valor pequeño" in text and "+2.6%" in text and "previstas" in text
