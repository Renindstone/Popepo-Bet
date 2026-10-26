#!/usr/bin/env bash
# Instala servicios systemd de usuario: base de datos, worker (tareas programadas) y, opcionalmente,
# API REST, panel web y bot de Telegram. Se puede volver a ejecutar sin problema (reescribe las unidades).
# Uso: scripts/install-services.sh [--with-api] [--with-web] [--with-bot]
#   --with-web instala también la API (el panel y las capturas la necesitan)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
BIN="$PROJECT_DIR/.venv/bin/apuestas"
mkdir -p "$UNIT_DIR"

cat > "$UNIT_DIR/apuestas-db.service" <<UNIT
[Unit]
Description=PostgreSQL del proyecto App Apuestas (puerto 5433)

[Service]
# oneshot + RemainAfterExit: "db.sh start" es idempotente, así no falla si el cluster ya estaba en marcha
Type=oneshot
RemainAfterExit=yes
ExecStart="$PROJECT_DIR/scripts/db.sh" start
ExecStop="$PROJECT_DIR/scripts/db.sh" stop

[Install]
WantedBy=default.target
UNIT

unit() {  # nombre, comando, descripción, líneas extra de [Service] (opcional)
  cat > "$UNIT_DIR/apuestas-$1.service" <<UNIT
[Unit]
Description=App Apuestas: $3
After=apuestas-db.service network-online.target
Requires=apuestas-db.service

[Service]
WorkingDirectory=$PROJECT_DIR
${4:-}
ExecStart="$BIN" $2
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
UNIT
}

web_unit() {
  local npm
  npm="$(command -v npm)" || { echo "Falta Node.js/npm para el panel web" >&2; exit 1; }
  if [[ ! -d "$PROJECT_DIR/web/node_modules" ]]; then
    echo "Instalando dependencias del panel (npm ci)…"
    (cd "$PROJECT_DIR/web" && "$npm" ci --no-audit --no-fund)
  fi
  cat > "$UNIT_DIR/apuestas-web.service" <<UNIT
[Unit]
Description=App Apuestas: panel web (http://localhost:3000)
After=apuestas-api.service
Wants=apuestas-api.service

[Service]
WorkingDirectory=$PROJECT_DIR/web
Environment=NODE_ENV=production
# Compila al arrancar: tras actualizar el código basta con reiniciar el servicio
ExecStartPre="$npm" run build
ExecStart="$npm" run start -- --hostname 127.0.0.1 --port 3000
TimeoutStartSec=600
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
UNIT
}

# El worker solo descarga de 05:00 a 20:00: por la noche no gasta recursos (decisión del usuario, 2026-10-26).
# Fuera de ese horario no arranca (ni al encender el PC); a las 20:00 se apaga y a las 05:00 vuelve. Al arrancar
# recupera las tareas del día que no corrieron.
unit worker worker "tareas programadas" "ExecCondition=/bin/sh -c 'h=\$(date +%%-H); [ \"\$h\" -ge 5 ] && [ \"\$h\" -lt 20 ]'"
cat > "$UNIT_DIR/apuestas-worker-stop.service" <<UNIT
[Unit]
Description=App Apuestas: apagar el worker por la noche

[Service]
Type=oneshot
ExecStart=$(command -v systemctl) --user stop apuestas-worker.service
UNIT
for when in stop start; do
  cat > "$UNIT_DIR/apuestas-worker-$when.timer" <<UNIT
[Unit]
Description=App Apuestas: $([[ $when == stop ]] && echo "apagar el worker a las 20:00" || echo "encender el worker a las 05:00")

[Timer]
OnCalendar=*-*-* $([[ $when == stop ]] && echo 20:00:00 || echo 05:00:00)
Unit=apuestas-worker$([[ $when == stop ]] && echo -stop).service

[Install]
WantedBy=timers.target
UNIT
done
services=(apuestas-db apuestas-worker)
with_api=false
for arg in "$@"; do
  case "$arg" in
    --with-api) with_api=true ;;
    --with-web) with_api=true; web_unit; services+=(apuestas-web) ;;
    --with-bot) unit bot bot "bot de Telegram"; services+=(apuestas-bot) ;;
    *) echo "Opción desconocida: $arg" >&2; exit 1 ;;
  esac
done
if $with_api; then
  unit api "api --host 127.0.0.1 --port 8000" "API REST y capturas"
  services+=(apuestas-api)
fi

systemctl --user daemon-reload
systemctl --user enable "${services[@]}"
systemctl --user enable --now apuestas-worker-stop.timer apuestas-worker-start.timer
# La BD solo se arranca (reiniciarla cortaría a los demás); el resto se reinicia para cargar el código actual
systemctl --user start apuestas-db
systemctl --user restart "${services[@]:1}"
systemctl --user --no-pager status "${services[@]}" | grep -E "●|Active:" || true
echo "Logs: journalctl --user -u apuestas-worker -f   (o apuestas-api, apuestas-web)"
