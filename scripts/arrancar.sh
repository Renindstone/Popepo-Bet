#!/usr/bin/env bash
# Arranca Popepo-Bet en esta terminal, sin servicios del sistema (Mac, o Linux sin systemd): base de datos,
# API (puerto 8000), tareas programadas (worker) y panel (http://localhost:3000). Ctrl+C lo para todo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

parar() {
  trap - INT TERM EXIT
  trap '' TERM
  echo "Parando…"
  # A todo el grupo (también los hijos del panel): lo lanzado en segundo plano no recibe el Ctrl+C
  kill -TERM 0 2>/dev/null || true
  wait 2>/dev/null || true
  scripts/db.sh stop >/dev/null 2>&1 || true
}
trap parar INT TERM EXIT

scripts/db.sh start
.venv/bin/apuestas api --host 127.0.0.1 --port 8000 &
.venv/bin/apuestas worker &
# El panel se compila al arrancar (1-2 min), igual que el servicio de Linux
(cd web && NODE_ENV=production npm run build && NODE_ENV=production npm run start -- --hostname 127.0.0.1 --port 3000) &

echo "Panel en http://localhost:3000 en cuanto termine de compilar. Ctrl+C para pararlo todo."
wait
