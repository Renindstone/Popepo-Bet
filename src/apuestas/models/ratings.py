"""Modelo de fuerza de equipos (ataque/defensa) multiplicativo tipo Poisson, conjunto para todas las ligas.

log E[y_home] = mu + home + att[home] - def[away]
log E[y_away] = mu        + att[away] - def[home]

- y puede ser goles, una mezcla goles/xG o cualquier conteo (remates, córners, tarjetas...).
  Con valores no enteros se usa cuasi-verosimilitud de Poisson (válida para la media).
- Pesos por antigüedad (vida media configurable) para que la forma reciente pese más.
- Regularización L2 hacia 0 para equipos con pocos partidos (ascendidos, rivales exóticos de Champions).
- Todas las ligas se ajustan juntas: los partidos de Champions/Europa y los ascensos/descensos
  conectan las escalas, así un 1.8 de ataque significa lo mismo en Inglaterra que en Portugal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
from scipy.optimize import minimize


@dataclass
class MatchObs:
    home: int
    away: int
    day: date
    y_home: float
    y_away: float
    neutral: bool = False
    weight: float = 1.0


@dataclass
class RatingModel:
    teams: list[int]
    mu: float
    home_adv: float
    attack: dict[int, float]
    defence: dict[int, float]
    dispersion: float = 0.0  # alfa de la binomial negativa (0 = Poisson)
    n_matches: dict[int, float] = field(default_factory=dict)  # partidos (ponderados) por equipo
    as_of: date | None = None

    def expected(self, home: int, away: int, neutral: bool = False) -> tuple[float, float]:
        ah, aa = self.attack.get(home, 0.0), self.attack.get(away, 0.0)
        dh, da = self.defence.get(home, 0.0), self.defence.get(away, 0.0)
        h = 0.0 if neutral else self.home_adv
        return float(np.exp(self.mu + h + ah - da)), float(np.exp(self.mu + aa - dh))

    def to_dict(self) -> dict:
        return {
            "mu": self.mu,
            "home_adv": self.home_adv,
            "dispersion": self.dispersion,
            "attack": {str(k): v for k, v in self.attack.items()},
            "defence": {str(k): v for k, v in self.defence.items()},
            "n_matches": {str(k): v for k, v in self.n_matches.items()},
            "as_of": self.as_of.isoformat() if self.as_of else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RatingModel:
        attack = {int(k): v for k, v in d["attack"].items()}
        return cls(
            teams=list(attack),
            mu=d["mu"],
            home_adv=d["home_adv"],
            attack=attack,
            defence={int(k): v for k, v in d["defence"].items()},
            dispersion=d.get("dispersion", 0.0),
            n_matches={int(k): v for k, v in d.get("n_matches", {}).items()},
            as_of=date.fromisoformat(d["as_of"]) if d.get("as_of") else None,
        )


def time_weights(days: np.ndarray, as_of: date, half_life_days: float) -> np.ndarray:
    age = np.array([(as_of - d).days for d in days], dtype=float)
    age = np.clip(age, 0, None)
    return np.power(0.5, age / half_life_days)


def fit(
    obs: list[MatchObs],
    as_of: date,
    half_life_days: float = 240.0,
    l2: float = 2.0,
    max_age_days: int = 1100,
) -> RatingModel:
    obs = [o for o in obs if 0 <= (as_of - o.day).days <= max_age_days]
    if not obs:
        raise ValueError("Sin partidos para ajustar el modelo")
    teams = sorted({o.home for o in obs} | {o.away for o in obs})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    hi = np.array([idx[o.home] for o in obs])
    ai = np.array([idx[o.away] for o in obs])
    yh = np.array([o.y_home for o in obs], dtype=float)
    ya = np.array([o.y_away for o in obs], dtype=float)
    hm = np.array([0.0 if o.neutral else 1.0 for o in obs])
    w = time_weights(np.array([o.day for o in obs]), as_of, half_life_days) * np.array([o.weight for o in obs])

    def unpack(theta: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
        return theta[0], theta[1], theta[2 : 2 + n], theta[2 + n :]

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        mu, home, att, de = unpack(theta)
        eta_h = mu + home * hm + att[hi] - de[ai]
        eta_a = mu + att[ai] - de[hi]
        lh, la = np.exp(eta_h), np.exp(eta_a)
        nll = np.sum(w * (lh - yh * eta_h)) + np.sum(w * (la - ya * eta_a))
        nll += 0.5 * l2 * (np.sum(att**2) + np.sum(de**2))
        rh, ra = w * (lh - yh), w * (la - ya)  # derivadas respecto a eta
        g = np.zeros_like(theta)
        g[0] = rh.sum() + ra.sum()
        g[1] = (rh * hm).sum()
        g_att = np.bincount(hi, weights=rh, minlength=n) + np.bincount(ai, weights=ra, minlength=n)
        g_def = -np.bincount(ai, weights=rh, minlength=n) - np.bincount(hi, weights=ra, minlength=n)
        g[2 : 2 + n] = g_att + l2 * att
        g[2 + n :] = g_def + l2 * de
        return nll, g

    mean_y = max(float(np.average(np.concatenate([yh, ya]), weights=np.concatenate([w, w]))), 1e-3)
    theta0 = np.zeros(2 + 2 * n)
    theta0[0] = np.log(mean_y)
    theta0[1] = 0.1
    res = minimize(objective, theta0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    mu, home, att, de = unpack(res.x)

    # Sobredispersión (alfa de NB) por momentos: Var = m + alfa m^2
    lh = np.exp(mu + home * hm + att[hi] - de[ai])
    la = np.exp(mu + att[ai] - de[hi])
    y = np.concatenate([yh, ya])
    mm = np.concatenate([lh, la])
    ww = np.concatenate([w, w])
    alpha = float(np.sum(ww * ((y - mm) ** 2 - mm)) / max(np.sum(ww * mm**2), 1e-9))

    counts = np.bincount(hi, weights=w, minlength=n) + np.bincount(ai, weights=w, minlength=n)
    return RatingModel(
        teams=teams,
        mu=float(mu),
        home_adv=float(home),
        attack={t: float(att[i]) for t, i in idx.items()},
        defence={t: float(de[i]) for t, i in idx.items()},
        dispersion=max(alpha, 0.0),
        n_matches={t: float(counts[i]) for t, i in idx.items()},
        as_of=as_of,
    )
