"""Apuestas con valor del día y "apuesta del día".

La apuesta del día NO es la más probable, sino la de mayor valor esperado entre las que superan
umbrales de probabilidad, cuota, valor y confianza. Si ninguna los supera, ese día no hay apuesta del día.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.betting.settlement import combo_profit, profit, settle
from apuestas.config import get_settings
from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models.fitting import ModelBundle, load_bundle
from apuestas.services.analysis import BetEval, MatchAnalysis, analyze, is_goal_market

log = logging.getLogger(__name__)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = get_settings().tz
    start = datetime.combine(day, time(0, 0), tz).astimezone(UTC)
    return start, start + timedelta(days=1)


def today_local() -> date:
    return datetime.now(get_settings().tz).date()


def matches_for_day(s: Session, day: date) -> list[m.Match]:
    start, end = local_day_bounds(day)
    codes = [c.code for c in FULL]
    return list(s.scalars(
        select(m.Match).join(m.Competition, m.Competition.id == m.Match.competition_id)
        .where(m.Competition.code.in_(codes), m.Match.kickoff_utc >= start, m.Match.kickoff_utc < end,
               m.Match.status.in_(["scheduled", "finished"]))
        .order_by(m.Match.kickoff_utc)
    ))


def qualifies(b: BetEval) -> bool:
    st = get_settings()
    return bool(
        (st.pick_allow_stat_markets or is_goal_market(b.market))
        and st.pick_min_odds <= b.odds <= st.pick_max_odds
        and b.prob >= st.pick_min_prob
        and b.ev >= st.pick_min_ev
        and b.confidence >= st.pick_min_confidence
    )


def score(b: BetEval) -> float:
    """Ordena candidatas: valor esperado ajustado por confianza."""
    return b.ev * b.confidence


def _upsert_pick(s: Session, match: m.Match, b: BetEval, day: date, stage: str) -> m.Pick:
    pick = s.scalar(select(m.Pick).where(
        m.Pick.match_id == match.id, m.Pick.market == b.market, m.Pick.selection == b.selection,
        m.Pick.line.is_(None) if b.line is None else m.Pick.line == b.line,
        m.Pick.bookmaker == b.bookmaker, m.Pick.status == "open"))
    if pick is None:
        pick = m.Pick(match_id=match.id, pick_date=day, market=b.market, selection=b.selection, line=b.line,
                      bookmaker=b.bookmaker)
        s.add(pick)
    pick.stage, pick.odds, pick.model_prob, pick.fair_odds = stage, b.odds, b.prob, b.fair_odds
    pick.ev, pick.confidence, pick.stake_pct, pick.reasons = b.ev, b.confidence, b.stake_pct, b.reasons
    pick.qualifies = qualifies(b)
    return pick


def generate(day: date | None = None, bundle: ModelBundle | None = None) -> dict:
    day = day or today_local()
    bundle = bundle or load_bundle()
    now = datetime.now(UTC)
    report: dict = {"date": day.isoformat(), "pick_of_day": None, "value_bets": [], "props_to_check": [],
                    "matches": [], "notes": []}
    with session_scope() as s:
        analyses: list[MatchAnalysis] = []
        for match in matches_for_day(s, day):
            if match.status != "scheduled":
                continue
            try:
                analyses.append(analyze(s, bundle, match))
            except Exception:  # noqa: BLE001 - un partido raro no debe tumbar el informe del día
                log.exception("No se pudo analizar el partido %s", match.id)

        candidates: list[tuple[MatchAnalysis, BetEval]] = []
        for an in analyses:
            mt = an.match
            started = mt.kickoff_utc <= now
            report["matches"].append({
                "match_id": mt.id, "competition": mt.competition.code,
                "kickoff_local": mt.kickoff_utc.astimezone(get_settings().tz).strftime("%H:%M"),
                "home": mt.home_team.name, "away": mt.away_team.name, "stage": an.stage,
                "home_id": mt.home_team_id, "away_id": mt.away_team_id,
                "difficulty": {"home": an.difficulty["home"]["ajustada"], "away": an.difficulty["away"]["ajustada"]},
                "1x2": an.model.summary()["1x2"],
            })
            for b in an.bets:
                if b.ev <= 0:
                    continue
                if not started:
                    pick = _upsert_pick(s, mt, b, day, an.stage)
                    s.flush()
                    b.reasons = [*b.reasons, f"pick_id={pick.id}"]
                if b.odds >= get_settings().value_list_min_odds:
                    report["value_bets"].append({**b.to_dict(), "match_id": mt.id,
                                                 "label": b.label(mt.home_team.name, mt.away_team.name),
                                                 "match": f"{mt.home_team.name} vs {mt.away_team.name}",
                                                 "qualifies": qualifies(b)})
                if qualifies(b) and not started:
                    candidates.append((an, b))
            for p in an.min_odds_props[:6]:
                report["props_to_check"].append({**p, "match_id": mt.id,
                                                 "match": f"{mt.home_team.name} vs {mt.away_team.name}"})

        # Retirar picks abiertos que ya no tienen valor (p.ej. tras conocerse la alineación)
        live_keys = {(an.match.id, b.market, b.selection, b.line, b.bookmaker) for an in analyses for b in an.bets if b.ev > 0}
        start, end = local_day_bounds(day)
        for pick in s.scalars(select(m.Pick).join(m.Match).where(
                m.Pick.status == "open", m.Match.kickoff_utc >= start, m.Match.kickoff_utc < end,
                m.Match.kickoff_utc > now)):
            if (pick.match_id, pick.market, pick.selection, pick.line, pick.bookmaker) not in live_keys:
                pick.status = "withdrawn"
                if pick.is_pick_of_day:
                    report["notes"].append("La apuesta del día anterior se retiró: perdió valor con la nueva información")

        # Elegir apuesta del día
        current = s.scalar(select(m.Pick).where(m.Pick.pick_date == day, m.Pick.is_pick_of_day.is_(True),
                                                m.Pick.status.in_(["open", "settled"])))
        if current is not None and (current.match.kickoff_utc <= now or current.status == "settled"):
            chosen = current  # ya empezó: no se cambia
        elif candidates:
            an, best = max(candidates, key=lambda x: score(x[1]))
            chosen = _upsert_pick(s, an.match, best, day, an.stage)
            if current is not None and current.id != chosen.id:
                current.is_pick_of_day = False
            chosen.is_pick_of_day = True
        else:
            chosen = None
            if current is not None:
                current.is_pick_of_day = False
            report["notes"].append(
                "Hoy no hay apuesta del día: ninguna apuesta supera los umbrales de valor y confianza. "
                "No apostar también es una decisión rentable.")
        s.flush()
        if chosen is not None:
            mt = chosen.match
            report["pick_of_day"] = {
                "pick_id": chosen.id, "match_id": mt.id, "match": f"{mt.home_team.name} vs {mt.away_team.name}",
                "home_id": mt.home_team_id, "away_id": mt.away_team_id,
                "competition": mt.competition.name,
                "kickoff_local": mt.kickoff_utc.astimezone(get_settings().tz).strftime("%Y-%m-%d %H:%M"),
                "market": chosen.market, "selection": chosen.selection, "line": chosen.line,
                "bookmaker": chosen.bookmaker, "odds": chosen.odds, "prob": round(chosen.model_prob, 3),
                "fair_odds": round(chosen.fair_odds, 2), "ev": round(chosen.ev, 3),
                "confidence": round(chosen.confidence, 2), "stake_pct": chosen.stake_pct,
                "stage": chosen.stage, "reasons": chosen.reasons,
            }
        # Primero las que pasan el corte, luego el resto; dentro de cada grupo, por valor esperado
        report["value_bets"].sort(key=lambda x: (not x["qualifies"], -x["ev"]))
    return report


# --------------------------------------------------------------------------- liquidación


def closing_price(s: Session, match_id: int, bookmaker: str, market: str, selection: str,
                  line: float | None) -> float | None:
    for book in (bookmaker, "bet365", "pinnacle", "betfair_ex"):
        row = s.scalar(select(m.OddsSnapshot).where(
            m.OddsSnapshot.match_id == match_id, m.OddsSnapshot.bookmaker == book,
            m.OddsSnapshot.market == market, m.OddsSnapshot.selection == selection,
            m.OddsSnapshot.line.is_(None) if line is None else m.OddsSnapshot.line == line,
            m.OddsSnapshot.kind == "closing").order_by(m.OddsSnapshot.captured_at.desc()).limit(1))
        if row is not None:
            return row.price
    return None


def settle_all() -> dict:
    out = {"picks": 0, "bets": 0}
    with session_scope() as s:
        for pick in s.scalars(select(m.Pick).where(m.Pick.status == "open")):
            res = settle(s, pick.match, pick.market, pick.selection, pick.line)
            if res is None:
                continue
            pick.result, pick.status = res, "settled"
            pick.closing_odds = closing_price(s, pick.match_id, pick.bookmaker, pick.market, pick.selection, pick.line)
            if pick.closing_odds:
                pick.clv = round(oddsmath.clv(pick.odds, pick.closing_odds), 4)
            out["picks"] += 1
        for bet in s.scalars(select(m.UserBet).where(m.UserBet.result.is_(None))):
            if bet.market == "combo":
                for leg in bet.legs:
                    if leg.result is None:
                        leg.result = settle(s, leg.match, leg.market, leg.selection, leg.line, leg.player_id)
                done = combo_profit(bet.stake, bet.odds, [(leg.result, leg.odds) for leg in bet.legs])
                if done is not None:
                    bet.result, bet.profit = done
                    out["bets"] += 1
                continue
            res = settle(s, bet.match, bet.market, bet.selection, bet.line, bet.player_id)
            if res is None:
                continue
            bet.result = res
            bet.profit = profit(res, bet.stake, bet.odds)
            bet.closing_odds = closing_price(s, bet.match_id, bet.bookmaker, bet.market, bet.selection, bet.line)
            if bet.closing_odds:
                bet.clv = round(oddsmath.clv(bet.odds, bet.closing_odds), 4)
            out["bets"] += 1
        out["clv"] = fill_missing_clv(s)
    return out


def fill_missing_clv(s: Session, days: int = 21) -> int:
    """CLV de lo ya liquidado sin cuota de cierre: football-data publica el cierre días después del partido."""
    since = datetime.now(UTC) - timedelta(days=days)
    n = 0
    for model in (m.Pick, m.UserBet):
        rows = s.scalars(select(model).join(m.Match, m.Match.id == model.match_id).where(
            model.result.is_not(None), model.closing_odds.is_(None), m.Match.kickoff_utc >= since)).all()
        for r in rows:
            r.closing_odds = closing_price(s, r.match_id, r.bookmaker, r.market, r.selection, r.line)
            if r.closing_odds:
                r.clv = round(oddsmath.clv(r.odds, r.closing_odds), 4)
                n += 1
    return n


HIT_RESULTS = ("win", "half_win")
MISS_RESULTS = ("loss", "half_loss")
PUSH_RESULTS = ("push", "void")


def record_from(rows: list) -> dict:
    """Contador de aciertos a partir de picks (status, result, odds, created_at), con 1 unidad por apuesta.

    El porcentaje de acierto no cuenta las devueltas (push/void): no se ganó ni se perdió.
    `since` es el día (en Lima) en que el sistema eligió la primera.
    """
    settled = [p for p in rows if p.status == "settled"]
    hits = sum(1 for p in settled if p.result in HIT_RESULTS)
    misses = sum(1 for p in settled if p.result in MISS_RESULTS)
    pushes = sum(1 for p in settled if p.result in PUSH_RESULTS)
    pl = sum(profit(p.result, 1.0, p.odds) for p in settled)
    decided = hits + misses
    return {
        "since": min((p.created_at for p in rows), default=None),
        "settled": len(settled), "hits": hits, "misses": misses, "pushes": pushes,
        "pending": sum(1 for p in rows if p.status == "open"),
        "hit_rate": round(hits / decided, 3) if decided else None,
        "profit_units": round(pl, 2), "roi": round(pl / len(settled), 4) if settled else None,
    }


def pick_record() -> dict:
    """Aciertos de la apuesta del día desde el primer día del sistema (las retiradas al recalcular no cuentan)."""
    with session_scope() as s:
        rows = list(s.scalars(select(m.Pick).where(
            m.Pick.is_pick_of_day.is_(True), m.Pick.status.in_(("open", "settled")))))
        out = record_from(rows)
    if out["since"]:
        out["since"] = out["since"].astimezone(get_settings().tz).date().isoformat()
    return out


def qualified_picks(days: int = 60) -> dict:
    """Todas las que pasaron el corte (no solo la apuesta del día): aciertos desde el inicio y las de los últimos días.

    Cuenta el último cálculo antes del partido: las retiradas o las que dejaron de pasar el corte no cuentan.
    """
    tz = get_settings().tz
    since = today_local() - timedelta(days=days)
    with session_scope() as s:
        rows = list(s.scalars(select(m.Pick).where(
            m.Pick.qualifies.is_(True), m.Pick.status.in_(("open", "settled")))))
        record = record_from(rows)
        if record["since"]:
            record["since"] = record["since"].astimezone(tz).date().isoformat()
        # De la más reciente a la más antigua; dentro de un mismo partido, la de más valor primero
        recent = sorted((p for p in rows if p.pick_date >= since),
                        key=lambda p: (p.match.kickoff_utc, p.ev), reverse=True)
        return {"record": record, "picks": [{
            "pick_id": p.id, "date": p.pick_date.isoformat(), "match_id": p.match_id,
            "kickoff_local": p.match.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
            "match": f"{p.match.home_team.name} vs {p.match.away_team.name}",
            "market": p.market, "selection": p.selection, "line": p.line, "bookmaker": p.bookmaker,
            "odds": p.odds, "prob": round(p.model_prob, 3), "ev": round(p.ev, 3),
            "confidence": round(p.confidence, 2), "is_pick_of_day": p.is_pick_of_day,
            "status": p.status, "result": p.result, "clv": p.clv,
            "profit_units": round(profit(p.result, 1.0, p.odds), 2) if p.result else None,
        } for p in recent]}


def pick_history(days: int = 60, only_pick_of_day: bool = True) -> dict:
    """Rendimiento histórico de los picks del sistema (stake plano de 1 unidad)."""
    since = today_local() - timedelta(days=days)
    with session_scope() as s:
        q = select(m.Pick).where(m.Pick.status == "settled", m.Pick.pick_date >= since)
        if only_pick_of_day:
            q = q.where(m.Pick.is_pick_of_day.is_(True))
        picks = list(s.scalars(q))
        n = len(picks)
        pl = sum(profit(p.result, 1.0, p.odds) for p in picks)
        wins = sum(1 for p in picks if p.result in ("win", "half_win"))
        clvs = [p.clv for p in picks if p.clv is not None]
        return {
            "picks": n, "profit_units": round(pl, 2), "roi": round(pl / n, 4) if n else None,
            "hit_rate": round(wins / n, 3) if n else None,
            "avg_clv": round(sum(clvs) / len(clvs), 4) if clvs else None,
            "last": [{"date": p.pick_date.isoformat(), "match": f"{p.match.home_team.name} vs {p.match.away_team.name}",
                      "market": p.market, "selection": p.selection, "line": p.line, "odds": p.odds,
                      "result": p.result, "clv": p.clv} for p in sorted(picks, key=lambda p: p.pick_date)[-10:]],
        }
