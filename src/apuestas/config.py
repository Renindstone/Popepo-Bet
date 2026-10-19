"""Configuración central, leída de variables de entorno (prefijo APUESTAS_) y del archivo .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APUESTAS_", env_file=PROJECT_DIR / ".env", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://apuestas@127.0.0.1:5433/apuestas"
    timezone: str = "America/Lima"
    var_dir: Path = PROJECT_DIR / "var"

    # Fuentes opcionales
    oddspapi_key: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    default_user: str = "renzo"

    # Acceso educado a fuentes externas: segundos mínimos entre peticiones al mismo host
    http_min_interval: float = 1.5
    http_user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

    # Temporadas de historial que usan los modelos (además de la actual)
    history_seasons: int = 3

    # Apuestas: gestión de banca
    kelly_fraction: float = 0.25
    max_stake_pct: float = 0.03
    daily_loss_limit_pct: float = 0.05
    weekly_loss_limit_pct: float = 0.10

    # Criterios de la apuesta del día
    pick_min_odds: float = 1.50
    pick_max_odds: float = 2.60
    pick_min_prob: float = 0.42
    pick_min_ev: float = 0.03
    pick_min_confidence: float = 0.60

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cache_dir(self) -> Path:
        return self.var_dir / "cache"

    @property
    def archive_dir(self) -> Path:
        return self.var_dir / "archive"


@lru_cache
def get_settings() -> Settings:
    return Settings()
