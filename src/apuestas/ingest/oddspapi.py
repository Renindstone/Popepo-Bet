"""OddsPapi (opcional, cuenta gratuita en https://oddspapi.io): cuotas de Betano para los próximos partidos.

Así se activa:
1. Crea la cuenta gratuita. En ella eliges qué casa(s) de apuestas incluye tu suscripción; para este proyecto,
   Betano. bet365 y Pinnacle ya llegan gratis por football-data.
2. Copia la clave de la cuenta en `.env`: `APUESTAS_ODDSPAPI_KEY=...`. Si incluiste otras casas, ponlas en
   `APUESTAS_ODDSPAPI_BOOKMAKERS=betano,pinnacle` (máximo 3).
3. Comprueba con `apuestas ingest oddspapi --estado` (cuota mensual) y `apuestas ingest oddspapi` (descarga).

El plan gratuito tiene un límite mensual de peticiones y **cada llamada cuenta**, aunque falle. Por eso:
- una descarga = 1 llamada de cuotas para las 4 competiciones a la vez + 1 de calendario por competición
  (los nombres de los equipos solo vienen ahí), más torneos y mercados una vez por semana;
- el worker la lanza una vez al día (08:30, previa) → unas 150 llamadas al mes.

Escrito con la documentación v4 (oct-2026). Partes sin verificar con una clave real: el signo de la línea del
hándicap asiático (se asume que es la del local) y que la cuota de Betano global coincida con betano.pe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apuestas.config import get_settings
from apuestas.core.competitions import FULL
from apuestas.db.session import session_scope
from apuestas.ingest import store
from apuestas.ingest.http import client

log = logging.getLogger(__name__)
BASE = "https://api.oddspapi.io/v4"
SOCCER = 10
# Nuestro código -> (slug del torneo, slug de la categoría) en OddsPapi
TOURNAMENTS = {
    "EPL": ("premier-league", "england"),
    "BUN": ("bundesliga", "germany"),
    "LAL": ("laliga", "spain"),
    "UCL": ("uefa-champions-league", "international-clubs"),
}
OUTCOMES_1X2 = {"101": "home", "102": "draw", "103": "away"}
# Variantes que no son el mercado del partido completo ("Both Teams To Score" sí entra: no lleva estas palabras)
_EXCLUDE = ("corner", "card", "booking", "half", "team total", "home team", "away team", "1st", "2nd", "player",
            "minute", "exact", "range", "odd even")


@dataclass
class Price:
    bookmaker: str
    market: str
    selection: str
    line: float | None
    price: float
    kind: str = "live"


def _get(path: str, ttl: float, **params) -> object:
    key = get_settings().oddspapi_key
    if not key:
        raise RuntimeError("Falta APUESTAS_ODDSPAPI_KEY en .env")
    return client().get_json(f"{BASE}/{path}", params={**params, "apiKey": key}, ttl=ttl)


def _items(data: object) -> list[dict]:
    """Las respuestas pueden venir como lista, como {"data": [...]} o como objeto indexado por id."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return data["data"]
        if "fixtureId" in data:
            return [data]
        return [v for v in data.values() if isinstance(v, dict)]
    return []


def bookmakers() -> list[str]:
    books = [b.strip().lower() for b in get_settings().oddspapi_bookmakers.split(",") if b.strip()]
    return books[:3]  # la API admite como mucho 3 por llamada


def account_status() -> dict:
    """Peticiones usadas y disponibles este mes (sin caché: es lo que se quiere ver)."""
    data = _get("account", ttl=0)
    subs = data.get("subscriptions", []) if isinstance(data, dict) else []
    active = next((x for x in subs if x.get("is_active")), subs[0] if subs else {})
    return {
        "peticiones_usadas": active.get("request_count"),
        "limite_mensual": active.get("request_limit"),
        "casas_incluidas": sorted((active.get("bookmakers") or {}).keys()),
        "casas_configuradas": bookmakers(),
        "valida_hasta": active.get("valid_until"),
    }


def tournament_ids() -> dict[str, int]:
    out = {}
    for t in _items(_get("tournaments", ttl=7 * 86400, sportId=SOCCER)):
        for code, (slug, cat) in TOURNAMENTS.items():
            if code not in out and t.get("tournamentSlug") == slug and t.get("categorySlug") == cat:
                out[code] = int(t["tournamentId"])
    return out


