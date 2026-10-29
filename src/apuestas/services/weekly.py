"""Resumen de la semana: el equipo, el jugador y el once que más superaron lo esperado.

- **Equipos**, frente a la casa: el 1X2 sin margen y la línea principal de goles y de córners de cada equipo antes del
  partido (si no hay línea, lo que esperaba el modelo en la previa).
- **Jugadores**, frente a la previa del modelo (`services/predictions.py`): remates, remates a puerta, goles y
  asistencias, ajustados a los minutos que jugó; porteros y defensas suman además los goles recibidos.

Cada dato suma de −1 a +1 (`models/surprise.py`; 0 = lo esperado) y la semana es la suma de sus partidos. Resume lo
que pasó: no predice la semana siguiente. Se calcula al leerlo, así que se completa solo cuando llegan los
resultados o el cierre de football-data.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.config import get_settings
from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models import fitting
from apuestas.models import surprise as sp
from apuestas.services import predictions

MIN_MINUTES = 30  # menos minutos: un solo remate en un rato suelto pesaría como el partido entero de otro
CONCEDED_MIN_MINUTES = 60
TOP_N = 10
FORMATION = (("GK", 1), ("DF", 4), ("MF", 3), ("FW", 3))
KINDS = ("closing", "live", "opening")  # el cierre es la mejor vara; si no hay, la última antes del inicio
BOOKS_1X2 = ("pinnacle", "betfair_ex", "bet365", "betano", "avg")
BOOKS_LINES = ("pinnacle", "betano")
MARKETS = ("1x2", "ou_goals", "ou_goals_home", "ou_goals_away", "ou_corners_home", "ou_corners_away")
PLAYER_ITEMS = (  # (dato, columna real, ¿binomial negativa?)
    ("shots", "shots", True),
    ("shots_on_target", "shots_on_target", True),
    ("goals", "goals", False),
    ("assists", "assists", False),
)
LABELS = {"result": "Resultado", "goals": "Goles", "corners": "Córners", "shots": "Remates",
          "shots_on_target": "Remates a puerta", "assists": "Asistencias", "conceded": "Goles recibidos"}
NOTE = ("Resume quién sorprendió a la casa (equipos) y a nuestro modelo (jugadores) en los partidos ya jugados. "
        "Una buena semana es en parte suerte: no dice que la siguiente vaya a repetirse.")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_bounds(monday: date) -> tuple[datetime, datetime]:
    """Lunes 00:00 a lunes siguiente 00:00, en hora de Lima, pasados a UTC."""
    tz = get_settings().tz
    start = datetime.combine(monday, time(0), tzinfo=tz)
    return start.astimezone(UTC), (start + timedelta(days=7)).astimezone(UTC)


# --------------------------------------------------------------------------- vara de la casa


def pre_kickoff(rows: list[m.OddsSnapshot], kickoff: datetime) -> dict[str, dict[tuple, float]]:
    """Por tipo de cuota, el último precio de cada (casa, mercado, selección, línea) antes del inicio. El cierre de
    football-data se guarda con la hora del inicio; las demás posteriores al inicio no valen (ya se estaba jugando)."""
    kickoff = _aware(kickoff)
    out: dict[str, dict[tuple, float]] = defaultdict(dict)
    for r in sorted(rows, key=lambda r: _aware(r.captured_at)):
        if r.kind != "closing" and _aware(r.captured_at) >= kickoff:
            continue
        out[r.kind][(r.bookmaker, r.market, r.selection, r.line)] = r.price
    return out


def vara_1x2(pk: dict[str, dict[tuple, float]]) -> dict | None:
    for kind in KINDS:
        for book in BOOKS_1X2:
            o = [pk.get(kind, {}).get((book, "1x2", sel, None)) for sel in ("home", "draw", "away")]
            if all(o) and min(o) > 1.0:
                probs = oddsmath.devig(o)
                return {"home": probs[0], "draw": probs[1], "away": probs[2], "book": book, "kind": kind}
    return None


def main_line(pk: dict[str, dict[tuple, float]], market: str) -> dict | None:
    """La línea principal (la más cercana al 50 % sin margen) de la primera casa que tenga más y menos."""
    for kind in KINDS:
        prices = pk.get(kind, {})
        for book in BOOKS_LINES:
            lines = {ln for (b, mk, _sel, ln) in prices if b == book and mk == market and ln is not None}
            best = None
            for ln in sorted(lines):
                ov, un = prices.get((book, market, "over", ln)), prices.get((book, market, "under", ln))
                if not (ov and un and min(ov, un) > 1.0):
                    continue
                p = oddsmath.devig([ov, un])[0]
                if best is None or abs(p - 0.5) < abs(best["p_over"] - 0.5):
                    best = {"line": ln, "p_over": p, "book": book, "kind": kind}
            if best:
                return best
    return None


def _prematch_goals(pk: dict[str, dict[tuple, float]]) -> tuple[str, str, float, float] | None:
    """Goles de cada equipo implícitos en el 1X2 y el más/menos 2.5 (para cuando no hay línea por equipo)."""
    for kind in KINDS:
        prices = {(b, mk, sel): p for (b, mk, sel, ln), p in pk.get(kind, {}).items()
                  if mk == "1x2" or (mk == "ou_goals" and ln == 2.5)}
        got = fitting.prematch_market_goals(prices) if prices else None
        if got:
            return kind, got[0], got[1], got[2]
    return None


def team_expectation(pk, payload: dict | None, side: str, stat: str, dispersion: float) -> dict | None:
    """Media esperada de goles o córners de un equipo: la casa (línea principal) o, si no hay, la previa."""
    ml = main_line(pk, f"ou_{stat}_{side}")
    if ml:
        mean = sp.solve_mean(ml["line"], ml["p_over"], dispersion)
        if mean is not None:
            return {"mean": mean, "dispersion": dispersion, "source": "casa", **ml}
    if stat == "goals":
        got = _prematch_goals(pk)
        if got:
            kind, book, lam_h, lam_a = got
            return {"mean": lam_h if side == "home" else lam_a, "dispersion": 0.0, "source": "casa",
                    "book": book, "kind": kind, "line": None, "p_over": None}
    if payload:
        mean = payload["goals"][side] if stat == "goals" else payload.get("counts", {}).get(stat, {}).get(side)
        if mean is not None:
            return {"mean": mean, "dispersion": dispersion, "source": "modelo", "book": None, "kind": None,
                    "line": None, "p_over": None}
    return None


# --------------------------------------------------------------------------- puntuación de un partido


def _item(key: str, actual, expected: dict, score: float) -> dict:
    return {"item": key, "label": LABELS[key], "actual": actual, "expected": round(float(expected["mean"]), 2),
            "line": expected.get("line"), "p_over": None if expected.get("p_over") is None else round(expected["p_over"], 3),
            "source": expected["source"], "book": expected.get("book"), "kind": expected.get("kind"),
            "score": round(float(score), 3)}


def team_items(mt: m.Match, side: str, pk, payload: dict | None, stats: m.TeamMatchStats | None,
               corners_alpha: float) -> tuple[list[dict], bool]:
    """Datos del equipo en el partido y si faltan estadísticas (aún no llegaron)."""
    gf, ga = (mt.home_goals, mt.away_goals) if side == "home" else (mt.away_goals, mt.home_goals)
    items: list[dict] = []
    vara = vara_1x2(pk)
    if vara is None and payload:
        vara = {**payload["1x2"], "book": None, "kind": None, "source": "modelo"}
    if vara is not None:
        pts = sp.points(gf, ga)
        p_win = vara[side]
        exp_pts = 3 * p_win + vara["draw"]
        items.append({"item": "result", "label": LABELS["result"], "actual": f"{gf}-{ga}",
                      "expected": round(exp_pts, 2), "line": None, "p_over": round(p_win, 3),
                      "source": vara.get("source", "casa"), "book": vara["book"], "kind": vara["kind"],
                      "score": round(sp.result_score(pts, p_win, vara["draw"]), 3)})
    goals = team_expectation(pk, payload, side, "goals", 0.0)
    if goals:
        items.append(_item("goals", gf, goals, sp.mid_pit(sp.count_dist(goals["mean"]), gf)))
    pending = stats is None or stats.corners is None
    if not pending:
        corners = team_expectation(pk, payload, side, "corners", corners_alpha)
        if corners:
            pmf = sp.count_dist(corners["mean"], corners_alpha)
            items.append(_item("corners", stats.corners, corners, sp.mid_pit(pmf, stats.corners)))
    return items, pending


def player_items(row: m.PlayerMatchStats, position: str | None, proj: dict, payload: dict,
                 conceded: tuple[int, dict] | None) -> list[dict]:
    """Datos del jugador frente a su proyección, ajustada a los minutos que jugó de verdad."""
    factor = (row.minutes or 0) / max(float(proj.get("expected_minutes") or 0.0), 1.0)
    alpha = payload.get("player_dispersion", {})
    items: list[dict] = []
    for key, column, nb in PLAYER_ITEMS:
        actual = getattr(row, column)
        lam = proj.get("lam", {}).get(key)
        if actual is None or lam is None:
            continue
        mean = lam * factor
        a = alpha.get(key, 0.15) if nb else 0.0
        exp = {"mean": mean, "source": "modelo"}
        items.append(_item(key, actual, exp, sp.mid_pit(sp.count_dist(mean, a), actual)))
    if conceded and position in ("GK", "DF") and (row.minutes or 0) >= CONCEDED_MIN_MINUTES:
        ga, exp = conceded
        items.append(_item("conceded", ga, exp, -sp.mid_pit(sp.count_dist(exp["mean"]), ga)))
    return items


# --------------------------------------------------------------------------- la semana


def _rank_key(row: dict) -> tuple:
    return (-round(row["score"], 3), -round(row["mean"], 3), row["name"])


def score_range(s: Session, start: datetime, end: datetime) -> dict:
    """Puntuación de equipos y jugadores en los partidos terminados entre `start` y `end`, ordenados y sin cortar.

    La usan la semana y el mes (`recap`) y el radar (`services/radar.py`)."""
    tz = get_settings().tz
    codes = [c.code for c in FULL]
    matches = list(s.scalars(
        select(m.Match).join(m.Competition, m.Competition.id == m.Match.competition_id)
        .where(m.Competition.code.in_(codes), m.Match.kickoff_utc >= start, m.Match.kickoff_utc < end)
        .order_by(m.Match.kickoff_utc)))
    played = [mt for mt in matches if mt.status == "finished" and mt.home_goals is not None
              and mt.away_goals is not None]
    ids = [mt.id for mt in played]
    previas, stale = predictions.usable(s, played)

    odds: dict[int, list[m.OddsSnapshot]] = defaultdict(list)
    tstats: dict[tuple[int, int], m.TeamMatchStats] = {}
    prows: dict[int, list[tuple[m.PlayerMatchStats, m.Player]]] = defaultdict(list)
    if ids:
        for r in s.scalars(select(m.OddsSnapshot).where(m.OddsSnapshot.match_id.in_(ids),
                                                        m.OddsSnapshot.market.in_(MARKETS))):
            odds[r.match_id].append(r)
        for r in s.scalars(select(m.TeamMatchStats).where(m.TeamMatchStats.match_id.in_(ids))):
            tstats[(r.match_id, r.team_id)] = r
    if previas:
        for r, p in s.execute(select(m.PlayerMatchStats, m.Player).join(m.Player, m.Player.id == m.PlayerMatchStats.player_id)
                              .where(m.PlayerMatchStats.match_id.in_(list(previas)))):
            prows[r.match_id].append((r, p))

    try:
        corners_alpha_default = fitting.load_bundle().counts["corners"].dispersion
    except (FileNotFoundError, KeyError):
        corners_alpha_default = 0.0

    teams: dict[int, dict] = {}
    players: dict[int, dict] = {}
    cov = {"played": len(played), "with_prediction": len(previas), "without_prediction": len(played) - len(previas),
           "stale": len(stale), "pending_stats": 0, "team_matches": 0, "scheduled": sum(
               1 for mt in matches if mt.status == "scheduled")}
    for mt in played:
        pk = pre_kickoff(odds.get(mt.id, []), mt.kickoff_utc)
        payload = previas.get(mt.id)
        alpha = (payload or {}).get("counts", {}).get("corners", {}).get("dispersion", corners_alpha_default)
        label = f"{mt.home_team.name} {mt.home_goals}-{mt.away_goals} {mt.away_team.name}"
        kickoff_local = _aware(mt.kickoff_utc).astimezone(tz).strftime("%Y-%m-%d %H:%M")
        counted = False
        expect_goals = {}
        for side, team in (("home", mt.home_team), ("away", mt.away_team)):
            items, pending = team_items(mt, side, pk, payload, tstats.get((mt.id, team.id)), alpha)
            cov["pending_stats"] += int(pending)
            expect_goals[side] = team_expectation(pk, payload, side, "goals", 0.0)
            if not items:
                continue
            counted = True
            score = sum(i["score"] for i in items)
            t = teams.setdefault(team.id, {"team_id": team.id, "name": team.name, "competition": mt.competition.code,
                                           "score": 0.0, "n_matches": 0, "matches": []})
            t["score"] += score
            t["n_matches"] += 1
            t["matches"].append({"match_id": mt.id, "label": label, "kickoff_local": kickoff_local,
                                 "stage": payload["stage"] if payload else None, "score": round(score, 3),
                                 "items": items})
        cov["team_matches"] += int(counted)

        if not payload:
            continue
        projs = {p["player_id"]: p for p in payload.get("players", [])}
        for row, player in prows.get(mt.id, []):
            proj = projs.get(player.id)
            if proj is None or (row.minutes or 0) < MIN_MINUTES:
                continue
            side = "home" if row.team_id == mt.home_team_id else "away"
            opp = "away" if side == "home" else "home"
            ga = mt.away_goals if side == "home" else mt.home_goals
            conceded = (ga, expect_goals[opp]) if expect_goals.get(opp) else None
            position = player.position or proj.get("position")
            items = player_items(row, position, proj, payload, conceded)
            if not items:
                continue
            score = sum(i["score"] for i in items)
            team = mt.home_team if side == "home" else mt.away_team
            pl = players.setdefault(player.id, {"player_id": player.id, "name": player.name, "position": position,
                                                "team_id": team.id, "team": team.name, "minutes": 0, "score": 0.0,
                                                "n_matches": 0, "matches": []})
            pl.update(team_id=team.id, team=team.name)  # el equipo de su último partido
            pl["minutes"] += row.minutes or 0
            pl["score"] += score
            pl["n_matches"] += 1
            pl["matches"].append({"match_id": mt.id, "label": label, "kickoff_local": kickoff_local,
                                  "minutes": row.minutes, "score": round(score, 3), "items": items})

    def finish(rows: dict[int, dict]) -> list[dict]:
        out = []
        for r in rows.values():
            r["mean"] = r["score"] / r["n_matches"]
            r["score"], r["mean"] = round(r["score"], 3), round(r["mean"], 3)
            out.append(r)
        return sorted(out, key=_rank_key)

    return {"teams": finish(teams), "players": finish(players), "coverage": cov}


def recap(s: Session, monday: date, now: datetime | None = None, detail: bool = True, weeks: int = 1) -> dict:
    """La semana del lunes dado o, con `weeks=4`, las 4 semanas que terminan en ella (el mes)."""
    now = now or datetime.now(UTC)
    tz = get_settings().tz
    first = monday - timedelta(days=7 * (weeks - 1))
    start, end = week_bounds(first)[0], week_bounds(monday)[1]
    scored = score_range(s, start, end)
    team_rank, player_rank, cov = scored["teams"], scored["players"], scored["coverage"]
    slots = []
    for line, n in FORMATION:
        chosen = [p for p in player_rank if p["position"] == line][:n]
        slots += [{"line": line, "player": p} for p in chosen] + [{"line": line, "player": None}] * (n - len(chosen))

    def brief(row: dict | None, keep: bool) -> dict | None:
        if row is None or keep:
            return row
        return {k: v for k, v in row.items() if k != "matches"}

    since = s.scalar(select(func.min(m.Prediction.created_at)))
    return {
        "period": "mes" if weeks > 1 else "semana",
        "weeks": weeks,
        "week_start": first.isoformat(),
        "week_end": (monday + timedelta(days=6)).isoformat(),
        "status": "en_curso" if now < end else "cerrada",
        "note": NOTE,
        "history_since": _aware(since).astimezone(tz).date().isoformat() if since else None,
        "coverage": cov,
        "team_of_week": team_rank[0] if team_rank else None,
        "player_of_week": player_rank[0] if player_rank else None,
        "eleven": {"formation": "4-3-3", "slots": [{**sl, "player": brief(sl["player"], detail)} for sl in slots]},
        "teams": [brief(r, detail) for r in team_rank[:TOP_N]],
        "players": [brief(r, detail) for r in player_rank[:TOP_N]],
    }


# --------------------------------------------------------------------------- el mes: 4 semanas completas

MONTH_WEEKS = 4


def first_full_week(s: Session) -> date | None:
    """Lunes de la primera semana completa con la previa guardada (la de los jugadores)."""
    first = s.scalar(select(func.min(m.Prediction.created_at)))
    if first is None:
        return None
    d = _aware(first).astimezone(get_settings().tz).date()
    return d if d.weekday() == 0 else week_start(d) + timedelta(days=7)


def month_available(s: Session, last_monday: date, now: datetime) -> bool:
    """El mes que termina en la semana de `last_monday`: sus 4 semanas acabaron y todas tienen previa."""
    first = first_full_week(s)
    if first is None:
        return False
    return last_monday - timedelta(days=7 * (MONTH_WEEKS - 1)) >= first and now >= week_bounds(last_monday)[1]


def period_recap(s: Session, day: date | None, period: str, now: datetime | None = None, detail: bool = True) -> dict:
    """La semana del día dado (por defecto, la actual) o el mes que termina en ella (por defecto, en la última
    semana completa)."""
    now = now or datetime.now(UTC)
    today = now.astimezone(get_settings().tz).date()
    if period == "semana":
        return {**recap(s, week_start(day or today), now, detail), "available": True}
    if period != "mes":
        raise ValueError(f"Periodo desconocido: {period} (semana o mes)")
    last = week_start(day) if day else week_start(today) - timedelta(days=7)
    if not month_available(s, last, now):
        first = first_full_week(s)
        return {"period": "mes", "weeks": MONTH_WEEKS, "available": False,
                "available_from": (first + timedelta(days=7 * MONTH_WEEKS)).isoformat() if first else None,
                "week_start": (last - timedelta(days=7 * (MONTH_WEEKS - 1))).isoformat(),
                "week_end": (last + timedelta(days=6)).isoformat(), "note": NOTE}
    return {**recap(s, last, now, detail, weeks=MONTH_WEEKS), "available": True}


def week_recap(day: date | None = None, detail: bool = True, period: str = "semana") -> dict:
    with session_scope() as s:
        return period_recap(s, day, period, detail=detail)
