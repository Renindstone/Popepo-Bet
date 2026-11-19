"""Veredicto de los revisores: racha, números fijos, los tres papeles, cuándo se pide y lo que ve cada usuario."""

import json
import math
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.services import verdict

KO = datetime(2026, 11, 3, 20, 0)  # sin zona: SQLite la pierde al leer
HOME, AWAY = 1, 2


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session
            session.flush()

        monkeypatch.setattr(verdict, "session_scope", scope)
        monkeypatch.setattr(verdict, "PARALLEL", 1)  # la sesión de SQLite de las pruebas no se comparte entre hilos
        yield session


def competition(s, code="UCL"):
    comp = s.query(m.Competition).filter_by(code=code).first()
    if comp is None:
        comp = m.Competition(code=code, name=code, country="x", tier="full")
        s.add(comp)
        s.flush()
    season = s.query(m.Season).filter_by(competition_id=comp.id).first()
    if season is None:
        season = m.Season(competition_id=comp.id, start_year=2026, label="2026/2027")
        s.add(season)
        s.flush()
    return comp, season


def team(s, name):
    t = m.Team(name=name)
    s.add(t)
    s.flush()
    return t


def add_match(s, home, away, kickoff, hg=None, ag=None, status="finished"):
    comp, season = competition(s)
    mt = m.Match(competition_id=comp.id, season_id=season.id, kickoff_utc=kickoff, home_team_id=home.id,
                 away_team_id=away.id, status=status, home_goals=hg, away_goals=ag)
    s.add(mt)
    s.flush()
    return mt


def play(s, t, pattern, before=KO):
    """Partidos de `t`, del más reciente al más antiguo: G ganó, E empató, P perdió."""
    rival = team(s, f"Rival de {t.name}")
    for i, r in enumerate(pattern):
        goals = {"G": (2, 0), "E": (1, 1), "P": (0, 1)}[r]
        add_match(s, t, rival, before - timedelta(days=4 * (i + 1)), *goals)


def form(s, pattern):
    t = team(s, f"Equipo {pattern}")
    play(s, t, pattern)
    return verdict.team_form(s, t.id, KO)


def add_pick(s, mt, **kw):
    base = dict(match_id=mt.id, pick_date=KO.date(), stage="confirmed", market="eh", selection="home", line=1.0,
                bookmaker="betano", odds=2.10, model_prob=0.62, fair_odds=1.61, ev=0.045, confidence=0.64,
                stake_pct=0.01, status="open", qualifies=True, is_pick_of_day=True)
    pick = m.Pick(**{**base, **kw})
    s.add(pick)
    s.flush()
    return pick


def villarreal_psg(s):
    villarreal, psg = team(s, "Villarreal"), team(s, "Paris Saint-Germain")
    play(s, psg, "GGGGG")
    play(s, villarreal, "PEGPE")
    return add_pick(s, add_match(s, villarreal, psg, KO, status="scheduled"))


# ------------------------------------------------------------------------- racha

def test_racha_con_tres_seguidas_o_cuatro_de_cinco(s):
    assert form(s, "GGG")["hot"] is True
    assert form(s, "GGEGG")["hot"] is True  # 4 de 5
    assert form(s, "GGEGP")["hot"] is False  # 3 de 5 y solo 2 seguidas
    assert form(s, "GG")["hot"] is False  # pocos partidos


def test_solo_cuentan_partidos_terminados_antes_del_inicio(s):
    t, rival = team(s, "Equipo"), team(s, "Otro")
    add_match(s, t, rival, KO - timedelta(days=3), 2, 0)
    add_match(s, t, rival, KO + timedelta(days=3), 2, 0)  # después
    add_match(s, t, rival, KO - timedelta(days=1), status="scheduled")  # sin jugar
    out = verdict.team_form(s, t.id, KO)
    assert out["played"] == 1 and out["run"] == 1
    assert out["results"][0]["opponent"] == "Otro" and out["results"][0]["score"] == "2-0"
    assert out["results"][0]["won"] is True


def test_la_racha_cuenta_de_visitante(s):
    t, rival = team(s, "Visitante"), team(s, "Local")
    add_match(s, rival, t, KO - timedelta(days=1), 1, 4)
    out = verdict.team_form(s, t.id, KO)
    assert out["wins"] == 1 and out["results"][0]["score"] == "1-4"


@pytest.mark.parametrize("market, selection, expected", [
    ("1x2", "home", {AWAY}), ("1x2", "away", {HOME}), ("1x2", "draw", {HOME, AWAY}),
    ("dc", "1x", {AWAY}), ("dc", "x2", {HOME}), ("dc", "12", set()),
    ("dnb", "home", {AWAY}), ("ah", "away", {HOME}), ("eh", "home", {AWAY}), ("eh", "draw", set()),
    ("ou_goals_home", "under", {HOME}), ("ou_goals_away", "under", {AWAY}), ("ou_goals_home", "over", set()),
    ("ou_goals", "under", set()), ("btts", "no", set()),
])
def test_cuando_va_en_contra(market, selection, expected):
    assert verdict.against(market, selection, HOME, AWAY) == expected


