"""Competiciones que maneja el sistema y sus códigos en cada fuente.

- Nivel "full": se analizan a fondo (estadísticas de partido, jugadores, alineaciones, árbitros, picks). La Serie A y
  la Ligue 1 lo son desde el 21-10-2026; antes eran "light" y ya daban sus resultados y cuotas de cierre al modelo.
- Nivel "light": solo resultados/xG para conectar la escala de fuerza entre ligas (rivales de
  Champions, equipos ascendidos, fichajes que llegan de otras ligas). No generan picks.

Las ligas "extra" de football-data.co.uk (`fd_extra`, archivos new/XXX.csv) solo traen resultados y el 1X2
de cierre. Sirven para dar ratings del mercado a los rivales de las copas europeas (Bodø/Glimt, Salzburg,
Copenhague, Young Boys, Legia...). Algunas se juegan de marzo a noviembre (`calendar_year`).

La Europa League y la Conference (`fotmob_stats`) traen además de FotMob el árbitro y las estadísticas de equipo de
sus partidos jugados (remates, córners, tarjetas, xG...), sin alineaciones ni jugadores: son los partidos que conectan
las ligas en los modelos de remates y córners.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Competition:
    code: str
    name: str
    country: str
    tier: str  # "full" | "light"
    is_cup: bool = False
    fd_code: str | None = None  # football-data.co.uk
    understat: str | None = None  # understat.com
    fotmob_id: int | None = None  # fotmob.com
    espn: str | None = None  # site.api.espn.com
    fd_extra: str | None = None  # football-data.co.uk, liga "extra" (new/XXX.csv)
    calendar_year: bool = False  # temporada de marzo a noviembre (se identifica por el año natural)
    fotmob_stats: bool = False  # nivel "light": árbitro y estadísticas de equipo de FotMob de los partidos jugados


COMPETITIONS: dict[str, Competition] = {
    c.code: c
    for c in [
        # --- Análisis completo ---
        Competition("EPL", "Premier League", "England", "full", fd_code="E0", understat="EPL", fotmob_id=47, espn="eng.1"),
        Competition("BUN", "Bundesliga", "Germany", "full", fd_code="D1", understat="Bundesliga", fotmob_id=54, espn="ger.1"),
        Competition("LAL", "LaLiga", "Spain", "full", fd_code="SP1", understat="La_liga", fotmob_id=87, espn="esp.1"),
        Competition("SA", "Serie A", "Italy", "full", fd_code="I1", understat="Serie_A", fotmob_id=55, espn="ita.1"),
        Competition("L1", "Ligue 1", "France", "full", fd_code="F1", understat="Ligue_1", fotmob_id=53, espn="fra.1"),
        Competition("UCL", "Champions League", "Europe", "full", is_cup=True, fotmob_id=42, espn="uefa.champions"),
        # --- Solo para la escala de fuerza ---
        Competition("POR", "Primeira Liga", "Portugal", "light", fd_code="P1"),
        Competition("NED", "Eredivisie", "Netherlands", "light", fd_code="N1"),
        Competition("BEL", "Pro League", "Belgium", "light", fd_code="B1"),
        Competition("TUR", "Süper Lig", "Turkey", "light", fd_code="T1"),
        Competition("SCO", "Premiership", "Scotland", "light", fd_code="SC0"),
        Competition("GRE", "Super League", "Greece", "light", fd_code="G1"),
        Competition("ENG2", "Championship", "England", "light", fd_code="E1"),
        Competition("GER2", "2. Bundesliga", "Germany", "light", fd_code="D2"),
        Competition("ESP2", "Segunda División", "Spain", "light", fd_code="SP2"),
        Competition("AUT", "Bundesliga (Austria)", "Austria", "light", fd_extra="AUT"),
        Competition("DEN", "Superliga (Dinamarca)", "Denmark", "light", fd_extra="DNK"),
        Competition("NOR", "Eliteserien", "Norway", "light", fd_extra="NOR", calendar_year=True),
        Competition("SUI", "Super League (Suiza)", "Switzerland", "light", fd_extra="SWZ"),
        Competition("POL", "Ekstraklasa", "Poland", "light", fd_extra="POL"),
        Competition("SWE", "Allsvenskan", "Sweden", "light", fd_extra="SWE", calendar_year=True),
        Competition("ROU", "Superliga (Rumanía)", "Romania", "light", fd_extra="ROU"),
        Competition("FIN", "Veikkausliiga", "Finland", "light", fd_extra="FIN", calendar_year=True),
        Competition("IRL", "Premier Division", "Ireland", "light", fd_extra="IRL", calendar_year=True),
        Competition("UEL", "Europa League", "Europe", "light", is_cup=True, fotmob_id=73, fotmob_stats=True),
        Competition("UECL", "Conference League", "Europe", "light", is_cup=True, fotmob_id=10216, fotmob_stats=True),
    ]
}

FULL = [c for c in COMPETITIONS.values() if c.tier == "full"]
LIGHT = [c for c in COMPETITIONS.values() if c.tier == "light"]


def season_start_year(d: date) -> int:
    """Las temporadas europeas empiezan en julio: 2026-10-19 -> 2026 (temporada 2026-27)."""
    return d.year if d.month >= 7 else d.year - 1


def season_label(start_year: int, calendar_year: bool = False) -> str:
    return str(start_year) if calendar_year else f"{start_year}-{str(start_year + 1)[-2:]}"


def fd_season_code(start_year: int) -> str:
    """football-data.co.uk usa '2627' para 2026-27."""
    return f"{str(start_year)[-2:]}{str(start_year + 1)[-2:]}"


def fotmob_season(start_year: int) -> str:
    return f"{start_year}/{start_year + 1}"
