"""Apuestas con valor del día y "apuesta del día".

La apuesta del día NO es la más probable, sino la de mayor valor esperado entre las que superan
umbrales de probabilidad, cuota, valor y confianza. Si ninguna los supera, ese día no hay apuesta del día.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from apuestas.betting import odds as oddsmath
from apuestas.betting.settlement import combo_profit, profit, settle
from apuestas.config import get_settings
from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models.fitting import ModelBundle, load_bundle
from apuestas.services import predictions, radar
from apuestas.services.analysis import BetEval, MatchAnalysis, analyze, book_fair_prob, is_goal_market

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
    same = (m.Pick.match_id == match.id, m.Pick.market == b.market, m.Pick.selection == b.selection,
            m.Pick.line.is_(None) if b.line is None else m.Pick.line == b.line, m.Pick.bookmaker == b.bookmaker)
    pick = s.scalar(select(m.Pick).where(*same, m.Pick.status == "open"))
    if pick is None:  # retirada ese día que recupera el valor: se reabre en lugar de duplicarla
        pick = s.scalar(select(m.Pick).where(*same, m.Pick.status == "withdrawn", m.Pick.pick_date == day,
                                             m.Pick.result.is_(None)))
        if pick is not None:
            pick.status = "open"
    if pick is None:
        pick = m.Pick(match_id=match.id, pick_date=day, market=b.market, selection=b.selection, line=b.line,
                      bookmaker=b.bookmaker)
        s.add(pick)
    pick.stage, pick.odds, pick.model_prob, pick.fair_odds = stage, b.odds, b.prob, b.fair_odds
    pick.ev, pick.confidence, pick.stake_pct, pick.reasons = b.ev, b.confidence, b.stake_pct, b.reasons
    pick.qualifies = qualifies(b)
    if pick.qualifies and pick.announced_at is None:
        _announce(pick)
    return pick


def _announce(pick: m.Pick) -> None:
    """Copia fija de lo que se vio en Hoy la primera vez que pasó el corte."""
    pick.announced_at = datetime.now(UTC)
    pick.announced_odds, pick.announced_prob, pick.announced_ev = pick.odds, pick.model_prob, pick.ev


def _announce_pod(pick: m.Pick) -> None:
    """Marca que fue la apuesta del día (aunque luego el recálculo elija otra o se retire)."""
    pick.was_pick_of_day = True
    if pick.announced_at is None:
        _announce(pick)


def taken_odds(p: m.Pick) -> float:
    """La cuota que se anunció (la que se habría tomado); si no se anunció, la del último cálculo."""
    return p.announced_odds or p.odds


def _lock_day(s: Session, day: date) -> None:
    """El worker y la API pueden calcular el mismo día a la vez: en PostgreSQL, uno espera al otro para no duplicar
    apuestas guardadas ni elegir dos apuestas del día."""
    if s.bind.dialect.name == "postgresql":
        s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 7_000_000 + day.toordinal()})


def _listed(odds: float, started: bool) -> bool:
    """Si una cuota con valor sale en «Con valor»: no las de menos de 1.20 ni las de partidos que ya empezaron (en
    directo esa cuota ya no es la de antes del partido)."""
    return not started and odds >= get_settings().value_list_min_odds


def generate(day: date | None = None, bundle: ModelBundle | None = None) -> dict:
    day = day or today_local()
    bundle = bundle or load_bundle()
    now = datetime.now(UTC)
    report: dict = {"date": day.isoformat(), "pick_of_day": None, "value_bets": [], "props_to_check": [],
                    "matches": [], "notes": []}
    with session_scope() as s:
        _lock_day(s, day)
        analyses: list[MatchAnalysis] = []
        for match in matches_for_day(s, day):
            if match.status != "scheduled":
                continue
            try:
                analyses.append(analyze(s, bundle, match))
            except Exception:  # noqa: BLE001 - un partido raro no debe tumbar el informe del día
                log.exception("No se pudo analizar el partido %s", match.id)

        # Previa de cada partido que aún no empezó (la última antes del inicio queda para el resumen de la semana)
        for an in analyses:
            predictions.store(s, an, bundle, now)

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
                "rivalry": an.rivalry["name"] if an.rivalry else None,
            })
            for b in an.bets:
                if b.ev <= 0:
                    continue
                if not started:
                    pick = _upsert_pick(s, mt, b, day, an.stage)
                    s.flush()
                    b.reasons = [*b.reasons, f"pick_id={pick.id}"]
                if _listed(b.odds, started):
                    report["value_bets"].append({**b.to_dict(), "match_id": mt.id,
                                                 "label": b.label(mt.home_team.name, mt.away_team.name),
                                                 "match": f"{mt.home_team.name} vs {mt.away_team.name}",
                                                 "rivalry": an.rivalry["name"] if an.rivalry else None,
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
            _announce_pod(chosen)
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
        try:
            flagged = radar.flagged_now()
            attach_alerts(report, {an.match.id: radar.alerts_for_match(s, an.match, now, flagged) for an in analyses})
        except Exception:  # noqa: BLE001 - sin radar el informe del día sigue sirviendo
            log.exception("No se pudieron calcular los avisos del radar")
            attach_alerts(report, {})
    return report


def request_notes(s: Session, settled: list[m.Pick]) -> int:
    """Pide la explicación de Claude de las apuestas del día perdidas sin arriesgar la liquidación: si falla, solo se
    deshace su propio savepoint."""
    from apuestas.services import ai_notes  # aquí: ai_notes importa queries, que importa este módulo

    try:
        with s.begin_nested():
            return ai_notes.after_settle(s, settled)
    except Exception:  # noqa: BLE001 - sin nota la liquidación sigue valiendo
        log.exception("No se pudo pedir la explicación de Claude")
        return 0


def attach_alerts(report: dict, alerts: dict[int, list[dict]]) -> None:
    """Pone los avisos del radar de cada partido en sus filas, en las apuestas con valor y en la del día."""
    for row in [*report.get("matches", []), *report.get("value_bets", [])]:
        row["alerts"] = alerts.get(row["match_id"], [])
    if report.get("pick_of_day"):
        report["pick_of_day"]["alerts"] = alerts.get(report["pick_of_day"]["match_id"], [])


# --------------------------------------------------------------------------- liquidación


# Referencias del CLV, de la más fiable a la menos, siempre sin margen: el cierre de las casas afiladas
# (football-data), el último precio de Pinnacle antes del inicio (OddsPapi; `jobs.scheduler.job_closing_odds` lo baja
# unos minutos antes de los partidos con apuestas que pasan el corte) y el cierre de bet365. football-data solo trae
# el cierre de 1X2, Más/Menos 2.5 y hándicap asiático de las ligas, y días después del partido.
CLV_REFERENCES = (("pinnacle", "closing"), ("betfair_ex", "closing"), ("pinnacle", "live"), ("bet365", "closing"))


def closing_reference(s: Session, match: m.Match, market: str, selection: str,
                      line: float | None) -> tuple[float, str, datetime] | None:
    """Cuota justa de referencia para el CLV: (cuota sin margen, casa, cuándo se vio ese precio por primera vez)."""
    rows = s.scalars(select(m.OddsSnapshot).where(
        m.OddsSnapshot.match_id == match.id, m.OddsSnapshot.market == market,
        m.OddsSnapshot.bookmaker.in_({b for b, _ in CLV_REFERENCES}),
        (m.OddsSnapshot.kind == "closing") | (m.OddsSnapshot.captured_at < match.kickoff_utc),
    ).order_by(m.OddsSnapshot.captured_at)).all()
    for book, kind in CLV_REFERENCES:
        latest = {(r.selection, r.line): r for r in rows if r.bookmaker == book and r.kind == kind}
        prob = book_fair_prob(list(latest.values()), book, market, selection, line)
        if prob:
            return round(1 / prob, 3), book, latest[(selection, line)].captured_at
    return None


def set_clv(s: Session, row: m.Pick | m.UserBet) -> bool:
    """Rellena la cuota de referencia y el CLV (cuánto mejor fue la cuota tomada que la justa del cierre)."""
    ref = closing_reference(s, row.match, row.market, row.selection, row.line)
    if ref is None:
        return False
    row.closing_odds, book, at = ref
    taken = taken_odds(row) if isinstance(row, m.Pick) else row.odds
    row.clv = round(oddsmath.clv(taken, row.closing_odds), 4)
    if isinstance(row, m.Pick):
        row.closing_source, row.closing_at = book, at
    return True


def settle_all() -> dict:
    out = {"picks": 0, "bets": 0}
    with session_scope() as s:
        settled = []
        # Las abiertas y las retiradas que llegaron a anunciarse (cuentan en los contadores con lo anunciado)
        for pick in s.scalars(select(m.Pick).where(or_(
                m.Pick.status == "open",
                and_(m.Pick.status == "withdrawn", m.Pick.announced_at.is_not(None), m.Pick.result.is_(None))))):
            try:
                res = settle(s, pick.match, pick.market, pick.selection, pick.line)
            except Exception:  # noqa: BLE001 - un dato roto no puede frenar la liquidación de las demás
                log.exception("No se pudo liquidar la apuesta %s (%s %s)", pick.id, pick.market, pick.selection)
                continue
            if res is None:
                continue
            pick.result = res
            if pick.status == "open":
                pick.status = "settled"
            set_clv(s, pick)
            settled.append(pick)
            out["picks"] += 1
        out["notes"] = request_notes(s, settled)
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
            try:
                res = settle(s, bet.match, bet.market, bet.selection, bet.line, bet.player_id)
            except Exception:  # noqa: BLE001
                log.exception("No se pudo liquidar la apuesta del usuario %s (%s)", bet.id, bet.market)
                continue
            if res is None:
                continue
            bet.result = res
            bet.profit = profit(res, bet.stake, bet.odds)
            set_clv(s, bet)
            out["bets"] += 1
        out["clv"] = fill_missing_clv(s)
    return out


def fill_missing_clv(s: Session, days: int = 21) -> int:
    """CLV de lo ya liquidado sin referencia: football-data publica el cierre días después del partido."""
    since = datetime.now(UTC) - timedelta(days=days)
    n = 0
    for model in (m.Pick, m.UserBet):
        rows = s.scalars(select(model).join(m.Match, m.Match.id == model.match_id).where(
            model.result.is_not(None), model.closing_odds.is_(None), m.Match.kickoff_utc >= since)).all()
        n += sum(set_clv(s, r) for r in rows)
    return n


HIT_RESULTS = ("win", "half_win")
MISS_RESULTS = ("loss", "half_loss")
PUSH_RESULTS = ("push", "void")


def record_from(rows: list) -> dict:
    """Contador de aciertos a partir de picks (status, result, odds, clv, created_at), con 1 unidad por apuesta.

    El porcentaje de acierto no cuenta las devueltas (push/void): no se ganó ni se perdió. El CLV medio, de las
    liquidadas que tienen referencia (`with_clv`).
    `since` es el día (en Lima) en que el sistema eligió la primera.
    """
    settled = [p for p in rows if p.result is not None]
    hits = sum(1 for p in settled if p.result in HIT_RESULTS)
    misses = sum(1 for p in settled if p.result in MISS_RESULTS)
    pushes = sum(1 for p in settled if p.result in PUSH_RESULTS)
    pl = sum(profit(p.result, 1.0, taken_odds(p)) for p in settled)
    decided = hits + misses
    clvs = [p.clv for p in settled if p.clv is not None]
    return {
        "since": min((p.created_at for p in rows), default=None),
        "settled": len(settled), "hits": hits, "misses": misses, "pushes": pushes,
        "pending": sum(1 for p in rows if p.result is None),
        "hit_rate": round(hits / decided, 3) if decided else None,
        "profit_units": round(pl, 2), "roi": round(pl / len(settled), 4) if settled else None,
        "avg_clv": round(sum(clvs) / len(clvs), 4) if clvs else None, "with_clv": len(clvs),
    }


def clv_fields(p: m.Pick) -> dict:
    """CLV de una apuesta guardada con su referencia, o por qué no lo tiene."""
    ref = None
    if p.closing_source:
        ref = {"book": p.closing_source, "kind": "closing" if p.closing_at >= p.match.kickoff_utc else "live",
               "minutes_before": max(0, round((p.match.kickoff_utc - p.closing_at).total_seconds() / 60))}
    note = None
    if p.status == "settled" and p.clv is None:
        note = "Sin cuota de referencia: ni Pinnacle ni el cierre de bet365 tenían esta línea antes del partido"
    return {"clv": p.clv, "closing_odds": p.closing_odds, "clv_ref": ref, "clv_note": note}


def pick_record() -> dict:
    """Aciertos de la apuesta del día desde el primer día del sistema: todas las que se anunciaron como apuesta del
    día, con la cuota anunciada, aunque luego se retiraran o el recálculo eligiera otra."""
    with session_scope() as s:
        rows = list(s.scalars(select(m.Pick).where(m.Pick.was_pick_of_day.is_(True))))
        out = record_from(rows)
    if out["since"]:
        out["since"] = out["since"].astimezone(get_settings().tz).date().isoformat()
    return out


def qualified_picks(days: int = 60) -> dict:
    """Todas las que pasaron el corte (no solo la apuesta del día): aciertos desde el inicio y las de los últimos días.

    Cuenta lo anunciado (la primera vez que pasó el corte), aunque luego se retirara o dejara de pasarlo.
    """
    tz = get_settings().tz
    since = today_local() - timedelta(days=days)
    with session_scope() as s:
        rows = list(s.scalars(select(m.Pick).where(m.Pick.announced_at.is_not(None))))
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
            "odds": taken_odds(p), "prob": round(p.announced_prob or p.model_prob, 3),
            "ev": round(p.announced_ev if p.announced_ev is not None else p.ev, 3),
            "confidence": round(p.confidence, 2), "is_pick_of_day": p.was_pick_of_day,
            "status": p.status, "result": p.result, **clv_fields(p),
            "profit_units": round(profit(p.result, 1.0, taken_odds(p)), 2) if p.result else None,
        } for p in recent]}


def pick_history(days: int = 60, only_pick_of_day: bool = True) -> dict:
    """Rendimiento histórico de los picks del sistema (stake plano de 1 unidad)."""
    since = today_local() - timedelta(days=days)
    with session_scope() as s:
        q = select(m.Pick).where(m.Pick.result.is_not(None), m.Pick.pick_date >= since)
        if only_pick_of_day:
            q = q.where(m.Pick.was_pick_of_day.is_(True))
        picks = list(s.scalars(q))
        n = len(picks)
        pl = sum(profit(p.result, 1.0, taken_odds(p)) for p in picks)
        wins = sum(1 for p in picks if p.result in ("win", "half_win"))
        clvs = [p.clv for p in picks if p.clv is not None]
        return {
            "picks": n, "profit_units": round(pl, 2), "roi": round(pl / n, 4) if n else None,
            "hit_rate": round(wins / n, 3) if n else None,
            "avg_clv": round(sum(clvs) / len(clvs), 4) if clvs else None,
            "last": [{"pick_id": p.id, "date": p.pick_date.isoformat(),
                      "match": f"{p.match.home_team.name} vs {p.match.away_team.name}",
                      "market": p.market, "selection": p.selection, "line": p.line, "odds": taken_odds(p),
                      "result": p.result, "clv": p.clv} for p in sorted(picks, key=lambda p: p.pick_date)[-10:]],
        }
