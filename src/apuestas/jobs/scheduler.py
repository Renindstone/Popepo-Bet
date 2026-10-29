"""Tareas programadas (hora de Lima). Se ejecuta como proceso aparte: `apuestas worker`.

05:30  resultados de ayer + liquidación + reentrenar modelos
08:30  detalles de próximos partidos (alineación prevista, bajas, árbitro) + cuotas
09:00  apuesta del día -> Telegram
70, 50, 35, 20 y 10 min antes de cada partido (si aún no hay alineación confirmada): descargarla, recalcular
             y avisar si cambia la apuesta del día. FotMob suele publicarla una hora antes.
15 min antes de cada partido con apuestas abiertas que pasan el corte: Pinnacle por OddsPapi, la referencia de su
             CLV (como mucho `oddspapi_closing_per_day` peticiones al día).
cada 30 min  partidos terminados (3 h tras el inicio) o apuestas abiertas de partidos jugados -> resultado y liquidar
cada 3 h     cuotas
02:00  descarga de detalles atrasados (historial)
lunes 04:00  niveles de almacenamiento (temporadas terminadas -> resumen y archivo)

Si el equipo estuvo apagado a la hora de una tarea diaria, se ejecuta al arrancar el worker (ver `catch_up`).
Si estuvo suspendido, la tarea corre al despertar si no pasó más de `MISFIRE_GRACE_S`.
Las tareas que descargan esperan a que haya internet (al encender el equipo la red tarda en llegar): las diarias
hasta `NETWORK_WAIT_S`; si sigue sin haber, no se marcan como hechas y `catch_up` vuelve a probar en
`CATCH_UP_RETRY_MIN`. Las periódicas (alineaciones, liquidación, cuotas) simplemente se saltan esa vuelta.
"""

from __future__ import annotations

import functools
import json
import logging
import socket
import threading
from datetime import UTC, datetime, time, timedelta
from time import monotonic, sleep

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import func, or_, select

from apuestas.config import get_settings
from apuestas.core.competitions import FULL, season_start_year
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.ingest import pipeline

log = logging.getLogger(__name__)


def _state_path():
    return get_settings().var_dir / "worker_state.json"


def _load_state() -> dict[str, str]:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}


def _mark_done(key: str) -> None:
    state = _load_state()
    state[key] = datetime.now(UTC).isoformat()
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(path)


def last_done(key: str) -> datetime | None:
    value = _load_state().get(key)
    return datetime.fromisoformat(value) if value else None


# ---------------------------------------------------------------------------------------------- internet

# Para saber si hay internet solo se resuelve el nombre de estos hosts: no se hace ninguna petición a las fuentes
NETWORK_PROBE_HOSTS = ("www.fotmob.com", "understat.com", "www.football-data.co.uk")
NETWORK_WAIT_S = 600.0  # una tarea diaria espera hasta 10 min a que haya internet
NETWORK_POLL_S = 15.0
CATCH_UP_RETRY_MIN = 15  # si aun así no lo hubo, se vuelve a probar a los 15 min
NO_NETWORK = "sin internet"  # lo que devuelve una tarea que no corrió por falta de internet


def network_ready() -> bool:
    """Hay internet si se resuelve el nombre de alguno de los hosts de prueba (el 23-10-2026, al encender el equipo,
    la tarea de recuperación arrancó sin red: «Temporary failure in name resolution» en todas las fuentes)."""
    for host in NETWORK_PROBE_HOSTS:
        try:
            socket.getaddrinfo(host, 443)
            return True
        except OSError:
            continue
    return False


def wait_for_network(max_wait_s: float = NETWORK_WAIT_S, poll_s: float = NETWORK_POLL_S) -> bool:
    deadline = monotonic() + max_wait_s
    while not network_ready():
        if monotonic() >= deadline:
            return False
        sleep(poll_s)
    return True


_sched = None  # el planificador en marcha, para reprogramar la recuperación
_running: set[str] = set()
_running_lock = threading.Lock()


