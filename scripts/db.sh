#!/usr/bin/env bash
# Cluster PostgreSQL propio del proyecto (no necesita sudo).
# Uso: scripts/db.sh init|start|stop|status|psql
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${APUESTAS_PGDATA:-$HOME/.local/share/apuestas/pgdata}"
RUN_DIR="${APUESTAS_PGRUN:-$HOME/.local/share/apuestas/run}"
PORT="${APUESTAS_PGPORT:-5433}"
LOG_FILE="$HOME/.local/share/apuestas/postgres.log"
ENV_FILE="$PROJECT_DIR/.env"

# Debian/Ubuntu y Homebrew (Mac) dejan los programas de PostgreSQL fuera del PATH: se busca la versión más alta
if ! command -v pg_ctl >/dev/null 2>&1; then
  for d in /usr/lib/postgresql/*/bin /opt/homebrew/opt/postgresql@*/bin /usr/local/opt/postgresql@*/bin; do
    if [[ -x "$d/pg_ctl" ]]; then PATH="$d:$PATH"; fi
  done
fi
command -v pg_ctl >/dev/null 2>&1 || { echo "Falta PostgreSQL (pg_ctl): mira el paso 1 de docs/instalacion.md" >&2; exit 1; }

start() {
  # Idempotente: si ya está en marcha no hace nada (útil para systemd y para varias sesiones)
  if pg_ctl -D "$DATA_DIR" status >/dev/null 2>&1; then
    echo "PostgreSQL ya está en marcha"; return 0
  fi
  mkdir -p "$RUN_DIR"
  pg_ctl -D "$DATA_DIR" -l "$LOG_FILE" -w -o "-p $PORT -k $RUN_DIR -c listen_addresses=127.0.0.1" start
}

case "${1:-}" in
  init)
    if [[ -f "$DATA_DIR/PG_VERSION" ]]; then
      echo "El cluster ya existe en $DATA_DIR"; exit 0
    fi
    mkdir -p "$DATA_DIR" "$RUN_DIR"
    PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
    PWFILE="$(mktemp)"; echo "$PASSWORD" > "$PWFILE"
    # El Mac no tiene la configuración regional C.UTF-8
    LOCALE=C.UTF-8; if [[ "$(uname)" == Darwin ]]; then LOCALE=en_US.UTF-8; fi
    initdb -D "$DATA_DIR" -U apuestas --pwfile="$PWFILE" --auth=scram-sha-256 -E UTF8 --locale="$LOCALE" >/dev/null
    rm -f "$PWFILE"
    start
    PGPASSWORD="$PASSWORD" createdb -h 127.0.0.1 -p "$PORT" -U apuestas apuestas
    if [[ ! -f "$ENV_FILE" ]]; then cp "$PROJECT_DIR/.env.example" "$ENV_FILE"; fi
    # sed -i.bak funciona igual en Linux y en Mac
    sed -i.bak "s#^APUESTAS_DATABASE_URL=.*#APUESTAS_DATABASE_URL=postgresql+psycopg://apuestas:${PASSWORD}@127.0.0.1:${PORT}/apuestas#" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
    echo "Base de datos creada. Credenciales guardadas en .env"
    ;;
  start) start ;;
  stop) pg_ctl -D "$DATA_DIR" -m fast stop ;;
  status) pg_ctl -D "$DATA_DIR" status ;;
  psql)
    URL="$(grep '^APUESTAS_DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | sed 's#+psycopg##')"
    shift; psql "$URL" "$@"
    ;;
  *) echo "Uso: $0 init|start|stop|status|psql"; exit 1 ;;
esac
