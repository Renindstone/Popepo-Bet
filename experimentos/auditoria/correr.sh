#!/usr/bin/env bash
# Corre los experimentos de la auditoría en orden. Resultados en var/experimentos/auditoria/data, registros en logs/.
set -euo pipefail
cd "$(dirname "$0")"
PY=../../.venv/bin/python
OUT=../../var/experimentos/auditoria
[ -d "$OUT/data/xgabora" ] || { echo "Primero corre experimentos/auditoria/preparar.sh"; exit 1; }
mkdir -p "$OUT/logs"

step() {
  local name="$1" log="$2"; shift 2
  echo
  echo "== $name"
  local t0=$SECONDS
  "$@" 2>&1 | tee "$log"
  echo "   ($(( (SECONDS - t0) / 60 )) min)"
}

step "1/11 Modelo del repo y variantes, walk-forward semanal 2016-26" "$OUT/logs/01_static.log" \
  $PY exp_goals_static.py 2016-07-01 2026-07-01
step "2/11 Hiperparámetros del modelo bayesiano dinámico (validación 2016-21)" "$OUT/data/ekf_tune.log" \
  $PY ekf_tune.py
step "3/11 Modelo dinámico final y versión con mercado" "$OUT/logs/03_ekf_final.log" $PY ekf_final.py
step "4/11 Remates a puerta como observación extra" "$OUT/logs/04_ekf_sot.log" $PY ekf_sot.py
step "5/11 LightGBM y apilado con el mercado" "$OUT/logs/05_ml.log" $PY exp_ml.py
step "6/11 Córners, tarjetas, faltas y remates (independencia y dispersión)" "$OUT/logs/06_stats.log" $PY exp_stats.py
step "7/11 Tablas de goles, resultado y apuestas" "$OUT/logs/07_analyze_goals.log" $PY analyze_goals.py
step "8/11 Tablas de estadísticas" "$OUT/logs/08_analyze_stats.log" $PY analyze_stats.py
step "9/11 Diferencias pareadas y valor anunciado frente a real" "$OUT/logs/09_summary.log" $PY summary2.py
step "10/11 Conteos del 21 y 22 de octubre con cuotas previas y nivel de liga dinámico" "$OUT/logs/10_conteos.log" \
  $PY exp_conteos_nuevos.py
step "11/11 Tablas de los conteos nuevos" "$OUT/logs/11_analyze_conteos.log" $PY analyze_conteos.py

echo
echo "Listo. Resúmenes en $OUT/data/*.json y registros en $OUT/logs/."
