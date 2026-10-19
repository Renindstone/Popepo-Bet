"""Understat: xG por partido (un segundo modelo de xG para promediar con el de Opta/FotMob)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from apuestas.ingest.http import client

BASE = "https://understat.com"


@dataclass
class USMatch:
    understat_id: int
    kickoff_utc: datetime
    home: str
    away: str
    is_result: bool
    home_goals: int | None
    away_goals: int | None
    home_xg: float | None
    away_xg: float | None


def league_season(league: str, start_year: int, ttl: float | None = 6 * 3600) -> list[USMatch]:
    data = client().get_json(
        f"{BASE}/getLeagueData/{league}/{start_year}",
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}/league/{league}/{start_year}"},
        ttl=ttl,
    )
    out = []
    for m in data.get("dates", []):
        is_result = bool(m.get("isResult"))
        goals, xg = m.get("goals") or {}, m.get("xG") or {}
        # Understat publica horas en UTC
        ko = datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        out.append(
            USMatch(
                understat_id=int(m["id"]),
                kickoff_utc=ko,
                home=m["h"]["title"],
                away=m["a"]["title"],
                is_result=is_result,
                home_goals=int(goals["h"]) if is_result and goals.get("h") is not None else None,
                away_goals=int(goals["a"]) if is_result and goals.get("a") is not None else None,
                home_xg=float(xg["h"]) if is_result and xg.get("h") is not None else None,
                away_xg=float(xg["a"]) if is_result and xg.get("a") is not None else None,
            )
        )
    return out
