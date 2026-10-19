"""Almacenamiento por niveles y resúmenes de temporada.

- hot  (temporada actual): todo el detalle en PostgreSQL.
- warm (temporadas dentro del historial que usan los modelos): se borran las cuotas intermedias;
  quedan apertura, cierre y la primera/última captura de cada selección.
- cold (más antiguas): el detalle (alineaciones, stats de jugadores, observaciones, cuotas) se exporta a
  Parquet (var/archive/<temporada>/<competición>/*.parquet) y se borra de la base. Se conservan el partido
  y las estadísticas de equipo (son pequeñas y sirven para ratings a largo plazo) y el resumen de temporada.
  Los Parquet se consultan con DuckDB: `apuestas archive query "select ..."`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import duckdb
import pandas as pd
from sqlalchemy import delete, func, select, text

from apuestas.config import get_settings
from apuestas.core.competitions import season_start_year
from apuestas.db import models as m
from apuestas.db.session import get_engine, session_scope

log = logging.getLogger(__name__)


def summarize_season(season_id: int) -> int:
    """Resumen por equipo, jugador y árbitro. Sirve de punto de partida para la temporada siguiente."""
    with session_scope() as s:
        season = s.get(m.Season, season_id)
        s.execute(delete(m.SeasonSummary).where(m.SeasonSummary.season_id == season_id))
        matches = list(s.scalars(select(m.Match).where(m.Match.season_id == season_id, m.Match.status == "finished")))
        team_acc: dict[int, dict] = {}
        for mt in matches:
            for tid, gf, ga, home in ((mt.home_team_id, mt.home_goals, mt.away_goals, True),
                                      (mt.away_team_id, mt.away_goals, mt.home_goals, False)):
                a = team_acc.setdefault(tid, {"played": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "home_pts": 0,
                                              "away_pts": 0})
                a["played"] += 1
                a["gf"] += gf
                a["ga"] += ga
                pts = 3 if gf > ga else (1 if gf == ga else 0)
                a["w" if pts == 3 else ("d" if pts == 1 else "l")] += 1
                a["home_pts" if home else "away_pts"] += pts
        stats = s.execute(
            select(m.TeamMatchStats.team_id, func.avg(m.TeamMatchStats.xg), func.avg(m.TeamMatchStats.shots),
                   func.avg(m.TeamMatchStats.shots_on_target), func.avg(m.TeamMatchStats.corners),
                   func.avg(m.TeamMatchStats.yellow_cards), func.avg(m.TeamMatchStats.fouls))
            .join(m.Match).where(m.Match.season_id == season_id).group_by(m.TeamMatchStats.team_id)).all()
        for tid, xg, sh, sot, co, yc, fo in stats:
            a = team_acc.setdefault(tid, {})
            a.update({"xg_avg": _r(xg), "shots_avg": _r(sh), "sot_avg": _r(sot), "corners_avg": _r(co),
                      "yellow_avg": _r(yc), "fouls_avg": _r(fo)})
        n = 0
        for tid, metrics in team_acc.items():
            s.add(m.SeasonSummary(season_id=season_id, entity_type="team", entity_id=tid, metrics=metrics))
            n += 1
        players = s.execute(
            select(m.PlayerMatchStats.player_id, func.count(), func.sum(m.PlayerMatchStats.minutes),
                   func.sum(m.PlayerMatchStats.goals), func.sum(m.PlayerMatchStats.assists),
                   func.sum(m.PlayerMatchStats.shots), func.sum(m.PlayerMatchStats.shots_on_target),
                   func.sum(m.PlayerMatchStats.xg), func.sum(m.PlayerMatchStats.yellow_cards),
                   func.avg(m.PlayerMatchStats.rating))
            .join(m.Match).where(m.Match.season_id == season_id).group_by(m.PlayerMatchStats.player_id)).all()
        for pid, apps, mins, g, a, sh, sot, xg, yc, rating in players:
            s.add(m.SeasonSummary(season_id=season_id, entity_type="player", entity_id=pid, metrics={
                "apps": apps, "minutes": mins, "goals": g, "assists": a, "shots": sh, "sot": sot,
                "xg": _r(xg), "yellow": yc, "rating": _r(rating)}))
            n += 1
        log.info("Resumen de %s %s: %d filas", season.competition.code, season.label, n)
        return n


def _r(x) -> float | None:
    return round(float(x), 3) if x is not None else None


def prune_odds(season_id: int) -> int:
    """Deja apertura, cierre y la primera/última captura 'live' de cada selección."""
    sql = text("""
        WITH ranked AS (
            SELECT o.id,
                   row_number() OVER w AS rn_first,
                   row_number() OVER (PARTITION BY o.match_id, o.bookmaker, o.market, o.selection, o.line, o.kind
                                      ORDER BY o.captured_at DESC) AS rn_last
            FROM odds_snapshot o JOIN match mt ON mt.id = o.match_id
            WHERE mt.season_id = :sid AND o.kind = 'live'
            WINDOW w AS (PARTITION BY o.match_id, o.bookmaker, o.market, o.selection, o.line, o.kind
                         ORDER BY o.captured_at)
        )
        DELETE FROM odds_snapshot WHERE id IN (SELECT id FROM ranked WHERE rn_first > 1 AND rn_last > 1)
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {"sid": season_id}).rowcount


