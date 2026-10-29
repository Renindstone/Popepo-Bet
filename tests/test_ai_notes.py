"""Notas de Claude: por qué falló la apuesta del día y qué pasa con un equipo o jugador del radar."""

from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_weekly import KICKOFF, add_played

from apuestas.config import get_settings
from apuestas.db import models as m
from apuestas.services import ai_notes, tracker

DAY = date(2026, 10, 29)
OWNER = get_settings().default_user


@pytest.fixture
def s(monkeypatch):
    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:

        @contextmanager
        def scope():
            yield session
            session.flush()

        monkeypatch.setattr(ai_notes, "session_scope", scope)
        yield session


def test_una_nota_por_apuesta(s):
    first = ai_notes.request(s, "fallo", "pick:7", DAY)
    again = ai_notes.request(s, "fallo", "pick:7", DAY)
    assert first.id == again.id and first.status == "pendiente"
    assert len(s.scalars(select(m.AiNote)).all()) == 1


def test_claim_una_vez(s):
    note = ai_notes.request(s, "radar", "team:16", DAY)
    assert ai_notes.claim(note.id) is True
    assert ai_notes.claim(note.id) is False


def test_comando_aislado(s, monkeypatch):
    monkeypatch.setattr(ai_notes.shutil, "which", lambda _: "/usr/bin/claude")
    cmd, env, workdir = ai_notes.command(ai_notes.request(s, "fallo", "pick:7", DAY))
    joined = " ".join(cmd)
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    allowed = cmd[cmd.index("--allowedTools") + 1].split(",")
    assert allowed == ["WebSearch", "WebFetch", "mcp__apuestas__datos_fallo", "mcp__apuestas__datos_radar",
                       "mcp__apuestas__guardar_explicacion"]
    assert '"APUESTAS_MCP_ENGINE": "true"' in joined and "--strict-mcp-config" in cmd
    assert "Bash" not in joined and "Read" not in allowed and "ANTHROPIC_API_KEY" not in env


def test_sin_claude_queda_en_error(s, monkeypatch):
    monkeypatch.setattr(get_settings(), "claude_bin", "no-existe-claude")
    note = ai_notes.request(s, "fallo", "pick:7", DAY)
    ai_notes.run(note.id)
    s.refresh(note)
    assert note.status == "error" and "No encuentro el CLI de Claude Code" in note.error


@pytest.mark.parametrize("texto, fuentes", [
    ("x" * 1201, []),
    ("Explicación corta.", [{"titulo": "Malo", "url": "javascript:alert(1)"}]),
    ("Explicación corta.", [{"titulo": f"N{i}", "url": f"https://e.com/{i}"} for i in range(7)]),
    ("   ", []),
])
def test_save_valida(s, texto, fuentes):
    note = ai_notes.request(s, "fallo", "pick:7", DAY)
    ai_notes.claim(note.id)
    with pytest.raises(ValueError):
        ai_notes.save("pick:7", texto, fuentes)


def test_save_guarda_texto_y_fuentes(s):
    note = ai_notes.request(s, "fallo", "pick:7", DAY)
    ai_notes.claim(note.id)
    ai_notes.save("pick:7", "  Lazio llegaba en racha.  ", [{"titulo": "Crónica", "url": "https://e.com/a"}])
    s.refresh(note)
    assert (note.status, note.text, note.sources) == ("lista", "Lazio llegaba en racha.",
                                                      [{"title": "Crónica", "url": "https://e.com/a"}])


def test_guardar_solo_en_motor(monkeypatch):
    from apuestas.mcp_server.server import build

    def tools():
        return {t.name for t in build()._tool_manager.list_tools()}

    assert "guardar_explicacion" not in tools() and {"datos_fallo", "datos_radar"} <= tools()
    monkeypatch.setattr(get_settings(), "mcp_engine", True)
    assert "guardar_explicacion" in tools()


def lost_pod(s, result="loss"):
    n = len(s.scalars(select(m.Team)).all())
    a, b = (m.Team(name=f"Equipo {n + i}") for i in range(2))
    s.add_all([a, b])
    s.flush()
    mt = add_played(s, a, b, KICKOFF, 0, 1)
    p = m.Pick(match_id=mt.id, pick_date=date(2026, 10, 20), stage="confirmed", market="1x2", selection="home",
               bookmaker="betano", odds=2.0, model_prob=0.55, fair_odds=1.8, ev=0.1, confidence=0.7, stake_pct=0.02,
               is_pick_of_day=True, qualifies=True, status="settled", result=result,
               created_at=KICKOFF - timedelta(hours=6))
    s.add(p)
    s.flush()
    return p


def test_settle_pide_nota_si_el_duenio_usa_la_ia(s):
    p = lost_pod(s)
    assert ai_notes.after_settle(s, [p, lost_pod(s, "win")]) == 1
    assert [n.ref for n in s.scalars(select(m.AiNote))] == [f"pick:{p.id}"]


def test_settle_no_pide_nota_con_la_ia_del_duenio_apagada(s):
    tracker.set_ai_enabled(s, OWNER, False)
    assert ai_notes.after_settle(s, [lost_pod(s)]) == 0


def test_ia_apagada_sin_nota(s):
    note = ai_notes.request(s, "fallo", "pick:7", DAY)
    tracker.set_ai_enabled(s, "amigo", False)
    assert ai_notes.public(s, note, "amigo") is None
    assert ai_notes.public(s, note, OWNER)["status"] == "pendiente"


def test_investigar_solo_el_duenio(s, monkeypatch):
    sent = []
    monkeypatch.setattr(ai_notes, "submit", sent.append)
    monkeypatch.setattr(ai_notes.radar, "get", lambda: RADAR)
    with pytest.raises(PermissionError):
        ai_notes.investigate("amigo", "team", 16)
    out = ai_notes.investigate(OWNER, "team", 16)
    assert out["status"] == "pendiente" and len(sent) == 1
    ai_notes.investigate(OWNER, "team", 16)  # pedirla otra vez el mismo día no lanza otra
    assert len(sent) == 1


def test_investigar_algo_fuera_del_radar(s, monkeypatch):
    monkeypatch.setattr(ai_notes.radar, "get", lambda: RADAR)
    with pytest.raises(ai_notes.queries.NotFound):
        ai_notes.investigate(OWNER, "team", 999)


RADAR = {"racha": [{"team_id": 16, "name": "Genoa"}], "baja": [], "jugadores": [{"player_id": 5, "name": "Baldanzi"}]}


def test_radar_con_notas(s, monkeypatch):
    monkeypatch.setattr(ai_notes, "today", lambda: DAY)
    ai_notes.request(s, "radar", "team:16", DAY)
    out = ai_notes.with_notes({k: [dict(x) for x in v] for k, v in RADAR.items()}, OWNER)
    assert out["racha"][0]["note"]["status"] == "pendiente" and out["jugadores"][0]["note"] is None
    tracker.set_ai_enabled(s, OWNER, False)
    assert ai_notes.with_notes({k: [dict(x) for x in v] for k, v in RADAR.items()}, OWNER)["racha"][0]["note"] is None


def test_tarea_del_worker(monkeypatch):
    from apuestas.jobs import scheduler

    calls = []
    monkeypatch.setattr(ai_notes, "process_pending", lambda: calls.append(1) or 0)
    scheduler.job_ai_notes()
    assert calls == [1]


def test_api_expone_investigar():
    from apuestas.api.app import app

    assert "/radar/investigate" in {r.path for r in app.routes}
