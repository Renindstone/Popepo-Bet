"""Equipos duplicados entre fuentes y su fusión.

Un mismo club puede entrar dos veces si las fuentes lo llaman distinto ("AEK" en football-data, "AEK Athens"
en FotMob) y el parecido no llega al umbral de `store.resolve_team`. Ese umbral es alto a propósito, porque
"Dundee" y "Dundee United" son clubes distintos. Si es una liga que también trae FotMob, el partido queda
duplicado y el rival de ese equipo "juega dos veces" cada jornada.

Para decidir se usa la evidencia de los partidos: dos registros del mismo club nunca se enfrentan, no juegan
el mismo día (salvo el mismo partido duplicado) y vienen de fuentes distintas. El nombre por sí solo no basta:
"Aris" (Grecia) y "Aris Limassol" (Chipre) cumplen todo eso y son clubes distintos.

- `candidates()`: pares con nombre parecido y sin evidencia en contra.
  - `safe=True` si el nombre coincide tras normalizar (incluidas las variantes revisadas de
    `names._TEAM_SEEDS`) o es casi idéntico.
  - Los demás quedan para revisar a mano (`apuestas equipos duplicados`).
- `merge_teams()`: fusiona un equipo en otro. Antes junta los partidos duplicados (cuotas, estadísticas,
  alineaciones…) y después reapunta todas las tablas.
- `merge_safe()`: fusiona solos los pares seguros. Lo llama la ingesta al terminar.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from rapidfuzz import fuzz
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, aliased

from apuestas.core import names
from apuestas.db import models as m
from apuestas.ingest import store

log = logging.getLogger(__name__)

SAFE_FUZZ = 92.0  # casi idéntico tras normalizar ("Bodo/Glimt" frente a "Bodø/Glimt")
REVIEW_FUZZ = 80.0
SAME_MATCH_HOURS = 40


@dataclass
class Candidate:
    keep_id: int
    drop_id: int
    keep_name: str
    drop_name: str
    score: float
    safe: bool
    duplicated_matches: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"conservar": f"{self.keep_name} ({self.keep_id})", "fusionar": f"{self.drop_name} ({self.drop_id})",
                "parecido": round(self.score, 1), "seguro": self.safe,
                "partidos_duplicados": self.duplicated_matches, "motivos": self.reasons}


# --------------------------------------------------------------------------- detección


def _name_score(a: str, b: str) -> tuple[float, bool]:
    """(parecido 0-100, uno contenido en el otro)."""
    ka, kb = names.team_key(a), names.team_key(b)
    if ka == kb:
        return 100.0, True
    ta, tb = set(ka.split()), set(kb.split())
    return float(fuzz.token_sort_ratio(ka, kb)), bool(ta and tb and (ta <= tb or tb <= ta))


def candidates(s: Session) -> list[Candidate]:
    teams = {t.id: t for t in s.scalars(select(m.Team))}
    sources: dict[int, set[str]] = defaultdict(set)
    for tid, src in s.execute(select(m.EntityAlias.entity_id, m.EntityAlias.source)
                              .where(m.EntityAlias.entity_type == "team")):
        sources[tid].add(src)
    games: dict[int, list[tuple]] = defaultdict(list)  # equipo -> (fecha, competición, rival, local, kickoff)
    for h, a, k, c in s.execute(select(m.Match.home_team_id, m.Match.away_team_id, m.Match.kickoff_utc,
                                       m.Match.competition_id)):
        games[h].append((k.date(), c, a, True, k))
        games[a].append((k.date(), c, h, False, k))

    found: list[Candidate] = []
    ids = sorted(teams)
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            score, contained = _name_score(teams[x].name, teams[y].name)
            if score < REVIEW_FUZZ and not contained:
                continue
            reasons = []
            if sources[x] & sources[y]:
                continue  # una misma fuente los distingue: son clubes distintos
            cx, cy = teams[x].country, teams[y].country
            if cx and cy and cx != cy:
                continue
            opp_x = {g[2] for g in games[x]}
            if y in opp_x:
                continue  # se enfrentaron
            dup, conflict = _same_day(games[x], games[y])
            if conflict:
                continue  # jugaron el mismo día partidos distintos
            safe = score >= SAFE_FUZZ
            if not safe:
                reasons.append("nombre parecido pero no igual: revisar a mano")
            if not (cx and cy):
                reasons.append("país desconocido en uno de los dos")
            keep, drop = _choose_keep(teams[x], teams[y], sources, games)
            found.append(Candidate(keep.id, drop.id, keep.name, drop.name, score, safe, dup, reasons))

    # Un equipo con dos candidatos seguros es ambiguo: no se fusiona solo
    count: dict[int, int] = defaultdict(int)
    for c in found:
        if c.safe:
            count[c.keep_id] += 1
            count[c.drop_id] += 1
    for c in found:
        if c.safe and (count[c.keep_id] > 1 or count[c.drop_id] > 1):
            c.safe = False
            c.reasons.append("ambiguo: más de un candidato")
    return sorted(found, key=lambda c: (not c.safe, -c.score))


def _same_day(gx: list[tuple], gy: list[tuple]) -> tuple[int, bool]:
    """(partidos duplicados, hay algún día con partidos distintos)."""
    by_day: dict = defaultdict(list)
    for g in gy:
        by_day[g[0]].append(g)
    dup = 0
    for g in gx:
        for h in by_day.get(g[0], []):
            if g[1] == h[1] and g[2] == h[2] and g[3] == h[3]:
                dup += 1
            else:
                return dup, True
    return dup, False


def _choose_keep(a: m.Team, b: m.Team, sources: dict, games: dict) -> tuple[m.Team, m.Team]:
    """Se conserva el registro de FotMob (nombres completos y más datos); si no, el que tiene más partidos."""
    def rank(t: m.Team) -> tuple:
        return ("fotmob" in sources[t.id], len(games[t.id]), -t.id)

    return (a, b) if rank(a) >= rank(b) else (b, a)


# --------------------------------------------------------------------------- fusión


def merge_teams(s: Session, keep_id: int, drop_id: int) -> dict:
    """Fusiona el equipo `drop_id` en `keep_id`. Todo en la transacción de la sesión."""
    if keep_id == drop_id:
        raise ValueError("Es el mismo equipo")
    keep, drop = s.get(m.Team, keep_id), s.get(m.Team, drop_id)
    if keep is None or drop is None:
        raise ValueError("No existe alguno de los dos equipos")
    if s.scalar(select(func.count()).select_from(m.Match).where(
            ((m.Match.home_team_id == keep_id) & (m.Match.away_team_id == drop_id))
            | ((m.Match.home_team_id == drop_id) & (m.Match.away_team_id == keep_id)))):
        raise ValueError(f"{keep.name} y {drop.name} se enfrentaron: no son el mismo club")

    # 1. Partidos duplicados (misma competición, mismo rival, mismo papel, ±40 h)
    survivors = []
    for dm in s.scalars(select(m.Match).where((m.Match.home_team_id == drop_id) | (m.Match.away_team_id == drop_id))).all():
        is_home = dm.home_team_id == drop_id
        rival = dm.away_team_id if is_home else dm.home_team_id
        km = s.scalar(select(m.Match).where(
            m.Match.competition_id == dm.competition_id,
            (m.Match.home_team_id == keep_id) if is_home else (m.Match.away_team_id == keep_id),
            (m.Match.away_team_id == rival) if is_home else (m.Match.home_team_id == rival),
            m.Match.kickoff_utc.between(dm.kickoff_utc - timedelta(hours=SAME_MATCH_HOURS),
                                        dm.kickoff_utc + timedelta(hours=SAME_MATCH_HOURS))))
        if km is not None:
            survivors.append(_merge_matches(s, km, dm, drop_id, keep_id))
    s.flush()

    # 2. Reapuntar todo lo que señala al equipo eliminado
    _repoint_team(s, drop_id, keep_id)
    for mt in survivors:
        s.refresh(mt)
        store.reconcile(s, mt)
    if not keep.country and drop.country:
        keep.country = drop.country
    drop_name = drop.name
    s.delete(drop)
    s.flush()
    log.info("Fusionado %s (%s) en %s (%s): %d partidos duplicados", drop_name, drop_id, keep.name, keep_id,
             len(survivors))
    return {"conservado": keep.name, "fusionado": drop_name, "partidos_duplicados": len(survivors)}


_MATCH_FIELDS = ("fotmob_id", "understat_id", "espn_id", "referee_id", "home_goals", "away_goals",
                 "home_goals_ht", "away_goals_ht", "lineup_status", "details_fetched_at")


def _merge_matches(s: Session, a: m.Match, b: m.Match, drop_team: int, keep_team: int) -> m.Match:
    """Junta dos registros del mismo partido. Sobrevive el de FotMob; los hijos del otro pasan a él."""
    keep, gone = (a, b) if (a.fotmob_id or not b.fotmob_id) else (b, a)
    copy = {f: getattr(gone, f) for f in _MATCH_FIELDS if getattr(keep, f, None) is None and getattr(gone, f, None) is not None}
    if gone.status == "finished":
        copy.setdefault("status", "finished")
    for f in ("fotmob_id", "understat_id", "espn_id"):  # únicos: liberarlos antes de copiarlos
        setattr(gone, f, None)
    s.flush()
    for f, v in copy.items():
        setattr(keep, f, v)

    # Observaciones por fuente: se descartan las que el superviviente ya tiene para ese equipo, contando los
    # dos registros del club como el mismo (aún no se han reapuntado)
    pair = {drop_team, keep_team}
    for r in s.scalars(select(m.StatObservation).where(m.StatObservation.match_id == gone.id)).all():
        side = pair if r.team_id in pair else {r.team_id}
        exists = s.scalar(select(m.StatObservation.id).where(
            m.StatObservation.match_id == keep.id, m.StatObservation.team_id.in_(side),
            m.StatObservation.stat == r.stat, m.StatObservation.source == r.source))
        if exists:
            s.delete(r)
        else:
            r.match_id = keep.id
    for model in (m.Lineup, m.PlayerMatchStats):
        have = set(s.scalars(select(model.player_id).where(model.match_id == keep.id)))
        for r in s.scalars(select(model).where(model.match_id == gone.id)).all():
            if r.player_id in have:
                s.delete(r)
            else:
                r.match_id = keep.id
    s.execute(delete(m.TeamMatchStats).where(m.TeamMatchStats.match_id == gone.id))  # se recalcula
    for model in (m.OddsSnapshot, m.Prediction, m.Pick, m.UserBet, m.UserBetLeg, m.OddsCapture):
        s.execute(update(model).where(model.match_id == gone.id).values(match_id=keep.id))
    s.execute(update(m.EntityAlias).where(m.EntityAlias.entity_type == "match", m.EntityAlias.entity_id == gone.id)
              .values(entity_id=keep.id))
    s.flush()
    s.delete(gone)
    return keep


def _repoint_team(s: Session, old: int, new: int) -> None:
    for model, col in ((m.Match, "home_team_id"), (m.Match, "away_team_id"), (m.TeamMatchStats, "team_id"),
                       (m.StatObservation, "team_id"), (m.Lineup, "team_id"), (m.PlayerMatchStats, "team_id"),
                       (m.Availability, "team_id"), (m.Player, "current_team_id")):
        s.execute(update(model).where(getattr(model, col) == old).values({col: new}))
    # Un "fichaje" entre los dos registros del mismo club no existió
    s.execute(delete(m.Transfer).where(((m.Transfer.from_team_id == old) & (m.Transfer.to_team_id == new))
                                       | ((m.Transfer.from_team_id == new) & (m.Transfer.to_team_id == old))))
    t2 = aliased(m.Transfer)
    s.execute(delete(m.Transfer).where(m.Transfer.to_team_id == old, select(t2.id).where(
        t2.to_team_id == new, t2.player_id == m.Transfer.player_id, t2.detected_on == m.Transfer.detected_on).exists()))
    s.execute(update(m.Transfer).where(m.Transfer.from_team_id == old).values(from_team_id=new))
    s.execute(update(m.Transfer).where(m.Transfer.to_team_id == old).values(to_team_id=new))
    s.execute(delete(m.TeamRating).where(m.TeamRating.team_id == old))  # se recalculan al entrenar
    ss2 = aliased(m.SeasonSummary)
    s.execute(delete(m.SeasonSummary).where(
        m.SeasonSummary.entity_type == "team", m.SeasonSummary.entity_id == old,
        select(ss2.id).where(ss2.entity_type == "team", ss2.entity_id == new,
                             ss2.season_id == m.SeasonSummary.season_id).exists()))
    s.execute(update(m.SeasonSummary).where(m.SeasonSummary.entity_type == "team", m.SeasonSummary.entity_id == old)
              .values(entity_id=new))
    s.execute(update(m.EntityAlias).where(m.EntityAlias.entity_type == "team", m.EntityAlias.entity_id == old)
              .values(entity_id=new))
    s.flush()


def merge_safe(s: Session) -> list[dict]:
    """Fusiona los pares seguros. Devuelve lo fusionado."""
    done = []
    for c in candidates(s):
        if c.safe:
            done.append(merge_teams(s, c.keep_id, c.drop_id))
    return done
