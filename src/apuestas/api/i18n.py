"""Respuestas de la API en inglés para el panel, que lo pide con la cabecera `Accept-Language: en`.

Los servicios, la BD, el bot de Telegram y el servidor MCP siguen en español: aquí solo se traduce lo que sale por la
API, texto a texto, con un catálogo de frases fijas y de plantillas. Lo que no está en el catálogo sale como está: los
resúmenes y explicaciones que escribió Claude, el texto leído de una captura y los nombres. Los valores que el panel usa
como clave («APOSTAR», «con valor», «racha», los niveles de dificultad, «goles»…) tampoco se tocan: los traduce el panel.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache

from apuestas.services import analysis, compare, queries, radar, sync, weekly


def wants_english(accept_language: str | None) -> bool:
    return (accept_language or "").strip().lower().startswith("en")


# Nombres de mercado de las etiquetas («Hándicap asiático: Arsenal -0.5»), como en Betano en inglés
MARKET_EN = {
    "1x2": "Match Result", "ah": "Asian Handicap", "eh": "Handicap (3-way)", "ou_goals": "Goals",
    "btts": "Both Teams To Score", "dnb": "Draw No Bet", "dc": "Double Chance",
    "ou_shots": "Total shots", "ou_shots_on_target": "Shots on target", "ou_sot": "Shots on target",
    "ou_corners": "Corners", "ah_corners": "Corners Handicap", "1x2_corners": "Most corners",
    "ou_cards": "Cards", "ah_cards": "Cards Handicap", "1x2_cards": "Most cards",
    "ou_fouls": "Fouls", "player_shots": "Player shots", "player_sot": "Player shots on target",
    "player_card": "Player to be booked", "player_goal": "Player to score", "player_fouls": "Player fouls",
    "player_assist": "Player to assist", "player_goal_assist": "Player to score or assist",
}
MARKETS = {analysis.MARKET_LABELS[k]: v for k, v in MARKET_EN.items()}
SELECTIONS = (("Empate", "Draw"), ("Más de ", "Over "), ("Menos de ", "Under "), ("Sí", "Yes"))

# Datos de «Sorpresas» (weekly.LABELS)
WEEKLY_EN = {"result": "Result", "goals": "Goals", "corners": "Corners", "shots": "Shots",
             "shots_on_target": "Shots on target", "assists": "Assists", "conceded": "Goals conceded"}

# Pasos de la sincronización manual (sync.py), en el orden de allí
SYNC_EN = ["FotMob fixtures and results", "football-data results and closing odds", "Understat xG", "Duplicate teams",
           "Details of the matches played", "Settling bets", "Line-ups, absences and referees of upcoming matches",
           "bet365 odds from football-data", "Retraining the model"]

DAYS = {"lun": "Mon", "mar": "Tue", "mié": "Wed", "jue": "Thu", "vie": "Fri", "sáb": "Sat", "dom": "Sun"}

EXACT: dict[str, str] = {
    **{weekly.LABELS[k]: v for k, v in WEEKLY_EN.items()},
    weekly.NOTE: "It sums up who surprised the bookmaker (teams) and our model (players) in the matches already played. "
                 "A good week is partly luck: it does not mean the next one will repeat it.",
    radar.NOTE: "It is a warning to look at it more carefully, not a signal: since 2023, whoever pulled off the surprise "
                "does not repeat it more than the bookmaker expects, so it does not change the probability or the cut.",
    compare.NOTE: "Since 19-10-2026, in corners and cards Betano often paid more than Pinnacle and Pinnacle did not "
                  "move towards Betano afterwards; in goals almost never. It is still only a few weeks: it is a price "
                  "edge, not a sure bet.",
    queries.AI_OFF: "AI is turned off for your user: you can turn it on at the end of Data.",
    # Apuesta del día (picks.py)
    "Hoy no hay apuesta del día: ninguna apuesta supera los umbrales de valor y confianza. No apostar también es una "
    "decisión rentable.": "No bet of the day today: no bet beats the value and confidence thresholds. Not betting is "
                          "also a profitable decision.",
    "La apuesta del día anterior se retiró: perdió valor con la nueva información":
        "The earlier bet of the day was withdrawn: it lost value with the new information",
    "Sin cuota de referencia: ni Pinnacle ni el cierre de bet365 tenían esta línea antes del partido":
        "No reference odds: neither Pinnacle nor the bet365 closing line had this line before kick-off",
    # Partido (analysis.py, features/lineup.py, queries.py)
    "Sin historial suficiente": "Not enough history",
    "equipo con pocas cuotas de referencia": "team with few reference odds",
    "Sin historial de alineaciones: no se ajusta": "No line-up history: no adjustment",
    "Alineación claramente más débil que la habitual (rotación o bajas importantes)":
        "Line-up clearly weaker than usual (rotation or key absences)",
    "Alineación más fuerte que la media reciente": "Line-up stronger than the recent average",
    "No figura en la alineación (o está de baja)": "Not in the line-up (or unavailable)",
    "alineaciones previstas": "predicted line-ups",
    # Datos (queries.py, sync.py)
    "Sin conexión a internet en este equipo": "No internet connection on this computer",
    "El sitio no responde": "The site does not respond",
    "equipos duplicados": "duplicate teams",
    **{label: en for (label, _), en in zip(sync.steps(), SYNC_EN, strict=True)},
    "Ya hay una sincronización en marcha.": "A sync is already running.",
    "El worker está descargando datos ahora mismo; espera a que termine.":
        "The worker is downloading data right now; wait for it to finish.",
    # Clásicos con nombre en español (core/rivalries.py); los demás van en su idioma
    "Derbi de Merseyside": "Merseyside derby", "Clásico del noroeste": "North West derby",
    "Derbi de Mánchester": "Manchester derby", "Derbi del norte de Londres": "North London derby",
    "Derbi de Londres": "London derby", "Derbi Tyne-Wear": "Tyne-Wear derby", "Derbi de la M23": "M23 derby",
    "El Clásico": "El Clásico", "Derbi madrileño": "Madrid derby", "Derbi sevillano": "Seville derby",
    "Derbi vasco": "Basque derby", "Derbi barcelonés": "Barcelona derby", "Derbi valenciano": "Valencia derby",
    "Derbi de la Comunidad Valenciana": "Valencian Community derby", "Derbi gallego": "Galician derby",
    "Derbi del Ruhr": "Ruhr derby", "Derbi renano": "Rhine derby", "Derbi del Rin-Meno": "Rhine-Main derby",
    "Derbi del Ródano": "Rhône derby", "Derbi de la Costa Azul": "Côte d'Azur derby", "Derbi del Norte": "Derby du Nord",
    "Derbi bretón": "Breton derby", "Derbi de París": "Paris derby", "Derbi de Lisboa": "Lisbon derby",
    "Derbi del Miño": "Minho derby", "Derbi de Brujas": "Bruges derby", "Clásico belga": "Belgian Clásico",
    "Derbi de Amberes": "Antwerp derby", "Derbi intercontinental": "Intercontinental derby",
    "Derbi de Estambul": "Istanbul derby",
    # Errores
    "Clave inválida": "Invalid key",
    "Falta la cabecera X-API-Key": "Missing the X-API-Key header",
    "Modelos no entrenados todavía (apuestas train)": "Models not trained yet (apuestas train)",
    "Sin escudo": "No crest",
    "La imagen ya no está en el disco": "The image is no longer on disk",
    "Tus capturas las procesa tu propio agente por MCP (capturas_pendientes)":
        "Your own agent processes your screenshots over MCP (capturas_pendientes)",
    "No hay un motor alternativo configurado": "No alternative engine is configured",
    "La cuota tiene que ser mayor que 1.": "The odds have to be greater than 1.",
    "El importe tiene que ser mayor que 0.": "The stake has to be greater than 0.",
    "El importe debe ser mayor que 0.": "The stake must be greater than 0.",
    "La banca debe ser mayor que 0.": "The bankroll must be greater than 0.",
    "El cupón está vacío.": "The slip is empty.",
    "Falta la cuota total del cupón (mayor que 1).": "The slip's total odds are missing (greater than 1).",
    "Un cupón necesita al menos 2 selecciones; para una sola, registra la apuesta normal.":
        "A slip needs at least 2 selections; for a single one, record a normal bet.",
    "El hándicap necesita línea": "The handicap needs a line",
    "El hándicap europeo necesita línea": "The 3-way handicap needs a line",
    "Over/under necesita línea": "Over/under needs a line",
    "Jugador sin proyección para este partido": "Player without a projection for this match",
    "La imagen está vacía": "The image is empty",
    "Formato no admitido: sube una imagen PNG, JPG o WEBP": "Format not supported: upload a PNG, JPG or WEBP image",
    "La captura se está procesando; espera a que termine": "The screenshot is being processed; wait for it to finish",
    "Solo el dueño, con la IA encendida, puede pedir explicaciones a Claude":
        "Only the owner, with AI turned on, can ask Claude for explanations",
}


def _label(m: re.Match[str]) -> str:
    """«Córners (Arsenal): Más de 4.5» → «Corners (Arsenal): Over 4.5» (analysis.bet_label)."""
    sel = m["sel"]
    for es, en in SELECTIONS:
        if sel.startswith(es):
            sel = en + sel[len(es):]
            break
    return f"{MARKETS[m['base']]}{m['rest']}: {sel}"


_BASES = "|".join(re.escape(b) for b in sorted(MARKETS, key=len, reverse=True))

# Plantillas: con `{nombre}` se copia el trozo; `_t` lo traduce, `_list` traduce cada elemento de una lista con comas
# y `_and` cambia el «y» de «Troyes y Le Mans»
PATTERNS: list[tuple[str, str | Callable[[re.Match[str]], str]]] = [
    (rf"(?P<base>{_BASES})(?P<rest>(?: \([^)]*\))?(?: — [^:]+)?): (?P<sel>.+)", _label),
    (r"(?P<d>lun|mar|mié|jue|vie|sáb|dom) (?P<rest>\d\d/\d\d \d\d:\d\d)", lambda m: f"{DAYS[m['d']]} {m['rest']}"),
    # Razones de una apuesta (analysis.py)
    (r"La casa \(sin margen\) da (?P<h>\d+%) y el modelo (?P<m>\d+%): discrepan mucho, probablemente se equivoca el "
     r"modelo \(confianza baja\)",
     "The bookmaker (margin-free) gives {h} and the model {m}: they disagree a lot, the model is probably wrong "
     "(low confidence)"),
    (r"Modelo (?P<m>\d+%) · casa sin margen (?P<h>\d+%) · mezcla (?P<p>\d+%): (?P<teams_and>.+) con pocos partidos con "
     r"esta estadística en nuestros datos",
     "Model {m} · margin-free bookmaker {h} · blend {p}: {teams_and} with few matches with this stat in our data"),
    (r"Modelo (?P<m>\d+%) · mercado afilado (?P<s>\d+%) · mezcla (?P<p>\d+%)", "Model {m} · sharp market {s} · blend {p}"),
    (r"Modelo (?P<m>\d+%) · cuota sin margen (?P<b>\d+%) · mezcla (?P<p>\d+%): (?P<note_t>.+)",
     "Model {m} · margin-free odds {b} · blend {p}: {note_t}"),
    (r"Probabilidad del modelo (?P<m>\d+%) \(sin referencia de mercado afilado\)",
     "Model probability {m} (no sharp market reference)"),
    (r"(?P<teams_and>.+) casi sin cuotas de su liga en nuestros datos; el modelo es poco fiable en este partido",
     "{teams_and} with almost no odds from their league in our data; the model is unreliable in this match"),
    (r"un equipo", "a team"),
    # Contexto de cada equipo (features/context.py, analysis.py)
    (r"Poco descanso \((?P<n>[\d.]+) días\)", "Little rest ({n} days)"),
    (r"Calendario cargado \((?P<n>\d+) partidos en 14 días\)", "Busy schedule ({n} matches in 14 days)"),
    (r"Juega Champions en (?P<n>\d+) días", "Plays in the Champions League in {n} days"),
    (r"Rival chico entre partidos grandes \((?P<teams>.+)\): desde 2024 en estos partidos se vieron menos tarjetas y "
     r"faltas, aunque no se confirmó; remates y goles, sin cambio",
     "Small opponent between big matches ({teams}): since 2024 these matches have shown fewer cards and fouls, though "
     "it was not confirmed; shots and goals, no change"),
    (r"Hace caer al rival en fuera de juego (?P<k>[\d.]+) veces la media \(defensa adelantada\)",
     "Catches opponents offside {k} times the average (high defensive line)"),
    # Banca (tracker.py)
    (r"Llegaste al límite de pérdida diario \((?P<x>[^)]+)\)\. Para por hoy\.",
     "You hit the daily loss limit ({x}). Stop for today."),
    (r"Llegaste al límite de pérdida semanal \((?P<x>[^)]+)\)\.", "You hit the weekly loss limit ({x})."),
    # Combinadas (queries.py, captures.py)
    (r"Combinada de (?P<n>\d+) selecciones", "{n}-selection accumulator"),
    (r"(?P<n>\d+) selecciones", "{n} selections"),
    (r"aproximado: (?P<legs_list>.+) se combina como si no dependiera del resultado",
     "approximate: {legs_list} combined as if it did not depend on the result"),
    (r"fuera del modelo: (?P<legs>.+)", "outside the model: {legs}"),
    (r"sin proyección del jugador \(no figura en la alineación o está de baja\): (?P<legs_list>.+)",
     "no player projection (not in the line-up or unavailable): {legs_list}"),
    (r"no se pudo calcular «(?P<leg_t>.+?)»: (?P<err_t>.+)", "could not calculate “{leg_t}”: {err_t}"),
    (r"el modelo no puede calcular estas selecciones junto con las demás \(pueden devolverse\): (?P<legs_list>.+)",
     "the model cannot calculate these selections together with the others (they can be refunded): {legs_list}"),
    (r"el modelo no puede calcular estas selecciones juntas: (?P<legs_list>.+)",
     "the model cannot calculate these selections together: {legs_list}"),
    # Sincronización (sync.py)
    (r"Se sincronizó hace poco: vuelve a intentarlo en (?P<n>\d+) min\.", "Synced recently: try again in {n} min."),
    (r"Falló en «(?P<step_t>.+?)»: (?P<rest>.*)", "Failed at “{step_t}”: {rest}"),
    # Errores con datos
    (r"No encuentro el equipo '(?P<x>.*)'", "Can't find the team '{x}'"),
    (r"No encuentro al jugador '(?P<x>.*)'", "Can't find the player '{x}'"),
    (r"No encuentro al árbitro '(?P<x>.*)'", "Can't find the referee '{x}'"),
    (r"No existe el partido (?P<x>.+)", "Match {x} does not exist"),
    (r"No existe la captura (?P<x>.+)", "Screenshot {x} does not exist"),
    (r"No hay partido próximo para '(?P<x>.*)' en los próximos (?P<n>\d+) días",
     "No upcoming match for '{x}' in the next {n} days"),
    (r"Sin escudo para el equipo (?P<x>.+)", "No crest for team {x}"),
    (r"La apuesta (?P<x>\d+) no es una apuesta del día perdida", "Bet {x} is not a lost bet of the day"),
    (r"Como máximo (?P<n>\d+) selecciones por cupón\.", "At most {n} selections per slip."),
    (r"No se encontró el partido: (?P<x>.+)", "Match not found: {x}"),
    (r"No se encontró el jugador: (?P<x>.+)", "Player not found: {x}"),
    (r"Falta la línea de «(?P<x>.+)» en el cupón: sin ella no se puede liquidar\.",
     "The line of “{x}” is missing in the slip: without it the bet cannot be settled."),
    (r"Falta la línea de la apuesta \((?P<x>.+)\): sin ella no se puede liquidar\.",
     "The bet's line is missing ({x}): without it the bet cannot be settled."),
    (r"Moneda no admitida: (?P<x>.+)\. Usa (?P<y>.+)\.", "Currency not supported: {x}. Use {y}."),
    (r"Estadística sin modelo: (?P<x>.+)", "Stat without a model: {x}"),
    (r"Mercado no soportado: (?P<x>.+)", "Market not supported: {x}"),
    (r"Mercado de jugador no soportado: (?P<x>.+)", "Player market not supported: {x}"),
    (r"Selección no válida: (?P<x>.+)", "Invalid selection: {x}"),
    (r"La imagen pesa más de (?P<n>[\d.]+) MB", "The image is larger than {n} MB"),
    (r"(?P<x>.+) no está en el radar de ahora", "{x} is not on the radar right now"),
]
_COMPILED = [(re.compile(p), r) for p, r in PATTERNS]


def _fill(template: str, m: re.Match[str]) -> str:
    vals = {}
    for k, v in m.groupdict(default="").items():
        if k.endswith("_t"):
            v = text(v)
        elif k.endswith("_list"):
            v = ", ".join(text(p) for p in v.split(", "))
        elif k.endswith("_and"):
            v = v.replace(" y ", " and ")
        vals[k] = v
    return template.format(**vals)


@lru_cache(maxsize=16384)
def text(s: str) -> str:
    """Un texto de la API en inglés, o tal cual si no está en el catálogo."""
    if s in EXACT:
        return EXACT[s]
    if " " not in s:
        return s
    for pattern, repl in _COMPILED:
        m = pattern.fullmatch(s)
        if m:
            return repl(m) if callable(repl) else _fill(repl, m)
    return s


def translate(value):
    """Traduce los textos (no las claves) de una respuesta JSON ya decodificada."""
    if isinstance(value, str):
        return text(value)
    if isinstance(value, list):
        return [translate(v) for v in value]
    if isinstance(value, dict):
        return {k: translate(v) for k, v in value.items()}
    return value
