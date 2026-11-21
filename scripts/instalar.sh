#!/usr/bin/env bash
# Instala Popepo-Bet con un solo comando (Linux, Mac o Windows, con WSL o con Git Bash): entorno de Python, base de datos
# propia, tablas, dependencias del panel y, la primera vez, el historial y los modelos (3-4 h).
# Se puede volver a ejecutar: si se corta, sigue donde iba (lo descargado queda en caché), y después de un
# `git pull` sirve para actualizar sin volver a descargar el historial.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

falta() { echo "Falta $1: mira el paso 1 de docs/instalacion.md para tu sistema." >&2; exit 1; }

PY=""
# "py -3.x" es el lanzador de Windows sin WSL (Git Bash); allí python3 puede ser una 3.15 sin paquetes compilados
for c in python3.14 python3.13 python3.12 "py -3.14" "py -3.13" "py -3.12" python3; do
  if $c -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
[[ -n "$PY" ]] || falta "Python 3.12 o superior"
command -v node >/dev/null 2>&1 \
  && node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 20 || (a === 20 && b >= 9) ? 0 : 1)' \
  || falta "Node.js 20.9 o superior"
command -v npm >/dev/null 2>&1 || falta "npm"

echo "== Entorno de Python ($PY)"
[[ -d .venv ]] || $PY -m venv .venv
BIN=.venv/bin; [[ -d $BIN ]] || BIN=.venv/Scripts  # Windows
$BIN/python -m pip install -e ".[dev]"

echo "== Base de datos"
scripts/db.sh init
scripts/db.sh start
$BIN/alembic upgrade head

echo "== Panel web"
if [[ ! -f web/node_modules/.package-lock.json || web/package-lock.json -nt web/node_modules/.package-lock.json ]]; then
  npm --prefix web ci --no-audit --no-fund
fi

if [[ ! -f var/models/latest.json ]]; then
  echo "== Historial y modelos: la primera vez tarda alrededor de 1 hora. Si se corta, vuelve a ejecutar scripts/instalar.sh"
  # Arranque rápido: resultados y cuotas de todo el historial, pero el detalle de FotMob solo de los 1.500 partidos más
  # recientes; el resto lo baja el worker en segundo plano (scheduler.BACKFILL_PER_HOUR, unos 2-3 días)
  $BIN/apuestas ingest all --seasons 3 --backfill 1500
  $BIN/apuestas train
fi

echo
echo "Instalado. Siguiente paso:"
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  echo "  scripts/install-services.sh --with-web   (queda funcionando solo; panel en http://localhost:3000)"
else
  echo "  scripts/arrancar.sh   (deja la terminal abierta; panel en http://localhost:3000)"
fi
