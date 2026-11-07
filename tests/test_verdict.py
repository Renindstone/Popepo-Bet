"""Veredicto de los revisores: racha, números fijos, los tres papeles, cuándo se pide y lo que ve cada usuario."""

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

MOTIVOS_OK = [{"etiqueta": "Riesgo", "texto": "Si gana por un gol, se pierde."},
              {"etiqueta": "Noticias", "texto": "Vuelve su delantero."}]


def review_for(s, pick=None, status="trabajando", **kw):
    if pick is None:
        a, b = team(s, "Local"), team(s, "Visita")
        pick = add_pick(s, add_match(s, a, b, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1), status="scheduled"),
                        pick_date=datetime.now().date())
    review = m.PickReview(pick_id=pick.id, day=pick.pick_date, status=status, attempts=0, stage=pick.stage,
                          numbers=verdict.snapshot(s, pick), **kw)
    s.add(review)
    s.flush()
    return review


def ref(review):
    return f"review:{review.id}"


def fake_claude(monkeypatch, s, on_role=None, skip=()):
    """Sustituye la ejecución de Claude: cada papel guarda lo suyo salvo los de `skip`. Devuelve los papeles lanzados."""
    launched = []

    def ask(papel, review_id):
        launched.append(papel)
        rf = f"review:{review_id}"
        if papel not in skip:
            if papel == "juez":
                verdict.save_verdict(rf, "Dudosa", MOTIVOS_OK)
            else:
                verdict.save_side(rf, papel, f"Texto de {papel}", [{"titulo": "Nota", "url": "https://e.com/a"}])
        if on_role:
            on_role(papel)
        return None

    monkeypatch.setattr(verdict, "_ask", ask)
    return launched


def test_el_juez_no_tiene_internet_y_los_revisores_si(monkeypatch):
    monkeypatch.setattr(verdict.ai_notes.shutil, "which", lambda _: "/usr/bin/claude")
    cmd, _, _ = verdict.command("juez")
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "WebSearch" not in cmd[cmd.index("--allowedTools") + 1]
    assert "mcp__apuestas__guardar_veredicto" in cmd[cmd.index("--allowedTools") + 1]
    assert cmd[cmd.index("--model") + 1] == "sonnet" and cmd[cmd.index("--effort") + 1] == "high"
    reviewer, _, _ = verdict.command("favor")
    assert reviewer[reviewer.index("--tools") + 1] == "WebSearch,WebFetch"
    assert "guardar_veredicto" not in reviewer[reviewer.index("--allowedTools") + 1]
    assert "guardar_revisor" in reviewer[reviewer.index("--allowedTools") + 1]


def test_un_revisor_no_recibe_el_texto_del_otro(s):
    review = review_for(s, favor="razón secreta a favor", contra="razón secreta en contra")
    assert "razón secreta" not in verdict.prompt(review, "contra")
    assert "razón secreta" not in verdict.prompt(review, "favor")
    juez = verdict.prompt(review, "juez")
    assert "razón secreta a favor" in juez and "razón secreta en contra" in juez


@pytest.mark.parametrize("palabra, motivos", [
    ("Quizás", MOTIVOS_OK), ("Apostar", []), ("Apostar", MOTIVOS_OK[:1]), ("Apostar", MOTIVOS_OK * 3),
    ("Apostar", [{"etiqueta": "Confianza", "texto": "x"}, {"etiqueta": "Riesgo", "texto": "y"}]),
    ("Apostar", [{"etiqueta": "racha", "texto": "x"}, {"etiqueta": "Riesgo", "texto": "y"}]),
    ("Apostar", [{"etiqueta": "Riesgo", "texto": "es una Apuesta Segura"}, {"etiqueta": "Noticias", "texto": "y"}]),
    ("Dudosa", [{"etiqueta": "Riesgo", "texto": "sin riesgo"}, {"etiqueta": "Noticias", "texto": "y"}]),
    ("Dudosa", [{"etiqueta": "Riesgo", "texto": "gana garantizado"}, {"etiqueta": "Noticias", "texto": "y"}]),
    ("Dudosa", [{"etiqueta": "Riesgo", "texto": "x" * 201}, {"etiqueta": "Noticias", "texto": "y"}]),
    ("Dudosa", [{"etiqueta": "x" * 21, "texto": "x"}, {"etiqueta": "Noticias", "texto": "y"}]),
])
def test_veredicto_invalido_se_rechaza(s, palabra, motivos):
    review = review_for(s)
    with pytest.raises(ValueError):
        verdict.save_verdict(ref(review), palabra, motivos)
    assert review.word is None


def test_veredicto_valido_se_guarda(s):
    review = review_for(s)
    verdict.save_verdict(ref(review), "Mejor no", MOTIVOS_OK)
    assert review.word == "Mejor no" and review.motives[0] == {"label": "Riesgo", "text": MOTIVOS_OK[0]["texto"]}


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


def test_los_tres_papeles_dejan_la_revision_lista(s, monkeypatch):
    launched = fake_claude(monkeypatch, s)
    review = review_for(s, status="pendiente")
    verdict.run(review.id)
    s.refresh(review)
    assert launched == ["favor", "contra", "juez"]
    assert review.status == "lista" and review.word == "Dudosa" and review.favor == "Texto de favor"
    assert review.favor_sources == [{"title": "Nota", "url": "https://e.com/a"}] and review.model == "sonnet"


def test_si_cambia_la_apuesta_a_mitad_se_descarta(s, monkeypatch):
    review = review_for(s, status="pendiente")

    def replaced(papel):
        if papel == "juez":
            review.pick.is_pick_of_day = False

    fake_claude(monkeypatch, s, on_role=replaced)
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "descartada"


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
    assert review.status == "pendiente" and review.word is None and review.attempts == 1
    assert "juez" not in launched
    verdict.run(review.id)
    s.refresh(review)
    assert review.status == "error" and review.attempts == 2 and "contra" in review.error


def test_el_reintento_no_repite_lo_ya_guardado(s, monkeypatch):
    launched = fake_claude(monkeypatch, s)
    review = review_for(s, status="pendiente", favor="Ya escrito", favor_sources=[])
    verdict.run(review.id)
    assert launched == ["contra", "juez"]


def test_un_fallo_de_claude_no_lanza_y_se_reintenta(s, monkeypatch):
    def boom(papel, review_id):
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


def test_datos_con_referencia_mala(s):
    with pytest.raises(ValueError):
        verdict.review_data("pick:1")


def test_herramientas_del_motor(monkeypatch):
    from apuestas.config import get_settings
    from apuestas.mcp_server.server import build

    def tools():
        return {t.name for t in build()._tool_manager.list_tools()}

    assert "datos_veredicto" in tools() and not {"guardar_revisor", "guardar_veredicto"} & tools()
    monkeypatch.setattr(get_settings(), "mcp_engine", True)
    assert {"datos_veredicto", "guardar_revisor", "guardar_veredicto"} <= tools()
    assert "registrar_apuesta" not in tools()
