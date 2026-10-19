"""Fuerza de la alineación y efecto de las bajas.

Cada jugador tiene un índice de calidad basado en su valor de mercado (escala logarítmica) y su
rating de temporada. La alineación de un partido se compara con la "alineación típica" del equipo
(media de sus últimas titularidades confirmadas): si sale peor que de costumbre, baja su ataque/defensa.

Pesos por posición: un delantero pesa mucho en ataque y poco en defensa; un mediocentro como
Szoboszlai pesa en ambos; porteros y defensas pesan sobre todo en defensa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.db import models as m

ATT_W = {"GK": 0.0, "DF": 0.25, "MF": 0.7, "FW": 1.0}
DEF_W = {"GK": 1.0, "DF": 1.0, "MF": 0.6, "FW": 0.15}
# Sensibilidad: cuánto cambia (en log) la media de goles por cada punto de diferencia en el índice.
# Calibrado con los onces confirmados 2024-26 (`apuestas backtest --lineups`): la regresión de goles da
# 0,11 ± 0,05 (ataque) y 0,10 ± 0,06 (defensa), la de xG 0,06 y 0,08; 0,10 da la mejor log-loss (0,30 empeoraba).
BETA_ATT = 0.10
BETA_DEF = 0.10
BASELINE_MATCHES = 8


def player_quality(market_value: float | None, season_rating: float | None) -> float:
    q = math.log1p((market_value or 2_000_000) / 1_000_000)
    if season_rating:
        q += 0.5 * max(min(season_rating - 6.8, 1.0), -1.0)
    return q


@dataclass
class XIStrength:
    attack: float
    defence: float
    players: list[dict] = field(default_factory=list)


def xi_strength(players: list[dict]) -> XIStrength:
    """players: [{player_id, name, position, quality}] (los 11 titulares)."""
    if not players:
        return XIStrength(0.0, 0.0, [])
    aw = sum(ATT_W.get(p.get("position") or "MF", 0.5) for p in players) or 1.0
    dw = sum(DEF_W.get(p.get("position") or "MF", 0.5) for p in players) or 1.0
    att = sum(ATT_W.get(p.get("position") or "MF", 0.5) * p["quality"] for p in players) / aw
    de = sum(DEF_W.get(p.get("position") or "MF", 0.5) * p["quality"] for p in players) / dw
    return XIStrength(att, de, players)


def _lineup_players(s: Session, match_id: int, team_id: int) -> tuple[list[dict], str | None]:
    rows = s.execute(
        select(m.Lineup, m.Player)
        .join(m.Player, m.Player.id == m.Lineup.player_id)
        .where(m.Lineup.match_id == match_id, m.Lineup.team_id == team_id, m.Lineup.is_starter.is_(True))
    ).all()
    status = rows[0][0].status if rows else None
    return [
        {
            "player_id": p.id,
            "name": p.name,
            "position": lu.position or p.position,
            "quality": player_quality(lu.market_value_eur or p.market_value_eur, lu.season_rating or p.season_rating),
        }
        for lu, p in rows
    ], status


def baseline(s: Session, team_id: int, before: datetime, n: int = BASELINE_MATCHES) -> tuple[XIStrength, dict[int, float]]:
    """Alineación típica del equipo y frecuencia de titularidad de cada jugador."""
    match_ids = s.scalars(
        select(m.Match.id)
        .join(m.Lineup, m.Lineup.match_id == m.Match.id)
        .where(
            m.Lineup.team_id == team_id,
            m.Lineup.status == "confirmed",
            m.Match.kickoff_utc < before,
            m.Match.status == "finished",
        )
        .group_by(m.Match.id)
        .order_by(m.Match.kickoff_utc.desc())
        .limit(n)
    ).all()
    if not match_ids:
        return XIStrength(0.0, 0.0), {}
    atts, defs, freq = [], [], {}
    for mid in match_ids:
        players, _ = _lineup_players(s, mid, team_id)
        st = xi_strength(players)
        atts.append(st.attack)
        defs.append(st.defence)
        for p in players:
            freq[p["player_id"]] = freq.get(p["player_id"], 0) + 1 / len(match_ids)
    return XIStrength(sum(atts) / len(atts), sum(defs) / len(defs)), freq


def xi_history(s: Session) -> dict[int, list[tuple[date, int, XIStrength]]]:
    """Onces confirmados de todos los partidos terminados, por equipo y en orden cronológico (para backtests).

    Misma calidad por jugador que `_lineup_players`, pero en una sola consulta.
    """
    rows = s.execute(
        select(m.Lineup.match_id, m.Lineup.team_id, m.Match.kickoff_utc, m.Lineup.position, m.Lineup.market_value_eur,
               m.Lineup.season_rating, m.Player)
        .join(m.Player, m.Player.id == m.Lineup.player_id)
        .join(m.Match, m.Match.id == m.Lineup.match_id)
        .where(m.Lineup.status == "confirmed", m.Lineup.is_starter.is_(True), m.Match.status == "finished")
    ).all()
    groups: dict[tuple[int, int], tuple[date, list[dict]]] = {}
    for mid, tid, ko, pos, mv, sr, p in rows:
        groups.setdefault((mid, tid), (ko.date(), []))[1].append(
            {"player_id": p.id, "position": pos or p.position,
             "quality": player_quality(mv or p.market_value_eur, sr or p.season_rating)}
        )
    out: dict[int, list[tuple[date, int, XIStrength]]] = {}
    for (mid, tid), (day, players) in groups.items():
        out.setdefault(tid, []).append((day, mid, xi_strength(players)))
    for hist in out.values():
        hist.sort(key=lambda x: x[0])
    return out


def baseline_from_history(hist: list[tuple[date, int, XIStrength]], before: date,
                          n: int = BASELINE_MATCHES) -> XIStrength | None:
    """Once típico (media de las últimas n titularidades confirmadas antes de `before`)."""
    prev = [x for day, _, x in hist if day < before][-n:]
    if not prev:
        return None
    return XIStrength(sum(x.attack for x in prev) / len(prev), sum(x.defence for x in prev) / len(prev))


@dataclass
class LineupAdjustment:
    team_id: int
    source: str  # confirmed | predicted | injuries_only | none
    attack_mult: float
    defence_mult: float  # multiplica los goles que RECIBE (>1 = defiende peor)
    xi_attack: float | None
    xi_defence: float | None
    base_attack: float | None
    base_defence: float | None
    missing_regulars: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def adjustment(s: Session, match: m.Match, team_id: int) -> LineupAdjustment:
    base, freq = baseline(s, team_id, match.kickoff_utc)
    players, status = _lineup_players(s, match.id, team_id)
    unavailable = s.execute(
        select(m.Availability, m.Player)
        .join(m.Player, m.Player.id == m.Availability.player_id)
        .where(m.Availability.team_id == team_id, m.Availability.active.is_(True))
    ).all()
    missing = [
        {
            "player_id": p.id,
            "name": p.name,
            "position": p.position,
            "kind": a.kind,
            "expected_return": a.expected_return,
            "start_rate": round(freq.get(p.id, 0.0), 2),
            "quality": round(player_quality(p.market_value_eur, p.season_rating), 2),
        }
        for a, p in unavailable
    ]
    missing_regulars = sorted([x for x in missing if x["start_rate"] >= 0.4], key=lambda x: -x["quality"])

    if not base.players and base.attack == 0.0:
        return LineupAdjustment(team_id, "none", 1.0, 1.0, None, None, None, None, missing_regulars,
                                ["Sin historial de alineaciones: no se ajusta"])

    if len(players) >= 10:
        xi = xi_strength(players)
        src = status or "predicted"
    else:
        # Sin alineación: partimos de la típica y quitamos a los titulares habituales que están de baja
        xi = XIStrength(base.attack, base.defence)
        src = "injuries_only"
        for x in missing_regulars:
            if x["kind"] in ("injury", "suspension"):
                replacement = base.attack - 1.2  # un suplente suele valer bastante menos que un titular
                pos = x["position"] or "MF"
                xi.attack -= x["start_rate"] * ATT_W[pos] * max(x["quality"] - replacement, 0) / 7.0
                xi.defence -= x["start_rate"] * DEF_W[pos] * max(x["quality"] - replacement, 0) / 7.0

    d_att = xi.attack - base.attack
    d_def = xi.defence - base.defence
    att_mult = math.exp(BETA_ATT * d_att)
    def_mult = math.exp(-BETA_DEF * d_def)
    notes = []
    if d_att < -0.25 or d_def < -0.25:
        notes.append("Alineación claramente más débil que la habitual (rotación o bajas importantes)")
    elif d_att > 0.2 or d_def > 0.2:
        notes.append("Alineación más fuerte que la media reciente")
    return LineupAdjustment(
        team_id=team_id,
        source=src,
        attack_mult=round(att_mult, 4),
        defence_mult=round(def_mult, 4),
        xi_attack=round(xi.attack, 3),
        xi_defence=round(xi.defence, 3),
        base_attack=round(base.attack, 3),
        base_defence=round(base.defence, 3),
        missing_regulars=missing_regulars,
        notes=notes,
    )
