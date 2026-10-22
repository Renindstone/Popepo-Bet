"""Guardado en base de datos y resolución de entidades entre fuentes.

La regla general: FotMob define las entidades (equipos, jugadores, partidos) de las competiciones
principales; football-data.co.uk y Understat se "enganchan" a esos partidos por fecha + equipos.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apuestas.core import names
from apuestas.core.competitions import COMPETITIONS, season_label
from apuestas.db import models as m
from apuestas.ingest.fotmob import FMDetails, FMMatch

log = logging.getLogger(__name__)

COUNT_STATS = ("shots", "shots_on_target", "corners", "fouls", "yellow_cards", "red_cards", "offsides", "saves")
# Prioridad de fuentes para estadísticas de conteo (la primera disponible es la "oficial")
SOURCE_PRIORITY = ("fotmob", "fdco", "espn")


# --------------------------------------------------------------------------- catálogo


def ensure_competitions(s: Session) -> dict[str, m.Competition]:
    existing = {c.code: c for c in s.scalars(select(m.Competition))}
    for code, comp in COMPETITIONS.items():
        if code not in existing:
            row = m.Competition(code=code, name=comp.name, country=comp.country, tier=comp.tier, is_cup=comp.is_cup)
            s.add(row)
            existing[code] = row
    s.flush()
    return existing


def get_season(s: Session, comp: m.Competition, start_year: int) -> m.Season:
    season = s.scalar(select(m.Season).where(m.Season.competition_id == comp.id, m.Season.start_year == start_year))
    if season is None:
        cdef = COMPETITIONS.get(comp.code)
        label = season_label(start_year, calendar_year=cdef is not None and cdef.calendar_year)
        season = m.Season(competition_id=comp.id, start_year=start_year, label=label)
        s.add(season)
        s.flush()
    return season


# --------------------------------------------------------------------------- alias


def _alias(s: Session, etype: str, source: str, key: str) -> int | None:
    return s.scalar(
        select(m.EntityAlias.entity_id).where(
            m.EntityAlias.entity_type == etype, m.EntityAlias.source == source, m.EntityAlias.source_key == key
        )
    )


def _add_alias(s: Session, etype: str, entity_id: int, source: str, key: str, name: str | None) -> None:
    if _alias(s, etype, source, key) is None:
        s.add(m.EntityAlias(entity_type=etype, entity_id=entity_id, source=source, source_key=key, source_name=name))
        s.flush()


# --------------------------------------------------------------------------- equipos


def resolve_team(
    s: Session, source: str, source_key: str, name: str, country: str | None = None, threshold: float = 90.0
) -> m.Team:
    """Busca el equipo por alias; si no existe, intenta por nombre parecido; si no, lo crea."""
    tid = _alias(s, "team", source, source_key)
    if tid is not None:
        return s.get(m.Team, tid)

    # Un equipo que ya tiene otro alias de esta misma fuente es otro club (la fuente los distingue)
    taken = set(
        s.scalars(select(m.EntityAlias.entity_id).where(m.EntityAlias.entity_type == "team", m.EntityAlias.source == source))
    )
    query = select(m.Team.id, m.Team.name, m.Team.country)
    candidates = {
        tid: tname
        for tid, tname, tcountry in s.execute(query)
        if tid not in taken and (country is None or tcountry in (None, country))
    }
    match_id, score = names.best_match(name, candidates, threshold=threshold)
    if match_id is not None:
        team = s.get(m.Team, match_id)
        if country and not team.country:
            team.country = country
        if source == "fotmob" and team.name != name and s.scalar(select(m.Team.id).where(m.Team.name == name)) is None:
            team.name = name  # FotMob tiene los nombres más completos
    else:
        unique_name = name
        if s.scalar(select(m.Team.id).where(m.Team.name == name)) is not None:
            unique_name = f"{name} ({country or source})"
        team = m.Team(name=unique_name, country=country)
        s.add(team)
        s.flush()
    _add_alias(s, "team", team.id, source, source_key, name)
    return team


def fotmob_team(s: Session, fotmob_id: int, name: str, country: str | None = None) -> m.Team:
    return resolve_team(s, "fotmob", str(fotmob_id), name, country)


def learn_team_alias(s: Session, team_id: int, source: str, source_key: str, name: str) -> None:
    _add_alias(s, "team", team_id, source, source_key, name)


# --------------------------------------------------------------------------- jugadores y árbitros


def resolve_player(
    s: Session,
    fotmob_id: int,
    name: str,
    team: m.Team | None,
    position: str | None = None,
    market_value: float | None = None,
    season_rating: float | None = None,
    seen_on: date | None = None,
) -> m.Player:
    pid = _alias(s, "player", "fotmob", str(fotmob_id))
    player = s.get(m.Player, pid) if pid is not None else None
    if player is None:
        player = m.Player(name=name, position=position, current_team_id=team.id if team else None)
        s.add(player)
        s.flush()
        _add_alias(s, "player", player.id, "fotmob", str(fotmob_id), name)
    if position and not player.position:
        player.position = position
    if market_value:
        player.market_value_eur = market_value
    if season_rating:
        player.season_rating = season_rating
    if team is not None and player.current_team_id != team.id:
        # Fichaje (o cesión) detectado: el jugador aparece con otro equipo
        if player.current_team_id is not None:
            day = seen_on or datetime.now(UTC).date()
            exists = s.scalar(
                select(m.Transfer.id).where(
                    m.Transfer.player_id == player.id, m.Transfer.to_team_id == team.id
                )
            )
            if exists is None:
                s.add(
                    m.Transfer(
                        player_id=player.id,
                        from_team_id=player.current_team_id,
                        to_team_id=team.id,
                        detected_on=day,
                        market_value_eur=market_value,
                    )
                )
        player.current_team_id = team.id
    return player


def resolve_referee(s: Session, name: str, country: str | None = None, source: str = "fotmob") -> m.Referee:
    rid = _alias(s, "referee", source, names.person_key(name))
    if rid is not None:
        return s.get(m.Referee, rid)
    best, best_score = None, 0.0
    for ref in s.scalars(select(m.Referee)):
        score = names.person_similarity(name, ref.name)
        if score > best_score:
            best, best_score = ref, score
    if best is None or best_score < 90:
        if source != "fotmob":
            # Para nombres abreviados ("T Bramall") preferimos esperar al nombre completo de FotMob,
            # pero si no existe lo creamos igualmente.
            pass
        best = m.Referee(name=name, country=country)
        s.add(best)
        s.flush()
    elif source == "fotmob" and len(name) > len(best.name):
        best.name = name
    _add_alias(s, "referee", best.id, source, names.person_key(name), name)
    return best


# --------------------------------------------------------------------------- partidos


def upsert_fotmob_match(s: Session, comp: m.Competition, season: m.Season, fm: FMMatch) -> m.Match:
    match = s.scalar(select(m.Match).where(m.Match.fotmob_id == fm.fotmob_id))
    home = fotmob_team(s, fm.home_id, fm.home_name)
    away = fotmob_team(s, fm.away_id, fm.away_name)
    if match is None:
        match = m.Match(
            competition_id=comp.id,
            season_id=season.id,
            fotmob_id=fm.fotmob_id,
            kickoff_utc=fm.kickoff_utc,
            home_team_id=home.id,
            away_team_id=away.id,
        )
        s.add(match)
    match.kickoff_utc = fm.kickoff_utc
    match.round = fm.round
    match.status = fm.status
    if fm.status == "finished":
        match.home_goals, match.away_goals = fm.home_goals, fm.away_goals
    s.flush()
    return match


def find_match(
    s: Session,
    competition_id: int,
    kickoff_utc: datetime,
    home_name: str,
    away_name: str,
    window_hours: int = 40,
    min_score: float = 70.0,
) -> m.Match | None:
    """Encuentra nuestro partido a partir de fecha + nombres de otra fuente."""
    lo, hi = kickoff_utc - timedelta(hours=window_hours), kickoff_utc + timedelta(hours=window_hours)
    rows = s.scalars(
        select(m.Match).where(
            m.Match.competition_id == competition_id, m.Match.kickoff_utc >= lo, m.Match.kickoff_utc <= hi
        )
    ).all()
    def name_score(a: str, b: str) -> float:
        # Mismo partido, misma hora y los dos equipos: que un nombre contenga al otro basta ("Inter Milano")
        sc = names.similarity(a, b)
        return max(sc, 80.0) if names.contained(a, b) else sc

    best, best_score = None, 0.0
    for match in rows:
        sh = name_score(home_name, match.home_team.name)
        sa = name_score(away_name, match.away_team.name)
        if min(sh, sa) < min_score:
            continue
        hours_off = abs((match.kickoff_utc - kickoff_utc).total_seconds()) / 3600
        score = sh + sa - hours_off * 0.5
        if score > best_score:
            best, best_score = match, score
    return best


def create_light_match(
    s: Session,
    comp: m.Competition,
    season: m.Season,
    kickoff_utc: datetime,
    home: m.Team,
    away: m.Team,
    home_goals: int | None,
    away_goals: int | None,
) -> m.Match:
    match = s.scalar(
        select(m.Match).where(
            m.Match.competition_id == comp.id,
            m.Match.home_team_id == home.id,
            m.Match.away_team_id == away.id,
            m.Match.kickoff_utc >= kickoff_utc - timedelta(hours=40),
            m.Match.kickoff_utc <= kickoff_utc + timedelta(hours=40),
        )
    )
    if match is None:
        match = m.Match(
            competition_id=comp.id,
            season_id=season.id,
            kickoff_utc=kickoff_utc,
            home_team_id=home.id,
            away_team_id=away.id,
        )
        s.add(match)
    if home_goals is not None and away_goals is not None:
        match.home_goals, match.away_goals, match.status = home_goals, away_goals, "finished"
    s.flush()
    return match


# --------------------------------------------------------------------------- estadísticas


def set_observations(s: Session, match: m.Match, team_id: int, source: str, stats: dict[str, float]) -> None:
    existing = {
        o.stat: o
        for o in s.scalars(
            select(m.StatObservation).where(
                m.StatObservation.match_id == match.id,
                m.StatObservation.team_id == team_id,
                m.StatObservation.source == source,
            )
        )
    }
    for stat, value in stats.items():
        if value is None:
            continue
        obs = existing.get(stat)
        if obs is None:
            s.add(m.StatObservation(match_id=match.id, team_id=team_id, stat=stat, source=source, value=float(value)))
        else:
            obs.value = float(value)
    s.flush()


def reconcile(s: Session, match: m.Match) -> None:
    """Construye TeamMatchStats a partir de las observaciones de todas las fuentes."""
    obs = s.scalars(select(m.StatObservation).where(m.StatObservation.match_id == match.id)).all()
    by_team: dict[int, dict[str, dict[str, float]]] = {}
    for o in obs:
        by_team.setdefault(o.team_id, {}).setdefault(o.stat, {})[o.source] = o.value
    for team_id, stats in by_team.items():
        is_home = team_id == match.home_team_id
        row = s.scalar(
            select(m.TeamMatchStats).where(m.TeamMatchStats.match_id == match.id, m.TeamMatchStats.team_id == team_id)
        )
        if row is None:
            row = m.TeamMatchStats(match_id=match.id, team_id=team_id, is_home=is_home)
            s.add(row)
        row.goals = match.home_goals if is_home else match.away_goals
        discrepancies: dict[str, dict[str, float]] = {}
        for stat in COUNT_STATS:
            values = stats.get(stat) or {}
            chosen = next((values[src] for src in SOURCE_PRIORITY if src in values), None)
            if chosen is not None:
                setattr(row, stat, int(round(chosen)))
            if len({round(v) for v in values.values()}) > 1:
                discrepancies[stat] = values
        # xG: cada proveedor tiene su modelo -> promedio (ensemble)
        xg_values = stats.get("xg") or {}
        if xg_values:
            row.xg = round(sum(xg_values.values()) / len(xg_values), 3)
            row.xg_sources = xg_values
        for stat in ("possession", "big_chances"):
            values = stats.get(stat) or {}
            chosen = next((values[src] for src in SOURCE_PRIORITY if src in values), None)
            if chosen is not None:
                setattr(row, stat, chosen if stat == "possession" else int(chosen))
        row.discrepancies = discrepancies or None
    s.flush()


# --------------------------------------------------------------------------- detalles FotMob


def apply_fotmob_details(s: Session, match: m.Match, det: FMDetails, stats_only: bool = False) -> None:
    """`stats_only` (Europa League y Conference): resultado, árbitro y estadísticas de equipo, sin alineaciones, bajas
    ni jugadores. Sus onces rotados cambiarían el once típico de los equipos de liga y sus jugadores no se usan."""
    home = fotmob_team(s, det.home_id, match.home_team.name)
    away = fotmob_team(s, det.away_id, match.away_team.name)
    team_by_fid = {det.home_id: home, det.away_id: away}
    seen_on = det.kickoff_utc.date()

    if det.cancelled:
        match.status = "cancelled"
    elif det.finished:
        match.status = "finished"
        match.home_goals, match.away_goals = det.home_goals, det.away_goals
        match.home_goals_ht, match.away_goals_ht = det.home_goals_ht, det.away_goals_ht
    match.kickoff_utc = det.kickoff_utc
    if det.referee:
        match.referee_id = resolve_referee(s, det.referee, det.referee_country).id

    # Alineación: se reemplaza completa (prevista -> confirmada)
    if det.players and not stats_only:
        s.query(m.Lineup).filter(m.Lineup.match_id == match.id).delete()
        status = det.lineup_type or ("confirmed" if det.finished else "predicted")
        for p in det.players:
            team = team_by_fid.get(p.team_fotmob_id)
            if team is None:
                continue
            player = resolve_player(
                s, p.fotmob_id, p.name, team, p.position, p.market_value, p.season_rating, seen_on
            )
            s.add(
                m.Lineup(
                    match_id=match.id,
                    team_id=team.id,
                    player_id=player.id,
                    status=status,
                    is_starter=p.is_starter,
                    position=p.position,
                    market_value_eur=p.market_value,
                    season_rating=p.season_rating,
                    shirt_number=p.shirt,
                    pos_x=p.x,
                    pos_y=p.y,
                )
            )
        match.lineup_status = status
        match.lineup_info = {str(team_by_fid[fid].id): info for fid, info in det.team_info.items()
                             if fid in team_by_fid} or None

    # Bajas: solo tiene sentido actualizarlas con partidos que aún no se han jugado
    if not det.finished and not stats_only:
        for team in (home, away):
            reported = [u for u in det.unavailable if team_by_fid.get(u.team_fotmob_id) is team]
            update_availability(s, team, reported, seen_on)

    # Estadísticas de equipo
    for fid, stats in det.team_stats.items():
        team = team_by_fid.get(fid)
        if team is not None:
            set_observations(s, match, team.id, "fotmob", stats)

    # Estadísticas por jugador
    if det.player_stats and not stats_only:
        s.query(m.PlayerMatchStats).filter(m.PlayerMatchStats.match_id == match.id).delete()
        starters = {p.fotmob_id for p in det.players if p.is_starter}
        for fid, row in det.player_stats.items():
            team = team_by_fid.get(row.get("team_fotmob_id"))
            if team is None or not row.get("minutes"):
                continue
            player = resolve_player(s, fid, row.get("name") or "", team, seen_on=seen_on)
            s.add(
                m.PlayerMatchStats(
                    match_id=match.id,
                    player_id=player.id,
                    team_id=team.id,
                    is_starter=fid in starters,
                    **{k: (int(v) if isinstance(v, float) and k not in ("xg", "xa", "rating") else v)
                       for k, v in row.items() if k not in ("team_fotmob_id", "name") and v is not None},
                )
            )
    match.details_fetched_at = datetime.now(UTC)
    s.flush()
    reconcile(s, match)


def update_availability(s: Session, team: m.Team, reported: Iterable, seen_on: date) -> None:
    """Marca como activas las bajas informadas y desactiva las que ya no aparecen (fuente fotmob)."""
    now = datetime.now(UTC)
    current = {
        a.player_id: a
        for a in s.scalars(
            select(m.Availability).where(
                m.Availability.team_id == team.id, m.Availability.active.is_(True), m.Availability.source == "fotmob"
            )
        )
    }
    seen: set[int] = set()
    for u in reported:
        player = resolve_player(s, u.fotmob_id, u.name, team, None, u.market_value, u.season_rating, seen_on)
        seen.add(player.id)
        row = current.get(player.id)
        if row is None:
            row = m.Availability(player_id=player.id, team_id=team.id, kind=u.kind, source="fotmob")
            s.add(row)
        row.kind, row.reason, row.expected_return = u.kind, u.reason, u.expected_return
        row.active, row.last_seen_at = True, now
    for pid, row in current.items():
        if pid not in seen:
            row.active = False
    s.flush()


# --------------------------------------------------------------------------- cuotas


def store_odds(s: Session, match: m.Match, odds: Iterable, source: str, captured_at: datetime | None = None) -> int:
    """Inserta solo cuando el precio cambia respecto al último guardado (ahorra ~90% de espacio)."""
    captured_at = captured_at or datetime.now(UTC)
    last: dict[tuple, float] = {}
    for row in s.scalars(
        select(m.OddsSnapshot).where(m.OddsSnapshot.match_id == match.id).order_by(m.OddsSnapshot.captured_at)
    ):
        last[(row.bookmaker, row.market, row.selection, row.line, row.kind)] = row.price
    added = 0
    for o in odds:
        key = (o.bookmaker, o.market, o.selection, o.line, o.kind)
        if last.get(key) == o.price:
            continue
        s.add(
            m.OddsSnapshot(
                match_id=match.id,
                bookmaker=o.bookmaker,
                market=o.market,
                selection=o.selection,
                line=o.line,
                price=o.price,
                kind=o.kind,
                source=source,
                captured_at=captured_at,
            )
        )
        last[key] = o.price
        added += 1
    s.flush()
    return added


def latest_1x2(s: Session, match: m.Match, bookmaker: str) -> dict[str, float]:
    """Última cuota 1X2 guardada de una casa (sin las de cierre): {"home": .., "draw": .., "away": ..}."""
    out: dict[str, float] = {}
    for row in s.scalars(
        select(m.OddsSnapshot)
        .where(
            m.OddsSnapshot.match_id == match.id,
            m.OddsSnapshot.bookmaker == bookmaker,
            m.OddsSnapshot.market == "1x2",
            m.OddsSnapshot.kind != "closing",
        )
        .order_by(m.OddsSnapshot.captured_at)
    ):
        out[row.selection] = row.price
    return out


def drop_odds(s: Session, match: m.Match, bookmaker: str, source: str) -> int:
    """Borra las cuotas de una casa llegadas por una fuente en un partido. Las demás casas y fuentes no se tocan."""
    n = (
        s.query(m.OddsSnapshot)
        .filter(
            m.OddsSnapshot.match_id == match.id,
            m.OddsSnapshot.bookmaker == bookmaker,
            m.OddsSnapshot.source == source,
        )
        .delete()
    )
    s.flush()
    return n
