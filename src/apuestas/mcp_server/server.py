"""Servidor MCP: permite que Claude (u otro agente compatible con MCP) consulte el sistema.

Modos:
- stdio (local, un usuario):      apuestas mcp
- HTTP (varios usuarios, con clave): apuestas mcp --http --port 8765
  Cada usuario usa su clave como token: Authorization: Bearer apk_...
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from apuestas.config import get_settings
from apuestas.db.session import session_scope
from apuestas.services import captures, queries, tracker

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
Sistema de análisis de apuestas de fútbol (Premier League, Bundesliga, LaLiga y Champions League).
Los números (probabilidades, cuotas justas, valor esperado) los calcula un modelo estadístico; tu papel
es interpretarlos, explicarlos y combinarlos con información cualitativa (noticias, ruedas de prensa).

Partidos: usa el id o texto "Equipo A vs Equipo B" (o solo un equipo para su próximo partido).

Mercados (parámetro `mercado`) y selecciones:
- 1x2 (home/draw/away), dc (1x/x2/12), dnb (home/away), btts (yes/no)
- ah = hándicap asiático (home/away + linea, p.ej. -0.75), eh = hándicap europeo (home/draw/away + linea del local)
- ou_goals, ou_goals_home, ou_goals_away (over/under + linea)
- ou_shots, ou_sot, ou_corners, ou_cards, ou_fouls (+ _home / _away para un equipo) (over/under + linea)
- ah_corners, ah_cards, 1x2_corners ... (hándicap / ganador de una estadística)
- player_shots, player_sot, player_fouls (over/under + linea + jugador), player_goal, player_card (yes/no + jugador)

Reglas: no recomiendes apostar si el veredicto no es "APOSTAR"; recuerda la gestión de banca y que
"no apostar" es válido. Las bajas manuales sirven para noticias que FotMob aún no refleja.

Capturas: el usuario sube imágenes de cuotas en el panel. capturas_pendientes → ver_captura (imagen + guía) →
evaluar_captura (las cuotas que leíste; el modelo calcula el veredicto) o evaluar_combinada (combinadas y Bet
Builders) → guardar_veredicto_captura (resumen). Si no hay nada evaluable: marcar_no_evaluable.
"""


class ApiKeyVerifier:
    """Valida tokens Bearer contra las claves de usuario guardadas (hash SHA-256)."""

    async def verify_token(self, token: str) -> AccessToken | None:
        with session_scope() as s:
            user = tracker.user_by_key(s, token)
            if user is None:
                return None
            return AccessToken(token=token, client_id=user.username, scopes=["apuestas"])


def _user() -> str:
    tok = get_access_token()
    if tok:
        return tok.client_id
    st = get_settings()
    return st.mcp_user or st.default_user