def test_villarreal_mas_uno_contra_el_psg(s):
    pick = villarreal_psg(s)
    assert verdict.streak_warnings(s, pick) == [{"team": "Paris Saint-Germain", "wins": 5, "played": 5, "run": 5}]


def test_a_favor_del_equipo_en_racha_no_avisa(s):
    pick = villarreal_psg(s)
    pick.selection = "away"  # ahora va con el PSG; el Villarreal no viene en racha
    assert verdict.streak_warnings(s, pick) == []


# ------------------------------------------------------------------------- números fijos

def test_historial_de_confianza_usa_lo_anunciado_y_las_medias(s):
    a, b = team(s, "A"), team(s, "B")
    mt = add_match(s, a, b, KO - timedelta(days=9), 1, 0)
    when = datetime(2026, 10, 1, tzinfo=UTC)
    rows = [(0.80, "win", when), (0.90, "half_win", when), (0.85, "loss", when), (0.79, "half_loss", when),
            (0.95, "push", when), (0.95, "win", None), (0.95, None, when)]
    for i, (conf, result, announced) in enumerate(rows):
        add_pick(s, mt, selection=f"s{i}", confidence=conf, result=result, announced_at=announced,
                 is_pick_of_day=False, status="settled")
    assert verdict.confidence_record(s) == {"threshold": 0.8, "high": {"hits": 2, "misses": 1},
                                             "low": {"hits": 0, "misses": 1}}


def test_copia_de_los_numeros(s):
    pick = villarreal_psg(s)
    numbers = verdict.snapshot(s, pick)
    assert numbers["odds"] == 2.10 and numbers["confidence"] == 0.64 and numbers["stage"] == "confirmed"
    assert numbers["implied"] == pytest.approx(1 / 2.10, abs=0.001) and "Villarreal" in numbers["label"]
    assert numbers["streaks"][0]["team"] == "Paris Saint-Germain"


# ------------------------------------------------------------------------- los tres papeles

def review_for(s, pick=None, status="trabajando", **kw):
    if pick is None:
        a, b = team(s, "Local"), team(s, "Visita")
        pick = add_pick(s, add_match(s, a, b, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1), status="scheduled"),
                        pick_date=datetime.now().date())
    review = m.PickReview(pick_id=pick.id, day=pick.pick_date, status=status, attempts=0,
                          numbers=verdict.snapshot(s, pick), **{"stage": pick.stage, **kw})
    s.add(review)
    s.flush()
    return review


def ref(review):
    return f"review:{review.id}"


def fake_claude(monkeypatch, s, on_role=None, skip=(), noes=()):
    """Sustituye la ejecución de Claude: cada revisor escribe su texto y cada agente vota sí (no, si está en `noes`),
    salvo lo que esté en `skip` ("contra", "rachero" o "rachero:2"). Devuelve lo lanzado: "favor", "contra" y
    "agente:ronda"."""
    launched = []

    def ask(papel, review_id, ronda=None):
        seat = papel if ronda is None else f"{papel}:{ronda}"
        launched.append(seat)
        rf = f"review:{review_id}"
        if seat not in skip and papel not in skip:
            if ronda is None:
                verdict.save_side(rf, papel, f"Texto de {papel}", [{"titulo": "Nota", "url": "https://e.com/a"}])
            else:
                verdict.save_vote(rf, seat, papel not in noes, f"Motivo de {papel}", f"Reason of {papel}")
        if on_role:
            on_role(seat)
        return None

    monkeypatch.setattr(verdict, "_ask", ask)
    return launched


def mcp_env(cmd):
    return json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["apuestas"]["env"]


def test_los_agentes_no_tienen_internet_y_votan_en_su_asiento(monkeypatch):
    monkeypatch.setattr(verdict.ai_notes.shutil, "which", lambda _: "/usr/bin/claude")
    cmd, _, _ = verdict.command("cazadora", 2)
    allowed = cmd[cmd.index("--allowedTools") + 1]
    assert cmd[cmd.index("--tools") + 1] == "" and "WebSearch" not in allowed
    assert "mcp__apuestas__guardar_voto" in allowed and "guardar_revisor" not in allowed
    assert cmd[cmd.index("--model") + 1] == "sonnet" and cmd[cmd.index("--effort") + 1] == "medium"
    assert mcp_env(cmd)["APUESTAS_MCP_AGENT"] == "cazadora:2" and mcp_env(cmd)["APUESTAS_MCP_ENGINE"] == "true"
    reviewer, _, _ = verdict.command("favor")
    allowed = reviewer[reviewer.index("--allowedTools") + 1]
    assert reviewer[reviewer.index("--tools") + 1] == "WebSearch,WebFetch" and reviewer[reviewer.index("--effort") + 1] == "high"
    assert "guardar_revisor" in allowed and "guardar_voto" not in allowed and "APUESTAS_MCP_AGENT" not in mcp_env(reviewer)


