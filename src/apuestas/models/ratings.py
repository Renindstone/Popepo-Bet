"""Modelo de fuerza de equipos (ataque/defensa) multiplicativo tipo Poisson, conjunto para todas las ligas.

log E[y_home] = mu + home + att[home] - def[away]
log E[y_away] = mu        + att[away] - def[home]

- y puede ser goles, una mezcla goles/xG o cualquier conteo (remates, córners, tarjetas...).
  Con valores no enteros se usa cuasi-verosimilitud de Poisson (válida para la media).
- Pesos por antigüedad (vida media configurable) para que la forma reciente pese más.
- Regularización L2 hacia 0 para equipos con pocos partidos (ascendidos, rivales exóticos de Champions).
- Fuerza de referencia (opcional, `strength`): ataque = b_ataque × fuerza + desviación del equipo (igual en defensa),
  con b ajustado y la L2 solo en la desviación. En los conteos, la fuerza es la del modelo de goles: así un equipo
  que domina una liga floja no parece igual de dominante en córners contra un rival de la Champions.
- Todas las ligas se ajustan juntas: los partidos de Champions/Europa y los ascensos/descensos
  conectan las escalas, así un 1.8 de ataque significa lo mismo en Inglaterra que en Portugal.
- Observaciones del mercado (market=True): goles esperados implícitos en las cuotas de cierre. Entran en el
  ajuste con su peso, pero no cuentan como partidos jugados ni para estimar la sobredispersión.
- Nivel reciente de la liga (opcional, `level` y `cup_level`, lo rellena `fitting.count_levels` en remates y a
  puerta): se suma a los dos equipos después del ajuste, sin tocar el ataque ni la defensa de ninguno.
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
    market: bool = False
    competition: str | None = None  # para la ventaja local de cada competición (`home_l2` en `fit`)


@dataclass
class RatingModel:
    teams: list[int]
    mu: float
    home_adv: float
    attack: dict[int, float]
    defence: dict[int, float]
    dispersion: float = 0.0  # alfa de la binomial negativa (0 = Poisson)
    # Alfa del total de los dos equipos (fitting.COUNT_TOTAL_DISPERSION); None = suma de independientes (goles y
    # paquetes antiguos)
    total_dispersion: float | None = None
    n_matches: dict[int, float] = field(default_factory=dict)  # partidos (ponderados) por equipo
    as_of: date | None = None
    # Partidos con cuotas de cierre en el último año (observaciones del mercado). Vacío = no se sabe (paquetes
    # antiguos o modelos sin mercado); 0 = el mercado no ha visto a este equipo (p.ej. ligas que no se descargan)
    market_matches: dict[int, int] = field(default_factory=dict)
    # Coeficientes b de la fuerza de referencia (ataque, defensa) cuando se ajusta con `strength`; None = sin ella.
    # Sirven para mover los conteos cuando la casa ve otra diferencia de fuerza (`fitting.strength_shift`).
    strength_coef: tuple[float, float] | None = None
    # Nivel reciente (log) de la liga de cada equipo y desvío propio de cada copa (`fitting.count_levels`). Vacíos =
    # sin nivel (goles, córners, faltas, tarjetas y paquetes antiguos).
    level: dict[int, float] = field(default_factory=dict)
    cup_level: dict[str, float] = field(default_factory=dict)
    # True: en una copa con nivel propio solo cuenta ese (tarjetas: la Champions no sigue a las ligas de sus equipos)
    cup_alone: bool = False
    # Desvío de la ventaja local de cada competición frente a home_adv (goles, `fit(home_l2=...)`); vacío = una sola
    home_by_comp: dict[str, float] = field(default_factory=dict)

    def level_for(self, home: int, away: int, competition: str | None = None) -> float:
        """Log del factor que el nivel reciente aplica a los dos equipos: media del de sus ligas (en un partido de
        liga, el de esa liga) más el desvío de la copa, si `competition` es una copa con desvío."""
        if self.cup_alone and competition in self.cup_level:
            return self.cup_level[competition]
        lv = 0.5 * (self.level.get(home, 0.0) + self.level.get(away, 0.0))
        return lv + self.cup_level.get(competition, 0.0) if competition else lv

    def expected(self, home: int, away: int, neutral: bool = False,
                 competition: str | None = None, level: bool = True) -> tuple[float, float]:
        """Medias (local, visitante). `level=False`: sin el nivel reciente de la liga (p. ej. para ajustar el factor
        del árbitro con partidos de hace años)."""
        ah, aa = self.attack.get(home, 0.0), self.attack.get(away, 0.0)
        dh, da = self.defence.get(home, 0.0), self.defence.get(away, 0.0)
        h = 0.0 if neutral else self.home_adv + self.home_by_comp.get(competition, 0.0)
        lv = self.level_for(home, away, competition) if level and (self.level or self.cup_level) else 0.0
        return float(np.exp(self.mu + lv + h + ah - da)), float(np.exp(self.mu + lv + aa - dh))

    def to_dict(self) -> dict:
        return {
            "mu": self.mu,
            "home_adv": self.home_adv,
            "dispersion": self.dispersion,
            "total_dispersion": self.total_dispersion,
            "attack": {str(k): v for k, v in self.attack.items()},
            "defence": {str(k): v for k, v in self.defence.items()},
            "n_matches": {str(k): v for k, v in self.n_matches.items()},
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "market_matches": {str(k): v for k, v in self.market_matches.items()},
            "strength_coef": list(self.strength_coef) if self.strength_coef else None,
            "level": {str(k): v for k, v in self.level.items()},
            "cup_level": dict(self.cup_level),
            "cup_alone": self.cup_alone,
            "home_by_comp": dict(self.home_by_comp),
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
            total_dispersion=d.get("total_dispersion"),
            n_matches={int(k): v for k, v in d.get("n_matches", {}).items()},
            as_of=date.fromisoformat(d["as_of"]) if d.get("as_of") else None,
            market_matches={int(k): int(v) for k, v in d.get("market_matches", {}).items()},
            strength_coef=tuple(d["strength_coef"]) if d.get("strength_coef") else None,
            level={int(k): v for k, v in d.get("level", {}).items()},
            cup_level=dict(d.get("cup_level", {})),
            cup_alone=bool(d.get("cup_alone", False)),
            home_by_comp=dict(d.get("home_by_comp", {})),
        )


MARKET_COVERAGE_DAYS = 365  # ventana para contar los partidos de cada equipo con cuotas de cierre


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
    market_half_life_days: float | None = None,
    prior_matches: float | None = None,
    strength: dict[int, float] | None = None,
    home_l2: float | None = None,
) -> RatingModel:
    """`prior_matches`: contracción hacia la media expresada en partidos (ponderados) "promedio" en vez de una L2
    fija. Cada partido aporta a la curvatura del ataque o la defensa de un equipo tanto como su media (~1,4 en
    goles, ~5 en córners, ~12 en remates), así que una misma L2 apenas contrae los conteos grandes: con L2 = 1, un
    equipo con 2 partidos de córners conserva el 90 % de lo que vio en ellos. Con `prior_matches` = K,
    L2 = K × media y un equipo con n partidos conserva ~n / (n + K).

    `strength`: fuerza de referencia de cada equipo (0 si falta). La contracción va entonces hacia b × fuerza en vez
    de hacia 0. Dentro de una liga casi no cambia nada (la desviación absorbe lo que se ve), pero entre ligas que
    apenas se cruzan (en córners, solo por la Champions) el nivel de cada liga lo da la fuerza y no la L2, que
    supone que todas las ligas son igual de fuertes. El modelo devuelto guarda en attack/defence la suma, así que se
    usa igual con o sin fuerza.

    `home_l2`: ventaja local propia de cada competición de las observaciones (`MatchObs.competition`), como desvío de
    la general con esta L2. None = una sola ventaja para todas."""
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
    real = np.array([not o.market for o in obs])
    days = np.array([o.day for o in obs])
    ow = np.array([o.weight for o in obs])
    comps = sorted({o.competition for o in obs if o.competition}) if home_l2 is not None else []
    nc = len(comps)
    cpos = {c: k for k, c in enumerate(comps)}
    ci = np.array([cpos.get(o.competition, nc) for o in obs])  # nc = sin desvío propio
    w = time_weights(days, as_of, half_life_days) * ow
    if market_half_life_days and not real.all():
        # El mercado apenas tiene ruido: puede pesar más lo reciente que en los partidos reales
        w = np.where(real, w, time_weights(days, as_of, market_half_life_days) * ow)

    # Centrada en los equipos que la tienen, para que mu siga siendo la media (los que no la tienen quedan en 0)
    strength = strength or {}
    known = [strength[t] for t in teams if t in strength]
    center = float(np.mean(known)) if known else 0.0
    xs = np.array([strength[t] - center if t in strength else 0.0 for t in teams])

    def unpack(theta: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray, float, float]:
        """mu, local, desviaciones de ataque y defensa, desvíos del local por competición y coeficientes b de la
        fuerza (ataque, defensa)."""
        return (theta[0], theta[1], theta[2 : 2 + n], theta[2 + n : 2 + 2 * n], theta[2 + 2 * n : 2 + 2 * n + nc],
                theta[-2], theta[-1])

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        mu, home, da, dd, hd, ba, bd = unpack(theta)
        att, de = da + ba * xs, dd + bd * xs
        eta_h = mu + (home + np.append(hd, 0.0)[ci]) * hm + att[hi] - de[ai]
        eta_a = mu + att[ai] - de[hi]
        lh, la = np.exp(eta_h), np.exp(eta_a)
        nll = np.sum(w * (lh - yh * eta_h)) + np.sum(w * (la - ya * eta_a))
        nll += 0.5 * l2 * (np.sum(da**2) + np.sum(dd**2)) + 0.5 * (home_l2 or 0.0) * np.sum(hd**2)
        rh, ra = w * (lh - yh), w * (la - ya)  # derivadas respecto a eta
        g = np.zeros_like(theta)
        g[0] = rh.sum() + ra.sum()
        g[1] = (rh * hm).sum()
        g_att = np.bincount(hi, weights=rh, minlength=n) + np.bincount(ai, weights=ra, minlength=n)
        g_def = -np.bincount(ai, weights=rh, minlength=n) - np.bincount(hi, weights=ra, minlength=n)
        g[2 : 2 + n] = g_att + l2 * da
        g[2 + n : 2 + 2 * n] = g_def + l2 * dd
        g[2 + 2 * n : 2 + 2 * n + nc] = np.bincount(ci, weights=rh * hm, minlength=nc + 1)[:nc] + (home_l2 or 0.0) * hd
        g[-2], g[-1] = g_att @ xs, g_def @ xs
        return nll, g

    mean_y = max(float(np.average(np.concatenate([yh, ya]), weights=np.concatenate([w, w]))), 1e-3)
    if prior_matches is not None:
        l2 = prior_matches * mean_y
    theta0 = np.zeros(4 + 2 * n + nc)
    theta0[0] = np.log(mean_y)
    theta0[1] = 0.1
    res = minimize(objective, theta0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    mu, home, da, dd, hd, ba, bd = unpack(res.x)
    att, de = da + ba * xs, dd + bd * xs

    # Sobredispersión (alfa de NB) por momentos: Var = m + alfa m^2 (solo con partidos reales)
    lh = np.exp(mu + (home + np.append(hd, 0.0)[ci]) * hm + att[hi] - de[ai])
    la = np.exp(mu + att[ai] - de[hi])
    y = np.concatenate([yh[real], ya[real]])
    mm = np.concatenate([lh[real], la[real]])
    ww = np.concatenate([w[real], w[real]])
    alpha = float(np.sum(ww * ((y - mm) ** 2 - mm)) / max(np.sum(ww * mm**2), 1e-9))

    wr = np.where(real, w, 0.0)
    counts = np.bincount(hi, weights=wr, minlength=n) + np.bincount(ai, weights=wr, minlength=n)
    recent_market = ~real & (np.array([(as_of - d).days for d in days]) <= MARKET_COVERAGE_DAYS)
    market_n = (np.bincount(hi[recent_market], minlength=n) + np.bincount(ai[recent_market], minlength=n)
                if not real.all() else None)
    return RatingModel(
        teams=teams,
        mu=float(mu),
        home_adv=float(home),
        attack={t: float(att[i]) for t, i in idx.items()},
        defence={t: float(de[i]) for t, i in idx.items()},
        dispersion=max(alpha, 0.0),
        n_matches={t: float(counts[i]) for t, i in idx.items()},
        as_of=as_of,
        market_matches={t: int(market_n[i]) for t, i in idx.items()} if market_n is not None else {},
        strength_coef=(float(ba), float(bd)) if known else None,
        home_by_comp={c: float(hd[k]) for c, k in cpos.items()},
    )
