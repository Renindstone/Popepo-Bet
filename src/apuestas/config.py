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
    # Solo se piden las competiciones con partidos en los próximos N días: la API admite 5 torneos por petición y,
    # si juegan más (con nueve competiciones, casi cada día), hace una segunda petición por casa
    oddspapi_window_days: float = 3.0
    # Descargas de Pinnacle antes del inicio para el CLV de las que pasan el corte (0 = ninguna). Aprobado por el
    # usuario el 2026-10-28: como mucho 3 al día, unas 40-90 peticiones más al mes
    oddspapi_closing_per_day: int = 3
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
    # Córners, tarjetas y demás estadísticas (y props de jugador) no se han validado contra cuotas reales: no
    # pueden ser apuesta del día salvo que se active esto (se siguen mostrando como apuestas con valor)
    pick_allow_stat_markets: bool = False
    # Las cuotas más bajas no salen en la lista «Con valor» de Hoy (a 1.01-1.19 casi no hay margen que ganar)
    value_list_min_odds: float = 1.20

    # Capturas de cuotas (imágenes de bet365/Betano que lee una IA vía MCP)
    # Motor automático: local (modelo de visión en esta PC con Ollama, gratis), claude_code (CLI con la suscripción
    # del dueño), api (API de Claude, de pago) o none (solo agentes externos conectados por MCP).
    captures_engine: str = "local"
    # Motor del botón "Leer con Claude" cuando la lectura local no basta (vacío = sin botón)
    captures_fallback_engine: str = "claude_code"
    captures_local_model: str = "qwen2.5vl:7b"
    ollama_url: str = "http://127.0.0.1:11434"
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
    # Solo para el MCP que lanza el motor de notas de Claude: habilita guardar_explicacion
    mcp_engine: bool = False
    ai_notes_timeout_s: int = 300

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

    def engine_users(self) -> set[str]:
        """Usuarios que pueden usar los motores de esta PC (capturas y Claude): por defecto, solo el dueño."""
        return {u.strip() for u in self.captures_engine_users.split(",") if u.strip()} or {self.default_user}

    def captures_engine_for(self, username: str) -> str | None:
        """Motor automático que procesa las capturas de este usuario (None = las procesa su propio agente)."""
        if self.captures_engine == "none":
            return None
        return self.captures_engine if username in self.engine_users() else None

    def captures_fallback_for(self, username: str) -> str | None:
        """Motor alternativo (p.ej. Claude) para releer una captura que el motor local no leyó bien."""
        engine = self.captures_fallback_engine
        if not engine or engine == self.captures_engine or self.captures_engine_for(username) is None:
            return None
        return engine


@lru_cache
def get_settings() -> Settings:
    return Settings()