def test_un_revisor_no_recibe_el_texto_del_otro(s):
    review = review_for(s, favor="razón secreta a favor", contra="razón secreta en contra")
    assert "razón secreta" not in verdict.prompt(review, "contra")
    assert "razón secreta" not in verdict.prompt(review, "favor")
    agent = verdict.prompt(review, "cazadora", 1)
    assert "razón secreta a favor" in agent and "razón secreta en contra" in agent and "La Cazadora de cuotas" in agent


def test_la_ronda_2_ve_la_ronda_1_y_la_1_no(s):
    review = review_for(s, favor="F", contra="C")
    verdict.save_vote(ref(review), "rachero:1", False, "Va contra un equipo en racha.", "x")
    verdict.save_vote(ref(review), "cazadora:1", True, "La cuota paga de más.", "x")
    first = verdict.prompt(review, "precavida", 1)
    assert "Va contra un equipo en racha" not in first and "<ronda_1>" not in first and "80 %" in first
    second = verdict.prompt(review, "precavida", 2)
    assert "- El Rachero: No. Va contra un equipo en racha." in second
    assert "- La Cazadora de cuotas: Sí. La cuota paga de más." in second and "<a_favor>\nF" in second
    own = verdict.prompt(review, "rachero", 2)
    assert "Tu voto en la ronda 1: No. Va contra un equipo en racha." in own and "- El Rachero" not in own


def test_en_paralelo_se_conserva_el_orden(monkeypatch):
    monkeypatch.setattr(verdict, "PARALLEL", 3)
    assert verdict._each(lambda x: x * 2, [1, 2, 3, 4, 5]) == [2, 4, 6, 8, 10]


# ------------------------------------------------------------------------- la mesa: votos, resultado y pesos

def test_un_voto_valido_se_guarda(s):
    review = review_for(s)
    verdict.save_vote(ref(review), "precavida:1", False, " No llega al 80 %. ", "It misses the 80%.")
    vote = review.votes[0]
    assert (vote.agent, vote.round, vote.vote) == ("precavida", 1, False)
    assert vote.text == "No llega al 80 %." and vote.text_en == "It misses the 80%."


@pytest.mark.parametrize("seat, motivo, motivo_en", [
    ("juez:1", "x", "x"), ("precavida:3", "x", "x"), ("precavida", "x", "x"), ("", "x", "x"),
    ("precavida:1", "", "x"), ("precavida:1", "x", " "), ("precavida:1", "x" * 301, "x"),
    ("precavida:1", "Es una Apuesta Segura.", "x"), ("precavida:1", "x", "A sure bet."),
    ("precavida:1", "x", "It is risk-free."), ("precavida:1", "Gana garantizado.", "x"),
])
def test_voto_invalido_se_rechaza(s, seat, motivo, motivo_en):
    review = review_for(s)
    with pytest.raises(ValueError):
        verdict.save_vote(ref(review), seat, True, motivo, motivo_en)
    assert review.votes == []


def test_un_asiento_no_vota_dos_veces(s):
    review = review_for(s)
    verdict.save_vote(ref(review), "rachero:2", True, "a", "a")
    with pytest.raises(ValueError):
        verdict.save_vote(ref(review), "rachero:2", False, "b", "b")
    verdict.save_vote(ref(review), "rachero:1", False, "c", "c")  # otra ronda sí
    assert [(v.round, v.vote) for v in review.votes] == [(2, True), (1, False)]


def test_no_se_vota_en_una_revision_terminada(s):
    review = review_for(s, status="lista")
    with pytest.raises(ValueError):
        verdict.save_vote(ref(review), "rachero:2", True, "a", "a")


def test_un_agente_solo_vota_en_su_asiento(s, monkeypatch):
    from apuestas.mcp_server.server import build

    monkeypatch.setattr(verdict.get_settings(), "mcp_engine", True)
    monkeypatch.setattr(verdict.get_settings(), "mcp_agent", "precavida:1")
    tool = build()._tool_manager.get_tool("guardar_voto")
    assert set(tool.parameters["properties"]) == {"ref", "voto", "motivo", "motivo_en"}  # ni agente ni ronda
    review = review_for(s)
    tool.fn(ref=ref(review), voto=True, motivo="Sí", motivo_en="Yes")
    assert [(v.agent, v.round, v.vote) for v in review.votes] == [("precavida", 1, True)]


def mesa(yes, total):
    return verdict.tally({f"a{i}": i < yes for i in range(total)}, {})


