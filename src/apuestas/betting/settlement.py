"""Liquidación de apuestas con el resultado real del partido."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.db import models as m
from apuestas.models import distributions as dist

RESULT_PROFIT = {"win": 1.0, "half_win": 0.5, "push": 0.0, "void": 0.0, "half_loss": -0.5, "loss": -1.0}
STAT_COLUMNS = {"goals": "goals", "shots": "shots", "sot": "shots_on_target", "shots_on_target": "shots_on_target",
                "corners": "corners", "fouls": "fouls", "cards": "cards"}
PLAYER_COLUMNS = {"player_shots": ("shots",), "player_sot": ("shots_on_target",), "player_fouls": ("fouls_committed",),
                  "player_goal": ("goals",), "player_assist": ("assists",), "player_goal_assist": ("goals", "assists"),
                  "player_card": ("yellow_cards",)}
YES = ("yes", "si", "sí")


def _team_value(st: m.TeamMatchStats | None, stat: str) -> int | None:
    if st is None:
        return None
    if stat == "cards":
        return None if st.yellow_cards is None else st.yellow_cards + (st.red_cards or 0)
    return getattr(st, STAT_COLUMNS[stat])


def _from_outcome(o: dist.Outcome) -> str:
    for name in ("win", "half_win", "push", "half_loss", "loss"):
        if getattr(o, name) > 0.5:
            return name
    return "void"


def settle(s: Session, match: m.Match, market: str, selection: str, line: float | None,
           player_id: int | None = None) -> str | None:
    """Devuelve win/half_win/push/half_loss/loss/void, o None si aún no hay datos para liquidar."""
    if match.status in ("cancelled", "postponed"):
        return "void"
    if match.status != "finished" or match.home_goals is None:
        return None
    market, selection = market.lower(), selection.lower()

    if market.startswith("player_"):
        pms = s.scalar(select(m.PlayerMatchStats).where(
            m.PlayerMatchStats.match_id == match.id, m.PlayerMatchStats.player_id == player_id))
        if pms is None:
            # No jugó: las casas suelen anular (void) las props de jugadores que no participan
            return "void" if match.details_fetched_at else None
        value = sum(getattr(pms, col) or 0 for col in PLAYER_COLUMNS[market])
        if market == "player_card":
            hit = value > 0 or (pms.red_cards or 0) > 0
            return "win" if hit == (selection in YES) else "loss"
        if selection in YES + ("no",):  # marca / asiste / gol o asistencia: sí = al menos una
            return "win" if (value > 0) == (selection in YES) else "loss"
        ln = 0.5 if line is None else line
        o = dist.over({value: 1.0}, ln) if selection == "over" else dist.under({value: 1.0}, ln)
        return _from_outcome(o)

    parts = market.split("_", 1)
    kind, rest = parts[0], (parts[1] if len(parts) > 1 else "goals")
    scope = "total"
    for sc in ("home", "away"):
        if rest.endswith("_" + sc):
            rest, scope = rest[: -len(sc) - 1], sc
    stat = rest or "goals"
    if stat == "goals":
        vh, va = match.home_goals, match.away_goals
    else:
        sh = s.scalar(select(m.TeamMatchStats).where(
            m.TeamMatchStats.match_id == match.id, m.TeamMatchStats.team_id == match.home_team_id))
        sa = s.scalar(select(m.TeamMatchStats).where(
            m.TeamMatchStats.match_id == match.id, m.TeamMatchStats.team_id == match.away_team_id))
        vh, va = _team_value(sh, stat), _team_value(sa, stat)
        if vh is None or va is None:
            return None
    diff, total = vh - va, vh + va

    if market == "btts":
        both = vh > 0 and va > 0
        return "win" if both == (selection in ("yes", "si", "sí")) else "loss"
    if market == "dc":
        res = "home" if diff > 0 else ("away" if diff < 0 else "draw")
        ok = {"1x": res in ("home", "draw"), "x2": res in ("away", "draw"), "12": res != "draw"}[selection]
        return "win" if ok else "loss"
    if market == "dnb":
        return _from_outcome(dist.line_outcome({diff if selection == "home" else -diff: 1.0}, 0.0))
    if kind == "1x2":
        res = "home" if diff > 0 else ("away" if diff < 0 else "draw")
        return "win" if res == selection else "loss"
    if kind == "ah":
        d = diff if selection == "home" else -diff
        return _from_outcome(dist.line_outcome({d: 1.0}, line))
    if kind == "eh":
        shifted = diff + line
        res = "home" if shifted > 0 else ("away" if shifted < 0 else "draw")
        return "win" if res == selection else "loss"
    if kind == "ou":
        value = {"total": total, "home": vh, "away": va}[scope]
        o = dist.over({value: 1.0}, line) if selection == "over" else dist.under({value: 1.0}, line)
        return _from_outcome(o)
    return None


def profit(result: str, stake: float, odds: float) -> float:
    k = RESULT_PROFIT[result]
    return round(stake * k * (odds - 1) if k > 0 else stake * k, 2)


def combo_profit(stake: float, total_odds: float, legs: list[tuple[str | None, float | None]]) -> tuple[str, float] | None:
    """Resultado y beneficio de una combinada a partir del resultado de cada selección y su cuota.

    Basta una selección perdida para perderla, aunque falten partidos. Si alguna se devuelve (push/void) o sale a
    medias (hándicap de cuarto), la cuota total se ajusta en proporción a la cuota de esa selección, como hacen las
    casas; si no se conoce su cuota, se deja la total. None si aún faltan selecciones por resolver.
    """
    if any(res == "loss" for res, _ in legs):
        return "loss", round(-stake, 2)
    if any(res is None for res, _ in legs):
        return None
    factor = 1.0
    for res, odds in legs:
        if res == "win" or odds is None or odds <= 1:
            continue
        factor *= {"push": 1 / odds, "void": 1 / odds, "half_win": (1 + odds) / (2 * odds),
                   "half_loss": 0.5 / odds}[res]
    payout = stake * total_odds * factor
    profit_ = round(payout - stake, 2)
    if all(res in ("push", "void") for res, _ in legs):
        return "void", 0.0
    if profit_ > 0:
        return "win", profit_
    return ("push", 0.0) if profit_ == 0 else ("half_loss", profit_)
