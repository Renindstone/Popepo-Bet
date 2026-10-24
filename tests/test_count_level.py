"""Nivel reciente de cada liga en remates y remates a puerta (`fitting.count_levels`): desde julio de 2026 los equipos
rematan un 10-20 % más en todas las ligas y el modelo de conteo, con su memoria de 240 días, tardaba meses en notarlo."""

from datetime import date, timedelta

import numpy as np
import pytest

from apuestas.models import fitting, ratings
from apuestas.models.fitting import MatchRow

TODAY = date(2026, 10, 21)
RISE_DAYS = 60  # la Premier remata un 20 % más en los últimos 60 días; la Bundesliga, igual que siempre
EPL, BUN = list(range(1, 9)), list(range(11, 19))
LONE = 99  # rival europeo sin liga en los datos


def _rows(cup_factor: float = 1.25) -> list[MatchRow]:
    rng = np.random.default_rng(7)
    rows, mid = [], 0
    for comp, teams in (("EPL", list(EPL)), ("BUN", list(BUN))):
        for w in range(150):
            day = TODAY - timedelta(days=7 * w + 1)
            f = 1.2 if comp == "EPL" and (TODAY - day).days <= RISE_DAYS else 1.0
            rng.shuffle(teams)
            for h, a in zip(teams[::2], teams[1::2], strict=True):
                mid += 1
                rows.append(MatchRow(mid, comp, day, int(h), int(a), False, 1, 1, None,
                                     {"shots": float(rng.poisson(13.5 * f)), "corners": float(rng.poisson(5.5 * f))},
                                     {"shots": float(rng.poisson(11.5 * f)), "corners": float(rng.poisson(4.5 * f))}))
    # Copa entre equipos de las dos ligas (y uno sin liga), con más remates de lo que dicen sus ligas
    for w in range(40):
        day = TODAY - timedelta(days=3 * w + 2)
        h, a = (EPL[w % 8], BUN[w % 8]) if w % 4 else (LONE, BUN[w % 8])
        mid += 1
        rows.append(MatchRow(mid, "UCL", day, h, a, False, 1, 1, None,
                             {"shots": float(rng.poisson(13.5 * cup_factor))},
                             {"shots": float(rng.poisson(11.5 * cup_factor))}))
    return rows


def _recent_ratio(cm: ratings.RatingModel, rows: list[MatchRow], comp: str) -> float:
    recent = [r for r in rows if r.competition == comp and (TODAY - r.day).days <= RISE_DAYS]
    real = sum(r.stats_h["shots"] + r.stats_a["shots"] for r in recent)
    return real / sum(sum(cm.expected(r.home, r.away, r.neutral, r.competition)) for r in recent)


def test_level_catches_up_with_a_league_that_shoots_more():
    rows = _rows()
    obs = fitting.count_obs(rows, "shots")
    old = fitting.fit_counts(obs, "shots", TODAY)
    new = fitting.fit_counts(obs, "shots", TODAY, rows=rows)
    gap_old = _recent_ratio(old, rows, "EPL") - 1
    assert gap_old > 0.08  # con 240 días de memoria se queda corto
    # Cierra la mayor parte del hueco (la contracción hacia el nivel de todas las competiciones deja algo)
    assert 0 <= _recent_ratio(new, rows, "EPL") - 1 < 0.5 * gap_old
    assert _recent_ratio(new, rows, "BUN") == pytest.approx(1.0, abs=0.04)
    # La fuerza de cada equipo no cambia: el nivel va aparte
    assert new.attack == old.attack and new.defence == old.defence


def test_level_is_per_league():
    rows = _rows()
    cm = fitting.fit_counts(fitting.count_obs(rows, "shots"), "shots", TODAY, rows=rows)
    assert cm.level[EPL[0]] > 0.05
    assert abs(cm.level[BUN[0]]) < 0.05
    assert len({cm.level[t] for t in EPL}) == 1  # todos los equipos de una liga, el mismo
    # En un partido de liga, el de esa liga
    assert cm.level_for(EPL[0], EPL[1], "EPL") == pytest.approx(cm.level[EPL[0]])


def test_cup_uses_the_leagues_of_both_teams_plus_its_own_offset():
    rows = _rows()
    cm = fitting.fit_counts(fitting.count_obs(rows, "shots"), "shots", TODAY, rows=rows)
    assert cm.cup_level["UCL"] > 0.03  # la copa remata más de lo que dicen las ligas
    h, a = EPL[0], BUN[0]
    assert cm.level_for(h, a, "UCL") == pytest.approx(0.5 * (cm.level[h] + cm.level[a]) + cm.cup_level["UCL"])
    with_cup, without = cm.expected(h, a, False, "UCL"), cm.expected(h, a)
    assert with_cup[0] / without[0] == pytest.approx(np.exp(cm.cup_level["UCL"]))
    # Un equipo sin liga en los datos toma el nivel de todas las competiciones juntas
    assert BUN[0] in cm.level and cm.level[EPL[0]] > cm.level[LONE] > cm.level[BUN[0]]


def test_cup_offset_shrinks_with_few_matches():
    rows = _rows(cup_factor=1.25)
    few = [r for r in rows if r.competition != "UCL" or (TODAY - r.day).days < 15]
    cm_all = fitting.fit_counts(fitting.count_obs(rows, "shots"), "shots", TODAY, rows=rows)
    cm_few = fitting.fit_counts(fitting.count_obs(few, "shots"), "shots", TODAY, rows=few)
    assert 0 < cm_few.cup_level["UCL"] < cm_all.cup_level["UCL"]


def test_level_only_in_shots_shots_on_target_and_cards():
    assert fitting.COUNT_LEVEL_STATS == ("shots", "shots_on_target", "cards")
    rows = _rows()
    cm = fitting.fit_counts(fitting.count_obs(rows, "corners"), "corners", TODAY, rows=rows)
    assert cm.level == {} and cm.cup_level == {}
    assert cm.level_for(EPL[0], BUN[0], "UCL") == 0.0


def test_level_survives_the_model_bundle():
    rows = _rows()
    cm = fitting.fit_counts(fitting.count_obs(rows, "shots"), "shots", TODAY, rows=rows)
    back = ratings.RatingModel.from_dict(cm.to_dict())
    assert back.level == pytest.approx(cm.level) and back.cup_level == pytest.approx(cm.cup_level)
    assert back.expected(EPL[0], BUN[0], False, "UCL") == pytest.approx(cm.expected(EPL[0], BUN[0], False, "UCL"))
    # Paquetes antiguos, sin nivel: todo como antes
    d = cm.to_dict()
    del d["level"], d["cup_level"]
    old = ratings.RatingModel.from_dict(d)
    assert old.level == {} and old.expected(1, 2, False, "EPL") == pytest.approx(
        fitting.fit_counts(fitting.count_obs(rows, "shots"), "shots", TODAY).expected(1, 2))