@pytest.mark.parametrize("yes, total, outcome", [
    (5, 7, "aprobado"), (4, 7, "medianamente"), (3, 7, "desaprobado"), (7, 7, "aprobado"), (0, 7, "desaprobado"),
    (4, 5, "aprobado"), (3, 5, "medianamente"), (2, 5, "desaprobado"),
    (4, 6, "aprobado"), (3, 6, "desaprobado"),  # 2/3 justo aprueba; la mitad justa no
])
def test_resultado_segun_los_votos(yes, total, outcome):
    out = mesa(yes, total)
    assert out["outcome"] == outcome and out["yes"] == yes and out["total"] == total


def test_resultado_con_pesos():
    half = verdict.tally({"a": True, "b": False, "c": False}, {"a": 2.0})
    assert half["yes_share"] == 0.5 and half["outcome"] == "desaprobado" and half["yes"] == 1
    two_thirds = verdict.tally({"a": True, "b": True, "c": False}, {"a": 1.5, "b": 0.5})
    assert two_thirds["outcome"] == "aprobado"
    assert verdict.tally({"a": True, "b": True, "c": False, "d": False}, {"a": 2.0})["outcome"] == "medianamente"


_n = iter(range(10_000))


def settled_day(s, votes, result, odds=1.72, days_ago=1):
    """Una apuesta del día contada y liquidada con su revisión lista antes del inicio y los votos finales dados."""
    i = next(_n)
    kickoff = KO - timedelta(days=days_ago)
    mt = add_match(s, team(s, f"Local {i}"), team(s, f"Visita {i}"), kickoff, 1, 0)
    pick = add_pick(s, mt, odds=odds, result=result, status="settled" if result else "open", was_pick_of_day=True,
                    is_pick_of_day=False)
    review = review_for(s, pick, status="lista")
    review.created_at = kickoff - timedelta(hours=1)
    for agent, vote in votes.items():
        review.votes.append(m.ReviewVote(agent=agent, round=2, vote=vote, text="x", text_en="x"))
    s.flush()
    return review


@pytest.mark.parametrize("vote, result, odds, expected", [
    (True, "win", 1.72, 1.036), (True, "loss", 1.72, 0.95), (False, "loss", 1.72, 1.05), (False, "win", 1.72, 0.964),
    (True, "half_win", 2.0, 1.025), (True, "half_loss", 2.0, 0.975), (True, "push", 1.72, 1.0),
    (False, "void", 1.72, 1.0),
])
def test_peso_tras_una_apuesta(s, vote, result, odds, expected):
    settled_day(s, {"cazadora": vote}, result, odds)
    w = verdict.weights(s)
    assert w["cazadora"] == pytest.approx(expected) and w["precavida"] == 1.0 and set(w) == set(verdict.AGENTS)


def test_pesos_con_tope_y_piso(s):
    for d in range(30):
        settled_day(s, {"rachero": True}, "loss", days_ago=100 - d)
        settled_day(s, {"contraria": True}, "win", odds=2.0, days_ago=100 - d)
    assert verdict.weights(s)["rachero"] == pytest.approx(0.5)
    assert verdict.weights(s)["contraria"] == pytest.approx(2.0)
    settled_day(s, {"rachero": True}, "win", odds=2.0, days_ago=10)
    assert verdict.weights(s)["rachero"] == pytest.approx(0.55)


def test_pesos_ignoran_lo_que_no_cuenta(s):
    late = settled_day(s, {"reportero": True}, "loss", days_ago=3)
    late.created_at = late.pick.match.kickoff_utc + timedelta(minutes=5)  # revisada después del inicio
    settled_day(s, {"reportero": True}, "loss", days_ago=4).pick.was_pick_of_day = False  # no contada
    settled_day(s, {"reportero": True}, None, days_ago=5)  # sin resultado
    first_round = settled_day(s, {}, "loss", days_ago=6)
    first_round.votes.append(m.ReviewVote(agent="reportero", round=1, vote=True, text="x", text_en="x"))
    s.flush()
    assert verdict.weights(s)["reportero"] == 1.0
    first = settled_day(s, {"reportero": True}, "loss", days_ago=2)
    second = review_for(s, first.pick, status="lista")  # la última antes del inicio es la que cuenta
    second.created_at = first.created_at + timedelta(minutes=10)
    second.votes.append(m.ReviewVote(agent="reportero", round=2, vote=False, text="x", text_en="x"))
    s.flush()
    assert verdict.weights(s)["reportero"] == pytest.approx(1.05)


def test_fuente_con_enlace_peligroso_se_rechaza(s):
    review = review_for(s)
    with pytest.raises(ValueError):
        verdict.save_side(ref(review), "favor", "texto", [{"titulo": "x", "url": "javascript:alert(1)"}])
    assert review.favor is None


def test_revisor_no_puede_prometer(s):
    review = review_for(s)
    with pytest.raises(ValueError):
        verdict.save_side(ref(review), "contra", "Esto es una apuesta segura.", [])


