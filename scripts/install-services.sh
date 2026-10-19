#!/usr/bin/env bash
# Instala servicios systemd de usuario: base de datos, worker (tareas programadas) y, opcionalmente, API y bot.
# Uso: scripts/install-services.sh [--with-api] [--with-bot]
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
BIN="$PROJECT_DIR/.venv/bin/apuestas"
mkdir -p "$UNIT_DIR"

cat > "$UNIT_DIR/apuestas-db.service" <<UNIT
[Unit]
Description=PostgreSQL del proyecto App Apuestas (puerto 5433)

[Service]
Type=forking
ExecStart="$PROJECT_DIR/scripts/db.sh" start
ExecStop="$PROJECT_DIR/scripts/db.sh" stop
Restart=on-failure

[Install]
WantedBy=default.target
UNIT

unit() {  # nombre, comando, descripción
  cat > "$UNIT_DIR/apuestas-$1.service" <<UNIT
[Unit]
Description=App Apuestas: $3
After=apuestas-db.service network-online.target
Requires=apuestas-db.service

[Service]
WorkingDirectory=$PROJECT_DIR
ExecStart="$BIN" $2
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
UNIT
}

unit worker worker "tareas programadas"
services=(apuestas-db apuestas-worker)
for arg in "$@"; do
  case "$arg" in
    --with-api) unit api "api --host 127.0.0.1 --port 8000" "API REST"; services+=(apuestas-api) ;;
    --with-bot) unit bot bot "bot de Telegram"; services+=(apuestas-bot) ;;
  esac
done

# Si el cluster ya está corriendo fuera de systemd, se para para que systemd lo gestione
"$PROJECT_DIR/scripts/db.sh" status >/dev/null 2>&1 && "$PROJECT_DIR/scripts/db.sh" stop || true

systemctl --user daemon-reload
systemctl --user enable --now "${services[@]}"
systemctl --user --no-pager status "${services[@]}" | grep -E "●|Active:"
echo "Logs: journalctl --user -u apuestas-worker -f"
