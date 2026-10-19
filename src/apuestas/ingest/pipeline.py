"""Orquestación de la ingesta: qué se descarga, en qué orden y con qué frecuencia."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select

from apuestas.config import get_settings
from apuestas.core.competitions import COMPETITIONS, FULL, LIGHT, fotmob_season, season_start_year
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.ingest import dedupe, football_data, fotmob, store, understat
from apuestas.ingest.http import SourceBlocked

log = logging.getLogger(__name__)


def _run(source: str, task: str, fn: Callable[[], int]) -> int:
    """Ejecuta una tarea registrándola en ingestion_run. Un fallo no detiene las demás."""
    with session_scope() as s:
        run = m.IngestionRun(source=source, task=task)
        s.add(run)
        s.flush()
        run_id = run.id
    try:
        rows = fn()
        status, error = "ok", None
    except (SourceBlocked, FileNotFoundError) as exc:
        rows, status, error = 0, "error", str(exc)
        log.warning("%s/%s: %s", source, task, exc)
    except Exception as exc:  # noqa: BLE001 - registramos y seguimos con otras fuentes
        rows, status, error = 0, "error", f"{exc}\n{traceback.format_exc()[-2000:]}"
        log.exception("%s/%s falló", source, task)
    with session_scope() as s:
        run = s.get(m.IngestionRun, run_id)
        run.finished_at, run.status, run.rows, run.error = datetime.now(UTC), status, rows, error
    return rows


def seasons_to_load(today: date | None = None) -> list[int]:
    cur = season_start_year(today or datetime.now(UTC).date())
    return list(range(cur - get_settings().history_seasons, cur + 1))


# --------------------------------------------------------------------------- FotMob


def sync_fotmob_leagues(start_years: list[int], codes: list[str] | None = None) -> int:
    total = 0
    current = season_start_year(datetime.now(UTC).date())
    for comp_def in COMPETITIONS.values():
        if comp_def.fotmob_id is None or (codes and comp_def.code not in codes):
            continue
        for year in start_years:

            def task(comp_def=comp_def, year=year) -> int:
                ttl = 3600 if year >= current else None
                fixtures = fotmob.league_matches(comp_def.fotmob_id, fotmob_season(year), ttl=ttl)
                with session_scope() as s:
                    comp = store.ensure_competitions(s)[comp_def.code]
                    season = store.get_season(s, comp, year)
                    for fm in fixtures:
                        store.upsert_fotmob_match(s, comp, season, fm)
                return len(fixtures)

            total += _run("fotmob", f"league {comp_def.code} {year}", task)
    return total


def sync_fotmob_details(
    days_ahead: float = 4,
    backfill_limit: int = 300,
    codes: list[str] | None = None,
    force_upcoming: bool = False,
    hours_ahead: float | None = None,
) -> int:
    """Detalles de partidos: próximos (alineación prevista/confirmada, bajas, árbitro) y jugados sin detalle.

    `hours_ahead` (si se da) sustituye a `days_ahead`: p.ej. 1.7 h para buscar alineaciones confirmadas.
    """
    codes = codes or [c.code for c in FULL]
    now = datetime.now(UTC)
    horizon = timedelta(hours=hours_ahead) if hours_ahead is not None else timedelta(days=days_ahead)
    with session_scope() as s:
        comp_ids = [c.id for c in store.ensure_competitions(s).values() if c.code in codes]
        upcoming = s.scalars(
            select(m.Match.id).where(
                m.Match.competition_id.in_(comp_ids),
                m.Match.fotmob_id.is_not(None),
                m.Match.status == "scheduled",
                m.Match.kickoff_utc >= now - timedelta(hours=3),
                m.Match.kickoff_utc <= now + horizon,
            )
        ).all()
        # Jugados sin detalle (o con detalle tomado antes de terminar): más recientes primero
        pending = s.scalars(
            select(m.Match.id)
            .where(
                m.Match.competition_id.in_(comp_ids),
                m.Match.fotmob_id.is_not(None),
                m.Match.kickoff_utc < now - timedelta(hours=3),
                m.Match.status.in_(["finished", "scheduled"]),
                or_(m.Match.details_fetched_at.is_(None), m.Match.details_fetched_at < m.Match.kickoff_utc + timedelta(hours=2)),
            )
            .order_by(m.Match.kickoff_utc.desc())
            .limit(backfill_limit)
        ).all()

    def fetch(match_id: int, ttl: float | None) -> None:
        with session_scope() as s:
            match = s.get(m.Match, match_id)
            det = fotmob.match_details(match.fotmob_id, ttl=ttl)
            if ttl is None and not det.finished and not det.cancelled:
                # La caché guardó la versión previa al partido: hay que volver a descargarla
                det = fotmob.match_details(match.fotmob_id, ttl=0)
            store.apply_fotmob_details(s, match, det)

    def task() -> int:
        done = 0
        for mid in upcoming:
            fetch(mid, 0 if force_upcoming else 600)
            done += 1
        for mid in pending:
            try:
                fetch(mid, None)  # partido terminado: se cachea para siempre
                done += 1
            except FileNotFoundError:
                log.info("Sin detalles en FotMob para el partido %s", mid)
        return done

    return _run("fotmob", f"details up={len(upcoming)} backfill={len(pending)}", task)


# --------------------------------------------------------------------------- football-data.co.uk


def sync_football_data(start_years: list[int]) -> int:
    total = 0
    current = season_start_year(datetime.now(UTC).date())
    for comp_def in [*FULL, *LIGHT]:
        if comp_def.fd_code is None:
            continue
        for year in start_years:

            def task(comp_def=comp_def, year=year) -> int:
                ttl = 6 * 3600 if year >= current else None
                rows = football_data.season_rows(comp_def.fd_code, year, ttl=ttl)
                with session_scope() as s:
                    comp = store.ensure_competitions(s)[comp_def.code]
                    season = store.get_season(s, comp, year)
                    for r in rows:
                        _apply_fd_row(s, comp, season, comp_def.tier, comp_def.country, r)
                return len(rows)

            total += _run("fdco", f"{comp_def.code} {year}", task)
    return total


def _apply_fd_row(s, comp, season, tier: str, country: str, r: football_data.FDRow) -> m.Match | None:
    # Si FotMob ya trae esta liga (las completas, Serie A, Ligue 1), el partido ya existe: se busca por fecha y
    # nombres parecidos en vez de crear otro. Así "Verona" (football-data) no duplica a "Hellas Verona".
    has_fotmob = tier == "full" or COMPETITIONS[comp.code].fotmob_id is not None
    match = store.find_match(s, comp.id, r.kickoff_utc, r.home, r.away) if has_fotmob else None
    if match is not None:
        store.learn_team_alias(s, match.home_team_id, "fdco", f"{country}:{r.home}", r.home)
        store.learn_team_alias(s, match.away_team_id, "fdco", f"{country}:{r.away}", r.away)
    elif tier == "full":
        log.debug("fdco sin partido: %s %s vs %s", r.kickoff_utc, r.home, r.away)
        return None
    else:
        home = store.resolve_team(s, "fdco", f"{country}:{r.home}", r.home, country)
        away = store.resolve_team(s, "fdco", f"{country}:{r.away}", r.away, country)
        match = store.create_light_match(s, comp, season, r.kickoff_utc, home, away, r.home_goals, r.away_goals)
    if r.home_goals is not None and match.home_goals is None:
        match.home_goals, match.away_goals, match.status = r.home_goals, r.away_goals, "finished"
        match.home_goals_ht, match.away_goals_ht = r.home_goals_ht, r.away_goals_ht
    if r.referee and match.referee_id is None:
        match.referee_id = store.resolve_referee(s, r.referee, source="fdco").id
    if r.stats.get("home") or r.stats.get("away"):
        store.set_observations(s, match, match.home_team_id, "fdco", r.stats.get("home", {}))
        store.set_observations(s, match, match.away_team_id, "fdco", r.stats.get("away", {}))
        store.reconcile(s, match)
    if r.odds:
        store.store_odds(s, match, r.odds, "fdco", captured_at=match.kickoff_utc)
    return match


def sync_upcoming_odds() -> int:
    """Cuotas de bet365 / Betfair Exchange para los próximos partidos (fixtures.csv)."""
    by_div = {c.fd_code: c for c in FULL if c.fd_code}

    def task() -> int:
        rows = football_data.upcoming_rows()
        n = 0
        with session_scope() as s:
            comps = store.ensure_competitions(s)
            for r in rows:
                comp_def = by_div.get(r.div)
                if comp_def is None:
                    continue
                match = store.find_match(s, comps[comp_def.code].id, r.kickoff_utc, r.home, r.away)
                if match is None:
                    continue
                opening = [o for o in r.odds if o.kind == "opening"]
                for o in opening:
                    o.kind = "live"
                n += store.store_odds(s, match, opening, "fdco_fixtures")
        return n

    return _run("fdco", "fixtures odds", task)


# --------------------------------------------------------------------------- Understat


def sync_understat(start_years: list[int]) -> int:
    total = 0
    current = season_start_year(datetime.now(UTC).date())
    for comp_def in FULL:
        if comp_def.understat is None:
            continue
        for year in start_years:

            def task(comp_def=comp_def, year=year) -> int:
                ttl = 6 * 3600 if year >= current else None
                games = understat.league_season(comp_def.understat, year, ttl=ttl)
                n = 0
                with session_scope() as s:
                    comp = store.ensure_competitions(s)[comp_def.code]
                    for g in games:
                        match = s.scalar(select(m.Match).where(m.Match.understat_id == g.understat_id))
                        if match is None:
                            match = store.find_match(s, comp.id, g.kickoff_utc, g.home, g.away)
                            if match is None:
                                continue
                            match.understat_id = g.understat_id
                            store.learn_team_alias(s, match.home_team_id, "understat", g.home, g.home)
                            store.learn_team_alias(s, match.away_team_id, "understat", g.away, g.away)
                        if g.is_result and g.home_xg is not None:
                            store.set_observations(s, match, match.home_team_id, "understat", {"xg": g.home_xg})
                            store.set_observations(s, match, match.away_team_id, "understat", {"xg": g.away_xg})
                            store.reconcile(s, match)
                            n += 1
                return n

            total += _run("understat", f"{comp_def.code} {year}", task)
    return total


# --------------------------------------------------------------------------- equipos duplicados


def merge_duplicate_teams() -> int:
    """Fusiona los equipos que entraron dos veces con nombres distintos (solo los pares seguros)."""

    def task() -> int:
        with session_scope() as s:
            done = dedupe.merge_safe(s)
        for d in done:
            log.info("Equipo duplicado fusionado: %s -> %s (%d partidos)", d["fusionado"], d["conservado"],
                     d["partidos_duplicados"])
        return len(done)

    return _run("dedupe", "equipos duplicados", task)


# --------------------------------------------------------------------------- todo junto


def full_sync(start_years: list[int] | None = None, backfill_limit: int = 300) -> None:
    years = start_years or seasons_to_load()
    sync_fotmob_leagues(years)
    sync_football_data(years)
    sync_understat(years)
    merge_duplicate_teams()
    sync_fotmob_details(backfill_limit=backfill_limit)
    sync_upcoming_odds()
    try:
        from apuestas.ingest import oddspapi

        if get_settings().oddspapi_key:
            _run("oddspapi", "upcoming odds", oddspapi.sync_upcoming)
    except ImportError:
        pass