def test_no_se_guarda_en_una_revision_terminada(s):
    review = review_for(s, status="lista")
    with pytest.raises(ValueError):
        verdict.save_side(ref(review), "favor", "texto", [])


def test_la_mesa_completa_deja_la_revision_lista(s, monkeypatch):
    launched = fake_claude(monkeypatch, s, noes=("precavida",))
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert launched == ["favor", "contra", *(f"{a}:{r}" for r in (1, 2) for a in verdict.AGENTS)]
    assert review.status == "lista" and len(review.votes) == 14 and review.favor == "Texto de favor"
    assert review.favor_sources == [{"title": "Nota", "url": "https://e.com/a"}] and review.model == "sonnet"


def test_si_cambia_la_apuesta_entre_rondas_se_descarta(s, monkeypatch):
    review = review_for(s, status="pendiente")

    def replaced(seat):
        if seat == "contraria:1":  # el último de la ronda 1
            review.pick.is_pick_of_day = False

    launched = fake_claude(monkeypatch, s, on_role=replaced)
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "descartada" and not any(x.endswith(":2") for x in launched)


def test_si_empieza_el_partido_no_se_revisa(s, monkeypatch):
    launched = fake_claude(monkeypatch, s)
    a, b = team(s, "Local"), team(s, "Visita")
    pick = add_pick(s, add_match(s, a, b, datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1), status="scheduled"))
    review = review_for(s, pick, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "descartada" and launched == []


def test_si_falta_un_revisor_no_hay_veredicto_y_se_reintenta_una_vez(s, monkeypatch):
    launched = fake_claude(monkeypatch, s, skip=("contra",))
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "pendiente" and review.votes == [] and review.attempts == 1
    assert not any(":" in x for x in launched)  # sin noticias de los dos lados, la mesa no vota
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "error" and review.attempts == 2 and "contra" in review.error


def test_si_falta_un_voto_se_reintenta_solo_ese_agente(s, monkeypatch):
    fake_claude(monkeypatch, s, skip=("rachero:2",))
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "pendiente" and review.attempts == 1 and "rachero" in review.error
    launched = fake_claude(monkeypatch, s)
    verdict.run(review.id)
    s.refresh(review)
    assert launched == ["rachero:2"] and review.status == "lista" and len(review.votes) == 14


def test_el_reintento_no_repite_lo_ya_guardado(s, monkeypatch):
    launched = fake_claude(monkeypatch, s)
    review = review_for(s, status="pendiente", favor="Ya escrito", favor_sources=[])
    verdict.run(review.id)
    assert launched[0] == "contra" and "favor" not in launched


def test_un_fallo_de_claude_no_lanza_y_se_reintenta(s, monkeypatch):
    def boom(papel, review_id, ronda=None):
        raise RuntimeError("No encuentro el CLI")

    monkeypatch.setattr(verdict, "_ask", boom)
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "pendiente" and "No encuentro el CLI" in review.error


def test_datos_del_handicap_europeo_explican_el_empate(s):
    review = review_for(s, villarreal_psg(s))
    data = verdict.review_data(ref(review))
    assert "pierde" in data["como_se_liquida"] and data["numbers"]["odds"] == 2.10
    assert data["visitante"]["forma"]["hot"] is True and data["visitante"]["bajas"] == []
    assert data["otras_casas"] == {"bet365": None, "pinnacle_justa": None}


def test_datos_con_referencia_mala(s):
    with pytest.raises(ValueError):
        verdict.review_data("pick:1")


def test_herramientas_del_motor(monkeypatch):
    from apuestas.config import get_settings
    from apuestas.mcp_server.server import build

    def tools():
        return {t.name for t in build()._tool_manager.list_tools()}

    assert "datos_veredicto" in tools() and not {"guardar_revisor", "guardar_voto"} & tools()
    monkeypatch.setattr(get_settings(), "mcp_engine", True)
    assert {"datos_veredicto", "guardar_revisor", "guardar_voto"} <= tools()
    assert "registrar_apuesta" not in tools() and "guardar_veredicto" not in tools()


def test_datos_traen_otras_casas(s):
    pick = add_pick(s, add_match(s, team(s, "Local OC"), team(s, "Visita OC"), KO, status="scheduled"),
                    market="ou_goals", selection="over", line=2.5)
    t = datetime(2026, 11, 2, 10, 0)
    rows = [("bet365", "over", 1.90, t), ("bet365", "over", 2.05, t + timedelta(hours=1)), ("bet365", "under", 1.80, t),
            ("pinnacle", "over", 1.95, t), ("pinnacle", "under", 1.95, t)]
    for i, (book, selection, price, when) in enumerate(rows, 1):  # BigInteger: SQLite no lo numera solo
        s.add(m.OddsSnapshot(id=i, match_id=pick.match_id, bookmaker=book, market="ou_goals", selection=selection,
                             line=2.5, price=price, source="prueba", captured_at=when))
    s.flush()
    assert verdict.review_data(ref(review_for(s, pick)))["otras_casas"] == {"bet365": 2.05, "pinnacle_justa": 2.0}


# ------------------------------------------------------------------------- cuándo se pide

def today_pick(s, stage="confirmed", minutes=60, **kw):
    a, b = team(s, f"Local {stage} {minutes}"), team(s, f"Visita {stage} {minutes}")
    kickoff = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=minutes)
    return add_pick(s, add_match(s, a, b, kickoff, status="scheduled"), stage=stage,
                    pick_date=verdict.picks.today_local(), **kw)


