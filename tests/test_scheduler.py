"""Recuperación de tareas diarias que no corrieron porque el equipo estaba apagado."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apuestas.jobs import scheduler

LIMA = ZoneInfo("America/Lima")


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "_state_path", lambda: tmp_path / "worker_state.json")


def test_last_fire():
    now = datetime(2026, 10, 20, 8, 28, tzinfo=LIMA)  # martes
    assert scheduler.last_fire(5, 30, None, now) == datetime(2026, 10, 20, 5, 30, tzinfo=LIMA)
    assert scheduler.last_fire(9, 0, None, now) == datetime(2026, 10, 19, 9, 0, tzinfo=LIMA)
    assert scheduler.last_fire(4, 0, 0, now) == datetime(2026, 10, 19, 4, 0, tzinfo=LIMA)  # lunes


def test_missed_jobs_after_a_night_switched_off(state):
    # Último arranque el 19 a las 23:00; el equipo se apagó a las 00:26 y volvió a las 07:44
    scheduler._state_path().parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime(2026, 10, 19, 23, 0, tzinfo=LIMA).isoformat()
    scheduler._state_path().write_text("{" + ",".join(f'"{k}": "{stamp}"' for k in scheduler.DAILY_JOBS) + "}")

    now = datetime(2026, 10, 20, 7, 44, tzinfo=LIMA)
    # resultados (05:30) e historial (02:00) no corrieron; la previa y la apuesta del día de ayer sí
    assert scheduler.missed_jobs(now) == ["results", "backfill"]
    later = datetime(2026, 10, 20, 9, 30, tzinfo=LIMA)
    assert scheduler.missed_jobs(later) == ["results", "preview", "daily_pick", "backfill"]


def test_old_pick_is_not_recovered(state):
    # Si el equipo arranca de noche, la apuesta del día de la mañana ya no sirve
    now = datetime(2026, 10, 20, 23, 0, tzinfo=LIMA)
    assert "daily_pick" not in scheduler.missed_jobs(now)
    assert "results" in scheduler.missed_jobs(now)


def test_safe_records_only_successes(state):
    @scheduler._safe("prueba", key="prueba")
    def ok():
        return 1

    @scheduler._safe("falla", key="falla")
    def boom():
        raise RuntimeError("x")

    assert ok() == 1 and scheduler.last_done("prueba") is not None
    assert boom() is None and scheduler.last_done("falla") is None


def test_lineup_checks_fire_once_at_each_point():
    # la tarea corre cada 5 minutos; con un partido a las 14:00 se mira a las 12:50, 13:10, 13:25, 13:40 y 13:50
    fired = [m for m in range(0, 121, 5) if scheduler.lineup_due(m)]
    assert fired == [10, 20, 35, 50, 70]
    # con un inicio que no cae en múltiplo de 5 (14:02) también se mira una vez cerca de cada punto
    fired = [m + 2 for m in range(0, 121, 5) if scheduler.lineup_due(m + 2)]
    assert len(fired) == 5 and 50 <= fired[3] <= 52



def test_lineup_search_retries_until_the_official_xi(state, monkeypatch):
    """A 50 minutos del inicio se vuelve a buscar el once de un partido con el último once de FotMob (lastStarting11,
    que se guarda como probable) o sin once; el que ya tiene el oficial (standard) no se vuelve a pedir, y los de la
    Europa League (sus alineaciones no se usan) tampoco."""
    from contextlib import contextmanager
    from datetime import UTC, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from apuestas.db import models as m
    from apuestas.ingest import fotmob, store
    from apuestas.services import picks

    class NaiveClock(datetime):
        """SQLite devuelve las fechas sin zona horaria: la tarea también las ve así."""

        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz).replace(tzinfo=None)

    kickoff = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=50)

    def payload(fid: int, lineup_type: str) -> dict:
        starters = [{"id": 1000 * fid + i, "name": f"Titular {fid}-{i}", "usualPlayingPositionId": 2} for i in range(11)]
        return {
            "general": {"matchId": str(fid), "matchTimeUTCDate": kickoff.isoformat()},
            "header": {"teams": [{"id": 10 * fid, "score": 0}, {"id": 10 * fid + 1, "score": 0}],
                       "status": {"utcTime": kickoff.isoformat(), "started": False, "finished": False}},
            "content": {"lineup": {"lineupType": lineup_type,
                                   "homeTeam": {"id": 10 * fid, "starters": starters, "subs": []},
                                   "awayTeam": {"id": 10 * fid + 1, "starters": [], "subs": []}}},
        }

    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    with Session(engine) as s:
        comp = store.ensure_competitions(s)["LAL"]
        season = store.get_season(s, comp, 2026)
        ids = {}
        for fid, lineup_type in ((1, "lastStarting11"), (2, "standard"), (3, None)):
            home, away = store.fotmob_team(s, 10 * fid, f"Local {fid}"), store.fotmob_team(s, 10 * fid + 1, f"Visita {fid}")
            match = m.Match(competition_id=comp.id, season_id=season.id, fotmob_id=fid, kickoff_utc=kickoff,
                            home_team_id=home.id, away_team_id=away.id, status="scheduled")
            s.add(match)
            s.flush()
            if lineup_type:
                store.apply_fotmob_details(s, match, fotmob.parse_match_details(payload(fid, lineup_type)))
            ids[lineup_type] = match.id
        uel = store.ensure_competitions(s)["UEL"]
        home, away = store.fotmob_team(s, 90, "Local UEL"), store.fotmob_team(s, 91, "Visita UEL")
        s.add(m.Match(competition_id=uel.id, season_id=store.get_season(s, uel, 2026).id, fotmob_id=9,
                      kickoff_utc=kickoff, home_team_id=home.id, away_team_id=away.id, status="scheduled"))
        s.flush()
        assert s.get(m.Match, ids["lastStarting11"]).lineup_status == "predicted"
        assert s.get(m.Match, ids["standard"]).lineup_status == "confirmed"

        @contextmanager
        def scope():
            yield s

        searched = []
        monkeypatch.setattr(scheduler, "datetime", NaiveClock)
        monkeypatch.setattr(scheduler, "session_scope", scope)
        monkeypatch.setattr(scheduler, "_last_pod", {})
        monkeypatch.setattr(scheduler.pipeline, "sync_fotmob_details", lambda **k: searched.extend(k["match_ids"]))
        monkeypatch.setattr(picks, "generate", lambda: {"date": "2026-10-25", "pick_of_day": None})
        scheduler.job_lineups()
    assert sorted(searched) == sorted([ids["lastStarting11"], ids[None]])
