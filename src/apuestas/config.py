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
    # Casas de OddsPapi (slugs). Cada una cuesta 1 petición al día. betano.pe = Betano Perú; Pinnacle da la
    # referencia del mercado afilado en Champions. Añade ",bet365" para sus cuotas de Champions (+30 al mes)
    oddspapi_bookmakers: str = "betano.pe,pinnacle"
    telegram_token: str = ""
    telegram_chat_id: str = ""
    default_user: str = "renzo"

    # Acceso educado a fuentes externas: segundos mínimos entre peticiones al mismo host
    http_min_interval: float = 1.5
    http_user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

    # Temporadas de historial que usan los modelos (además de la actual)
    history_seasons: int = 3
    # Entrenar también con las ligas extra de football-data (Austria, Noruega...). Se descargan siempre, pero con
    # el modelo actual no mejoran el backtest de las copas europeas (ver docs/modelos.md)
    extra_leagues_in_model: bool = False

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

    # Capturas de cuotas (imágenes de bet365/Betano que lee una IA vía MCP)
    # Motor automático: claude_code (CLI con la suscripción del dueño), api (API de Claude, de pago) o none
    # (solo agentes externos conectados por MCP).
    captures_engine: str = "claude_code"
    # Usuarios cuyas capturas procesa el motor automático, separados por comas (vacío = solo default_user).
    # Con claude_code deja solo al dueño: la suscripción es personal.
    captures_engine_users: str = ""
    captures_timeout_s: int = 300
    captures_max_mb: float = 10.0
    claude_bin: str = "claude"
    captures_cli_model: str = "sonnet"  # alias del CLI de Claude Code
    anthropic_api_key: str = ""  # solo motor api
    captures_api_model: str = "claude-sonnet-5-5"
    # Usuario con el que actúa el servidor MCP en modo stdio (vacío = default_user)
    mcp_user: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cache_dir(self) -> Path:
        return self.var_dir / "cache"

    @property
    def archive_dir(self) -> Path:
        return self.var_dir / "archive"

    @property
    def captures_dir(self) -> Path:
        return self.var_dir / "capturas"

    def captures_engine_for(self, username: str) -> str | None:
        """Motor automático que procesa las capturas de este usuario (None = las procesa su propio agente)."""
        if self.captures_engine == "none":
            return None
        allowed = {u.strip() for u in self.captures_engine_users.split(",") if u.strip()} or {self.default_user}
        return self.captures_engine if username in allowed else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
