"""Capturas de cuotas: validación de imágenes, aislamiento del motor Claude Code y bucle del motor API."""

import json
from types import SimpleNamespace

import pytest

from apuestas.config import Settings, get_settings
from apuestas.services import capture_engines, captures

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 20


def test_detect_mime_by_content_not_by_name():
    assert captures.detect_mime(PNG) == "image/png"
    assert captures.detect_mime(JPEG) == "image/jpeg"
    assert captures.detect_mime(WEBP) == "image/webp"
    assert captures.detect_mime(b"GIF89a" + b"\x00" * 20) is None
    assert captures.detect_mime(b"<svg xmlns='http://www.w3.org/2000/svg'/>") is None


def test_create_rejects_bad_files_before_touching_db():
    with pytest.raises(captures.CaptureError, match="vacía"):
        captures.create("renzo", b"")
    with pytest.raises(captures.CaptureError, match="Formato"):
        captures.create("renzo", b"%PDF-1.7 no es una imagen")
    too_big = PNG + b"\x00" * int(get_settings().captures_max_mb * 1024 * 1024)
    with pytest.raises(captures.CaptureError, match="MB"):
        captures.create("renzo", too_big)


def test_selection_synonyms():
    assert captures.normalize_selection("Local") == "home"
    assert captures.normalize_selection("X") == "draw"
    assert captures.normalize_selection("Más") == "over"
    assert captures.normalize_selection("sí") == "yes"
    assert captures.normalize_selection("over") == "over"


def test_summary_counts_and_best_line():
    def ev(e, verdict):
        return {"eval": {"ev": e, "verdict": verdict}, "odds": 2.0, "label": f"línea {e}"}

    lines = [ev(-0.1, "NO apostar"), ev(0.05, "APOSTAR"), ev(0.02, "valor pequeño o poca confianza"),
             {"error": "Jugador no encontrado", "odds": 1.8}]
    s = captures.summarize(lines)
    assert (s["lines"], s["evaluated"], s["errors"], s["bet"], s["positive_ev"]) == (4, 3, 1, 1, 2)
    assert s["best"]["ev"] == 0.05
    assert captures.summarize([ev(-0.2, "NO apostar")])["best"] is None


def test_engine_only_for_owner_by_default():
    st = Settings(default_user="renzo", captures_engine="claude_code", captures_engine_users="")
    assert st.captures_engine_for("renzo") == "claude_code"
    assert st.captures_engine_for("amigo") is None  # la suscripción es personal
    st = Settings(default_user="renzo", captures_engine="api", captures_engine_users="renzo, amigo")
    assert st.captures_engine_for("amigo") == "api"
    assert Settings(captures_engine="none").captures_engine_for("renzo") is None


def test_claude_code_runs_isolated(monkeypatch):
    monkeypatch.setattr(capture_engines.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-no-debe-usarse")
    cmd, env, workdir = capture_engines.claude_code_command(7, "amigo")
    assert cmd[:2] == ["/usr/bin/claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""  # sin archivos ni terminal
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    allowed = cmd[cmd.index("--allowedTools") + 1].split(",")
    assert allowed == [f"mcp__apuestas__{t}" for t in capture_engines.MCP_TOOLS]
    mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["apuestas"]
    assert mcp["args"] == ["mcp"] and mcp["env"] == {"APUESTAS_MCP_USER": "amigo"}
    assert "ANTHROPIC_API_KEY" not in env  # usa la suscripción iniciada
    assert workdir.name == "_motor" and workdir.parent == get_settings().captures_dir


def test_parse_claude_output():
    ok = json.dumps({"result": "Hecho", "is_error": False, "num_turns": 4, "duration_ms": 13000,
                     "modelUsage": {"claude-sonnet-5-5": {}}, "total_cost_usd": 0.08, "permission_denials": []})
    info = capture_engines.parse_claude_output(0, "aviso previo\n" + ok, "")
    assert info["turns"] == 4 and info["models"] == ["claude-sonnet-5-5"] and "error" not in info
    bad = capture_engines.parse_claude_output(1, json.dumps({"result": "sin sesión", "is_error": True}), "")
    assert bad["error"] == "sin sesión"
    crash = capture_engines.parse_claude_output(127, "", "claude: command not found")
    assert "command not found" in crash["error"]


def test_api_engine_tool_loop(monkeypatch, tmp_path):
    img = tmp_path / "c.png"
    img.write_bytes(PNG)
    calls = []
    monkeypatch.setattr(captures, "context_for_ai", lambda user, cid: (img, "image/png", "contexto"))
    monkeypatch.setattr(captures, "evaluate_lines",
                        lambda user, cid, lineas, partido, notas, engine: calls.append(("evaluar", lineas, partido, engine))
                        or {"lineas": [{"veredicto": "NO apostar"}]})
    monkeypatch.setattr(captures, "save_verdict",
                        lambda user, cid, text: calls.append(("veredicto", text)) or {"estado": "lista"})

    linea = {"mercado": "1x2", "seleccion": "home", "cuota": 1.45}
    replies = [
        SimpleNamespace(stop_reason="tool_use", usage=SimpleNamespace(input_tokens=1500, output_tokens=80), content=[
            SimpleNamespace(type="tool_use", id="t1", name="evaluar_captura", input={"partido": "4808", "lineas": [linea]})]),
        SimpleNamespace(stop_reason="tool_use", usage=SimpleNamespace(input_tokens=1700, output_tokens=60), content=[
            SimpleNamespace(type="tool_use", id="t2", name="guardar_veredicto_captura", input={"veredicto": "Sin valor."})]),
        SimpleNamespace(stop_reason="end_turn", usage=SimpleNamespace(input_tokens=1800, output_tokens=5),
                        content=[SimpleNamespace(type="text", text="Listo")]),
    ]
    sent = []

    class FakeMessages:
        def create(self, **kw):
            sent.append(kw)
            return replies[len(sent) - 1]

    info = capture_engines.run_api(3, "renzo", client=SimpleNamespace(messages=FakeMessages()))
    assert calls == [("evaluar", [linea], "4808", "api"), ("veredicto", "Sin valor.")]
    first = sent[0]["messages"][0]["content"]
    assert first[0]["type"] == "image" and first[0]["source"]["media_type"] == "image/png"
    assert {t["name"] for t in sent[0]["tools"]} == {"evaluar_captura", "evaluar_combinada", "marcar_no_evaluable",
                                                    "guardar_veredicto_captura"}
    # La lista de mensajes es la misma en cada llamada: [usuario, asistente, resultados t1, asistente, ...]
    result = sent[0]["messages"][2]["content"][0]
    assert result["tool_use_id"] == "t1" and not result["is_error"]
    assert info["input_tokens"] == 5000 and info["output_tokens"] == 145


def test_mcp_server_exposes_capture_tools():
    from apuestas.mcp_server.server import build

    names = {t.name for t in build()._tool_manager.list_tools()}
    assert {"capturas_pendientes", "ver_captura", "evaluar_captura", "evaluar_combinada", "marcar_no_evaluable",
            "guardar_veredicto_captura"} <= names
