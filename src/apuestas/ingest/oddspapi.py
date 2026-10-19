"""OddsPapi (opcional, requiere clave gratuita en https://oddspapi.io): cuotas de Betano y Pinnacle.

EXPERIMENTAL: escrito a partir de la documentación pública sin una clave para probarlo. El mercado
1X2 (id 101) está documentado; el resto se intenta mapear con el catálogo de mercados de la API.
Betano Perú (betano.pe) es un espejo de la cuota global de Betano según OddsPapi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apuestas.config import get_settings
from apuestas.core import names
from apuestas.core.competitions import FULL
from apuestas.db.session import session_scope
from apuestas.ingest import store
from apuestas.ingest.http import client

log = logging.getLogger(__name__)
BASE = "https://api.oddspapi.io/v4"
BOOKMAKERS = ("betano", "pinnacle", "bet365")
TOURNAMENT_NAMES = {"EPL": ("premier league", "england"), "BUN": ("bundesliga", "germany"),
                    "LAL": ("laliga", "spain"), "UCL": ("champions league", "")}
OUTCOMES_1X2 = {"101": "home", "102": "draw", "103": "away"}


@dataclass
class Price:
    bookmaker: str
    market: str
    selection: str
    line: float | None
    price: float
    kind: str = "live"


def _get(path: str, ttl: float = 600, **params) -> object:
    key = get_settings().oddspapi_key
    if not key:
        raise RuntimeError("Falta APUESTAS_ODDSPAPI_KEY")
    return client().get_json(f"{BASE}/{path}", params={**params, "apiKey": key}, ttl=ttl)


def tournament_ids() -> dict[str, str]:
    data = _get("tournaments", ttl=7 * 86400, sportId=10)
    out = {}
    for t in data if isinstance(data, list) else data.get("data", []):
        name = names.normalize(t.get("tournamentName", ""))
        cat = names.normalize(t.get("categoryName", ""))
        for code, (tname, tcat) in TOURNAMENT_NAMES.items():
            if code not in out and name == names.normalize(tname) and (not tcat or tcat in cat):
                out[code] = str(t["tournamentId"])
    return out


def market_catalog() -> dict[str, tuple[str, float | None, dict[str, str]]]:
    """marketId -> (mercado interno, línea, {outcomeId: selección}). Vacío si el endpoint no existe."""
    try:
        data = _get("markets", ttl=7 * 86400, sportId=10)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for mk in data if isinstance(data, list) else data.get("data", []):
        name = (mk.get("marketName") or "").lower()
        line = mk.get("handicap")
        outcomes = {str(o.get("outcomeId")): (o.get("outcomeName") or "").lower() for o in mk.get("outcomes", [])}
        if "over" in name or "total" in name:
            sel = {k: ("over" if "over" in v else "under") for k, v in outcomes.items()}
            out[str(mk["marketId"])] = ("ou_goals", float(line) if line is not None else None, sel)
        elif "handicap" in name and "asian" in name:
            sel = {k: ("home" if v in ("1", "home") else "away") for k, v in outcomes.items()}
            out[str(mk["marketId"])] = ("ah", float(line) if line is not None else None, sel)
        elif "both teams" in name:
            sel = {k: ("yes" if "yes" in v else "no") for k, v in outcomes.items()}
            out[str(mk["marketId"])] = ("btts", None, sel)
    return out


def parse_fixture_odds(fx: dict, catalog: dict) -> list[Price]:
    prices = []
    for book, bdata in (fx.get("bookmakerOdds") or {}).items():
        if book not in BOOKMAKERS:
            continue
        for market_id, mdata in (bdata.get("markets") or {}).items():
            if market_id == "101":
                market, line, sel_map = "1x2", None, OUTCOMES_1X2
            elif market_id in catalog:
                market, line, sel_map = catalog[market_id]
            else:
                continue
            for outcome_id, odata in (mdata.get("outcomes") or {}).items():
                sel = sel_map.get(str(outcome_id))
                player = ((odata.get("players") or {}).get("0") or {})
                price = player.get("price")
                if sel and price and player.get("active", True):
                    ln = line
                    if market == "ah" and line is not None and sel == "away":
                        ln = -line
                    prices.append(Price(book, market, sel, ln, float(price)))
    return prices


def sync_upcoming() -> int:
    tids = tournament_ids()
    catalog = market_catalog()
    if not tids:
        log.warning("OddsPapi: no se encontraron los torneos")
        return 0
    n = 0
    now = datetime.now(UTC)
    for code in [c.code for c in FULL]:
        if code not in tids:
            continue
        for book in BOOKMAKERS:
            data = _get("odds-by-tournaments", ttl=900, bookmaker=book, tournamentIds=tids[code])
            fixtures = data if isinstance(data, list) else data.get("data", [])
            with session_scope() as s:
                comp = store.ensure_competitions(s)[code]
                for fx in fixtures:
                    start = datetime.fromisoformat(fx["startTime"].replace("Z", "+00:00"))
                    if start < now or start > now + timedelta(days=7):
                        continue
                    home = fx.get("participant1Name") or ""
                    away = fx.get("participant2Name") or ""
                    match = store.find_match(s, comp.id, start, home, away, window_hours=3) if home else None
                    if match is None:
                        continue
                    n += store.store_odds(s, match, parse_fixture_odds(fx, catalog), "oddspapi")
    return n
