"""FotMob: calendario, resultados, estadísticas de partido (datos Opta), alineaciones (previstas y
confirmadas), bajas (lesiones/sanciones), árbitro y estadísticas por jugador.

Endpoints públicos que usa la propia web de FotMob. Uso personal y con ritmo moderado.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from apuestas.ingest.http import client

BASE = "https://www.fotmob.com/api/data"

POSITION_BY_USUAL = {0: "GK", 1: "DF", 2: "MF", 3: "FW"}

# clave FotMob -> columna de TeamMatchStats
TEAM_STAT_KEYS = {
    "expected_goals": "xg",
    "total_shots": "shots",
    "ShotsOnTarget": "shots_on_target",
    "corners": "corners",
    "fouls": "fouls",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "Offsides": "offsides",
    "BallPossesion": "possession",
    "keeper_saves": "saves",
    "big_chance": "big_chances",
}

PLAYER_STAT_KEYS = {
    "minutes_played": "minutes",
    "goals": "goals",
    "assists": "assists",
    "total_shots": "shots",
    "ShotsOnTarget": "shots_on_target",
    "expected_goals": "xg",
    "expected_assists": "xa",
    "chances_created": "key_passes",
    "fouls": "fouls_committed",
    "was_fouled": "fouls_won",
    "matchstats.headers.tackles": "tackles",
    "saves": "saves",
    "rating_title": "rating",
}


@dataclass
class FMMatch:
    fotmob_id: int
    kickoff_utc: datetime
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    round: str | None
    status: str
    home_goals: int | None
    away_goals: int | None


@dataclass
class FMPlayer:
    fotmob_id: int
    name: str
    team_fotmob_id: int
    position: str | None
    is_starter: bool
    market_value: float | None
    season_rating: float | None
    shirt: int | None = None
    # Posición en el campo (vista vertical de FotMob, 0-1): x a lo ancho, y desde la portería propia
    x: float | None = None
    y: float | None = None


@dataclass
class FMUnavailable:
    fotmob_id: int
    name: str
    team_fotmob_id: int
    kind: str
    reason: str | None
    expected_return: str | None
    market_value: float | None
    season_rating: float | None


@dataclass
class FMDetails:
    fotmob_id: int
    finished: bool
    cancelled: bool
    kickoff_utc: datetime
    home_id: int
    away_id: int
    home_goals: int | None
    away_goals: int | None
    home_goals_ht: int | None
    away_goals_ht: int | None
    referee: str | None
    referee_country: str | None
    lineup_type: str | None  # predicted | confirmed | None
    players: list[FMPlayer] = field(default_factory=list)
    unavailable: list[FMUnavailable] = field(default_factory=list)
    team_stats: dict[int, dict[str, float]] = field(default_factory=dict)  # team_fotmob_id -> stats
    player_stats: dict[int, dict[str, Any]] = field(default_factory=dict)  # player_fotmob_id -> stats
    cards: dict[int, dict[str, int]] = field(default_factory=dict)  # player_fotmob_id -> {yellow, red}
    team_info: dict[int, dict[str, Any]] = field(default_factory=dict)  # team_fotmob_id -> {formation, coach}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _num(value: Any) -> float | None:
    """'158 (71%)' -> 158 ; '0.90' -> 0.9 ; None -> None"""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).split(" ")[0].replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def league_matches(fotmob_league_id: int, season: str, ttl: float | None = 3600) -> list[FMMatch]:
    data = client().get_json(f"{BASE}/leagues", params={"id": fotmob_league_id, "season": season}, ttl=ttl)
    out = []
    for m in data.get("fixtures", {}).get("allMatches", []):
        st = m.get("status", {})
        status = "scheduled"
        if st.get("cancelled"):
            status = "cancelled" if st.get("reason", {}).get("short") != "PP" else "postponed"
        elif st.get("finished"):
            status = "finished"
        elif st.get("reason", {}).get("short") in ("PP", "Pst"):
            status = "postponed"
        hg = ag = None
        if status == "finished" and st.get("scoreStr"):
            with contextlib.suppress(ValueError):
                hg, ag = (int(x) for x in st["scoreStr"].replace(" ", "").split("-")[:2])
        out.append(
            FMMatch(
                fotmob_id=int(m["id"]),
                kickoff_utc=_parse_dt(st["utcTime"]),
                home_id=int(m["home"]["id"]),
                home_name=m["home"]["name"],
                away_id=int(m["away"]["id"]),
                away_name=m["away"]["name"],
                round=str(m.get("round") or m.get("roundName") or "") or None,
                status=status,
                home_goals=hg,
                away_goals=ag,
            )
        )
    return out


def matches_by_date(day: str, ttl: float = 900) -> dict[int, list[int]]:
    """day='20261019' -> {fotmob_league_id: [match ids]}"""
    data = client().get_json(f"{BASE}/matches", params={"date": day}, ttl=ttl)
    return {int(lg["primaryId"]): [int(m["id"]) for m in lg.get("matches", [])] for lg in data.get("leagues", [])}


def match_details(fotmob_match_id: int, ttl: float | None = 900) -> FMDetails:
    data = client().get_json(f"{BASE}/matchDetails", params={"matchId": fotmob_match_id}, ttl=ttl)
    return parse_match_details(data)


def parse_match_details(data: dict) -> FMDetails:
    general, header, content = data["general"], data["header"], data.get("content") or {}
    status = header.get("status", {})
    teams = header["teams"]
    home_id, away_id = int(teams[0]["id"]), int(teams[1]["id"])
    finished = bool(status.get("finished"))
    det = FMDetails(
        fotmob_id=int(general["matchId"]),
        finished=finished,
        cancelled=bool(status.get("cancelled")),
        kickoff_utc=_parse_dt(status.get("utcTime") or general["matchTimeUTCDate"]),
        home_id=home_id,
        away_id=away_id,
        home_goals=int(teams[0]["score"]) if finished else None,
        away_goals=int(teams[1]["score"]) if finished else None,
        home_goals_ht=None,
        away_goals_ht=None,
        referee=None,
        referee_country=None,
        lineup_type=None,
    )

    facts = content.get("matchFacts") or {}
    ref = (facts.get("infoBox") or {}).get("Referee") or {}
    if ref.get("text"):
        det.referee = ref["text"].strip()
        det.referee_country = ref.get("country")

    # Eventos: tarjetas por jugador y marcador al descanso
    for ev in (facts.get("events") or {}).get("events", []) or []:
        if ev.get("type") == "Half" and ev.get("halfStrShort") == "HT":
            det.home_goals_ht, det.away_goals_ht = ev.get("homeScore"), ev.get("awayScore")
        if ev.get("type") == "Card" and ev.get("playerId"):
            pid = int(ev["playerId"])
            card = (ev.get("card") or "").lower()
            entry = det.cards.setdefault(pid, {"yellow": 0, "red": 0})
            if card == "yellow":
                entry["yellow"] += 1
            elif card in ("red", "yellowred", "secondyellow"):
                entry["red"] += 1

    # Alineaciones y bajas
    lineup = content.get("lineup") or {}
    ltype = lineup.get("lineupType")
    if ltype:
        det.lineup_type = "predicted" if ltype == "predicted" else "confirmed"
    for side_key in ("homeTeam", "awayTeam"):
        side = lineup.get(side_key) or {}
        team_fid = int(side.get("id") or (home_id if side_key == "homeTeam" else away_id))
        coach = side.get("coach") or {}
        det.team_info[team_fid] = {"formation": side.get("formation"), "coach": coach.get("name")}
        for group, starter in (("starters", True), ("subs", False)):
            for p in side.get(group, []) or []:
                perf = p.get("performance") or {}
                layout = p.get("verticalLayout") or {}
                det.players.append(
                    FMPlayer(
                        fotmob_id=int(p["id"]),
                        name=p.get("name", ""),
                        team_fotmob_id=team_fid,
                        position="GK" if p.get("positionId") == 11 else POSITION_BY_USUAL.get(p.get("usualPlayingPositionId")),
                        is_starter=starter,
                        market_value=_num(p.get("marketValue")),
                        season_rating=_num(perf.get("seasonRating")),
                        shirt=int(p["shirtNumber"]) if str(p.get("shirtNumber") or "").isdigit() else None,
                        x=_num(layout.get("x")) if starter else None,
                        y=_num(layout.get("y")) if starter else None,
                    )
                )
        for p in side.get("unavailable", []) or []:
            un = p.get("unavailability") or {}
            kind = (un.get("type") or "other").lower()
            if kind not in ("injury", "suspension"):
                kind = "doubtful" if "doubt" in (un.get("expectedReturn") or "").lower() else "other"
            det.unavailable.append(
                FMUnavailable(
                    fotmob_id=int(p["id"]),
                    name=p.get("name", ""),
                    team_fotmob_id=team_fid,
                    kind=kind,
                    reason=un.get("injuryType") or un.get("type"),
                    expected_return=un.get("expectedReturn"),
                    market_value=_num(p.get("marketValue")),
                    season_rating=_num((p.get("performance") or {}).get("seasonRating")),
                )
            )

    # Estadísticas de equipo
    periods = ((content.get("stats") or {}).get("Periods") or {}).get("All") or {}
    stats_home: dict[str, float] = {}
    stats_away: dict[str, float] = {}
    for grp in periods.get("stats", []) or []:
        for s in grp.get("stats", []) or []:
            col = TEAM_STAT_KEYS.get(s.get("key"))
            vals = s.get("stats") or [None, None]
            if col and s.get("type") != "title" and len(vals) == 2:
                h, a = _num(vals[0]), _num(vals[1])
                if h is not None:
                    stats_home.setdefault(col, h)
                if a is not None:
                    stats_away.setdefault(col, a)
    if stats_home or stats_away:
        det.team_stats = {home_id: stats_home, away_id: stats_away}

    # Estadísticas por jugador
    for pid, p in (content.get("playerStats") or {}).items():
        row: dict[str, Any] = {"team_fotmob_id": int(p.get("teamId") or 0), "name": p.get("name")}
        for grp in p.get("stats", []) or []:
            for s in (grp.get("stats") or {}).values():
                col = PLAYER_STAT_KEYS.get(s.get("key"))
                if col and col not in row:
                    row[col] = _num((s.get("stat") or {}).get("value"))
        card = det.cards.get(int(pid), {"yellow": 0, "red": 0})
        row["yellow_cards"], row["red_cards"] = card["yellow"], card["red"]
        det.player_stats[int(pid)] = row
    return det