def due(s):
    return verdict.request_due(s, datetime.now(UTC))


def test_con_alineacion_confirmada_se_pide(s):
    pick = today_pick(s)
    review = due(s)
    assert review.pick_id == pick.id and review.status == "pendiente" and review.stage == "confirmed"
    assert review.numbers["odds"] == pick.odds


def test_prevista_a_mas_de_40_minutos_espera(s):
    today_pick(s, stage="predicted", minutes=41)
    assert due(s) is None


def test_prevista_a_40_minutos_se_pide(s):
    today_pick(s, stage="predicted", minutes=40)
    assert due(s).stage == "predicted"


def test_la_revision_guarda_los_pesos_al_crearse(s):
    settled_day(s, {"cazadora": True}, "loss")
    today_pick(s)
    assert due(s).weights == {**dict.fromkeys(verdict.AGENTS, 1.0), "cazadora": 0.95}


def test_empezado_no_se_pide(s):
    today_pick(s, minutes=-1)
    assert due(s) is None


def test_apuesta_de_otro_dia_no_se_pide(s):
    pick = today_pick(s)
    pick.pick_date += timedelta(days=1)
    assert due(s) is None


def test_si_ya_no_es_la_apuesta_del_dia_no_se_pide(s):
    today_pick(s, is_pick_of_day=False)
    assert due(s) is None


def test_con_la_ia_apagada_no_se_pide(s, monkeypatch):
    today_pick(s)
    monkeypatch.setattr(verdict.ai_notes, "auto_enabled", lambda _: False)
    assert due(s) is None


def test_no_se_duplica_con_la_misma_alineacion(s):
    today_pick(s)
    due(s).status = "lista"
    assert due(s) is None


def test_una_revision_en_error_no_se_pide_otra_vez(s):
    today_pick(s)
    due(s).status = "error"
    assert due(s) is None


def test_de_prevista_a_confirmada_se_revisa_otra_vez(s):
    pick = today_pick(s, stage="predicted", minutes=20)
    due(s).status = "lista"
    assert due(s) is None
    pick.stage = "confirmed"
    assert due(s).stage == "confirmed"


def test_sin_confirmar_no_se_repite_si_cambia_a_otro_estado_sin_once(s):
    pick = today_pick(s, stage="injuries_only", minutes=20)
    due(s).status = "lista"
    pick.stage = "predicted"
    assert due(s) is None


def test_si_la_apuesta_vuelve_se_reutiliza_el_veredicto(s):
    a = today_pick(s)
    due(s).status = "lista"
    a.is_pick_of_day = False
    b = today_pick(s, minutes=90)
    due(s).status = "lista"
    b.is_pick_of_day = False
    a.is_pick_of_day = True
    assert due(s) is None


def test_una_descartada_se_puede_pedir_otra_vez(s):
    today_pick(s)
    due(s).status = "descartada"
    assert due(s) is not None


def test_maximo_dos_revisiones_al_dia(s):
    for minutes in (60, 70):
        pick = today_pick(s, minutes=minutes)
        due(s).status = "lista"
        pick.is_pick_of_day = False
    today_pick(s, minutes=90)
    assert due(s) is None


def test_reinicio_a_mitad_vuelve_a_pendiente(s):
    review = review_for(s)
    review.attempts = 1
    now = datetime.now(UTC)
    steps = len(verdict.SIDES) + len(verdict.ROUNDS) * math.ceil(len(verdict.AGENTS) / verdict.PARALLEL)
    limit = steps * verdict.get_settings().ai_notes_timeout_s + verdict.ai_notes.STUCK_MARGIN_S
    review.updated_at = now - timedelta(seconds=limit - 5)
    assert verdict.rescue_stuck(now) == 0
    review.updated_at = now - timedelta(seconds=limit + 5)
    assert verdict.rescue_stuck(now) == 1 and review.status == "pendiente"


def test_reinicio_con_los_intentos_gastados_queda_en_error(s):
    review = review_for(s)
    review.attempts = 2
    now = datetime.now(UTC)
    review.updated_at = now - timedelta(days=1)
    assert verdict.rescue_stuck(now) == 1 and review.status == "error"