def _safe(fn, *args: Any, **kwargs: Any) -> str:
    try:
        return json.dumps(fn(*args, **kwargs), ensure_ascii=False, default=str, indent=1)
    except queries.NotFound as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({"error": "Los modelos aún no están entrenados. Ejecuta `apuestas train`."})
    except ValueError as exc:  # incluye CaptureError
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def build(http: bool = False, public_url: str | None = None) -> MCPServer:
    kwargs: dict[str, Any] = {}
    if http:
        url = public_url or "http://127.0.0.1:8765"
        kwargs = {"token_verifier": ApiKeyVerifier(),
                  "auth": AuthSettings(issuer_url=url, resource_server_url=url, required_scopes=["apuestas"])}
    server = MCPServer(name="apuestas-futbol", title="Análisis de apuestas de fútbol", instructions=INSTRUCTIONS,
                       version="0.1.0", **kwargs)

    @server.tool()
    def partidos_proximos(dias: int = 3, competicion: str | None = None) -> str:
        """Lista los próximos partidos (EPL, BUN, LAL, UCL) con hora de Lima, árbitro y estado de alineaciones."""
        return _safe(queries.upcoming, dias, competicion)

    @server.tool()
    def analizar_partido(partido: str) -> str:
        """Análisis completo: probabilidades de todos los mercados, cuotas justas, dificultad para cada equipo
        (base y con la alineación real), bajas, árbitro, contexto (descanso, rotaciones), apuestas con valor,
        cuotas mínimas para props y proyección de jugadores."""
        return _safe(queries.match_analysis, partido)

    @server.tool()
    def apuesta_del_dia(fecha: str | None = None, recalcular: bool = False) -> str:
        """Apuesta del día (la de mayor valor esperado entre las que superan umbrales de confianza),
        otras apuestas con valor y props para revisar. fecha en formato AAAA-MM-DD (por defecto hoy en Lima)."""
        return _safe(queries.pick_of_day, fecha, recalcular)

    @server.tool()
    def evaluar_cuota(partido: str, mercado: str, seleccion: str, cuota: float, linea: float | None = None,
                      casa: str = "betano", jugador: str | None = None) -> str:
        """Evalúa una cuota concreta que el usuario ve en Betano/bet365: probabilidad, cuota justa,
        valor esperado, stake sugerido (Kelly fraccional) y veredicto."""
        return _safe(queries.evaluate_odds, partido, mercado, seleccion, cuota, linea, casa, jugador)

    @server.tool()
    def bajas_equipo(equipo: str) -> str:
        """Lesionados, sancionados y dudas activos de un equipo."""
        return _safe(queries.absences, equipo)

    @server.tool()
    def registrar_baja(equipo: str, jugador: str, tipo: str = "injury", motivo: str | None = None,
                       regreso: str | None = None) -> str:
        """Registra una baja que salió en noticias. tipo: injury | suspension | doubtful."""
        return _safe(queries.add_absence, equipo, jugador, tipo, motivo, regreso)

    @server.tool()
    def quitar_baja(equipo: str, jugador: str) -> str:
        """Marca que un jugador ya está disponible."""
        return _safe(queries.remove_absence, equipo, jugador)

    @server.tool()
    def perfil_arbitro(nombre: str) -> str:
        """Tarjetas por partido del árbitro, factor respecto a lo esperado y sus próximos partidos."""
        return _safe(queries.referee_profile, nombre)

    @server.tool()
    def proyeccion_jugador(jugador: str, partido: str | None = None) -> str:
        """Tasas por 90' de un jugador y probabilidades para su próximo partido (remates, a puerta, gol, tarjeta)."""
        return _safe(queries.player_projection, jugador, partido)

    @server.tool()
    def registrar_apuesta(partido: str, mercado: str, seleccion: str, cuota: float, monto: float,
                          linea: float | None = None, casa: str = "betano", jugador: str | None = None,
                          notas: str | None = None) -> str:
        """Guarda una apuesta real del usuario para el seguimiento de rendimiento (se liquida sola)."""
        return _safe(queries.register_bet, _user(), partido, mercado, seleccion, cuota, monto, linea, casa,
                     jugador, notas)

    @server.tool()
    def mis_apuestas(solo_pendientes: bool = False) -> str:
        """Últimas apuestas registradas por el usuario."""
        return _safe(queries.my_bets, _user(), solo_pendientes)

    @server.tool()
    def mi_rendimiento(dias: int | None = None) -> str:
        """ROI, acierto, CLV y beneficio por mercado, competición, casa y rango de cuota; estado de la banca."""
        return _safe(queries.performance, _user(), dias)

    @server.tool()
    def configurar_banca(monto: float, moneda: str = "PEN") -> str:
        """Fija la banca del usuario (base para el stake sugerido y los límites de pérdida)."""
        return _safe(queries.set_bankroll, _user(), monto, moneda)

    @server.tool()
    def historial_apuesta_del_dia(dias: int = 60) -> str:
        """Rendimiento real de las apuestas del día pasadas (stake plano de 1 unidad), más el contador de
        aciertos desde el inicio del sistema."""
        from apuestas.services import picks

        return _safe(lambda d: {**picks.pick_history(d), "desde_el_inicio": picks.pick_record()}, dias)

    @server.tool()
    def capturas_pendientes() -> str:
        """Capturas de cuotas (imágenes de bet365/Betano) que el usuario subió al panel y esperan lectura."""
        return _safe(captures.pending, _user())

    @server.tool()
    def ver_captura(captura_id: int) -> list[Image | str]:
        """Devuelve la imagen de una captura de cuotas con las pistas del usuario, los partidos próximos y la guía
        para pasar cada mercado al formato de evaluar_captura."""
        try:
            path, mime, text = captures.context_for_ai(_user(), captura_id)
        except queries.NotFound as exc:
            return [json.dumps({"error": str(exc)}, ensure_ascii=False)]
        return [Image(data=path.read_bytes(), format=mime.split("/")[1]), text]

    @server.tool()
    def evaluar_captura(captura_id: int, lineas: list[captures.CaptureLine], partido: str | None = None,
                        notas: str | None = None) -> str:
        """Envía las cuotas leídas en una captura. El modelo devuelve probabilidad, cuota justa, valor esperado,
        stake y veredicto de cada una (las guarda en la captura). partido: id o 'Local vs Visitante'."""
        return _safe(captures.evaluate_lines, _user(), captura_id, lineas, partido, notas)

    @server.tool()
    def evaluar_combinada(captura_id: int, bloques: list[captures.ComboBlock], cuota_total: float | None = None,
                          notas: str | None = None) -> str:
        """Combinada o Bet Builder de una captura: un bloque por partido con sus selecciones (y la cuota del bloque si
        aparece) más la cuota total. El modelo calcula la probabilidad conjunta de cada bloque con la matriz de
        marcadores y la del total; las selecciones fuera del modelo se marcan, sin inventar."""
        return _safe(captures.evaluate_combo, _user(), captura_id, bloques, cuota_total, notas)

    @server.tool()
    def marcar_no_evaluable(captura_id: int, motivo: str) -> str:
        """La captura no tiene nada que el modelo pueda evaluar: guarda el motivo para que el usuario lo vea."""
        return _safe(captures.mark_not_evaluable, _user(), captura_id, motivo)

    @server.tool()
    def guardar_veredicto_captura(captura_id: int, veredicto: str) -> str:
        """Guarda el resumen final de la captura (2 a 5 frases basadas solo en los números del modelo)."""
        return _safe(captures.save_verdict, _user(), captura_id, veredicto)

    @server.tool()
    def estado_datos() -> str:
        """Frescura de cada fuente de datos y fecha del último entrenamiento del modelo."""
        return _safe(queries.data_status)

    return server


def run(http: bool = False, host: str = "127.0.0.1", port: int = 8765, public_url: str | None = None) -> None:
    server = build(http=http, public_url=public_url)
    if http:
        server.run("streamable-http", host=host, port=port)
    else:
        server.run()