def market_catalog(data: object | None = None) -> dict[str, tuple[str, float | None, dict[str, str]]]:
    """marketId -> (mercado interno, línea, {outcomeId: selección}). Solo partido completo y sin props."""
    if data is None:
        data = _get("markets", ttl=7 * 86400)
    out: dict[str, tuple[str, float | None, dict[str, str]]] = {}
    for mk in _items(data):
        name = (mk.get("marketName") or "").lower()
        if mk.get("playerProp") or (mk.get("period") or "fulltime").lower() != "fulltime":
            continue
        if any(w in name for w in _EXCLUDE):
            continue
        outcomes = {str(o.get("outcomeId")): (o.get("outcomeName") or "").strip().lower()
                    for o in mk.get("outcomes", [])}
        line = mk.get("handicap")
        mid = str(mk.get("marketId"))
        if mid == "101":
            continue  # 1X2: se trata aparte
        if "both teams to score" in name:
            out[mid] = ("btts", None, {k: "yes" if v.startswith("y") else "no" for k, v in outcomes.items()})
        elif "asian handicap" in name and line is not None:
            out[mid] = ("ah", float(line), {k: "home" if v in ("1", "home") else "away" for k, v in outcomes.items()})
        elif name.startswith("over under") and line is not None:
            out[mid] = ("ou_goals", float(line), {k: "over" if v.startswith("o") else "under" for k, v in outcomes.items()})
    return out


def parse_fixture_odds(fx: dict, catalog: dict, books: list[str]) -> list[Price]:
    prices = []
    for book, bdata in (fx.get("bookmakerOdds") or {}).items():
        if book not in books or not isinstance(bdata, dict):
            continue
        for market_id, mdata in (bdata.get("markets") or {}).items():
            if str(market_id) == "101":
                market, line, sel_map = "1x2", None, OUTCOMES_1X2
            elif str(market_id) in catalog:
                market, line, sel_map = catalog[str(market_id)]
            else:
                continue
            for outcome_id, odata in (mdata.get("outcomes") or {}).items():
                sel = sel_map.get(str(outcome_id))
                player = (odata.get("players") or {}).get("0") or {}
                price = player.get("price")
                if not sel or not price or player.get("active") is False or float(price) <= 1.0:
                    continue
                ln = line
                if market == "ah" and line is not None and sel == "away":
                    ln = -line  # en nuestro "ah" la línea es la del equipo elegido
                prices.append(Price(book, market, sel, ln, float(price)))
    return prices


def fixtures(tournament_id: int) -> dict[str, dict]:
    """fixtureId -> partido con nombres y hora (los nombres no vienen en la respuesta de cuotas)."""
    return {str(f["fixtureId"]): f for f in _items(_get("fixtures", ttl=12 * 3600, tournamentId=tournament_id))
            if f.get("fixtureId")}


def sync_upcoming() -> int:
    books = bookmakers()
    if not books:
        raise RuntimeError("APUESTAS_ODDSPAPI_BOOKMAKERS está vacío")
    tids = tournament_ids()
    if not tids:
        log.warning("OddsPapi: no se encontraron los torneos")
        return 0
    catalog = market_catalog()
    codes = [c.code for c in FULL if c.code in tids]
    names_by_fixture: dict[str, tuple[str, dict]] = {}
    for code in codes:
        for fid, f in fixtures(tids[code]).items():
            names_by_fixture[fid] = (code, f)
    odds = _get("odds-by-tournaments", ttl=1800, tournamentIds=",".join(str(tids[c]) for c in codes),
                bookmakers=",".join(books))
    now = datetime.now(UTC)
    n = matched = 0
    with session_scope() as s:
        comps = store.ensure_competitions(s)
        for fx in _items(odds):
            code, f = names_by_fixture.get(str(fx.get("fixtureId")), (None, {}))
            home, away = f.get("participant1Name"), f.get("participant2Name")
            start_raw = fx.get("startTime") or f.get("startTime")
            if not (code and home and away and start_raw):
                continue
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            if start < now or start > now + timedelta(days=7):
                continue
            match = store.find_match(s, comps[code].id, start, home, away, window_hours=3)
            if match is None:
                log.info("OddsPapi sin partido: %s %s vs %s", code, home, away)
                continue
            matched += 1
            n += store.store_odds(s, match, parse_fixture_odds(fx, catalog, books), "oddspapi")
    log.info("OddsPapi: %d partidos emparejados, %d cuotas nuevas (%s)", matched, n, ",".join(books))
    return n