DETAIL_TABLES = {
    "lineup": m.Lineup, "player_match_stats": m.PlayerMatchStats, "stat_observation": m.StatObservation,
    "odds_snapshot": m.OddsSnapshot,
}


def export_cold(season_id: int) -> dict[str, int]:
    """Exporta el detalle de la temporada a Parquet y lo borra de PostgreSQL."""
    out: dict[str, int] = {}
    engine = get_engine()
    with session_scope() as s:
        season = s.get(m.Season, season_id)
        folder = get_settings().archive_dir / season.label / season.competition.code
        folder.mkdir(parents=True, exist_ok=True)
        match_ids = list(s.scalars(select(m.Match.id).where(m.Match.season_id == season_id)))
    if not match_ids:
        return out
    for name, model in {"match": m.Match, "team_match_stats": m.TeamMatchStats, **DETAIL_TABLES}.items():
        col = model.id if name == "match" else model.match_id
        df = pd.read_sql(select(model).where(col.in_(match_ids)), engine)
        df.to_parquet(folder / f"{name}.parquet", index=False, compression="zstd")
        out[name] = len(df)
    with session_scope() as s:
        for model in DETAIL_TABLES.values():
            s.execute(delete(model).where(model.match_id.in_(match_ids)))
        s.get(m.Season, season_id).storage_tier = "cold"
    return out


def apply_tiers(today: datetime | None = None) -> dict:
    """Recalcula el nivel de cada temporada y aplica podas/exportaciones."""
    cur = season_start_year((today or datetime.now(UTC)).date())
    keep = get_settings().history_seasons
    report = {}
    with session_scope() as s:
        seasons = [(x.id, x.start_year, x.storage_tier, x.competition.code, x.label) for x in s.scalars(select(m.Season))]
    for sid, year, tier, code, label in seasons:
        key = f"{code} {label}"
        if year >= cur:
            continue
        if year < cur - keep and tier != "cold":
            summarize_season(sid)
            prune_odds(sid)
            report[key] = {"cold": export_cold(sid)}
        elif year >= cur - keep and tier == "hot":
            summarize_season(sid)
            report[key] = {"warm_pruned_odds": prune_odds(sid)}
            with session_scope() as s:
                s.get(m.Season, sid).storage_tier = "warm"
    return report


def query_archive(sql: str) -> pd.DataFrame:
    """Consulta SQL (DuckDB) sobre los Parquet. Ej.: select * from 'var/archive/*/EPL/match.parquet'"""
    base = str(get_settings().archive_dir)
    return duckdb.sql(sql.replace("archive://", base + "/")).df()


def storage_report() -> dict:
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT relname, pg_total_relation_size(relid) AS bytes, n_live_tup
            FROM pg_stat_user_tables ORDER BY 2 DESC""")).all()
    archive = get_settings().archive_dir
    parquet_bytes = sum(p.stat().st_size for p in archive.rglob("*.parquet")) if archive.exists() else 0
    return {"postgres_tables": {r[0]: {"mb": round(r[1] / 1e6, 2), "rows": r[2]} for r in rows},
            "postgres_total_mb": round(sum(r[1] for r in rows) / 1e6, 1),
            "parquet_mb": round(parquet_bytes / 1e6, 2)}
