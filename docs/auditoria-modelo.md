# Auditoría del modelo (octubre de 2026)

Revisión del modelo con datos reales y fuera de muestra, hecha entre el 19 y el 22 de octubre de 2026 sobre los commits `e7f58aa` y `960b1c5`. Los experimentos están en [`experimentos/auditoria/`](../experimentos/auditoria/) y se pueden repetir en cualquier equipo. Las cifras de esta página salen de ahí.

**Lo principal.** Ningún modelo probado, ni bayesiano ni de machine learning, le gana a la cuota previa de bet365 en 1X2. Lo que sí mejora con claridad es el modelo propio (fuerza dinámica, más observaciones, dispersión bien puesta), y eso pesa donde no hay cuota afilada. Lo único que dio retorno positivo fue comparar precios entre casas.

## Datos y método

- 62.140 partidos de las 14 ligas con estadísticas (julio de 2013 a septiembre de 2026), de football-data y ClubElo a través del conjunto público de xgabora. Cuota previa de bet365 (1X2, más/menos 2,5 y hándicap asiático), cuota máxima de unas 17 casas, remates, remates a puerta, córners, faltas, tarjetas y Elo.
- Sin xG, Pinnacle, cuota de cierre ni árbitro. La versión "con mercado" del modelo usa la cuota previa de bet365 de partidos ya jugados.
- Walk-forward con el código del repo (`ratings.fit`, `market.implied_goals`, `fitting.fit_counts`) y sus parámetros. Prueba en 2021-22 a 2025-26 (23.548 partidos); los hiperparámetros nuevos se eligieron en 2016-21.
- Log-loss como métrica principal, errores estándar con bootstrap por jornadas. En las tablas, "±" es un error estándar.

## Resultados del modelo de goles

| Qué se probó | Diferencia de log-loss por partido (negativo = mejor) |
| --- | --- |
| Repo con mercado frente a bet365 sin margen | +0,0069 ± 0,0006 (14 ligas), +0,0084 ± 0,0014 (3 completas) |
| Mezcla fija 25/75 (`W_MODEL`) frente a solo la cuota | +0,0008 ± 0,0001 |
| Apilado logístico aprendido frente a solo la cuota | −0,0001 ± 0,0002 (el peso del modelo sale casi cero) |
| Modelo bayesiano dinámico (filtro de Kalman) frente a `ratings.fit`, solo goles | −0,0047 ± 0,0007 en 1X2 y −0,0037 ± 0,0005 en más/menos 2,5; gana las 5 temporadas |
| Remates a puerta como observación extra del dinámico | −0,0015 ± 0,0003 en 1X2 y −0,0027 ± 0,0003 en más/menos |
| Ventaja local por liga frente a una sola para todas | LaLiga −0,0024 ± 0,0010, Segunda −0,0035 ± 0,0013, Serie A −0,0012 ± 0,0005, total −0,0004 ± 0,0002 |
| Capa de calibración logística sobre el 1X2 del repo | −0,0005 ± 0,0002 (corrige los empates de menos) |
| LightGBM sin cuotas frente al dinámico de solo goles | −0,0035 ± 0,0008, pero 0,012 detrás de bet365 |
| LightGBM con cuotas como entrada frente a solo la cuota | +0,0022 ± 0,0005 |

El modelo dinámico tiene ataque y defensa por equipo con un paseo aleatorio (varianza de 0,00001 por día y 0,01 extra en el parón de verano), y nivel de goles y ventaja local por liga que también se mueven. Se actualiza con la verosimilitud de Poisson de cada partido y da la varianza de cada predicción. Corre en 17 segundos para 62.000 partidos (`experimentos/auditoria/ekf.py`).

Otras cosas que se vieron. El repo con mercado se quedó corto en goles en 10 de 14 ligas (más de 2,5 en 51,0 % contra 52,1 % real). En los tramos medios de probabilidad de empate predice 25,9 % y 27,6 % y salieron 27,3 % y 29,3 %.

## Resultados de los conteos

**Los cambios del 21 y 22 de octubre funcionan.** Repetidos con la cuota *previa* de bet365 (el backtest del repo usa el cierre, que ya conoce las alineaciones), las mejoras por equipo son casi las mismas que dice `docs/modelos.md`.

