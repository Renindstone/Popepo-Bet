"""Modelo de un partido concreto: distribuciones de goles, estadísticas y jugadores, y probabilidad
de cualquier mercado (1X2, hándicap, goles, remates, córners, tarjetas, props de jugador)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from apuestas.models import distributions as dist
from apuestas.models.distributions import Outcome

STAT_ALIASES = {"sot": "shots_on_target", "remates": "shots", "corners": "corners", "cards": "cards",
                "tarjetas": "cards", "fouls": "fouls", "faltas": "fouls", "shots": "shots",
                "shots_on_target": "shots_on_target"}
PLAYER_MARKETS = {"player_shots": "shots", "player_sot": "shots_on_target", "player_fouls": "fouls_committed"}


@dataclass
class PlayerProjection:
    player_id: int
    name: str
    team_id: int
    position: str | None
    expected_minutes: float
    start_prob: float
    lam: dict[str, float]  # tasa esperada en el partido para cada estadística

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "team_id": self.team_id,
            "position": self.position,
            "expected_minutes": round(self.expected_minutes, 1),
            "start_prob": round(self.start_prob, 2),
            "expected": {k: round(v, 3) for k, v in self.lam.items()},
        }


@dataclass
class MatchModel:
    home_id: int
    away_id: int
    lam_home: float
    lam_away: float
    rho: float
    count_means: dict[str, tuple[float, float]]
    count_dispersion: dict[str, float]
    players: dict[int, PlayerProjection] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.matrix = dist.dixon_coles_matrix(self.lam_home, self.lam_away, self.rho)
        self._pmfs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for stat, (mh, ma) in self.count_means.items():
            a = self.count_dispersion.get(stat, 0.0)
            self._pmfs[stat] = (dist.count_pmf(mh, a), dist.count_pmf(ma, a))

    # ------------------------------------------------------------------ goles
    def probs_1x2(self) -> dict[str, float]:
        mat = self.matrix
        return {
            "home": float(np.tril(mat, -1).sum()),
            "draw": float(np.trace(mat)),
            "away": float(np.triu(mat, 1).sum()),
        }

    def _goal_pmfs(self) -> tuple[dict[int, float], dict[int, float], dict[int, float], dict[int, float]]:
        mat = self.matrix
        return (
            dist.diff_pmf_from_matrix(mat),
            dist.total_pmf_from_matrix(mat),
            dist.pmf_to_dict(mat.sum(axis=1)),
            dist.pmf_to_dict(mat.sum(axis=0)),
        )

    def _stat_pmfs(self, stat: str) -> tuple[dict[int, float], dict[int, float], dict[int, float], dict[int, float]]:
        ph, pa = self._pmfs[stat]
        diff: dict[int, float] = {}
        for i, p in enumerate(ph):
            if p < 1e-10:
                continue
            for j, q in enumerate(pa):
                if q < 1e-10:
                    continue
                diff[i - j] = diff.get(i - j, 0.0) + p * q
        total = dist.pmf_to_dict(dist.convolve(ph, pa))
        return diff, total, dist.pmf_to_dict(ph), dist.pmf_to_dict(pa)

    # ------------------------------------------------------------------ varias selecciones del mismo partido
    def goal_mask(self, market: str, selection: str, line: float | None = None) -> np.ndarray | None:
        """Marcadores (i goles del local, j del visitante) en los que gana una selección de goles.

        None si la selección no depende solo del marcador (córners, jugadores…) o si puede devolverse (líneas
        enteras o de cuarto, empate no válido): esas no se pueden combinar celda a celda.
        """
        market, selection = market.lower(), selection.lower()
        i, j = np.indices(self.matrix.shape)
        half = line is not None and abs(line * 2) % 2 == 1  # x.5
        if market == "1x2":
            return {"home": i > j, "draw": i == j, "away": i < j}.get(selection)
        if market == "dc":
            return {"1x": i >= j, "x2": i <= j, "12": i != j}.get(selection)
        if market == "btts":
            both = (i > 0) & (j > 0)
            return {"yes": both, "no": ~both}.get(selection)
        if market in ("ou_goals", "ou_goals_home", "ou_goals_away") and half:
            goals = {"ou_goals": i + j, "ou_goals_home": i, "ou_goals_away": j}[market]
            return {"over": goals > line, "under": goals < line}.get(selection)
        if market == "eh" and line is not None:  # 3 vías: la línea es el hándicap del local
            shifted = i - j + line
            return {"home": shifted > 0, "draw": shifted == 0, "away": shifted < 0}.get(selection)
        if market == "ah" and half:  # la línea es la del equipo elegido
            return {"home": (i - j) + line > 0, "away": (j - i) + line > 0}.get(selection)
        return None

    def joint_goal_prob(self, legs: list[tuple[str, str, float | None]]) -> float | None:
        """Probabilidad de que se cumplan a la vez varias selecciones de goles del mismo partido (Bet Builder).

        Se suma la matriz de marcadores en las celdas donde ganan todas, así que tiene en cuenta que dependen
        entre sí ("gana el City" y "más de 2,5 goles" no son independientes). None si alguna no es de goles.
        """
        mask = np.ones(self.matrix.shape, dtype=bool)
        for market, selection, line in legs:
            m = self.goal_mask(market, selection, line)
            if m is None:
                return None
            mask &= m
        return float(self.matrix[mask].sum() / self.matrix.sum())

    # ------------------------------------------------------------------ mercado genérico
    def outcome(self, market: str, selection: str, line: float | None = None, player_id: int | None = None) -> Outcome:
        market, selection = market.lower(), selection.lower()

        if market.startswith("player_"):
            return self._player_outcome(market, selection, line, player_id)

        # Mercado de goles o de una estadística (ou_corners, ah_cards, 1x2_corners...)
        parts = market.split("_", 1)
        kind = parts[0]
        rest = parts[1] if len(parts) > 1 else "goals"
        scope = "total"
        for sc in ("home", "away"):
            if rest.endswith("_" + sc):
                rest, scope = rest[: -len(sc) - 1], sc
        stat = "goals" if rest in ("goals", "") else STAT_ALIASES.get(rest, rest)
        if stat == "goals":
            diff, total, th, ta = self._goal_pmfs()
        elif stat in self._pmfs:
            diff, total, th, ta = self._stat_pmfs(stat)
        else:
            raise ValueError(f"Estadística sin modelo: {stat}")

        if market in ("1x2", "dc", "dnb", "btts") or kind == "1x2":
            p = {"home": sum(v for d, v in diff.items() if d > 0), "draw": diff.get(0, 0.0),
                 "away": sum(v for d, v in diff.items() if d < 0)}
            if market == "dnb":
                return dist.line_outcome(diff if selection == "home" else {-d: v for d, v in diff.items()}, 0.0)
            if market == "dc":
                mapping = {"1x": p["home"] + p["draw"], "x2": p["away"] + p["draw"], "12": p["home"] + p["away"]}
                return dist.prob_outcome(mapping[selection])
            if market == "btts":
                mat = self.matrix
                yes = float(mat[1:, 1:].sum())
                return dist.prob_outcome(yes if selection in ("yes", "si", "sí") else 1 - yes)
            return dist.prob_outcome(p[selection])

        if kind == "ah":
            if line is None:
                raise ValueError("El hándicap necesita línea")
            d = diff if selection == "home" else {-k: v for k, v in diff.items()}
            return dist.line_outcome(d, line)

        if kind == "eh":  # hándicap europeo (3 vías), línea = hándicap del local
            if line is None:
                raise ValueError("El hándicap europeo necesita línea")
            shifted = {k + line: v for k, v in diff.items()}
            p = {"home": sum(v for k, v in shifted.items() if k > 0), "draw": shifted.get(0, 0.0),
                 "away": sum(v for k, v in shifted.items() if k < 0)}
            return dist.prob_outcome(p[selection])

        if kind == "ou":
            if line is None:
                raise ValueError("Over/under necesita línea")
            pmf = {"total": total, "home": th, "away": ta}[scope]
            return dist.over(pmf, line) if selection == "over" else dist.under(pmf, line)

        raise ValueError(f"Mercado no soportado: {market}")

    def _player_outcome(self, market: str, selection: str, line: float | None, player_id: int | None) -> Outcome:
        if player_id is None or player_id not in self.players:
            raise ValueError("Jugador sin proyección para este partido")
        pp = self.players[player_id]
        if market in PLAYER_MARKETS:
            lam = pp.lam[PLAYER_MARKETS[market]]
            pmf = dist.pmf_to_dict(dist.count_pmf(lam, 0.15))
            ln = 0.5 if line is None else line
            return dist.over(pmf, ln) if selection == "over" else dist.under(pmf, ln)
        if market == "player_goal":
            p = 1 - math.exp(-pp.lam["goals"])
        elif market == "player_card":
            p = 1 - math.exp(-pp.lam["yellow_cards"])
        else:
            raise ValueError(f"Mercado de jugador no soportado: {market}")
        return dist.prob_outcome(p if selection in ("yes", "si", "sí") else 1 - p)

    # ------------------------------------------------------------------ resumen
    def summary(self) -> dict:
        p = self.probs_1x2()
        diff, total, th, ta = self._goal_pmfs()
        mat = self.matrix
        top_scores = sorted(
            ((f"{i}-{j}", float(mat[i, j])) for i in range(6) for j in range(6)), key=lambda x: -x[1]
        )[:6]
        out = {
            "expected_goals": {"home": round(self.lam_home, 2), "away": round(self.lam_away, 2)},
            "1x2": {k: round(v, 4) for k, v in p.items()},
            "fair_odds_1x2": {k: round(1 / v, 2) if v > 0 else None for k, v in p.items()},
            "btts_yes": round(float(mat[1:, 1:].sum()), 4),
            "over_goals": {str(ln): round(dist.over(total, ln).effective_prob(), 4) for ln in (0.5, 1.5, 2.5, 3.5, 4.5)},
            "asian_handicap_home": {
                str(ln): round(dist.line_outcome(diff, ln).effective_prob(), 4) for ln in (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)
            },
            "top_scores": [{"score": sc, "prob": round(pr, 4)} for sc, pr in top_scores],
            "stats": {},
        }
        for stat, (mh, ma) in self.count_means.items():
            _, tot, _, _ = self._stat_pmfs(stat)
            mean_total = mh + ma
            lines = sorted({math.floor(mean_total) + 0.5 + k for k in (-2, -1, 0, 1, 2) if math.floor(mean_total) + 0.5 + k > 0})
            out["stats"][stat] = {
                "expected": {"home": round(mh, 2), "away": round(ma, 2), "total": round(mean_total, 2)},
                "over": {str(ln): round(dist.over(tot, ln).effective_prob(), 4) for ln in lines},
            }
        return out
