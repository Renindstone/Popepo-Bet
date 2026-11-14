"""¿Hay un índice de calidad del once mejor que el actual (`features/lineup.py`)?

Corre el backtest de siempre con los onces (`engine.run(lineups=True)`: las ocho ligas y la Champions, de agosto de
2024 a hoy) y, en los partidos con el once confirmado de los dos equipos, compara la pérdida logarítmica del 1X2 y
la de los goles del modelo sin ajuste, con el índice actual (valor de mercado, β = 0,10) y con índices hechos solo
con datos de FotMob anteriores a cada partido:

- nota: la nota media de FotMob del jugador en sus últimos 10 partidos, contraída hacia 6,8;
- xg+xa: su xG + xA por 90 minutos en esos partidos, contraído hacia la media de su posición;
- habituales: en cuántos de los últimos 8 onces de su equipo fue titular;
- actual + habituales y todo junto: el actual con el tercero, y el actual con los tres.

Cada índice mide la diferencia entre el once de hoy y el once típico (los titulares de los últimos 8 onces, pesados
por las veces que salieron), los dos con la calidad de antes del partido. Las β de cada índice se ajustan (Poisson
con offset, como `engine.lineup_regression`) con dos temporadas y se miden en la tercera: todas las cifras son fuera
de muestra, menos la del índice actual con β = 0,10, que es la de producción. La ventana de 10 partidos y las
contracciones se fijaron antes de medir y no se afinaron.

Ojo: el valor de mercado guardado es el del día de la descarga (noviembre de 2026 para todo el historial), así que
el índice actual ve el futuro en los partidos antiguos y sale algo favorecido; los índices nuevos no.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/calidad_once.py (unos 3 min)
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from sqlalchemy import text

from apuestas.backtest import engine
from apuestas.db.session import session_scope
from apuestas.features import lineup as lu

START, END = date(2024, 8, 1), date(2026, 11, 9)
FOLDS = (date(2025, 7, 1), date(2026, 7, 1))  # 2024-25 | 2025-26 | 2026-27
WINDOW = 10  # partidos del jugador que cuentan
RATING_PRIOR_MIN = 270  # minutos a 6,8 que se suman a su nota
XGXA_PRIOR_MIN = 450  # minutos a la media de su posición que se suman a su xG + xA
INDICES = ("nota", "xg+xa", "habituales")
VARIANTS = {"actual, β ajustada": ("actual",), "nota": ("nota",), "xg+xa": ("xg+xa",), "habituales": ("habituales",),
            "actual + habituales": ("actual", "habituales"), "todo junto": ("actual", *INDICES)}


def collect() -> dict[int, dict]:
    """Partidos con el once confirmado de los dos equipos: medias del modelo y diferencias del índice actual."""
    out: dict[int, dict] = {}
    orig = engine._evaluate_lineup

    def spy(r, gm, rho, od, xi_hist, xi_idx, ll_lu, lu_rows):
        n = len(lu_rows)
        orig(r, gm, rho, od, xi_hist, xi_idx, ll_lu, lu_rows)
        if len(lu_rows) == n + 2:  # (partido, media, Δataque propio, Δdefensa rival, goles, xG) de cada equipo
            (_, lh, dah, dda, *_), (_, la, daa, ddh, *_) = lu_rows[-2:]
            out[r.match_id] = {"r": r, "lh": lh, "la": la, "rho": rho, "actual": ((dah, ddh), (daa, dda)),
                               "bet365": engine._book_probs(od, "bet365"),
                               "pinnacle": engine._book_probs(od, "pinnacle") or engine._book_probs(od, "betfair_ex"),
                               "cierre": engine._book_probs(od, "pinnacle", "closing")}

    engine._evaluate_lineup = spy
    try:
        res = engine.run(START, END, lineups=True, extra_competitions=("UCL",))
    finally:
        engine._evaluate_lineup = orig
    # Comprobación: lo capturado da la misma pérdida que el propio backtest, con y sin el ajuste actual
    for comp in {row["r"].competition for row in out.values()}:
        mine = [losses(row, *eta(row, "actual", np.array([lu.BETA_ATT, lu.BETA_DEF])))[0]
                for row in out.values() if row["r"].competition == comp]
        theirs = res.lineups["logloss_modelo_por_competicion"][f"{comp}:modelo+alineacion"]
        assert len(mine) == theirs["partidos"] and abs(np.mean(mine) - theirs["logloss"]) < 1e-4, (comp, theirs)
    return out


def load() -> tuple[dict, dict, dict, dict]:
    """Historial de cada jugador (sumas acumuladas), media de xG + xA por posición y onces confirmados."""
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        stats = s.execute(text("""
            select p.player_id, m.kickoff_utc, p.minutes, p.rating, coalesce(p.xg, 0) + coalesce(p.xa, 0),
                   coalesce(pl.position, 'MF')
            from player_match_stats p join match m on m.id = p.match_id join player pl on pl.id = p.player_id
            where m.status = 'finished' and p.minutes > 0
            order by m.kickoff_utc""")).all()
        starters = s.execute(text("""
            select l.team_id, m.kickoff_utc, l.match_id, l.player_id, coalesce(l.position, pl.position, 'MF')
            from lineup l join match m on m.id = l.match_id join player pl on pl.id = l.player_id
            where l.status = 'confirmed' and l.is_starter and m.status = 'finished'
            order by m.kickoff_utc, l.match_id""")).all()
    # Por jugador: días y sumas acumuladas de minutos, nota × minutos, minutos con nota y xG + xA (un xG vacío es 0:
    # FotMob solo lo da a quien remató)
    hist: dict[int, tuple] = defaultdict(lambda: ([], [0.0], [0.0], [0.0], [0.0]))
    by_pos: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for pid, kickoff, mins, rating, xgxa, pos in stats:
        day = kickoff.date()  # el mismo día que `MatchRow.day` del backtest
        days, c_min, c_rat, c_rmin, c_x = hist[pid]
        days.append(day)
        c_min.append(c_min[-1] + mins)
        c_rat.append(c_rat[-1] + (rating * mins if rating else 0.0))
        c_rmin.append(c_rmin[-1] + (mins if rating else 0))
        c_x.append(c_x[-1] + xgxa)
        if day < START:  # la media de cada posición sale de 2023-24: nada del periodo que se mide
            by_pos[pos][0] += xgxa
            by_pos[pos][1] += mins
    prior = {pos: 90 * x / mins for pos, (x, mins) in by_pos.items()}
    xis: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)
    team_days: dict[int, list[tuple[date, int]]] = defaultdict(list)
    for tid, kickoff, mid, pid, pos in starters:
        if (mid, tid) not in xis:
            team_days[tid].append((kickoff.date(), mid))
        xis[(mid, tid)].append((pid, pos))
    return dict(hist), prior, dict(xis), dict(team_days)


def team_deltas(tid: int, mid: int, day: date, hist: dict, prior: dict, xis: dict, team_days: dict) -> dict | None:
    """{índice: (Δataque, Δdefensa)} del once de hoy frente al once típico, con la calidad de antes del partido."""
    today = xis.get((mid, tid))
    seen = team_days.get(tid, [])
    prev = [xis[(m, tid)] for _, m in seen[max(bisect_left(seen, (day, 0)) - lu.BASELINE_MATCHES, 0):bisect_left(seen, (day, 0))]]
    if not today or not prev:
        return None
    freq: dict[int, float] = defaultdict(float)
    pos_of: dict[int, str] = {}
    for players in prev:
        for pid, pos in players:
            freq[pid] += 1 / len(prev)
            pos_of[pid] = pos
    cache: dict[int, tuple[float, float, float]] = {}

    def quality(pid: int, pos: str) -> tuple[float, float, float]:
        if pid not in cache:
            h = hist.get(pid)
            mins = rat = rmin = x = 0.0
            if h:
                i = bisect_left(h[0], day)  # solo partidos anteriores al día del partido
                mins, rat, rmin, x = (c[i] - c[max(i - WINDOW, 0)] for c in h[1:])
            cache[pid] = ((rat + 6.8 * RATING_PRIOR_MIN) / (rmin + RATING_PRIOR_MIN) - 6.8,
                          (x + prior.get(pos, prior["MF"]) * XGXA_PRIOR_MIN / 90) / ((mins + XGXA_PRIOR_MIN) / 90),
                          freq.get(pid, 0.0))
        return cache[pid]

    out = {}
    for k, name in enumerate(INDICES):
        sides = []
        for weights in (lu.ATT_W, lu.DEF_W):
            # «habituales» no depende de la posición: cuenta igual un portero que un delantero
            w = (lambda pos: 1.0) if name == "habituales" else (lambda pos, weights=weights: weights.get(pos, 0.5))
            xi = sum(w(pos) * quality(pid, pos)[k] for pid, pos in today) / sum(w(pos) for _, pos in today)
            base = (sum(f * w(pos_of[pid]) * quality(pid, pos_of[pid])[k] for pid, f in freq.items())
                    / sum(f * w(pos_of[pid]) for pid, f in freq.items()))
            sides.append(xi - base)
        out[name] = tuple(sides)
    return out


def features(row: dict, names: tuple[str, ...]) -> tuple[list[float], list[float]]:
    """Variables de los goles del local y del visitante: Δataque propio y −Δdefensa del rival de cada índice."""
    xh, xa = [], []
    for name in names:
        (ah, dh), (aa, da) = row[name]
        xh += [ah, -da]
        xa += [aa, -dh]
    return xh, xa


def eta(row: dict, name: str | tuple[str, ...], beta: np.ndarray) -> tuple[float, float]:
    xh, xa = features(row, (name,) if isinstance(name, str) else name)
    return float(np.dot(xh, beta)), float(np.dot(xa, beta))


def losses(row: dict, eta_h: float = 0.0, eta_a: float = 0.0) -> tuple[float, float]:
    """Pérdida logarítmica del 1X2 y de los goles (Poisson de cada equipo) con las medias ajustadas."""
    r = row["r"]
    lh, la = row["lh"] * math.exp(eta_h), row["la"] * math.exp(eta_a)
    p = engine._probs_1x2(lh, la, row["rho"])
    k = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
    return -math.log(max(p[k], 1e-9)), -float(poisson.logpmf(r.hg, lh) + poisson.logpmf(r.ag, la))


def fit(rows: list[dict], names: tuple[str, ...]) -> np.ndarray:
    """β de la regresión de Poisson con offset; el intercepto se ajusta pero no se aplica, como en producción."""
    y, off, x = [], [], []
    for row in rows:
        xh, xa = features(row, names)
        y += [row["r"].hg, row["r"].ag]
        off += [math.log(row["lh"]), math.log(row["la"])]
        x += [[1.0, *xh], [1.0, *xa]]
    y, off, x = np.array(y, dtype=float), np.array(off), np.array(x)

    def nll(b: np.ndarray) -> tuple[float, np.ndarray]:
        e = off + x @ b
        mu = np.exp(e)
        return float(np.sum(mu - y * e)), x.T @ (mu - y)

    return minimize(nll, np.zeros(x.shape[1]), jac=True, method="BFGS").x[1:]


def fold(day: date) -> int:
    return sum(day >= d for d in FOLDS)


def pm(d: np.ndarray) -> str:
    return f"{d.mean():+.4f} ± {1.96 * d.std(ddof=1) / math.sqrt(len(d)):.4f}"


def main() -> None:
    rows = collect()
    hist, prior, xis, team_days = load()
    data = []
    for mid, row in rows.items():
        r = row["r"]
        dh, da = (team_deltas(t, mid, r.day, hist, prior, xis, team_days) for t in (r.home, r.away))
        if dh and da:
            data.append(row | {name: (dh[name], da[name]) for name in INDICES})
    print(f"{len(data)} partidos con el once de los dos equipos ({len(rows) - len(data)} sin historial para los nuevos)")
    print("xG + xA por 90 de cada posición (2023-24):", ", ".join(f"{p} {v:.2f}" for p, v in sorted(prior.items())))

    # Pérdidas por partido de cada variante: {variante: [(1X2, goles)]}, en el orden de `data`
    out = {"sin ajuste": [losses(row) for row in data],
           "actual, β = 0,10": [losses(row, *eta(row, "actual", np.array([lu.BETA_ATT, lu.BETA_DEF]))) for row in data]}
    betas: dict[str, list[np.ndarray]] = defaultdict(list)
    for variant, names in VARIANTS.items():
        res: list = [None] * len(data)
        for f in range(len(FOLDS) + 1):
            beta = fit([row for row in data if fold(row["r"].day) != f], names)  # se ajusta fuera de la temporada medida
            betas[variant].append(beta)
            for i, row in enumerate(data):
                if fold(row["r"].day) == f:
                    res[i] = losses(row, *eta(row, names, beta))
        out[variant] = res

    print("\nβ ajustadas (media de los tres ajustes) y cuánto mueve los goles una desviación típica del índice:")
    for variant, names in VARIANTS.items():
        b = np.mean(betas[variant], axis=0)
        sd = np.std([features(row, names)[0] for row in data], axis=0)
        print(f"  {variant}: " + "; ".join(
            f"{n} ataque {b[2 * i]:+.3f} ({100 * b[2 * i] * sd[2 * i]:+.1f} %), defensa {b[2 * i + 1]:+.3f} "
            f"({100 * b[2 * i + 1] * sd[2 * i + 1]:+.1f} %)" for i, n in enumerate(names)))

    groups = {"Ligas": [i for i, row in enumerate(data) if row["r"].competition in engine.LEAGUES],
              "Champions": [i for i, row in enumerate(data) if row["r"].competition == "UCL"],
              "Todas": list(range(len(data)))}
    for group, ids in groups.items():
        print(f"\n{group} ({len(ids)} partidos). Diferencia de pérdida logarítmica (negativo = mejor):")
        print(f"  {'variante':<20} {'1X2':>7}  {'frente a sin ajuste':>20}  {'frente al actual':>20}  {'goles, frente a sin ajuste':>27}")
        for variant, res in out.items():
            a = np.array([res[i] for i in ids])
            none, cur = (np.array([out[k][i] for i in ids]) for k in ("sin ajuste", "actual, β = 0,10"))
            print(f"  {variant:<20} {a[:, 0].mean():.4f}  {pm(a[:, 0] - none[:, 0]):>20}  {pm(a[:, 0] - cur[:, 0]):>20}  "
                  f"{pm(a[:, 1] - none[:, 1]):>27}")
        for f, label in enumerate(("2024-25", "2025-26", "2026-27")):
            sub = [i for i in ids if fold(data[i]["r"].day) == f]
            if len(sub) > 30:
                print(f"  {label} ({len(sub)}), 1X2 frente a sin ajuste: " + "; ".join(
                    f"{v} {pm(np.array([out[v][i][0] - out['sin ajuste'][i][0] for i in sub]))}" for v in out if v != "sin ajuste"))

    ids = [i for i in groups["Ligas"] if all(data[i][b] for b in ("bet365", "pinnacle", "cierre"))]
    print(f"\nLigas con cuota previa de bet365 y Pinnacle y cierre de Pinnacle ({len(ids)} partidos), pérdida 1X2:")
    for variant, res in out.items():
        print(f"  {variant:<20} {np.mean([res[i][0] for i in ids]):.4f}")
    for book, label in (("bet365", "bet365, previa"), ("pinnacle", "Pinnacle, previa"), ("cierre", "Pinnacle, cierre")):
        ll = []
        for i in ids:
            r = data[i]["r"]
            ll.append(-math.log(max(data[i][book][0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)], 1e-9)))
        print(f"  {label:<20} {np.mean(ll):.4f}")


if __name__ == "__main__":
    main()