def test_sin_el_cli_de_claude_queda_en_error_sin_romper(s, monkeypatch):
    monkeypatch.setattr(verdict.get_settings(), "claude_bin", "no-existe-claude")
    today_pick(s)
    assert verdict.process_due(datetime.now(UTC)) == 1
    review = s.query(m.PickReview).one()
    s.refresh(review)
    assert review.status == "pendiente"
    verdict.process_due(datetime.now(UTC))
    s.refresh(review)
    assert review.status == "error" and "No encuentro el CLI de Claude Code" in review.error


def test_una_tarea_completa_escribe_la_revision(s, monkeypatch):
    fake_claude(monkeypatch, s)
    today_pick(s)
    assert verdict.process_due(datetime.now(UTC)) == 1
    review = s.query(m.PickReview).one()
    s.refresh(review)
    assert review.status == "lista" and verdict.process_due(datetime.now(UTC)) == 0


# ------------------------------------------------------------------------- lo que ve cada usuario

OWNER = "renzo"


def view(pick, user=OWNER):
    return verdict.for_user(pick.id, user)


def ready_review(s, pick, numbers=None, noes=(), **kw):
    """Revisión lista con los 7 votos de cada ronda: sí, salvo los agentes de `noes`."""
    review = review_for(s, pick, status="lista", favor="A favor", favor_sources=[], contra="En contra",
                        contra_sources=[{"title": "Nota", "url": "https://e.com/a"}], **kw)
    for rnd in verdict.ROUNDS:
        for agent in verdict.AGENTS:
            review.votes.append(m.ReviewVote(agent=agent, round=rnd, vote=agent not in noes, text=f"{agent} {rnd}",
                                             text_en=f"{agent} en {rnd}"))
    if numbers:
        review.numbers = {**review.numbers, **numbers}
    s.flush()
    return review


def test_con_la_ia_apagada_no_sale_nada(s):
    s.add(m.User(username="sin_ia", ai_enabled=False))
    pick = today_pick(s)
    ready_review(s, pick)
    assert view(pick, "sin_ia") is None


def test_dia_futuro_no_sale_nada(s):
    pick = today_pick(s)
    pick.pick_date += timedelta(days=1)
    assert view(pick) is None


def test_hoy_sin_revision_espera(s):
    assert view(today_pick(s))["status"] == "espera"


def test_dia_pasado_sin_revision_no_sale_nada(s):
    pick = today_pick(s, minutes=-600)
    pick.pick_date -= timedelta(days=1)
    assert view(pick) is None


def test_hoy_en_marcha_y_en_error(s):
    pick = today_pick(s)
    review = review_for(s, pick)
    assert view(pick)["status"] == "trabajando"
    review.status, review.error = "error", "Claude tardó demasiado"
    out = view(pick)
    assert out["status"] == "error" and out["error"] == "Claude tardó demasiado" and out["outcome"] is None


def test_veredicto_listo_trae_sus_partes(s):
    pick = today_pick(s)
    ready_review(s, pick, noes=("precavida", "desconfiado", "rachero"), weights={"precavida": 2.0})
    out = view(pick)
    # 4 sí que valen 4 contra 3 no que valen 4 (la Precavida cuenta doble): la mitad justa no aprueba
    assert out["status"] == "lista" and out["outcome"] == "desaprobado" and out["threshold"] == 0.8
    assert out["yes"] == 4 and out["total"] == 7 and out["yes_share"] == 0.5
    assert out["votes"][0] == {"agent": "precavida", "name": "La Precavida", "name_en": "The Cautious One",
                               "vote": False, "text": "precavida 2", "text_en": "precavida en 2", "weight": 2.0,
                               "changed": False}
    assert [v["agent"] for v in out["votes"]] == list(verdict.AGENTS) and out["votes"][1]["weight"] == 1.0
    assert len(out["round1"]) == 7 and out["round1"][0]["text"] == "precavida 1"
    assert out["debate"]["contra"]["sources"][0]["url"] == "https://e.com/a"
    assert out["record"]["high"] == {"hits": 0, "misses": 0} and out["streaks"] == []
    assert out["numbers_changed"] is False and out["updating"] is False


def test_cambio_de_opinion(s):
    pick = today_pick(s)
    review = ready_review(s, pick)
    next(v for v in review.votes if v.agent == "rachero" and v.round == 1).vote = False
    changed = {v["agent"]: v["changed"] for v in view(pick)["votes"]}
    assert changed["rachero"] is True and not any(c for a, c in changed.items() if a != "rachero")


def test_hoy_la_confianza_es_la_actual_y_avisa_si_cruza_el_80(s):
    pick = today_pick(s, confidence=0.83)
    ready_review(s, pick, numbers={"confidence": 0.78})
    out = view(pick)
    assert out["confidence"] == 0.83 and out["numbers_changed"] is True


def test_sin_cruzar_el_80_no_avisa(s):
    pick = today_pick(s, confidence=0.70)
    ready_review(s, pick, numbers={"confidence": 0.78})
    assert view(pick)["numbers_changed"] is False


