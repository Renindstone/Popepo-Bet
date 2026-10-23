# Experimentos de la auditoría del modelo

Reproducen las cifras de [`docs/auditoria-modelo.md`](../../docs/auditoria-modelo.md) con datos públicos: 62.140 partidos de 14 ligas, de julio de 2013 a septiembre de 2026 (football-data.co.uk y ClubElo a través de [xgabora/Club-Football-Match-Data-2000-2025](https://github.com/xgabora/Club-Football-Match-Data-2000-2025), fijado al commit `25882a5`). No usan la base de datos del proyecto, así que se pueden correr en cualquier equipo con el `.venv` del repo.

Esos datos no traen xG, Pinnacle, cuota de cierre ni árbitro. Por eso el "repo con mercado" usa la cuota previa de bet365 de partidos ya jugados en lugar del cierre de Pinnacle, y sale un poco más débil que el de producción.

## Uso

```bash
experimentos/auditoria/preparar.sh   # pyarrow y lightgbm en el .venv del repo, y los datos en var/experimentos/auditoria
experimentos/auditoria/correr.sh     # los 11 pasos, entre 10 y 40 minutos según el equipo
```

Los resultados quedan en `var/experimentos/auditoria/data` (`*.json` con los resúmenes) y lo que imprime cada paso en `var/experimentos/auditoria/logs`. Nada de eso se sube a git.

## Qué mide cada script

| Paso | Script | Qué mide |
| --- | --- | --- |
| 1 | `exp_goals_static.py` | Modelo de goles del repo con y sin mercado, ventaja local por liga y nivel por liga, con reajuste semanal |
| 2 | `ekf_tune.py` | Hiperparámetros del modelo bayesiano dinámico (filtro de Kalman), elegidos en 2016-21 |
| 3 | `ekf_final.py` | Modelo dinámico final y su versión con observaciones del mercado |
| 4 | `ekf_sot.py` | Remates a puerta como observación extra de la fuerza |
| 5 | `exp_ml.py` | LightGBM con y sin cuotas, y apilado con el mercado |
| 6 | `exp_stats.py` | Córners, tarjetas, faltas y remates: independencia entre equipos, dispersión y media de la liga |
| 7 | `analyze_goals.py` | Tablas contra bet365, sesgo por liga, empates y simulación de apuestas |
| 8 | `analyze_stats.py` | Mejora sobre la media de la liga, colas y PIT |
| 9 | `summary2.py` | Diferencias pareadas con errores estándar y valor anunciado frente a real |
| 10 | `exp_conteos_nuevos.py` | Cambios del 21 y 22 de octubre en los conteos, con la cuota previa en vez del cierre, y un nivel de liga dinámico |
| 11 | `analyze_conteos.py` | Tablas del paso 10 |

Módulos de apoyo: `exp_common.py` (datos, métricas y modelo de fuerza ampliado), `ekf.py` (filtro bayesiano dinámico) y `ekf_eval.py`.

## Notas

- Las cifras de log-loss salen idénticas en Linux y en Mac. En la simulación de apuestas pueden cambiar unas pocas apuestas que quedan justo en el umbral de 3 % de valor, por el redondeo de cada máquina; LightGBM también varía un poco.
- Las ligas "completas" de estos experimentos son Premier, Bundesliga y LaLiga, como cuando se hizo la auditoría (la Serie A y la Ligue 1 pasaron a completas el 21-10-2026).
- Los pasos 1 a 9 se escribieron sobre el commit `e7f58aa`; el 10 usa el código actual de `models/fitting.py` (`fit_counts`, `strength_shift`).
