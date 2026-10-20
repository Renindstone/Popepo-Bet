"""football-data.co.uk: resultados, estadísticas básicas, árbitro (Inglaterra) y cuotas.

Incluye cuotas de bet365 (previas y de cierre), Betfair Exchange y Pinnacle (referencias "afiladas"),
y desde 2026-27 también xG. `fixtures.csv` trae las cuotas de los próximos partidos.

Las ligas "extra" (new/XXX.csv: Austria, Dinamarca, Noruega...) usan otro formato: un archivo con todas
las temporadas, solo resultado y 1X2 de cierre (Pinnacle hasta 2025, bet365, Betfair Exchange, media y máxima).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apuestas.core.competitions import fd_season_code
from apuestas.ingest.http import client

BASE = "https://www.football-data.co.uk"
UK = ZoneInfo("Europe/London")

BOOKS = {"B365": "bet365", "BFE": "betfair_ex", "PS": "pinnacle", "Avg": "avg", "Max": "max"}
# En O/U y hándicap asiático Pinnacle usa el prefijo "P"
OU_PREFIX = {"B365": "bet365", "BFE": "betfair_ex", "P": "pinnacle", "Avg": "avg", "Max": "max"}


@dataclass
class FDOdds:
    bookmaker: str
    market: str  # 1x2 | ou_goals | ah
    selection: str
    line: float | None
    price: float
    kind: str  # opening | closing


# Formato de las ligas extra -> nombres de columna del formato principal
EXTRA_COLUMNS = {"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG"}
# Un mismo club con dos grafías en el mismo archivo (cambian de una temporada a otra)
RENAMES = {"Ham-Kam": "HamKam", "Din. Bucuresti": "Dinamo Bucuresti", "Gornik Z.": "Gornik Zabrze"}


@dataclass
class FDRow:
    div: str
    kickoff_utc: datetime
    home: str
    away: str
    referee: str | None
    season: int | None = None  # año de inicio (solo en las ligas extra; "2025/2026" -> 2025, "2025" -> 2025)
    home_goals: int | None = None
    away_goals: int | None = None
    home_goals_ht: int | None = None
    away_goals_ht: int | None = None
    stats: dict[str, dict[str, float]] = field(default_factory=dict)  # "home"/"away" -> stat -> value
    odds: list[FDOdds] = field(default_factory=list)


def _f(row: dict, key: str) -> float | None:
    v = (row.get(key) or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _i(row: dict, key: str) -> int | None:
    v = _f(row, key)
    return int(v) if v is not None else None


def _kickoff(row: dict) -> datetime:
    date_s = row["Date"].strip()
    fmt = "%d/%m/%Y" if len(date_s.split("/")[-1]) == 4 else "%d/%m/%y"
    d = datetime.strptime(date_s, fmt)
    t = (row.get("Time") or "15:00").strip() or "15:00"
    hh, mm = (int(x) for x in t.split(":")[:2])
    return d.replace(hour=hh, minute=mm, tzinfo=UK).astimezone(UTC)


def _odds(row: dict) -> list[FDOdds]:
    out: list[FDOdds] = []

    def add(book: str, market: str, sel: str, line: float | None, key: str, kind: str) -> None:
        price = _f(row, key)
        if price and price > 1.0:
            out.append(FDOdds(book, market, sel, line, price, kind))

    for kind, c in (("opening", ""), ("closing", "C")):
        for prefix, book in BOOKS.items():
            for sel, suf in (("home", "H"), ("draw", "D"), ("away", "A")):
                add(book, "1x2", sel, None, f"{prefix}{c}{suf}", kind)
        for prefix, book in OU_PREFIX.items():
            add(book, "ou_goals", "over", 2.5, f"{prefix}{c}>2.5", kind)
            add(book, "ou_goals", "under", 2.5, f"{prefix}{c}<2.5", kind)
        line = _f(row, "AHh" if not c else "AHCh")
        if line is not None:
            for prefix, book in OU_PREFIX.items():
                add(book, "ah", "home", line, f"{prefix}{c}AHH", kind)
                add(book, "ah", "away", -line, f"{prefix}{c}AHA", kind)
    return out


def parse_csv(text: str) -> list[FDRow]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    rows: list[FDRow] = []
    for r in reader:
        for extra, main in EXTRA_COLUMNS.items():
            if extra in r and main not in r:
                r[main] = r[extra]
        if not r.get("HomeTeam") or not r.get("Date"):
            continue
        season = (r.get("Season") or "").strip()[:4]
        home, away = r["HomeTeam"].strip(), r["AwayTeam"].strip()
        row = FDRow(
            div=r.get("Div", "").strip(),
            kickoff_utc=_kickoff(r),
            home=RENAMES.get(home, home),
            away=RENAMES.get(away, away),
            referee=(r.get("Referee") or "").strip() or None,
            season=int(season) if season.isdigit() else None,
            home_goals=_i(r, "FTHG"),
            away_goals=_i(r, "FTAG"),
            home_goals_ht=_i(r, "HTHG"),
            away_goals_ht=_i(r, "HTAG"),
        )
        for side, p in (("home", "H"), ("away", "A")):
            st = {
                "xg": _f(r, f"{p}xG"),
                "shots": _f(r, f"{p}S"),
                "shots_on_target": _f(r, f"{p}ST"),
                "fouls": _f(r, f"{p}F"),
                "corners": _f(r, f"{p}C"),
                "yellow_cards": _f(r, f"{p}Y"),
                "red_cards": _f(r, f"{p}R"),
            }
            row.stats[side] = {k: v for k, v in st.items() if v is not None}
        row.odds = _odds(r)
        rows.append(row)
    return rows


def _decode(raw: bytes) -> str:
    """Los CSV vienen en UTF-8 con BOM o en latin-1 según la temporada."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1").lstrip("\u00ef\u00bb\u00bf")


def season_rows(fd_code: str, start_year: int, ttl: float | None = 6 * 3600) -> list[FDRow]:
    url = f"{BASE}/mmz4281/{fd_season_code(start_year)}/{fd_code}.csv"
    return parse_csv(_decode(client().get_bytes(url, ttl=ttl)))


def extra_league_rows(fd_extra: str, ttl: float | None = 6 * 3600) -> list[FDRow]:
    """Liga extra: todas las temporadas en un solo archivo (se actualiza durante la temporada)."""
    return parse_csv(_decode(client().get_bytes(f"{BASE}/new/{fd_extra}.csv", ttl=ttl)))


def upcoming_rows(ttl: float = 3 * 3600) -> list[FDRow]:
    """Próximos partidos con cuotas (se actualiza varias veces por semana)."""
    return parse_csv(_decode(client().get_bytes(f"{BASE}/fixtures.csv", ttl=ttl)))
