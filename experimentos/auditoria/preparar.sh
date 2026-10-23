#!/usr/bin/env bash
# Prepara los experimentos de la auditoría: librerías extra en el .venv del repo y datos de prueba en var/.
set -euo pipefail
cd "$(dirname "$0")/../.."          # raíz del repo

[ -x .venv/bin/python ] || { echo "Falta el .venv del repo: .venv/bin/pip install -e \".[dev]\" (docs/instalacion.md)"; exit 1; }
if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
  brew list libomp >/dev/null 2>&1 || brew install libomp   # LightGBM la necesita en Mac
fi
.venv/bin/pip install -r experimentos/auditoria/requirements.txt

# Datos de football-data y ClubElo (xgabora), en la misma versión que se usó en la auditoría
DATOS=var/experimentos/auditoria/data
mkdir -p "$DATOS" var/experimentos/auditoria/logs
if [ ! -d "$DATOS/xgabora/.git" ]; then
  git init -q "$DATOS/xgabora"
  git -C "$DATOS/xgabora" remote add origin https://github.com/xgabora/Club-Football-Match-Data-2000-2025
fi
git -C "$DATOS/xgabora" fetch -q --depth 1 origin 25882a58a736daf7ece3781940eac17ae1117a66
git -C "$DATOS/xgabora" checkout -q FETCH_HEAD

.venv/bin/python -c "import apuestas.models.fitting, lightgbm, pyarrow; print('Listo. Ahora: experimentos/auditoria/correr.sh')"