def _retry_catch_up() -> None:
    if _sched is not None:
        when = datetime.now(get_settings().tz) + timedelta(minutes=CATCH_UP_RETRY_MIN)
        _sched.add_job(catch_up, "date", run_date=when, id="catch_up", replace_existing=True)


def _safe(name: str, key: str | None = None, network: float | None = None):
    """Registra inicio y fallos sin tumbar el worker; con `key`, guarda la hora del último éxito.

    `network`: segundos que espera a que haya internet antes de empezar (None = la tarea no lo necesita; 0 = si no
    hay, se salta). Sin internet no corre, no se marca como hecha y devuelve `NO_NETWORK`; si es una tarea diaria,
    se reprograma la recuperación. Una tarea no corre dos veces a la vez (a su hora y desde la recuperación).
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            busy = key or name
            with _running_lock:
                if busy in _running:
                    log.info("Tarea %s: ya está en marcha", name)
                    return None
                _running.add(busy)
            try:
                if network is not None and not wait_for_network(network):
                    if key:
                        log.warning("Tarea %s: sin internet; se vuelve a probar en %d min", name, CATCH_UP_RETRY_MIN)
                        _retry_catch_up()
                    return NO_NETWORK
                log.info("Tarea %s: inicio", name)
                try:
                    out = fn(*a, **k)
                except Exception:  # noqa: BLE001
                    log.exception("Tarea %s falló", name)
                    return None
                if key:
                    _mark_done(key)
                return out
            finally:
                with _running_lock:
                    _running.discard(busy)
        return wrapper
    return deco


@_safe("resultados", key="results", network=NETWORK_WAIT_S)
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


@_safe("previa", key="preview", network=NETWORK_WAIT_S)
def job_preview() -> None:
    pipeline.sync_fotmob_details(days_ahead=4, backfill_limit=0, force_upcoming=True)
    pipeline.sync_upcoming_odds()
    if get_settings().oddspapi_key:
        from apuestas.ingest import oddspapi

        pipeline._run("oddspapi", "upcoming odds", oddspapi.sync_upcoming)
    from apuestas.services.queries import warm_team_logos

    warm_team_logos()


@_safe("apuesta del día", key="daily_pick")
def job_daily_pick() -> None:
    from apuestas.bot import telegram
    from apuestas.services import picks

    report = picks.generate()
    telegram.send(telegram.fmt_pick_report(report))


_last_pod: dict[str, tuple] = {}


# Minutos antes del inicio en que se busca la alineación confirmada (mientras no esté). FotMob suele publicarla
# una hora antes; la de 50 deja margen si se retrasa, y las siguientes la recogen si llega tarde.
LINEUP_CHECKS_MIN = (70, 50, 35, 20, 10)
LINEUP_EVERY_MIN = 5  # la tarea corre cada 5 minutos y solo descarga los partidos que tocan


def lineup_due(minutes_to_kickoff: float) -> bool:
    """Si a esta distancia del inicio toca buscar la alineación (una vez por cada punto de LINEUP_CHECKS_MIN)."""
    half = LINEUP_EVERY_MIN / 2
    return any(t - half < minutes_to_kickoff <= t + half for t in LINEUP_CHECKS_MIN)


@_safe("alineaciones", network=0)
def job_lineups() -> None:
    """Busca la alineación confirmada de los partidos que empiezan pronto; si cambia la apuesta del día, avisa."""
    from apuestas.bot import telegram
    from apuestas.services import picks

    now = datetime.now(UTC)
    horizon = timedelta(minutes=max(LINEUP_CHECKS_MIN) + LINEUP_EVERY_MIN)
    with session_scope() as s:
        # Solo las competiciones completas: de la Europa League y la Conference no se usan las alineaciones (con
        # ellas, un jueves eran 18 partidos y cinco búsquedas por partido que no servían para nada)
        soon = s.execute(select(m.Match.id, m.Match.kickoff_utc)
                         .join(m.Competition, m.Competition.id == m.Match.competition_id).where(
            m.Competition.code.in_([c.code for c in FULL]),
            m.Match.status == "scheduled", m.Match.fotmob_id.is_not(None),
            m.Match.kickoff_utc >= now, m.Match.kickoff_utc <= now + horizon,
            (m.Match.lineup_status.is_(None)) | (m.Match.lineup_status != "confirmed"))).all()
    due = [mid for mid, ko in soon if lineup_due((ko - now).total_seconds() / 60)]
    if not due:
        return
    log.info("Buscando alineaciones confirmadas de %s partidos", len(due))
    pipeline.sync_fotmob_details(match_ids=due, backfill_limit=0, force_upcoming=True, hours_ahead=2)
    report = picks.generate()
    pod = report.get("pick_of_day")
    key = (pod["match_id"], pod["market"], pod["selection"], pod["line"]) if pod else None
    day = report["date"]
    if day in _last_pod and _last_pod[day] != key:
        telegram.send("🔄 <b>Cambio en la apuesta del día tras conocerse alineaciones</b>\n\n"
                      + telegram.fmt_pick_report(report))
    _last_pod[day] = key


# Minutos antes del inicio en que se baja Pinnacle para el CLV (la tarea corre cada LINEUP_EVERY_MIN minutos)
CLOSING_CHECK_MIN = 15
CLOSING_TASK = "closing odds"


def closing_due(minutes_to_kickoff: float) -> bool:
    half = LINEUP_EVERY_MIN / 2
    return CLOSING_CHECK_MIN - half < minutes_to_kickoff <= CLOSING_CHECK_MIN + half


@_safe("cierre de Pinnacle", network=0)
def job_closing_odds() -> None:
    """Pinnacle poco antes de los partidos con apuestas abiertas que pasan el corte, para su CLV (cupo de OddsPapi)."""
    from apuestas.services.picks import local_day_bounds, today_local

    st = get_settings()
    if not (st.oddspapi_key and st.oddspapi_closing_per_day > 0):
        return
    now = datetime.now(UTC)
    with session_scope() as s:
        soon = s.execute(select(m.Competition.code, m.Match.kickoff_utc)
                         .join(m.Match, m.Match.competition_id == m.Competition.id)
                         .join(m.Pick, m.Pick.match_id == m.Match.id).where(
            m.Pick.status == "open", m.Pick.qualifies.is_(True), m.Match.status == "scheduled",
            m.Match.kickoff_utc > now, m.Match.kickoff_utc <= now + timedelta(minutes=CLOSING_CHECK_MIN + LINEUP_EVERY_MIN),
        )).all()
        codes = {code for code, ko in soon if closing_due((ko - now).total_seconds() / 60)}
        if not codes:
            return
        # Las que fallan también cuentan: OddsPapi cobra cada llamada
        done = s.scalar(select(func.count()).select_from(m.IngestionRun).where(
            m.IngestionRun.source == "oddspapi", m.IngestionRun.task == CLOSING_TASK,
            m.IngestionRun.started_at >= local_day_bounds(today_local())[0]))
    if done >= st.oddspapi_closing_per_day:
        log.info("Cierre de Pinnacle: ya van %d descargas hoy; %s se queda con el último precio guardado", done, codes)
        return
    from apuestas.ingest import oddspapi

    pipeline._run("oddspapi", CLOSING_TASK, lambda: oddspapi.sync_closing(codes))


POST_MATCH_HOURS = 3  # desde el inicio: el partido ya terminó y FotMob tiene el resultado y las estadísticas


@_safe("notas de Claude", network=0)
def job_ai_notes() -> None:
    """Escribe con Claude las explicaciones pendientes (por qué falló la apuesta del día), de una en una."""
    from apuestas.services import ai_notes

    n = ai_notes.process_pending()
    if n:
        log.info("Notas de Claude escritas: %d", n)


@_safe("liquidación tras el partido", network=0)
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


@_safe("cuotas", network=0)
def job_odds() -> None:
    pipeline.sync_upcoming_odds()


@_safe("historial", key="backfill", network=NETWORK_WAIT_S)
def job_backfill() -> None:
    pipeline.sync_fotmob_details(days_ahead=0, backfill_limit=400)


@_safe("almacenamiento", key="storage")
def job_storage() -> None:
    from apuestas.archive.seasons import apply_tiers

    log.info("Niveles: %s", apply_tiers())


# Tareas diarias o semanales que se recuperan si el equipo estaba apagado a su hora, en este orden
# (la apuesta del día necesita los resultados y la previa). id -> (función, hora, minuto, día de la semana, horas de margen)
DAILY_JOBS: dict[str, tuple] = {
    "results": (job_results, 5, 30, None, 20),
    "preview": (job_preview, 8, 30, None, 20),
    "daily_pick": (job_daily_pick, 9, 0, None, 12),  # pasado ese margen, la apuesta de hoy ya no sirve
    "backfill": (job_backfill, 2, 0, None, 20),
    "storage": (job_storage, 4, 0, 0, 24 * 6),
}
MISFIRE_GRACE_S = 3600  # si el equipo estuvo suspendido, una tarea atrasada aún corre al despertar


def last_fire(hour: int, minute: int, weekday: int | None, now: datetime) -> datetime:
    """Última hora programada (en la zona de `now`) igual o anterior a `now`."""
    fire = datetime.combine(now.date(), time(hour, minute), tzinfo=now.tzinfo)
    while fire > now or (weekday is not None and fire.weekday() != weekday):
        fire -= timedelta(days=1)
    return fire


def missed_jobs(now: datetime) -> list[str]:
    """Tareas cuya última hora programada pasó sin que terminaran bien después (y dentro de su margen)."""
    out = []
    for key, (_fn, hour, minute, weekday, grace_h) in DAILY_JOBS.items():
        fire = last_fire(hour, minute, weekday, now)
        done = last_done(key)
        if now - fire <= timedelta(hours=grace_h) and (done is None or done < fire):
            out.append(key)
    return out


def catch_up() -> None:
    """Ejecuta las tareas diarias que no corrieron porque el equipo estaba apagado."""
    now = datetime.now(get_settings().tz)
    pending = missed_jobs(now)
    if not pending:
        return
    log.info("Recuperando tareas que no corrieron con el equipo apagado: %s", pending)
    for key in pending:
        fn, hour, minute, weekday, _grace = DAILY_JOBS[key]
        done = last_done(key)
        if done and done >= last_fire(hour, minute, weekday, now):  # ya corrió a su hora mientras recuperábamos
            continue
        if fn() == NO_NETWORK:
            # Las siguientes dependen de esta (la apuesta del día necesita los resultados y la previa): se esperan
            # a la próxima vuelta, que ya quedó programada
            break


def run() -> None:
    global _sched
    tz = get_settings().tz
    sched = _sched = BlockingScheduler(timezone=tz, job_defaults={"misfire_grace_time": MISFIRE_GRACE_S, "coalesce": True})
    for key, (fn, hour, minute, weekday, _grace) in DAILY_JOBS.items():
        sched.add_job(fn, "cron", hour=hour, minute=minute, id=key,
                      **({"day_of_week": weekday} if weekday is not None else {}))
    sched.add_job(job_lineups, "cron", minute=f"*/{LINEUP_EVERY_MIN}", id="lineups")
    sched.add_job(job_closing_odds, "cron", minute=f"*/{LINEUP_EVERY_MIN}", id="closing_odds")
    sched.add_job(job_post_match, "cron", minute="15,45", id="post_match")
    sched.add_job(job_odds, "cron", hour="*/3", minute=10, id="odds")
    sched.add_job(job_ai_notes, "cron", minute="5,25,45", id="ai_notes")
    sched.add_job(catch_up, "date", run_date=datetime.now(tz) + timedelta(seconds=10), id="catch_up")
    log.info("Worker iniciado (%s). Tareas: %s", tz, [j.id for j in sched.get_jobs()])
    sched.start()
