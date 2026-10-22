"""Cliente HTTP "educado" para fuentes externas.

- Respeta un intervalo mínimo entre peticiones al mismo host.
- Guarda en disco (gzip) las respuestas para no repetir descargas: los partidos terminados
  no cambian, así que se cachean para siempre; lo demás tiene un TTL.
- Reintenta con espera exponencial ante errores temporales.
- Si un host no acepta la conexión tras los reintentos, se da por caído durante `HOST_DOWN_PAUSE` y las demás
  descargas de ese host fallan al momento (`SourceUnavailable`) en vez de esperar cada una sus reintentos.
- No intenta saltarse protecciones anti-bots: si una fuente bloquea (403), se registra y se sigue.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from apuestas.config import get_settings

log = logging.getLogger(__name__)


class SourceBlocked(RuntimeError):
    """La fuente rechazó la petición (403/401). No se reintenta."""


class SourceUnavailable(RuntimeError):
    """El host no acepta conexiones (caído o inalcanzable). Se vuelve a probar pasada la pausa."""


# Tras agotar los reintentos sin poder conectar, ese host no se vuelve a probar en 30 minutos. Sin esto, con
# football-data caído (21-10-2026) cada archivo esperaba 104 s y la ingesta de resultados tardaba casi una hora.
HOST_DOWN_PAUSE = 1800.0


class PoliteClient:
    def __init__(self, min_interval: float | None = None, cache_dir: Path | None = None):
        settings = get_settings()
        self.min_interval = settings.http_min_interval if min_interval is None else min_interval
        self.cache_dir = cache_dir or settings.cache_dir / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_call: dict[str, float] = {}
        self._down_until: dict[str, float] = {}  # host -> time.monotonic() hasta el que se da por caído
        self._lock = threading.Lock()
        self._client = httpx.Client(
            headers={"User-Agent": settings.http_user_agent, "Accept": "application/json, text/plain, */*"},
            timeout=httpx.Timeout(30.0, connect=15.0),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ caché
    def _cache_path(self, url: str, params: dict | None, headers: dict | None) -> Path:
        key = json.dumps([url, sorted((params or {}).items()), sorted((headers or {}).items())])
        digest = hashlib.sha256(key.encode()).hexdigest()
        host = urlparse(url).netloc.replace(":", "_")
        return self.cache_dir / host / digest[:2] / f"{digest}.gz"

    def _read_cache(self, path: Path, ttl: float | None) -> bytes | None:
        if not path.exists():
            return None
        if ttl is not None and time.time() - path.stat().st_mtime > ttl:
            return None
        return gzip.decompress(path.read_bytes())

    def _write_cache(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(content))
        tmp.replace(path)

    def forget(self, url: str, params: dict | None = None, headers: dict | None = None) -> None:
        self._cache_path(url, params, headers).unlink(missing_ok=True)

    # ------------------------------------------------------------------ red
    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last_call.get(host, 0) + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call[host] = time.monotonic()

    def get_bytes(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        ttl: float | None = 3600,
        retries: int = 3,
        store: bool = True,
    ) -> bytes:
        """Descarga con caché. `ttl=None` = cachear para siempre; `ttl=0` = siempre descargar.

        `store=False` no guarda la respuesta en disco (p.ej. si trae datos sensibles, como una clave de API).
        """
        path = self._cache_path(url, params, headers)
        if ttl != 0:
            cached = self._read_cache(path, ttl)
            if cached is not None:
                return cached

        host = urlparse(url).netloc
        down_until = self._down_until.get(host)
        if down_until is not None and time.monotonic() < down_until:
            minutes = max(1, round((down_until - time.monotonic()) / 60))
            raise SourceUnavailable(f"{host} no responde; se vuelve a probar en {minutes} min")
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle(host)
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError as exc:
                last_exc = exc
                time.sleep(2**attempt * 2)
                continue
            if resp.status_code in (401, 403):
                raise SourceBlocked(f"{host} respondió {resp.status_code} para {url}")
            if resp.status_code == 404:
                raise FileNotFoundError(url)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                time.sleep(2**attempt * 5)
                continue
            if resp.status_code >= 400:
                # Sin la URL completa: los parámetros pueden llevar claves de API (p.ej. OddsPapi usa ?apiKey=)
                raise RuntimeError(f"{host} respondió {resp.status_code} para {urlparse(url).path}: "
                                   f"{resp.text[:300]}")
            if store:
                self._write_cache(path, resp.content)
            self._down_until.pop(host, None)
            return resp.content
        if isinstance(last_exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            self._down_until[host] = time.monotonic() + HOST_DOWN_PAUSE
            log.warning("%s no acepta conexiones; se salta durante %d min", host, HOST_DOWN_PAUSE // 60)
            raise SourceUnavailable(f"{host} no responde (sin conexión): {last_exc}")
        raise RuntimeError(f"No se pudo descargar {url}: {last_exc}")

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return json.loads(self.get_bytes(url, **kwargs))

    def get_text(self, url: str, encoding: str = "utf-8", **kwargs: Any) -> str:
        return self.get_bytes(url, **kwargs).decode(encoding, errors="replace")


_client: PoliteClient | None = None


def client() -> PoliteClient:
    global _client
    if _client is None:
        _client = PoliteClient()
    return _client