@pytest.mark.parametrize("odds, changed", [(2.09, False), (2.11, True), (1.89, True)])
def test_cuota_movida_mas_de_5_por_ciento_avisa(s, odds, changed):
    pick = today_pick(s, odds=odds, confidence=0.70)
    ready_review(s, pick, numbers={"odds": 2.00, "confidence": 0.70})
    assert view(pick)["numbers_changed"] is changed


def test_dia_pasado_usa_la_copia(s):
    pick = today_pick(s, minutes=-600, confidence=0.90)
    pick.pick_date -= timedelta(days=1)
    ready_review(s, pick, numbers={"confidence": 0.64})
    out = view(pick)
    assert out["confidence"] == 0.64 and out["numbers_changed"] is False


def test_veredicto_anterior_se_mantiene_si_la_nueva_falla_o_esta_en_marcha(s):
    pick = today_pick(s)
    ready_review(s, pick)
    newer = review_for(s, pick)
    out = view(pick)
    assert out["outcome"] == "aprobado" and out["updating"] is True
    newer.status = "error"
    out = view(pick)
    assert out["outcome"] == "aprobado" and out["status"] == "lista" and out["updating"] is False


def test_no_se_ensena_el_veredicto_de_otra_apuesta(s):
    ready_review(s, today_pick(s))
    assert view(today_pick(s, minutes=90))["status"] == "espera"


def test_descartada_no_se_ensena(s):
    pick = today_pick(s)
    ready_review(s, pick).status = "descartada"
    assert view(pick)["status"] == "espera"


def test_apuesta_que_no_existe(s):
    with pytest.raises(verdict.queries.NotFound):
        verdict.for_user(999, OWNER)


# ------------------------------------------------------------------------- medición

def with_votes(review, yes):
    """Los 7 votos finales: sí los `yes` primeros agentes."""
    for i, agent in enumerate(verdict.AGENTS):
        review.votes.append(m.ReviewVote(agent=agent, round=2, vote=i < yes, text="x", text_en="x"))
    return review


def test_medicion_cuenta_la_ultima_valida_antes_del_inicio_y_una_por_dia(s):
    a, b = team(s, "A"), team(s, "B")
    counted = add_pick(s, add_match(s, a, b, KO, 0, 1), was_pick_of_day=True, status="settled", result="loss")
    with_votes(review_for(s, counted, status="lista", stage="predicted"), 5).created_at = KO - timedelta(hours=3)
    with_votes(review_for(s, counted, status="lista"), 2).created_at = KO - timedelta(hours=1)  # la que cuenta
    with_votes(review_for(s, counted, status="lista"), 5).created_at = KO + timedelta(minutes=5)  # después: no
    review_for(s, counted, status="error").created_at = KO - timedelta(minutes=30)
    replaced = add_pick(s, add_match(s, a, b, KO + timedelta(hours=2), 2, 0), selection="away", status="settled",
                        result="win")
    with_votes(review_for(s, replaced, status="lista"), 4).created_at = KO
    s.flush()
    out = verdict.measure(s)
    assert out["contados"]["desaprobado"]["misses"] == 1 and set(out["contados"]) == {"desaprobado"}
    assert out["todos"]["medianamente"]["hits"] == 1 and out["todos"]["desaprobado"]["misses"] == 1
    assert out["pesos"]["contraria"] == pytest.approx(1.05) and out["pesos"]["precavida"] == pytest.approx(0.95)


# ------------------------------------------------------------------------- correcciones del revisor final

def test_un_revisor_que_escribe_la_parte_del_otro_falla(s, monkeypatch):
    def ask(papel, review_id, ronda=None):
        rf = f"review:{review_id}"
        verdict.save_side(rf, "favor", "A favor", [])
        verdict.save_side(rf, "contra", "Escrito por el revisor a favor", [])  # una página se lo pidió
        return None

    monkeypatch.setattr(verdict, "_ask", ask)
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "pendiente" and review.contra is None and review.votes == []
    assert "contra" in review.error


def test_el_tope_cuenta_las_descartadas_que_gastaron(s):
    for minutes in (60, 70):
        pick = today_pick(s, minutes=minutes)
        review = due(s)
        review.status, review.attempts = "descartada", 1
        pick.is_pick_of_day = False
    today_pick(s, minutes=90)
    assert due(s) is None


def test_al_arrancar_el_worker_las_que_trabajaban_vuelven_a_pendiente(s):
    review = review_for(s)
    review.attempts, review.updated_at = 1, datetime.now(UTC)
    assert verdict.reset_running() == 1 and review.status == "pendiente"


def test_con_la_ia_apagada_no_se_reintenta(s, monkeypatch):
    launched = fake_claude(monkeypatch, s)
    review_for(s, status="pendiente")
    monkeypatch.setattr(verdict.ai_notes, "auto_enabled", lambda _: False)
    assert verdict.process_pending() == 0 and launched == []
