"""OddsPapi (opcional, cuenta gratuita en https://oddspapi.io): cuotas de Betano para los próximos partidos.

Así se activa:
1. Crea la cuenta gratuita. En ella eliges qué casa(s) de apuestas incluye tu suscripción; para este proyecto,
   Betano. bet365 y Pinnacle ya llegan gratis por football-data.
2. Copia la clave de la cuenta en `.env`: `APUESTAS_ODDSPAPI_KEY=...`. Las casas se eligen con
   `APUESTAS_ODDSPAPI_BOOKMAKERS` (por defecto `betano.pe,pinnacle`; cada casa = 1 petición al día).
3. Comprueba con `apuestas ingest oddspapi --estado` (cuota mensual) y `apuestas ingest oddspapi` (descarga).

El plan gratuito tiene un límite mensual de peticiones (250 en oct-2026) y **cada llamada cuenta**, aunque falle.
La API solo admite una casa por petición y **como mucho 5 torneos** por petición, así que:
- una descarga = 1 llamada por casa con las competiciones que juegan en los próximos 3 días
  (`oddspapi_window_days`; cuenta 1 aunque traiga varios torneos). Si son las seis (semanas de Champions), 2
  llamadas por casa. Nombres de equipos (participants), torneos y mercados se piden una vez por semana;
- el worker la lanza una vez al día (08:30) → con 2 casas, unas 60-90 llamadas al mes más ~12 de catálogos;
- y, para el CLV, una de Pinnacle unos 15 min antes de cada hora de inicio con apuestas abiertas que pasan el
  corte, como mucho `oddspapi_closing_per_day` al día (3: unas 40-90 al mes; `sync_closing`).

Probado con una clave real (19-10-2026). Los mercados se reconocen por su tipo (`marketType`) y su nombre exacto:
goles, ambos marcan, hándicaps asiático y europeo, y córners y tarjetas (total, por equipo y hándicap).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from apuestas.config import get_settings
from apuestas.db import models as m
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
    "SA": ("serie-a", "italy"),
    "L1": ("ligue-1", "france"),
    "UCL": ("uefa-champions-league", "international-clubs"),
}
# La API rechaza más de 5 torneos por petición (400 INVALID_PARAMETER, visto el 22-10-2026 con seis competiciones)
MAX_TOURNAMENTS = 5
OUTCOMES_1X2 = {"101": "home", "102": "draw", "103": "away"}
# Tipo de mercado de OddsPapi -> (nuestro mercado, nombre exacto del mercado a partido completo)
MARKET_TYPES = {
    "totals": ("ou_goals", "Over Under Full Time"),
    "teamtotals-team1": ("ou_goals_home", "Over Under Team 1"),
    "teamtotals-team2": ("ou_goals_away", "Over Under Team 2"),
    "bothteamsscore": ("btts", "Both Teams To Score"),
    "spreads": ("ah", "Asian Handicap"),
    "spreads-european": ("eh", "European Handicap"),  # el hándicap "normal" (3 vías) de Betano
    "totals-corners": ("ou_corners", "Corners - Over Under Full Time"),
    "teamtotals-corners-team1": ("ou_corners_home", "Corners - Over Under Team 1"),
    "teamtotals-corners-team2": ("ou_corners_away", "Corners - Over Under Team 2"),
    "spreads-corners": ("ah_corners", "Corners - Handicap"),
    # "Bookings" = número de tarjetas (no puntos de tarjeta: las líneas van de 0,5 a 14,5)
    "totals-bookings": ("ou_cards", "Bookings - Over Under Full Time"),
    "teamtotals-bookings-team1": ("ou_cards_home", "Bookings - Over Under Team 1"),
    "teamtotals-bookings-team2": ("ou_cards_away", "Bookings - Over Under Team 2"),
    "spreads-bookings": ("ah_cards", "Bookings - Handicap"),
}
_OUTCOME_NAMES = {"over": "over", "under": "under", "yes": "yes", "no": "no", "1": "home", "x": "draw", "2": "away"}

@dataclass
class Price:
    bookmaker: str
    market: str
    selection: str
    line: float | None
    price: float
    kind: str = "live"


def _get(path: str, ttl: float, store: bool = True, **params) -> object:
    key = get_settings().oddspapi_key
    if not key:
        raise RuntimeError("Falta APUESTAS_ODDSPAPI_KEY en .env")
    return client().get_json(f"{BASE}/{path}", params={**params, "apiKey": key}, ttl=ttl, store=store)


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
    return [b.strip().lower() for b in get_settings().oddspapi_bookmakers.split(",") if b.strip()]


def our_name(slug: str) -> str:
    """Slug de OddsPapi -> nombre de la casa en nuestro sistema ("betano.pe" -> "betano")."""
    for base in ("betano", "bet365", "pinnacle"):
        if slug == base or slug.startswith(base + "."):
            return base
    return slug


def account_status() -> dict:
    """Peticiones usadas y disponibles este mes (sin caché: es lo que se quiere ver)."""
    data = _get("account", ttl=0, store=False)  # la respuesta incluye la clave: no se guarda en la caché
    subs = data.get("subscriptions", []) if isinstance(data, dict) else []
    active = next((x for x in subs if x.get("is_active")), subs[0] if subs else {})
    return {
        "peticiones_usadas": active.get("request_count"),
        "limite_mensual": active.get("request_limit"),
        "casas_incluidas": len(active.get("bookmakers") or {}),
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
        spec = MARKET_TYPES.get(mk.get("marketType") or "")
        if spec is None or mk.get("playerProp") or (mk.get("period") or "").lower() != "fulltime":
            continue
        market, name = spec
        if (mk.get("marketName") or "").strip() != name:
            continue
        sel = {str(o.get("outcomeId")): _OUTCOME_NAMES.get((o.get("outcomeName") or "").strip().lower())
               for o in mk.get("outcomes", [])}
        if None in sel.values():
            continue
        line = None if market == "btts" else float(mk.get("handicap") or 0.0)
        out[str(mk.get("marketId"))] = (market, line, sel)
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
                if market.startswith("ah") and line is not None and sel == "away":
                    ln = -line  # en nuestros hándicaps asiáticos la línea es la del equipo elegido; en "eh", la del local
                prices.append(Price(our_name(book), market, sel, ln, float(price)))
    return prices


# --------------------------------------------------------------------------- coherencia de las cuotas
# OddsPapi a veces junta en un mismo partido cuotas de un evento de la casa con local y visitante invertidos
# (Betano en Atlético - Deportivo, 24-10-2026: 1X2, hándicaps positivos y goles por equipo al revés; hándicaps
# negativos bien). La respuesta no trae el nombre del equipo de cada selección, así que no se puede dar la vuelta
# con seguridad: las cuotas de esa casa para ese partido se descartan.
LINE_TOLERANCE = 1.10  # una línea más favorable nunca paga más; 10 % de margen por redondeos de la casa
REVERSED_GAP = 0.25  # diferencia mínima en la probabilidad implícita del local frente a Pinnacle


def incoherent_lines(prices: list[Price]) -> str | None:
    """Primer mercado cuyas líneas alternativas no son monótonas (o None si todas lo son).

    Con más hándicap a favor, o un over más bajo, la cuota nunca sube. Si sube, el partido mezcla cuotas de dos
    orientaciones distintas. El empate del hándicap europeo no es monótono y no se mira.
    """
    groups: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for p in prices:
        if p.line is not None and p.selection != "draw":
            groups.setdefault((p.market, p.selection), []).append((p.line, p.price))
    for (market, sel), pts in groups.items():
        # La cuota sube con la línea en el over y en el visitante del hándicap europeo (la línea es la del local)
        rising = sel == "over" or (market == "eh" and sel == "away")
        pts.sort()
        for (l1, p1), (l2, p2) in zip(pts, pts[1:], strict=False):
            if l1 != l2 and (p1 > p2 * LINE_TOLERANCE if rising else p2 > p1 * LINE_TOLERANCE):
                return f"{market} {sel}: {l1:+g} @{p1} y {l2:+g} @{p2}"
    return None


def reversed_1x2(prices: list[Price], ref: dict[str, float]) -> bool:
    """¿El favorito del 1X2 es el contrario que en la referencia (Pinnacle) y por mucho?"""
    own = {p.selection: p.price for p in prices if p.market == "1x2"}
    if not all(sel in own and sel in ref for sel in ("home", "away")):
        return False
    if (own["home"] < own["away"]) == (ref["home"] < ref["away"]):
        return False
    return abs(1 / own["home"] - 1 / ref["home"]) >= REVERSED_GAP


def rejection_reason(prices: list[Price], ref: dict[str, float] | None) -> str | None:
    """Motivo para descartar las cuotas de una casa en un partido, o None si parecen coherentes."""
    if ref and reversed_1x2(prices, ref):
        own = {p.selection: p.price for p in prices if p.market == "1x2"}
        return (f"1X2 al revés que Pinnacle: local {own['home']} / visitante {own['away']} "
                f"frente a {ref['home']} / {ref['away']}")
    bad = incoherent_lines(prices)
    return f"líneas incoherentes, {bad}" if bad else None


def participants() -> dict[str, str]:
    """participantId -> nombre del equipo (la respuesta de cuotas solo trae ids). Una llamada por semana."""
    data = _get("participants", ttl=7 * 86400, sportId=SOCCER)
    return {str(k): v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}


def playing_soon(days: float, now: datetime | None = None) -> set[str]:
    """Competiciones con algún partido programado en los próximos `days` días (las demás no gastan petición)."""
    now = now or datetime.now(UTC)
    with session_scope() as s:
        return set(s.scalars(
            select(m.Competition.code).join(m.Match, m.Match.competition_id == m.Competition.id)
            .where(m.Match.status == "scheduled", m.Match.kickoff_utc >= now,
                   m.Match.kickoff_utc <= now + timedelta(days=days)).distinct()))


def tournament_groups(tids: dict[str, int], codes: set[str]) -> list[list[int]]:
    """Torneos a pedir, en grupos de como mucho MAX_TOURNAMENTS (cada grupo es una petición por casa)."""
    ids = [tid for code, tid in tids.items() if code in codes]
    return [ids[i:i + MAX_TOURNAMENTS] for i in range(0, len(ids), MAX_TOURNAMENTS)]


def sync_upcoming(books: list[str] | None = None, codes: set[str] | None = None, ttl: float = 1800) -> int:
    """Cuotas de las casas configuradas para las competiciones que juegan pronto (o solo `books` y `codes`)."""
    books = books or bookmakers()
    if not books:
        raise RuntimeError("APUESTAS_ODDSPAPI_BOOKMAKERS está vacío")
    tids = tournament_ids()
    if not tids:
        log.warning("OddsPapi: no se encontraron los torneos")
        return 0
    now = datetime.now(UTC)
    groups = tournament_groups(tids, playing_soon(get_settings().oddspapi_window_days, now) if codes is None else codes)
    if not groups:
        log.info("OddsPapi: ninguna competición juega en los próximos días; no se gasta ninguna petición")
        return 0
    catalog = market_catalog()
    team_names = participants()
    code_of = {tid: code for code, tid in tids.items()}
    # La API exige una sola casa y como mucho 5 torneos por petición: 1 llamada por casa y grupo. Se descargan
    # todas antes de guardar para que el 1X2 de Pinnacle sirva de referencia a las demás casas.
    odds = {book: [fx for group in groups
                   for fx in _items(_get("odds-by-tournaments", ttl=ttl, bookmaker=book,
                                         tournamentIds=",".join(str(t) for t in group)))]
            for book in books}
    sharp = {fx.get("fixtureId"): {p.selection: p.price for p in parse_fixture_odds(fx, {}, [book])}
             for book, fixtures in odds.items() if our_name(book) == "pinnacle" for fx in fixtures}
    n = matched = 0
    unmatched: list[str] = []
    rejected: list[str] = []
    for book, fixtures in odds.items():
        name = our_name(book)
        with session_scope() as s:
            comps = store.ensure_competitions(s)
            for fx in fixtures:
                code = code_of.get(int(fx.get("tournamentId") or 0))
                home = team_names.get(str(fx.get("participant1Id")))
                away = team_names.get(str(fx.get("participant2Id")))
                if not (code and home and away and fx.get("startTime")):
                    continue
                start = datetime.fromisoformat(fx["startTime"].replace("Z", "+00:00"))
                if start < now or start > now + timedelta(days=7):
                    continue
                match = store.find_match(s, comps[code].id, start, home, away, window_hours=3)
                if match is None:
                    unmatched.append(f"{code} {home} vs {away}")
                    continue
                matched += 1
                prices = parse_fixture_odds(fx, catalog, [book])
                ref = None
                if name != "pinnacle":  # Pinnacle de esta misma descarga o, si no vino, la última guardada
                    ref = sharp.get(fx.get("fixtureId")) or store.latest_1x2(s, match, "pinnacle")
                why = rejection_reason(prices, ref)
                if why:
                    # Las cuotas anteriores de esta casa en el partido vienen del mismo emparejamiento: fuera también
                    dropped = store.drop_odds(s, match, name, "oddspapi")
                    log.warning("OddsPapi: descarto %s en %s %s vs %s (%s); %d cuotas anteriores borradas",
                                name, code, home, away, why, dropped)
                    rejected.append(f"{name} {home} vs {away}")
                    continue
                n += store.store_odds(s, match, prices, "oddspapi")
    if unmatched:
        log.info("OddsPapi sin partido en nuestra BD: %s", "; ".join(sorted(set(unmatched))[:20]))
    log.info("OddsPapi: %d partido-casa emparejados, %d descartados, %d cuotas nuevas (%s)",
             matched, len(rejected), n, ",".join(books))
    return n


def sync_closing(codes: set[str]) -> int:
    """Pinnacle poco antes del inicio, para el CLV (`picks.closing_reference`): 1 petición por cada 5 torneos."""
    return sync_upcoming(books=["pinnacle"], codes=codes, ttl=300)