| Cambio | Remates | A puerta | Córners | Faltas | Tarjetas |
| --- | --- | --- | --- | --- | --- |
| Contracción en partidos y fuerza del modelo de goles (21-10), por equipo | +0,0236 ± 0,0015 | +0,0205 ± 0,0013 | +0,0304 ± 0,0018 | +0,0165 ± 0,0015 | +0,0178 ± 0,0014 |
| Reparto por el 1X2 previo de la casa (22-10), por equipo | +0,0151 ± 0,0012 | +0,0100 ± 0,0009 | +0,0075 ± 0,0007 | no aplica | no aplica |
| Dispersión del total calibrada fuera de muestra, sobre el modelo actual | +0,0045 ± 0,0008 | −0,0003 ± 0,0003 | +0,0057 ± 0,0008 | +0,0039 ± 0,0006 | +0,0060 ± 0,0011 |
| Nivel de liga dinámico (45 días de errores fuera de muestra), por equipo | +0,0024 ± 0,0007 | −0,0005 ± 0,0007 | −0,0014 ± 0,0004 | +0,0060 ± 0,0009 | +0,0023 ± 0,0008 |

Log-verosimilitud por partido, positivo = mejor.

**Lo que sigue abierto.** El total se calcula como si los dos equipos fueran independientes (`MatchModel._stat_pmfs`, convolución). En los datos, los residuos del local y del visitante se correlacionan +0,22 en tarjetas, −0,23 en córners y −0,22 en remates. Por eso el total de tarjetas sale demasiado estrecho (una línea a la que el modelo da 20 % de "más" sale 23 % de las veces) y los hándicaps de córners y tarjetas están mal tarifados. Calibrar la dispersión del total arregla buena parte (fila 3).

**Tendencias de esta temporada.** En agosto y septiembre de 2026 se remata más y se ven menos tarjetas. El modelo de remates se queda 7,7 % corto en el total y el de tarjetas 16 % alto, con datos hasta el 3 de septiembre. Coincide con lo que ya anota `docs/estado.md`. La vida media de 240 días tarda en recogerlo; el nivel de liga dinámico ayuda en remates, faltas y tarjetas, pero al empezar la temporada necesita unas semanas de partidos.

**Córners y tarjetas ya aportan algo.** Comparando el total con la dispersión calibrada en los dos lados, el modelo de antes no le ganaba a la media de la liga en córners (−0,0058 ± 0,0019 por partido, 14 ligas) ni en tarjetas (−0,0020 ± 0,0020). El actual sí, con córners +0,0069 ± 0,0011 y tarjetas +0,0077 ± 0,0015 (en las 3 completas, +0,0117 y +0,0156). Sigue sin haber backtest contra cuotas de estadísticas, que es lo que decide si hay valor.

## Decisión de apostar

- Las apuestas que el modelo del repo marca con valor contra bet365 anunciaron +8,5 % de media y perdieron 7,5 % ± 1,4 % (8.845 apuestas). Por tramos de valor anunciado (3-6 %, 6-10 %, 10-20 %, más de 20 %) el retorno real fue −8,2 %, −10,6 %, −11,6 % y +1,5 % ± 7,5 %. El valor anunciado no predice la ganancia.
- La apuesta del día con las reglas de producción anunció +12,1 % y perdió 7,2 % ± 3,9 % (969 días). Elegir el máximo entre muchas candidatas selecciona errores del modelo.
- Comparar precios fue lo único positivo. Con la probabilidad del apilado (casi la del mercado) y la mejor de unas 17 casas, +6,1 % ± 2,6 % en 2.855 apuestas. Es lo que encontraron Kaunitz y otros (2017), que acabaron con las cuentas limitadas. La versión al alcance del proyecto es comparar Betano con Pinnacle sin margen, con lo que ya guarda OddsPapi.

## Fallos abiertos en el código (commit `960b1c5`)

