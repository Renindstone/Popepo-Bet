"""Tareas programadas (hora de Lima). Se ejecuta como proceso aparte: `apuestas worker`.

05:30  resultados de ayer + liquidación + reentrenar modelos
08:30  detalles de próximos partidos (alineación prevista, bajas, árbitro) + cuotas
09:00  apuesta del día -> Telegram
cada 20 min  partidos que empiezan en < 100 min: alineación confirmada -> recalcular y avisar si cambia
cada 30 min  partidos terminados (3 h tras el inicio) o apuestas abiertas de partidos jugados -> resultado y liquidar
cada 3 h     cuotas
02:00  descarga de detalles atrasados (historial)
lunes 04:00  niveles de almacenamiento (temporadas terminadas -> resumen y archivo)
"""

from __future__ import annotations

import functools
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import func, or_, select

from apuestas.config import get_settings
from apuestas.core.competitions import season_start_year
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.ingest import pipeline

log = logging.getLogger(__name__)


def _safe(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            log.info("Tarea %s: inicio", name)
            try:
                return fn(*a, **k)
            except Exception:  # noqa: BLE001
                log.exception("Tarea %s falló", name)
        return wrapper
    return deco


@_safe("resultados")
def job_results() -> None:
    from apuestas.models.fitting import fit_all, save_bundle, store_team_ratings
    from apuestas.services.picks import settle_all

    cur = season_start_year(datetime.now(UTC).date())
    pipeline.sync_fotmob_leagues([cur])
    pipeline.sync_football_data([cur])
    pipeline.sync_understat([cur])
    pipeline.merge_duplicate_teams()
    pipeline.sync_fotmob_details(days_ahead=1, backfill_limit=150)
    settled = settle_all()
    bundle = fit_all()
    save_bundle(bundle)
    store_team_ratings(bundle)
    log.info("Liquidadas %s; modelo actualizado a %s", settled, bundle.as_of)


@_safe("previa")
def job_preview() -> None:
    pipeline.sync_fotmob_details(days_ahead=4, backfill_limit=0, force_upcoming=True)
    pipeline.sync_upcoming_odds()
    if get_settings().oddspapi_key:
        from apuestas.ingest import oddspapi

        pipeline._run("oddspapi", "upcoming odds", oddspapi.sync_upcoming)


@_safe("apuesta del día")
def job_daily_pick() -> None:
    from apuestas.bot import telegram
    from apuestas.services import picks

    report = picks.generate()
    telegram.send(telegram.fmt_pick_report(report))


_last_pod: dict[str, tuple] = {}


@_safe("alineaciones")
def job_lineups() -> None:
    """Refresca partidos que empiezan pronto; si cambia la apuesta del día, avisa."""
    from apuestas.bot import telegram
    from apuestas.services import picks

    now = datetime.now(UTC)
    with session_scope() as s:
        soon = s.scalars(select(m.Match.id).where(
            m.Match.status == "scheduled", m.Match.fotmob_id.is_not(None),
            m.Match.kickoff_utc >= now, m.Match.kickoff_utc <= now + timedelta(minutes=100),
            (m.Match.lineup_status.is_(None)) | (m.Match.lineup_status != "confirmed"))).all()
    if not soon:
        return
    pipeline.sync_fotmob_details(hours_ahead=1.7, backfill_limit=0, force_upcoming=True)
    report = picks.generate()
    pod = report.get("pick_of_day")
    key = (pod["match_id"], pod["market"], pod["selection"], pod["line"]) if pod else None
    day = report["date"]
    if day in _last_pod and _last_pod[day] != key:
        telegram.send("🔄 <b>Cambio en la apuesta del día tras conocerse alineaciones</b>\n\n"
                      + telegram.fmt_pick_report(report))
    _last_pod[day] = key


POST_MATCH_HOURS = 3  # desde el inicio: el partido ya terminó y FotMob tiene el resultado y las estadísticas


@_safe("liquidación tras el partido")
def job_post_match() -> None:
    """Liquida poco después de cada partido, sin esperar a las 05:30 (solo descarga si hay algo que liquidar)."""
    from apuestas.services.picks import settle_all

    now = datetime.now(UTC)
    played = now - timedelta(hours=POST_MATCH_HOURS)
    with session_scope() as s:
        fresh = s.scalar(select(func.count()).select_from(m.Match).where(
            m.Match.fotmob_id.is_not(None), m.Match.kickoff_utc <= played,
            m.Match.kickoff_utc >= now - timedelta(hours=12),
            or_(m.Match.status != "finished", m.Match.details_fetched_at.is_(None),
                m.Match.details_fetched_at < m.Match.kickoff_utc + timedelta(hours=2))))
        open_bets = s.scalar(select(func.count()).select_from(m.UserBet).join(m.Match).where(
            m.UserBet.result.is_(None), m.Match.kickoff_utc <= played))
        open_picks = s.scalar(select(func.count()).select_from(m.Pick).join(m.Match).where(
            m.Pick.status == "open", m.Match.kickoff_utc <= played))
    if not (fresh or open_bets or open_picks):
        return
    if fresh:
        pipeline.sync_fotmob_details(hours_ahead=0, backfill_limit=fresh + 5)
    out = settle_all()
    if out["picks"] or out["bets"] or out["clv"]:
        log.info("Liquidación tras el partido: %s", out)


@_safe("cuotas")
def job_odds() -> None:
    pipeline.sync_upcoming_odds()


@_safe("historial")
def job_backfill() -> None:
    pipeline.sync_fotmob_details(days_ahead=0, backfill_limit=400)


@_safe("almacenamiento")
def job_storage() -> None:
    from apuestas.archive.seasons import apply_tiers

    log.info("Niveles: %s", apply_tiers())


def run() -> None:
    tz = get_settings().tz
    sched = BlockingScheduler(timezone=tz)
    sched.add_job(job_results, "cron", hour=5, minute=30, id="results")
    sched.add_job(job_preview, "cron", hour=8, minute=30, id="preview")
    sched.add_job(job_daily_pick, "cron", hour=9, minute=0, id="daily_pick")
    sched.add_job(job_lineups, "cron", minute="*/20", id="lineups")
    sched.add_job(job_post_match, "cron", minute="15,45", id="post_match")
    sched.add_job(job_odds, "cron", hour="*/3", minute=10, id="odds")
    sched.add_job(job_backfill, "cron", hour=2, minute=0, id="backfill")
    sched.add_job(job_storage, "cron", day_of_week="mon", hour=4, minute=0, id="storage")
    log.info("Worker iniciado (%s). Tareas: %s", tz, [j.id for j in sched.get_jobs()])
    sched.start()