| Fallo | Dónde | Arreglo |
| --- | --- | --- |
| El valor de las líneas de cuarto sale inflado entre 12 % y 16 %: solo descuenta la devolución completa | `services/analysis.py` línea 390 | Usar `Outcome.ev` con la probabilidad mezclada, que cuenta medias ganadas y perdidas |
| Doble oportunidad, empate no válido, ambos marcan y hándicap europeo usan solo el modelo | `analysis._sharp_prob` (línea 326) | Invertir 1X2 y más/menos de Pinnacle a una matriz y sacar de ahí todos los mercados de goles (rama local `claude/precio-afilado-mercados`) |
| La apuesta guardada se sobrescribe en cada recálculo, así que el contador de aciertos y el CLV miden la última versión y no lo que se anunció | `picks._upsert_pick` (línea 73), `qualified_picks` | Guardar una copia fija al publicar y medir también las retiradas |
| Mezcla fija con el mercado | `analysis.W_MODEL` (línea 24) | Apilado aprendido por tipo de mercado, entrenado con temporadas anteriores |
| Confianza como producto de factores a mano, multiplicada por el valor para elegir | `analysis._confidence`, `picks.score` | Probabilidad de que el valor sea positivo, con la varianza del modelo |
| Kelly con la probabilidad como si fuera exacta | `betting/odds.py` `stake_pct` | Contraer según la varianza (Baker y McHale, 2013) |
| La base de "frente a la media de la liga" es la media global | `backtest/engine.py` líneas 470 y 476 | Media de cada liga, local y visitante por separado |
| El conteo de cada equipo se suma como independiente | `match_model._stat_pmfs` (línea 108) | Total con dispersión calibrada y reparto beta-binomial, o binomial negativa bivariada |
| Una sola ventaja local para todas las ligas y copas | `models/ratings.py`, `home_adv` | Ventaja local por liga con contracción |
| Suplentes con 12 minutos promedio aunque la apuesta se anula si no juegan | `analysis.py` línea 274 | Mezcla de escenarios condicionada a que juegue |
| Contracción fija de 4 partidos en tasas por 90 y dispersión fija de 0,15 en remates del jugador | `analysis.py` línea 268, `match_model.py` línea 295 | Bayes empírico por estadística y posición |

## Qué implementar y en qué orden

1. **Arreglos sin riesgo.** Valor de las líneas de cuarto, copia fija de lo anunciado y base por liga en el backtest.
2. **Fuerza dinámica para goles.** El filtro de `experimentos/auditoria/ekf.py` como alternativa a `ratings.fit`, con goles, xG y remates a puerta como observaciones y el cierre de Pinnacle (o el de OddsPapi mientras football-data siga caído) como observación del mercado. Ventaja extra: no descarta el mercado a los 14 días, lo mantiene con incertidumbre creciente. Necesita `apuestas backtest` con la BD.
3. **Conteos.** Dispersión del total calibrada fuera de muestra en todos, y nivel de liga dinámico en remates, faltas y tarjetas (no en córners ni a puerta).
4. **Mercado y calibración.** Matriz de Pinnacle para todos los mercados de goles, apilado aprendido en vez de `W_MODEL` y una capa de calibración para los empates.
5. **Decisión.** Elegir por la probabilidad de valor positivo, contraer valor y Kelly con la varianza, y un comparador de Betano contra Pinnacle sin margen. Pedir una segunda foto de cuotas cerca del inicio solo para los partidos con apuesta, para tener CLV de Betano.
6. **Jugadores.** Modelo jerárquico con minutos como mezcla y contracción estimada de los datos.

Cada paso entra solo si mejora de forma pareada en una temporada guardada que no se use para ajustar.

## Referencias

- Koopman y Lit, modelo de Poisson bivariado dinámico para la Premier: https://ideas.repec.org/p/tin/wpaper/20120099.html
- Egidi, Pauli y Torelli (2018), datos históricos y cuotas en un modelo bayesiano jerárquico: https://arxiv.org/abs/1802.08848
- Ley, Van de Wiele y Van Eetvelde, comparación de modelos de máxima verosimilitud: https://arxiv.org/pdf/1705.09575
- Benz y López (2021), la ventaja local sin público cambió distinto en cada liga: https://arxiv.org/pdf/2012.14949
- Wheatcroft (2021), predecir partidos prediciendo sus estadísticas: https://ar5iv.arxiv.org/html/2001.09097
- Walsh y Joshi (2024), elegir modelos por calibración y no por acierto: https://researchportal.bath.ac.uk/en/publications/machine-learning-for-sports-betting-should-model-selection-be-bas/
- Baker y McHale (2013), Kelly bajo incertidumbre: https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html
- Kaunitz, Zhong y Kreiner (2017), comparar casas contra el consenso: https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/
