# Modelos y validación

## 1. Fuerza de equipos (`models/ratings.py`)

Modelo multiplicativo tipo Poisson ajustado **a la vez para 17 ligas**:

```
log E[goles_local]     = mu + ventaja_local + ataque[local]     - defensa[visitante]
log E[goles_visitante] = mu                 + ataque[visitante] - defensa[local]
```

- **Objetivo**: 15 % goles + 85 % xG (el xG predice mejor que los goles; el peso se eligió con el backtest).
- **Ratings implícitos del mercado** (`models/market.py`): las cuotas de cierre de cada partido jugado (Pinnacle; si no hay, bet365), sin margen, se invierten a goles esperados (local, visitante): las dos medias cuya matriz Dixon-Coles reproduce el 1X2 y el más/menos 2.5. Entran en el ajuste como observaciones extra con **peso 128** y **vida media de 14 días** (`MARKET_WEIGHT`, `MARKET_HALF_LIFE`). No cuentan como partidos jugados ni para la sobredispersión. Cubren unos 14.000 partidos de las 14 ligas con cuotas (las copas europeas no tienen). En la práctica el rating sigue a la opinión reciente del mercado, y los goles/xG reales mandan solo cuando faltan cuotas recientes (por ejemplo, al empezar la temporada).
- **Antigüedad**: vida media de 240 días (probados 120, 240 y 400).
- **Regularización L2**: los equipos con pocos partidos (ascendidos, rivales exóticos de Champions) se acercan a la media.
- **Escala común**: los partidos de Champions/Europa y los ascensos/descensos (Championship, 2. Bundesliga, Segunda) conectan las ligas. Así un ascendido o un rival portugués de Champions tienen un rating comparable.
- **Fichajes**: el ajuste por alineación (abajo) usa el valor de mercado y el rating de cada jugador. Un fichaje entra en la alineación con su calidad, aunque el equipo aún tenga pocos partidos con él. Los fichajes se detectan cuando un jugador aparece con otro equipo (tabla `transfer`).

## 2. Goles y mercados (`models/distributions.py`, `services/match_model.py`)

Matriz de marcadores **Dixon-Coles**, con ρ estimado sobre los datos. De ahí salen 1X2, doble oportunidad, empate no válido, hándicap asiático (incluidas las líneas de cuarto, con medias ganadas o perdidas), hándicap europeo, más/menos goles (total y por equipo) y ambos marcan.

## 3. Estadísticas: remates, a puerta, córners, faltas y tarjetas

Mismo modelo de fuerza aplicado a cada estadística (cuánto genera cada equipo y cuánto concede), con distribución **binomial negativa** (la sobredispersión se estima de los datos). Los totales del partido salen de la convolución de ambos equipos.

- **Contracción hacia la media en "partidos equivalentes"** (desde el 21-10-2026, `fitting.COUNT_PRIOR_MATCHES`): remates y remates a puerta 1, córners 5, faltas 5 y tarjetas 10. Un equipo con n partidos (ponderados por antigüedad) conserva más o menos n / (n + K) de lo que se ve en ellos; los de liga (25-45 partidos) apenas cambian. Antes era una L2 fija de 1, la misma que en goles. Pero cada partido pesa en el ajuste tanto como su media (~1,4 goles, ~5 córners, ~12 remates), así que esa L2 casi no contraía: equivalía a 0,1 partidos en remates y faltas, 0,2 en córners y 0,5 en tarjetas.

  Caso real: **Aston Villa-Viking** (Champions, 21-10-2026). Viking es noruego. La liga noruega no entra en el modelo y football-data no trae sus córners, así que solo había dos partidos suyos con estadísticas: 5 córners en Stuttgart y 7 contra el Bayern. Con ellos su ataque en córners salía ×1,8 la media. El modelo esperaba 14,7 córners (Villa 9,1, Viking 5,6) frente a 10,5 de Pinnacle (7,4 y 3,0), y en Hoy salían "Córners: Más de 16.5" a 10,00 con +232 % y "Córners de Viking: Más de 6.5" a 9,75 con +230 %. Con la contracción, 11,3 (7,0 y 4,3); el resto lo corrige la regla de prudencia de la sección 6.

- **Remates, remates a puerta y córners guiados por la fuerza del modelo de goles** (desde el 21-10-2026, `fitting.COUNT_STRENGTH_PRIOR`). En estas tres estadísticas, que dependen de cuánto domina cada equipo, la fuerza de un equipo es `b × fuerza_goles + desviación`, con `fuerza_goles` = ataque + defensa en el modelo de goles, `b` ajustado (uno para generar y otro para conceder) y la contracción solo en la desviación. Así, un equipo con pocos datos se acerca a lo que corresponde a su fuerza y no a la media, y la contracción es mayor: K = 8 en remates y a puerta, y 20 en córners. En tarjetas y faltas no mejora (se quedan como estaban).

  Motivo: hasta el 21-10-2026 las ligas solo se cruzaban en estas estadísticas por la Champions (de la Europa League y la Conference solo se bajaban los resultados): unos 14 partidos ponderados para la Eredivisie, 11 para la liga belga y 2 para la escocesa. Dentro de una liga, solo se sabe cuánto domina cada equipo a sus rivales; el nivel de toda la liga frente a las demás lo fijaba la contracción, que suponía todas las ligas igual de fuertes. Por eso un equipo que domina una liga floja salía igual de dominante en la Champions. El modelo de goles, en cambio, sí conoce bien la fuerza de cada liga: tiene las cuotas de cierre y todos los partidos europeos.

  Caso real: **Betis-Feyenoord** (Champions, 21-10-2026). El análisis daba 4,3 córners al Betis y 5,6 al Feyenoord; Pinnacle, 5,3 y 4,1. "Córners de Feyenoord: Más de 7.5" a 9,00 salía con +108 % y las cuatro primeras "Otras apuestas con valor" de Hoy eran córners del Feyenoord. Ahora 4,9 y 4,9, y esa cuota da +41 % (la primera de Hoy es otra). Sigue lejos de Pinnacle: es mejor, pero no lo arregla del todo (ver backtest, sección 7).

- **Europa League y Conference** (desde el 21-10-2026): sus estadísticas de FotMob entran en los cinco modelos de conteo. Son unos 1.020 partidos desde 2023-24, y casi duplican los cruces entre ligas: la Eredivisie pasa de 13 a 27 partidos ponderados, la belga de 10 a 18, la griega de 4 a 17 y la escocesa de 1 a 10. Su xG, en cambio, **no entra en el modelo de goles** (`fitting.GOALS_XG_SKIP`): con él empeoraba la Champions. Detalle en la sección 7.

- **El 1X2 de la casa mueve el reparto de remates, a puerta y córners** (desde el 22-10-2026, `fitting.COUNT_MARKET_SHIFT` y `fitting.strength_shift`). Esas tres estadísticas se guían por la fuerza del modelo de goles (punto anterior), así que heredan sus errores, y el modelo de goles no le gana al mercado. Si la casa ve a un equipo más fuerte que el modelo, el reparto de esas estadísticas se mueve hacia ella:
  1. Con el 1X2 y el más/menos 2.5 de Pinnacle (si no hay, de bet365; si tampoco, de Betano) se sacan los goles esperados de la casa (`fitting.prematch_market_goals`).
  2. δ = ½ × [log(local / visitante) de la casa − log(local / visitante) del modelo de goles], este último ya con las alineaciones, para no contar dos veces las bajas que la casa también conoce. Es la fuerza que hay que sumar al local y restar al visitante para que el modelo de goles diga lo mismo que la casa.
  3. El conteo del local se multiplica por exp(0,75 × b × δ) y el del visitante se divide por lo mismo, con b el coeficiente de la fuerza en ese conteo (ataque + defensa, guardado en el paquete de modelos: ~0,6 en córners y remates, ~0,73 a puerta). Después se reparte de nuevo para que **el total del partido no cambie**: el 1X2 dice quién domina, no cuánto se juega.

  Sin cuotas de esas casas, todo queda como antes. El análisis guarda la casa y δ en `count_market_shift`. El peso 0,75 es casi el mejor en las tres estadísticas (sección 7).

  Caso real: **Betis-Feyenoord** (Champions, 21-10-2026). El modelo de goles veía a los dos casi igual de fuertes (1X2 46/22/32); Pinnacle, al Betis claro favorito (60/20/20; δ = 0,18). Los córners salían 4,6-4,7 (Pinnacle 5,3-4,1); ahora 5,0-4,3. En el análisis real, con las alineaciones, de 4,7-4,7 a 5,1-4,4, y la mejor cuota de córners "con valor" del partido pasa de +30 % a +10 %.

- **Nivel reciente de cada liga en remates y remates a puerta** (desde el 22-10-2026, `fitting.count_levels` y `COUNT_LEVEL_*`). El modelo de conteo recuerda 1.100 días con vida media de 240, así que tarda meses en notar que **toda una liga** cambia. Y en 2026-27 pasó: se remata un 10-20 % más en casi todas las ligas, y el modelo se quedaba corto (sección 7). Sobre el modelo ajustado como siempre, se añade un nivel por liga:
  1. En los partidos de cada liga de los últimos 400 días, con vida media de **30 días**: nivel = (real + K·g·m) / (esperado + K·m), con m el total de un partido medio, **K = 10 partidos** y g el mismo cociente con todas las competiciones juntas (cada liga se contrae hacia lo que pasa en todas).
  2. Cada equipo toma el nivel de su liga (la de su último partido de liga); un rival europeo sin liga en los datos toma g. En un partido de liga se aplica el de esa liga a los dos equipos; en una copa, la media de los de las dos ligas.
  3. En las copas se suma además un **desvío propio de la copa**, medido sobre lo esperado ya con el nivel de las ligas, con vida media de **120 días** y **K = 30**: en la Champions el modelo se quedaba corto en los remates a puerta en las tres últimas temporadas (4 %, 8 % y 17 %), más que en las ligas de sus equipos.

  El nivel no cambia la fuerza de ningún equipo (ataque y defensa son los mismos) ni el reparto entre los dos: sube o baja el total, y los remates de jugador, que reparten lo del equipo (sección 4), lo heredan. Se guarda en el paquete de modelos (`level` por equipo y `cup_level` por copa) y el análisis lo aplica con la competición del partido. En **córners** se probó y empeora un poco (no hay un cambio común a todas las ligas: Bundesliga +10 %, Premier −6 %); en faltas no se ha validado, y las tarjetas lo llevan con sus propios parámetros (abajo). Niveles al 22-10-2026 en remates: Bundesliga ×1,12, Serie A ×1,10, LaLiga ×1,07, Ligue 1 ×1,06, Premier ×1,05; a puerta: ×1,12, ×1,11, ×1,07, ×1,06 y ×0,99; desvío de la Champions en a puerta, ×1,03.

  Caso real (análisis del 22-10-2026, partidos del fin de semana): **Stuttgart-Gladbach**, remates 19,7-10,2 → 22,0-11,4 y a puerta 8,1-3,3 → 9,0-3,7, y Demirović de 3,08 a 3,44 remates; **Torino-Monza**, 13,7-11,7 → 15,0-12,8; **Ipswich-Nottingham Forest**, 11,9-14,4 → 12,5-15,1 (a puerta igual: en la Premier no sube). Los córners no cambian.

- **Árbitro**: factor = (observado + K) / (esperado + K), con K en partidos "neutros". En **faltas** mejora la predicción (K = 20). En **tarjetas**, medido de nuevo con los árbitros de LaLiga y la Bundesliga (FotMob), K = 80. Ayuda claramente en LaLiga y en la Serie A, y algo en la Bundesliga; en la Premier no ayuda. En la Ligue 1 ayuda sobre todo en las faltas (ver backtest).
- **Nivel reciente de cada liga en tarjetas** (desde el 22-10-2026; el mismo `fitting.count_levels`, con `COUNT_LEVEL_PARAMS["cards"]`). Las tarjetas por equipo bajan de temporada en temporada en casi todas las ligas (Serie A, primera vuelta: 2,29 en 2023-24, 2,05, 2,01 y 1,68 en 2026-27; Bundesliga 2,07 → 1,75; Ligue 1 2,08 → 1,69), y el modelo de tarjetas, con 240 días de vida media, va por detrás: se pasaba un 5 % en las ligas (Serie A +8 %, Champions +8 %). Llevan el nivel de los remates con dos cambios: **K = 20** partidos (en vez de 10) y, en las copas, **solo el nivel de la copa** (`cup_alone`; 120 días y K = 30), sin la media de las ligas de los dos equipos: en tarjetas la Champions va por su cuenta (en las eliminatorias se ven muchas menos), y con esa media empeoraba. El factor del árbitro se ajusta frente al modelo sin el nivel (`expected(..., level=False)`): el nivel de hoy no vale para partidos de hace años, y de media el factor vale 1,00 en cada liga. El análisis guarda el nivel del partido en `data_quality.cards_level`. Al 22-10-2026: Serie A ×0,93, Bundesliga ×0,93, Ligue 1 ×0,95, LaLiga ×1,02, Premier ×1,03 y Champions ×0,93. Cifras en la sección 7.
- **Alineación**: un once más fuerte de lo habitual genera más remates y córners (efecto atenuado, exponente 0,7).

## 4. Jugadores (`services/analysis.py::_player_projections`)

Tasas por 90' ponderadas por antigüedad (remates, a puerta, goles, xG, asistencias, xA, faltas, amarillas), **contraídas hacia la media de su posición** (equivalente a 4 partidos). Minutos esperados según la alineación: confirmado titular, previsto (85 %), suplente o, si el partido aún no tiene alineación, sus minutos en los últimos partidos de su equipo (abajo, "Minutos sin alineación"). Goles, asistencias, remates, a puerta y tarjetas se reparten a partir de lo que se espera de su equipo en ese partido (abajo); las faltas salen de su tasa por 90' y sus minutos.

**Goles y asistencias: parte de los goles del equipo** (desde el 20-10-2026). Para cada jugador se calcula qué parte de los goles de su equipo marca, asiste, y su xG y xA, **en los minutos que jugó** (goles del equipo × minutos/90 como exposición), contraída hacia la de su posición con unos 6 goles de equipo de peso. Goles esperados del jugador = (½ parte de goles + ½ parte de xG) × minutos esperados/90 × goles esperados de su equipo en ese partido; igual con asistencias y xA. "Gol o asistencia" suma las dos (un jugador no se asiste a sí mismo).

Antes se usaban las tasas por 90' escaladas contra la media del equipo "frente a un rival promedio". Ese rival promedio sale de todas las ligas de la BD, incluidas las de segunda y las ligas ligeras, y por eso infla la media de los equipos de las ligas grandes: sus goles reales fueron el 78 % (Premier), 91 % (Bundesliga) y 90 % (LaLiga) de esa media. Los goles de jugador salían bajos en todos los equipos. Comprobación fuera de muestra (modelo entrenado antes del periodo, Premier, Bundesliga, LaLiga y Champions):

| Periodo | Mercado | Esperado antes | Esperado ahora | Real | Log-loss antes → ahora |
|---|---|---|---|---|---|
| 90 días (10.969 jugadores-partido) | Gol | 578 | 712 | 731 | 0,2012 → 0,1981 |
| | Asistencia | 427 | 531 | 550 | 0,1759 → 0,1732 |
| | Gol o asistencia | 957 | 1.170 | 1.190 | 0,2840 → 0,2788 |
| 45 días (7.618) | Gol | 390 | 482 | 530 | 0,2098 → 0,2062 |
| | Gol o asistencia | 647 | 793 | 869 | 0,2996 → 0,2929 |

En los últimos 45 días aún se queda un 9 % corto (en 90 días, un 2-3 %). La misma comprobación con la Serie A y la Ligue 1 está en la sección 7 ("Serie A y Ligue 1 como ligas completas"). **Ningún mercado de jugador tiene backtest contra cuotas**: esta comprobación mide que las probabilidades estén bien calibradas, no que ganen a las casas.

**Remates, a puerta y tarjetas: parte de los del equipo** (desde el 22-10-2026, `fitting.VOLUME_SHARE_STATS`). Igual que los goles: para cada jugador se calcula qué parte de los remates, de los remates a puerta y de las tarjetas (amarillas + rojas, como en el modelo de tarjetas) de su equipo hace **en los minutos que jugó**, contraída hacia la de su posición con el peso de 4 partidos de su equipo (unos 51 remates o 18 a puerta; en tarjetas, 20 partidos, unas 40 tarjetas, desde el 22-10-2026: ver «Tarjeta al jugador» abajo). Remates esperados del jugador = parte × minutos esperados/90 × remates esperados de su equipo en ese partido (con alineaciones, árbitro y 1X2 de la casa, sección 3); igual con a puerta y tarjetas. La suma de los jugadores de un equipo es así el total que espera el modelo del equipo.

Antes era la tasa por 90' × minutos × (remates esperados del equipo en el partido / su media "frente a un rival promedio"), el mismo factor que dejaba cortos los goles hasta el 20-10: vale de media 0,82, y los remates de jugador salían un 15 % cortos en todas las ligas (sección 7, "Serie A y Ligue 1 como ligas completas"). Un detalle de los datos: FotMob deja **vacío, no 0**, el remate de quien no remató (en los porteros, el 99,8 % de las filas); al calcular la parte cuenta como 0, como ya hacían las tasas por 90'. Si no, la parte sale inflada (los jugadores sumaban 1,6 veces el equipo).

Comprobación fuera de muestra con las seis competiciones (modelo entrenado hasta el día de corte, partidos con once confirmado de los 90 días siguientes; medias del equipo del modelo de conteo con el factor del árbitro; esperado / real):

| Corte (jugadores-partido) | Mercado | Antes | Ahora | Log-loss antes → ahora |
|---|---|---|---|---|
| 15-01-2026 (27.220) | Remates | 0,85 | **1,00** | Más de 1.5: 0,3125 → 0,3032 · más de 2.5: 0,1811 → 0,1747 |
| | Remates a puerta | 0,86 | **1,01** | Más de 0.5: 0,3469 → 0,3435 |
| | Tarjeta (sí) | 0,95 | 0,97 | 0,2749 → 0,2742 |
| | Gol / asistencia | 0,99 / 1,00 | igual | igual (0,1853 en el gol) |
| 23-07-2026 (16.463) | Remates | 0,79 | 0,92 | Más de 1.5: 0,3408 → 0,3291 · más de 2.5: 0,2098 → 0,2024 |
| | Remates a puerta | 0,79 | 0,93 | Más de 0.5: 0,3630 → 0,3589 |
| | Tarjeta (sí) | 0,97 | 1,02 | 0,2661 → 0,2658 |
| | Gol / asistencia | 0,98 / 0,97 | igual | igual (0,1953 en el gol) |

Por competición (remates · a puerta · tarjeta, esperado / real antes → ahora):

| Liga | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier | 0,78 → 1,00 · 0,84 → 1,07 · 0,94 → 0,95 | 0,75 → 0,96 · 0,83 → 1,05 · 0,91 → 0,93 |
| Bundesliga | 0,86 → 1,00 · 0,85 → 0,98 · 0,91 → 0,94 | 0,73 → 0,83 · 0,74 → 0,86 · 0,99 → 1,03 |
| LaLiga | 0,85 → 0,99 · 0,85 → 0,98 · 0,90 → 0,90 | 0,84 → 0,96 · 0,83 → 0,95 · 0,94 → 0,97 |
| Serie A | 0,88 → 1,01 · 0,92 → 1,04 · 1,01 → 1,05 | 0,80 → 0,89 · 0,81 → 0,88 · 1,03 → 1,10 |
| Ligue 1 | 0,90 → 1,00 · 0,93 → 1,05 · 0,93 → 0,94 | 0,83 → 0,91 · 0,80 → 0,90 · 1,03 → 1,06 |
| Champions | 0,79 → 0,98 · 0,73 → 0,93 · 1,04 → 1,06 | 0,77 → 0,94 · 0,73 → 0,90 · 1,03 → 1,07 |

- **El reparto entre jugadores queda bien en las dos fechas.** Escalando lo de cada jugador al total real de su equipo (para medir solo el reparto), los remates pasan de 0,86 a 1,01 (enero) y de 0,88 a 1,02 (julio), y todas las ligas quedan entre 0,99 y 1,04; a puerta, de 0,86 a 1,01 y de 0,89 a 1,03.
- **Lo que falta en julio es del modelo de remates del equipo**, no del jugador: esperaba 12,8 remates por equipo y hubo 14,2. En la temporada 2026-27 se remata un 10-20 % más en todas las ligas (por equipo, Bundesliga 13,0 → 15,5, Serie A 12,4 → 14,6, Premier 12,7 → 13,9; football-data y FotMob dan lo mismo) y el modelo, con 240 días de vida media, aún no lo recogía. Afecta igual a los mercados de remates del equipo. Desde el 22-10-2026 el modelo de remates lleva el nivel reciente de cada liga (sección 3), y como el paquete de modelos se reajusta cada día, los remates de jugador lo heredan. Este corte de julio no lo puede ver (el modelo queda fijo 91 días, sin la temporada nueva); el walk-forward semanal de la sección 7 sí: en octubre de 2026, 14,1 remates esperados por equipo frente a 14,3 reales.
- **Tarjetas**: el reparto ya estaba casi bien (el factor del rival promedio en tarjetas apenas se alejaba de 1); lo nuevo mejora un poco la log-loss. Lo que quedaba por liga (Serie A alta, LaLiga baja en enero) venía del modelo de tarjetas del equipo y de cómo se pasaba de λ a probabilidad: corregido el 22-10-2026 (abajo, "Tarjeta al jugador").
- **Alternativa probada**: dividir entre la media real reciente del equipo (vida media 200 días) en lugar de la del rival promedio. El reparto también queda bien (1,00 y 1,01), pero la log-loss es algo peor en enero (más de 2.5 remates: 0,1756 frente a 0,1747) y en la Champions se queda corta (0,92 frente a 0,98); en julio, empate. Se eligió la parte del equipo: es el mismo método que los goles y sigue bien a un jugador que cambia de equipo.

Caso real (22-10-2026, alineaciones probables): **Arsenal-Everton**, Saka pasa de 1,79 a 2,69 remates esperados ("Más de 1.5 remates" de 51 % a 70 %) y Havertz de 1,29 a 2,07; **Aston Villa-Manchester City**, Haaland de 2,54 a 2,97 (67 % → 74 %). Con la alineación probable (solo 11 titulares, sin banquillo) la suma de los listados no llega al total del equipo: falta lo de los suplentes, que no están en la lista.

El paquete de modelos guarda la parte de cada jugador (`volume_share` y su exposición `volume_team90`; el archivo pasa de 1,8 a 2,4 MB). Entra al reentrenar (tarea diaria de resultados o `apuestas train`); con un paquete anterior se usa la fórmula de antes. Medición: `medir_jugadores.py` en las notas de la sesión del 22-10-2026 (no está en el repositorio).

**Minutos sin alineación** (desde el 22-10-2026, `fitting.recent_minutes` y `analysis._minutes_without_lineup`). Días antes del partido no hay ninguna alineación, ni probable. Antes entraban todos los jugadores del equipo con al menos 2 titularidades, con probabilidad de ser titular = titularidades / partidos que jugó (como mucho 0,9) y sin suplentes. Esa frecuencia no cuenta los partidos en que el jugador no jugó: el que juega uno de cada dos partidos, pero siempre de titular, salía casi seguro titular, igual que el que se fue cedido a una liga sin datos o lleva meses sin jugar. Los minutos de un equipo sumaban 1.300-1.400 en lugar de los 988 que juega de verdad (11 titulares de ~82' y 4,5 suplentes de ~20', media de 2025-26), y los goles, remates y tarjetas de sus jugadores, un 20-35 % más que lo que el modelo espera del equipo.

Ahora los minutos esperados de cada jugador son su media en los **últimos 8 partidos de su equipo** con datos de jugadores (`RECENT_TEAM_MATCHES`), con 0 en los que no jugó, y contando solo desde su primer partido con ese equipo: un fichaje que lleva 3 partidos de titular tiene ~90', no 3 × 90 / 8. La probabilidad de ser titular es la misma frecuencia con las titularidades (como mucho 0,9). Después se escalan para que el equipo sume 988 minutos (`TEAM_MINUTES`): los de los lesionados o sancionados se reparten entre el resto, sin pasar de lo que juega cada uno cuando es titular. Con alineación probable o confirmada no cambia nada.

Comprobación fuera de muestra: modelos reentrenados cada 7 días con los datos anteriores (en producción, cada día) y partidos con once confirmado de los 90 días siguientes, simulando que aún no tenían alineación. Sin lista de bajas (solo se guarda desde el 19-10-2026; la de hoy en partidos de enero sería ruido). Lo real son todos los jugadores del equipo en el partido: los que no salen en la proyección cuentan con 0 esperado. Quedan fuera 16 equipo-partidos de julio de equipos sin ningún dato de jugadores (recién ascendidos y debutantes en la Champions, como Coventry, Schalke, Viking o Feyenoord), que no tienen jugadores ni antes ni ahora.

| Corte | | Antes | Ahora | Con once confirmado |
|---|---|---|---|---|
| 15-01-2026 (643 partidos, 37.380 jugadores-partido) | Minutos por equipo | 1.401 | 983 | 1.025 |
| | Jugadores / equipo: goles · remates · tarjetas | 1,28 · 1,31 · 1,35 | **0,99 · 0,99 · 0,94** | 1,01 · 1,01 · 0,98 |
| | Esperado / real: goles · asistencias · remates · amarillas | 1,29 · 1,32 · 1,30 · 1,45 | **0,99 · 0,99 · 0,98 · 1,01** | 1,01 · 1,02 · 1,00 · 1,05 |
| | Log-loss: gol · asistencia · más de 1.5 remates · tarjeta | 0,1608 · 0,1301 · 0,2996 · 0,2439 | **0,1480 · 0,1225 · 0,2689 · 0,2247** | 0,1349 · 0,1143 · 0,2201 · 0,2008 |
| 23-07-2026 (386 partidos, 22.619 jugadores-partido) | Minutos por equipo | 1.303 | 982 | 1.027 |
| | Jugadores / equipo: goles · remates · tarjetas | 1,20 · 1,22 · 1,26 | **0,99 · 0,99 · 0,95** | 1,01 · 1,02 · 0,99 |
| | Esperado / real: goles · asistencias · remates · amarillas | 1,14 · 1,11 · 1,11 · 1,40 | **0,93 · 0,88 · 0,89 · 1,06** | 0,95 · 0,92 · 0,92 · 1,10 |
| | Log-loss: gol · asistencia · más de 1.5 remates · tarjeta | 0,1861 · 0,1529 · 0,3751 · 0,2565 | **0,1677 · 0,1400 · 0,3255 · 0,2300** | 0,1429 · 0,1240 · 0,2411 · 0,1938 |

Por competición (minutos antes → ahora · goles de los jugadores / del equipo · esperado / real de goles y de remates, entre paréntesis con once confirmado):

| Liga | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier | 1.384 → 984 · 1,27 → 0,99 · goles 1,47 → 1,13 (1,18) · remates 1,27 → 0,97 (1,00) | 1.298 → 983 · 1,23 → 0,99 · 1,31 → 1,04 (1,07) · 1,18 → 0,93 (0,95) |
| Bundesliga | 1.370 → 982 · 1,24 → 0,97 · 1,23 → 0,97 (0,98) · 1,27 → 0,98 (1,00) | 1.226 → 982 · 1,12 → 0,98 · 1,05 → 0,90 (0,90) · 0,99 → 0,84 (0,84) |
| LaLiga | 1.409 → 983 · 1,29 → 1,01 · 1,20 → 0,96 (0,97) · 1,26 → 0,98 (1,00) | 1.351 → 983 · 1,20 → 0,97 · 1,16 → 0,92 (0,96) · 1,17 → 0,92 (0,96) |
| Serie A | 1.443 → 983 · 1,34 → 1,00 · 1,32 → 0,97 (1,00) · 1,38 → 1,00 (1,02) | 1.362 → 982 · 1,27 → 1,01 · 1,16 → 0,91 (0,94) · 1,12 → 0,87 (0,91) |
| Ligue 1 | 1.474 → 983 · 1,35 → 0,99 · 1,43 → 1,05 (1,06) · 1,38 → 1,00 (1,01) | 1.352 → 982 · 1,24 → 1,00 · 1,25 → 1,00 (1,01) · 1,15 → 0,92 (0,94) |
| Champions | 1.285 → 984 · 1,18 → 0,97 · 1,09 → 0,88 (0,90) · 1,20 → 0,96 (0,98) | 1.128 → 984 · 1,04 → 0,98 · 0,85 → 0,77 (0,80) · 0,97 → 0,88 (0,92) |

- **Sin alineación queda casi igual que con el once confirmado** en la suma (0,97-1,01 del equipo en goles y remates, en todas las ligas) y en la calibración: lo que aún se separa de lo real (la Premier alta en goles en enero, la Champions y julio cortos) se separa igual con el once confirmado, así que viene de los modelos del equipo (en julio, los remates de la temporada 2026-27, arriba), no de los minutos. La log-loss baja en todos los mercados y en los dos cortes; también contando solo los jugadores que salen en las dos versiones (gol 0,2173 → 0,2158 y 0,2185 → 0,2158; más de 0.5 remates 0,5829 → 0,5692 y 0,5894 → 0,5656). Con once confirmado sigue siendo bastante mejor: saber quién juega vale mucho.
- **Tarjetas, 0,94-0,95 del equipo**, como con once confirmado (0,98): el modelo de tarjetas del equipo cuenta las rojas, y la parte del jugador, solo sus amarillas. (Desde «Tarjeta al jugador», abajo, la parte cuenta también la roja y los suplentes, unos minutos más.)
- **Ventana**: 4, 6, 8, 12 y 20 partidos dan casi lo mismo (log-loss del gol 0,1496 / 0,1483 / 0,1480 / 0,1484 / 0,1489 en enero y 0,1668 / 0,1672 / 0,1677 / 0,1682 / 0,1691 en julio); 8 es la mejor o casi en los dos cortes y es la misma ventana que el once típico (sección 5).
- **Bajas**: sin histórico de bajas no se puede medir el reparto de los minutos de un lesionado con las bajas reales. Haciendo de baja a los que venían jugando y no estaban en la convocatoria (más de lo que se sabe antes del partido), la suma sigue en 986 y 979 minutos y los goles en 1,00 y 0,98 del equipo; saber las bajas baja la log-loss del gol de 0,1480 a 0,1414 en enero (con la regla de antes, de 0,1608 a 0,1523, con 1.218 minutos).
- **Limitación**: un jugador que vuelve de una lesión larga tarda unos partidos en recuperar sus minutos (el 22-10, Rubén Vargas sale con 5' en Sevilla-Osasuna tras 2 partidos en 8; antes, 59'), y un fichaje no aparece en su equipo nuevo hasta que juega con él.

Caso real (26-28 de octubre, aún sin alineaciones; goles de los jugadores frente a los del equipo): Torino 1,42 → 1,08 (equipo 1,08), Sevilla 1,85 → 1,35 (1,53), Sassuolo 1,77 → 1,44 (1,35). En el Lazio, Pinamonti baja de 61' a 25' (22 % → 10 % de marcar) y Frattesi sube de 27' a 80'. El paquete de modelos guarda `recent_minutes` y `recent_start_rate` de cada jugador; entra al reentrenar, y con un paquete anterior se usa la regla de antes. Medición: `medir_minutos.py` en las notas de la sesión del 22-10-2026 (no está en el repositorio).

**Tarjeta al jugador** (desde el 22-10-2026). Dos fallos que se compensaban en el total, pero no por liga: la probabilidad salía un ~7 % baja y el modelo de tarjetas del equipo se pasaba un 4-8 % (Serie A +12-17 %). Al corregir la probabilidad apareció lo que esa compensación tapaba: la parte de cada jugador salía demasiado dispersa y daba de más a los titulares y de menos a los suplentes. Cambios, medidos juntos:

1. **Probabilidad = λ** (con tope de 0,95; `MatchModel._player_outcome`), no 1 − e^(−λ). FotMob registra como mucho una amarilla por jugador y partido (la segunda cuenta como roja: `player_match_stats.yellow_cards` es siempre 0 o 1), así que la parte de cada jugador ya mide la probabilidad de ver tarjeta por cada tarjeta que se espera de su equipo. Con 1 − e^(−λ), como si pudiera ver varias, salía un ~7 % baja.
2. **Cuenta si vio tarjeta, amarilla o roja** (`fitting._player_volume`), igual que se liquida «Tarjeta al jugador» (`betting/settlement.py`, que ya daba ganada la apuesta con una roja directa). Antes la parte solo contaba amarillas: las 658 rojas directas de la BD no contaban. La doble amarilla cuenta una vez.
3. **Más contracción hacia su posición en tarjetas**: 20 partidos de su equipo (unas 40 tarjetas) en vez de 4 (`analysis.VOLUME_SHARE_PRIOR_MATCHES`). Con 4, los titulares con menos del 5 % de probabilidad veían tarjeta un 55 % más de lo esperado y los de más del 30 %, un 35-40 % menos. Con 20 y 40 la log-loss es casi igual (diferencias de 0,0001) y mejor que con 10; se eligió 20, la mejor en julio.
4. **Los suplentes cuentan con 20 minutos más** en tarjetas (`fitting.CARD_SUB_EXTRA_MINUTES`), al ajustar su parte y en el partido (si sale, el 55 % de las veces). Por minuto, un suplente ve 1,7-2,3 veces más tarjetas que un titular de su posición (2023-26: entra al final, cuando hay más tarjetas, y juega el descuento); con 15 minutos más quedan a la par los defensas, con 20 los medios y con 25 los delanteros. Sin esto, la parte de los titulares sale inflada: con los otros tres cambios, sus tarjetas esperadas eran 1,07 (enero) y 1,11 (julio) de las reales.
5. **Nivel reciente de cada liga en tarjetas** en el modelo del equipo (sección 3).

Comprobación fuera de muestra con las seis competiciones: modelo entrenado hasta el corte y **reentrenado cada semana** durante los 90 días siguientes (en producción se reentrena a diario, y así el nivel de cada competición se va poniendo al día), partidos con once confirmado. «Titulares» son los del once confirmado, lo que se suele apostar; «todos» incluye a los suplentes, y el que no sale cuenta como que no vio tarjeta (al liquidar, se anula). Esperado / real, con lo real = vio amarilla o roja:

| Corte | Grupo | Antes | Ahora | Log-loss antes → ahora |
|---|---|---|---|---|
| 15-01-2026 | Titulares (14.146) | 0,965 | **0,995** | 0,4166 → **0,4112** |
| | Todos (27.220) | 0,935 | 1,046 | 0,2805 → **0,2774** |
| | Tarjetas del equipo (1.286) | 1,038 | **1,011** | −1,6305 → **−1,6288** |
| 23-07-2026 | Titulares (8.492) | 1,016 | **0,996** | 0,4047 → **0,3992** |
| | Todos (16.678) | 0,973 | 1,040 | 0,2742 → **0,2709** |
| | Tarjetas del equipo (772) | 1,080 | **1,003** | −1,6086 → **−1,6016** |

Titulares por competición (esperado / real y log-loss, antes → ahora):

| Liga | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier | 0,95 → 0,97 · 0,4222 → 0,4207 | 0,92 → 0,92 · 0,4319 → 0,4293 |
| Bundesliga | 0,96 → 0,97 · 0,4152 → 0,4099 | 1,11 → 1,06 · 0,3891 → 0,3820 |
| LaLiga | 0,91 → 0,97 · 0,4611 → 0,4524 | 0,97 → 0,97 · 0,4447 → 0,4376 |
| Serie A | 1,05 → 1,06 · 0,3894 → 0,3828 | 1,11 → 1,05 · 0,3630 → 0,3587 |
| Ligue 1 | 0,93 → 0,97 · 0,4234 → 0,4176 | 1,03 → 0,97 · 0,3945 → 0,3861 |
| Champions | 1,06 → 1,07 · 0,3731 → 0,3693 | 1,08 → 1,09 · 0,3806 → 0,3779 |

Tarjetas del equipo por competición (esperadas / reales, antes → ahora): enero, Premier 1,02 → 0,99, Bundesliga 1,04 → 0,99, LaLiga 0,95 → 0,96, Serie A 1,12 → 1,07, Ligue 1 1,05 → 1,03, Champions 1,13 → 1,07; julio, 0,99 → 0,94, 1,14 → 1,04, 1,02 → 0,97, 1,17 → 1,05, 1,14 → 1,02 y 1,14 → 1,09.

- **La log-loss mejora en todas las ligas y en los dos cortes**, y la diferencia entre ligas se estrecha (titulares: de 0,91-1,06 a 0,97-1,07 en enero y de 0,92-1,11 a 0,92-1,09 en julio). Antes, en LaLiga salía baja (0,91) porque las dos cosas se sumaban; en la Serie A, la Champions y la Bundesliga de julio, alta, porque el modelo del equipo se pasaba más de lo que la probabilidad se quedaba corta.
- **Lo que queda es del modelo de tarjetas del equipo**, no del jugador: los titulares siguen a las tarjetas del equipo (en julio, 1,00 frente a 1,00). La Serie A y la Champions quedan algo altas (1,05-1,09: se ven menos tarjetas que nunca y el nivel aún va un poco por detrás) y la Premier de 2026-27, baja (0,92; es la única liga en la que suben, y el nivel la contrae hacia el de todas).
- **Por tramos de probabilidad** (titulares): en enero, de 0,48 / 0,79 / 0,87 / 1,00 / 1,10 / 1,43 (menos del 5 %, 5-10 %, 10-15 %, 15-20 %, 20-30 % y más del 30 %) a 0,66 / 0,99 / 0,95 / 1,01 / 1,02 / 1,39; en julio, de 0,63 / 0,84 / 0,89 / 1,07 / 1,17 / 1,33 a 1,45 / 1,14 / 0,94 / 1,02 / 0,98 / 0,82. Los extremos tienen pocos casos (el tramo de más del 30 % pasa de 311 a 123 titulares en enero y de 221 a 50 en julio).
- **Con 1 − e^(−λ)** y los demás cambios, la log-loss es peor en los dos cortes (titulares 0,4117 y 0,3999, frente a 0,4112 y 0,3992; todos 0,2775 y 0,2712, frente a 0,2774 y 0,2709), y los titulares salen cortos (0,92 y 0,92).
- **«Todos» sale alto (1,05-1,08)** porque el modelo supone que cada suplente del once confirmado sale el 55 % de las veces y juega 22 minutos, y de julio a octubre salió el 45 % y jugó 20. Afecta a todos los mercados de los suplentes (pendiente en "Próximas mejoras"). Además, las apuestas a un suplente que no sale se anulan, y el modelo da su probabilidad contando que puede no salir: para un suplente, «Sí» sale bajo y «No» alto.
- **Con el modelo fijo los 90 días** (sin reentrenar, como la comprobación de los remates de arriba), los titulares quedan en 0,966 → 0,998 (enero, log-loss 0,4148 → 0,4104) y 1,030 → 1,043 (julio, 0,4007 → 0,3977): el nivel de cada liga no se actualiza y en julio vale el de antes del verano.

Reproducir: `medir_tarjetas.py DESDE 90 salida.json --semanal` (y `--registros` para cada jugador) y `medir_k.py` para la contracción, en las notas de la sesión del 22-10-2026 (no están en el repositorio).

**Bet Builders con jugadores** (`MatchModel.joint_prob`): si el equipo marca k goles, cada uno lo marca el jugador con su parte de los goles esperados del equipo (y lo asiste con su parte de asistencias). Así "gana el Real Madrid y marca Mbappé" se calcula sobre la matriz de marcadores, con su correlación positiva, y "Arsenal o empate y Kane marca o asiste" con su correlación negativa. Varias selecciones de jugadores del mismo equipo se combinan por inclusión-exclusión. Con un solo jugador sale la misma probabilidad que el mercado suelto. Córners, tarjetas, remates y faltas no dependen solo del marcador: en un Bet Builder se multiplican como si fueran independientes y el resultado se marca **aproximado**.

## 5. Alineaciones y bajas (`features/lineup.py`)

`calidad = ln(1 + valor_mercado_M€) + 0,5 × (rating − 6,8)` (rating acotado a ±1).
Fuerza ofensiva y defensiva del once = media ponderada por posición:

| | POR | DEF | MED | DEL |
|---|---|---|---|---|
| Ataque | 0 | 0,25 | 0,7 | 1 |
| Defensa | 1 | 1 | 0,6 | 0,15 |

Se compara con el **once típico** (media de las últimas 8 titularidades confirmadas):
`goles_a_favor × exp(0,10 × Δataque)` y `goles_en_contra × exp(−0,10 × Δdefensa)`.
Sin alineación publicada, se parte del once típico y se resta a los titulares habituales que están de baja.
El coeficiente 0,10 está calibrado con los onces confirmados históricos de FotMob (2.119 partidos de 2024-26). Antes era 0,30, una estimación a priori que exageraba el efecto (ver backtest).
Limitación: en partidos antiguos el valor de mercado es el de la fecha de descarga, no el de entonces.

## 6. Valor, confianza y apuesta del día

- **Probabilidad final** = 25 % modelo + 75 % mercado afilado (Pinnacle/Betfair sin margen) cuando existe. Si no existe, solo el modelo.
- **Valor esperado** = prob × cuota − 1 (corregido por la probabilidad de devolución en líneas asiáticas).
- **Confianza** (0-1) = alineación (confirmada 1 · prevista 0,85 · solo bajas 0,72; el último once que FotMob da cuando aún no tiene probable cuenta como previsto, y solo el oficial como confirmado) × muestra × tipo de mercado (principal 1 / estadísticas 0,75 / jugador 0,65) × acuerdo modelo-mercado × riesgo de rotación × cobertura del mercado (abajo).
- **Equipos que el mercado no ha visto** (`analysis.MARKET_COVERED`). Se cuentan los partidos de cada equipo con cuotas de cierre en el último año (`RatingModel.market_matches`). Si alguno de los dos equipos tiene menos de 10:
  - la confianza se multiplica por un factor que baja linealmente hasta 0,6 con 0 partidos;
  - en los mercados de goles (1X2, doble oportunidad, empate no válido, ambos marcan, hándicaps y más/menos goles), si no hay mercado afilado, la probabilidad se mezcla con la de la propia cuota sin margen (se supone un 5 %). El peso del modelo es el mismo 25 % de la mezcla con Pinnacle cuando el equipo tiene 0 partidos, y sube hasta 100 % con 10.

  Afecta a equipos de ligas que no se descargan y que solo vemos en copas europeas (Bodø/Glimt, Slavia, Shakhtar…). **Es una regla de prudencia, no un parámetro ajustado**: esos partidos no tienen cuotas en football-data, así que el backtest no puede medirla. En las ligas no cambia nada, porque todos sus equipos tienen cuotas. Ejemplo, Napoli-Bodø/Glimt (UCL, 20-10-2026):

  | Cuota | Antes | Ahora |
  |---|---|---|
  | Bodø @9,00 | probabilidad 32 %, valor +185 %, confianza 0,65 | probabilidad 15 %, valor +39 %, confianza 0,31 (no puede ser apuesta del día) |
  | Napoli @1,30 | probabilidad 44 % | probabilidad 66 % |
- **Apuesta del día**: máxima `valor × confianza` con cuota entre 1,50 y 2,60, prob ≥ 42 %, valor ≥ 3 % y confianza ≥ 0,60. **Si ninguna cumple, no hay apuesta del día.**
  Solo puede salir de los **mercados de goles** (1X2, doble oportunidad, empate no válido, ambos marcan, hándicaps y más/menos goles), que son los validados en el backtest contra cuotas reales. Córners, tarjetas, el resto de estadísticas y las props de jugador se muestran como apuestas con valor, pero no pueden ser apuesta del día hasta validarlos (`APUESTAS_PICK_ALLOW_STAT_MARKETS=true` lo cambia).
- **Discrepancia con la casa en estadísticas.** En córners, tarjetas y el resto de estadísticas, si la casa tiene todos los lados de la línea (más y menos, o los dos equipos del hándicap), se calcula su probabilidad sin margen y se compara con la del modelo:
  - hasta 5 puntos de diferencia, la confianza no cambia;
  - de 5 a 20 puntos, baja linealmente hasta ×0,3 (`STAT_DISAGREE_*` en `analysis.py`).

  La probabilidad del modelo no se toca: solo la confianza. Es una regla de prudencia, porque no hay historial de cuotas de estadísticas para ajustarla con el backtest.

  Motivo: con las cuotas de Betano (OddsPapi, 19-10-2026), el modelo veía "valor" en 412 cuotas de los 9 partidos de Champions del día siguiente. Algunas eran absurdas, como "Napoli más de 10,5 córners" a 9,00 con +164 %. La apuesta del día salía de un hándicap de córners con +41 %.
- **Equipos con pocos partidos con esa estadística** (`analysis.STAT_COVERED`, desde el 21-10-2026). En córners, tarjetas y el resto de estadísticas, si el equipo menos visto de los dos tiene menos de 10 partidos (ponderados) con esa estadística, la probabilidad se mezcla con la de la casa sin margen (o con la cuota suelta, quitándole un 5 %, si la casa no tiene los dos lados). El peso del modelo es n / 10: con 0 partidos manda la casa y no puede salir valor; con 10 o más, solo el modelo. Es más estricta que la regla de goles (que deja un 25 % de modelo con 0 partidos) porque los modelos de estadísticas no tienen ningún backtest contra cuotas. Afecta a los mismos rivales europeos (Viking, LASK, Slavia, Shakhtar, Bodø/Glimt…). Es una regla de prudencia, no un parámetro ajustado.

  Aston Villa-Viking (Viking con 1,9 partidos): "Córners de Viking: Más de 5.5" a 6,50 pasa de +73 % (solo con la contracción) a +11 %, con confianza 0,08. Antes, 34 cuotas de córners de ese partido salían con valor y la mayor daba +232 %; ahora la mayor es esa, con +11 %.
- **Stake**: Kelly × 0,25, con tope del 3 % de la banca. Límites de pérdida: 5 % diario y 10 % semanal.
- **CLV de las apuestas guardadas** (`picks.closing_reference`, desde el 2026-10-28). Al liquidar, cada apuesta guardada (y cada apuesta registrada) se compara con la cuota **justa** (sin margen, `betting/odds.py::devig`) de la referencia más afilada que haya antes del partido: CLV = cuota tomada × probabilidad justa − 1. Orden: cierre de Pinnacle o de Betfair (football-data), el último precio de Pinnacle antes del inicio (OddsPapi) y el cierre de bet365. Hace falta que la referencia tenga todos los lados de esa línea (más y menos, los tres del hándicap europeo, los dos del asiático, sí y no); si no, la apuesta queda sin CLV y el panel dice por qué. Se guarda de qué casa sale y cuándo se vio ese precio por primera vez (`pick.closing_source`, `pick.closing_at`).

  Por qué no basta el cierre de football-data: solo trae 1X2, Más/Menos 2.5 y el hándicap asiático principal de las ligas, días después del partido, y casi todas las que pasan el corte son de Betano en goles por equipo, hándicap europeo o ambos marcan. Medido el 2026-10-28 con las 40 liquidadas que pasan el corte: el cierre de bet365 o Betfair servía para 2; el último Pinnacle guardado, para las 40, pero solo 24 a menos de 3 horas del inicio (la descarga de las 08:30 queda lejos de los partidos de la tarde o del día siguiente). Por eso, **unos 15 minutos antes de cada hora de inicio con apuestas abiertas que pasan el corte**, el worker baja Pinnacle por OddsPapi (`job_closing_odds`; como mucho `APUESTAS_ODDSPAPI_CLOSING_PER_DAY` = 3 descargas al día, unas 40-90 peticiones más al mes, aprobado por el usuario el 2026-10-28).

  Primeros resultados (2026-10-28, sin la descarga de antes del inicio): **CLV medio −3,5 %** en las 40 que pasan el corte (9 de 40 positivas): las cuotas de Betano y bet365 que el modelo elige quedan, de media, un 3,5 % por debajo de la justa de Pinnacle. Por antigüedad de la referencia: al cierre (Betfair) +2,8 % en 2; a menos de 3 h −3,2 % en 22; de 3 a 12 h −1,1 % en 4; más de 12 h −6,1 % en 12. Cuadra con el backtest (el modelo no le gana al mercado en goles). Con unos cientos de apuestas el CLV dirá si hay ventaja mucho antes que el ROI: con 40, el ROI tiene un margen de unos ±15 puntos.

## 7. Backtest (`backtest/engine.py`)

Walk-forward: cada semana se reajusta con datos anteriores y se apuesta contra la **cuota previa de bet365**. CLV contra el cierre de bet365.

**Temporadas 2024-25 y 2025-26** (2.132 partidos de EPL, BUN y LAL; la log-loss se mide en los 1.998 con cuotas de bet365 y Pinnacle). Ya con los detalles de FotMob completos: alineaciones, árbitros y xG de todos los partidos desde 2023. El "modelo anterior" se ha vuelto a medir con los datos completos (antes daba 0,992 con datos parciales).

| Log-loss 1X2 | Modelo | bet365 | Pinnacle | Mezcla 25/75 |
|---|---|---|---|---|
| Modelo anterior (solo goles/xG) | 0,993 | 0,975 | 0,975 | 0,977 |
| **Con ratings del mercado** | **0,981** | 0,975 | 0,975 | 0,976 |

Mejora pareada por partido: −0,0116 ± 0,0029 (unos 4 errores estándar). Brier: 0,591 → 0,584 (bet365 0,581). La distancia con Pinnacle baja de 0,017 a 0,006.

Peso y vida media de las observaciones del mercado (log-loss del modelo):

| Peso \ vida media | 7 días | 14 días | 28 días | 60 días |
|---|---|---|---|---|
| 8 | 0,9877 | 0,9859 | 0,9850 | 0,9854 |
| 32 | 0,9836 | 0,9824 | 0,9827 | 0,9846 |
| 64 | 0,9819 | 0,9815 | 0,9824 | 0,9845 |
| 128 | 0,9809 | **0,9811** | 0,9822 | 0,9845 |

Con más peso apenas cambia (256 y 512 con 7 días: 0,9804 y 0,9803). Las diferencias dentro de la meseta son ruido. Se eligió 14 días porque aguanta mejor el arranque de temporada (agosto-septiembre: 0,956 frente a 0,958 con 7 días).

| Estrategia (valor ≥ 3 %) | Anterior: apuestas | ROI | CLV medio | Nuevo: apuestas | ROI | CLV medio |
|---|---|---|---|---|---|---|
| Solo modelo | 2.668 | −4,2 % | +0,2 % | 1.559 | −6,8 % | +0,5 % |
| · hándicap asiático | 1.289 | +0,3 % | +0,2 % | 849 | −4,2 % | +0,2 % |
| · más/menos 2.5 | 770 | −8,6 % | +0,2 % | 282 | −3,1 % | +2,1 % |
| · 1X2 | 609 | −8,2 % | +0,1 % | 428 | −14,4 % | −0,2 % |
| Modelo + mercado | 290 | −11,1 % | +1,1 % | 82 | −23,4 % | +2,2 % |
| bet365 frente a Pinnacle (sin margen) | 4 | — | — | 4 | — | — |

El error estándar del ROI con 1.500-2.700 apuestas a cuota ~2,2 es de 2-3 puntos, así que la caída del ROI no es significativa. La subida del CLV (y del % de apuestas que baten el cierre, 42 % → 45 %) es pequeña.

**Alineaciones** (`apuestas backtest --lineups`; 1.986 partidos con el once confirmado de ambos equipos y cuotas). Regresión de Poisson de goles/xG reales sobre la media del modelo y la diferencia entre el once y el once típico (4.238 equipo-partido, errores agrupados por partido):

| Objetivo | β ataque | β defensa |
|---|---|---|
| Goles | 0,11 ± 0,05 | 0,10 ± 0,06 |
| xG | 0,06 ± 0,03 | 0,08 ± 0,04 |

| Log-loss 1X2 | Sin ajuste | β = 0,05 | **β = 0,10** | β = 0,15 | β = 0,30 (anterior) | bet365 | Pinnacle previa | Pinnacle cierre |
|---|---|---|---|---|---|---|---|---|
| | 0,9812 | 0,9803 | **0,9798** | 0,9797 | 0,9818 | 0,9759 | 0,9759 | 0,9630 |

Con β = 0,10 la mejora frente a no ajustar es −0,0014 ± 0,0010; con 0,30 el modelo empeoraba. La mejora viene sobre todo de LaLiga (−0,003); en la Premier es nula. Las apuestas del backtest no usan este ajuste: el once sale ~1 h antes del partido y la cuota previa es de días antes.

Variantes probadas sin mejora (diferencia de log-loss frente a no ajustar; 2.119 partidos de liga + 361 de Champions):

| Variante (β = 0,10 salvo indicación) | Ligas | Champions |
|---|---|---|
| Once típico de todas las competiciones (se mantiene) | −0,0014 ± 0,0009 | −0,0011 ± 0,0024 |
| Once típico de la misma competición | −0,0012 ± 0,0009 | −0,0018 ± 0,0024 |
| Once típico de liga frente a copas europeas | −0,0012 ± 0,0009 | −0,0018 ± 0,0024 |
| Tope del ajuste (±10 % en la media de goles) | −0,0015 ± 0,0009 | −0,0010 ± 0,0024 |
| β = 0,30 (anterior) | +0,0013 ± 0,0028 | +0,0004 ± 0,0072 |

Los onces *previstos* (FotMob) no se pueden calibrar porque no se guarda su historial: cuando sale el confirmado, la fila se sobrescribe. Se les aplica el mismo β, que probablemente es algo alto para ellos, porque un once previsto mal acertado mete ruido. Ejemplo: en Liverpool-Villarreal (UCL, 20-10-2026) el once previsto de Liverpool incluye a varios suplentes y el de Villarreal es el de Champions (en liga rota). Con β = 0,30 el modelo daba 0,43 al local; con 0,10 da 0,59; el mercado, ~0,66.

**Árbitro en tarjetas** (mejora de log-verosimilitud por partido frente al modelo sin árbitro; 2.105 partidos):

| K | Total | Premier | Bundesliga | LaLiga |
|---|---|---|---|---|
| 20 | +0,0041 | −0,0105 | +0,0066 | +0,0170 |
| 40 | +0,0048 | −0,0066 | +0,0060 | +0,0155 |
| **80** | **+0,0044** | −0,0034 | +0,0046 | +0,0122 |
| 120 (anterior) | +0,0037 | −0,0022 | +0,0036 | +0,0099 |
| 250 | +0,0024 | −0,0009 | +0,0021 | +0,0061 |

K = 80 mejora a 120 en +0,0006 ± 0,0004. K = 40 da algo más de media, pero con más varianza. En la Premier el historial del árbitro no predice las tarjetas con ningún K (−0,003 ± 0,002 con K = 80). No se ha puesto una excepción por liga para no ajustarla a la misma muestra. En faltas se mantiene K = 20 (con 40 la diferencia es menor que su error).

**Copas europeas** (`--europa`; no hay cuotas de football-data, así que solo se mide el modelo). Log-loss 1X2 del modelo: Champions 0,903 (377 partidos), Europa League 0,984 (371) y Conference 1,021 (282). Sin referencia de mercado no se puede decir cuánto le falta. Hay dos limitaciones conocidas:
- 102 equipos solo aparecen en copas europeas: son de ligas que el modelo no usa. No tienen ratings del mercado, así que su rating sale solo de pocos partidos europeos. Ejemplo: Bodø/Glimt sale casi tan fuerte como el Napoli (+0,62 frente a +0,67), mientras que la cuota de 1,30 del Napoli implica ~77 %. Una ventaja local propia por equipo (Bodø: +0,3 de xG en casa y −1,7 fuera) se probó y no mejora: empeora las ligas en +0,001 y no cambia la Champions. Las ligas extra de football-data cubren 43 de esos 102 equipos, pero con el modelo actual no ayudan (abajo); los otros 59 son de ligas que football-data no tiene (Chequia, Croacia, Serbia, Ucrania, Chipre, Israel...).
- **Ligas extra de football-data** (19-10-2026): Austria, Dinamarca, Noruega, Suiza, Polonia, Suecia, Rumanía, Finlandia e Irlanda, con 6.852 partidos con cuota de cierre desde 2023. Con ellas tienen ratings del mercado 43 de los 102 equipos: 35 de esas ligas (Bodø/Glimt, Salzburg, Young Boys, Copenhague, Legia, Malmö, FCSB...) y 8 que eran duplicados. **Se descargan, pero no se usan para entrenar** (`APUESTAS_EXTRA_LEAGUES_IN_MODEL=false`), porque no mejoran el modelo actual. A/B sobre la misma BD, con log-loss por partido en los partidos que se evalúan en las dos versiones:

  | Log-loss 1X2 del modelo | Sin ligas extra | Con ligas extra | Diferencia |
  |---|---|---|---|
  | Ligas (2.132 partidos) | 0,9801 | 0,9800 | −0,0001 |
  | Champions (377) | 0,9017 | 0,9064 | +0,0046 ± 0,0061 |
  | Europa League (371) | 0,9856 | 0,9842 | −0,0014 ± 0,0074 |
  | Conference (282) | 1,0150 | 1,0236 | +0,0085 ± 0,0108 |

  Con las ligas extra se evalúan además 5 partidos de Europa League y 8 de Conference de equipos que antes no tenían rating. Así, `APUESTAS_EXTRA_LEAGUES_IN_MODEL=true apuestas backtest --lineups --europa` da 0,906 (377) / 0,984 (376) / 1,026 (290).

  El motivo es que el modelo no tiene un nivel por liga. La L2 encoge cada equipo hacia 0, así que una liga entera, conectada con las demás solo por sus partidos europeos, se acerca en bloque a la media: Irlanda sale al nivel de la Eredivisie. Los mejores de cada liga, que le sacan mucha ventaja al resto, quedan inflados. Bodø/Glimt pasa de +0,62 a +0,93 (Napoli +0,73) y Napoli-Bodø pasa de 47/25/28 a 39/24/37, con el mercado en ~77 % para el Napoli. Además, esos equipos dejarían de activar la regla de prudencia para equipos que el mercado no ha visto (sección 6). Bajar la L2 (0,5 o 0,1) separa más las ligas, pero no corrige a Bodø (+0,93 y +0,96).

  Experimento no aplicado: fuerza = nivel de la liga + desviación del equipo, con la L2 solo en la desviación (liga = la de su último partido de liga). Sin ligas extra: Champions 0,8966, Europa League 0,9757, Conference 1,0122 y ligas 0,9798. Con ellas: 0,8957 / 0,9719 / 1,0122 y ligas 0,9797. La mejora viene sobre todo del nivel por liga, y con él las ligas extra dejan de empeorar. Pero ninguna diferencia es significativa (copas juntas −0,008 ± 0,006 frente al modelo actual) y Napoli-Bodø sigue lejos del mercado (50/23/27).
- ~~Hay equipos duplicados entre fuentes~~ **Corregido el 19-10-2026** (`ingest/dedupe.py`). Se fusionaron 9 equipos:
  - AEK, PAOK, NEC Nijmegen, Royal Antwerp, Union Saint-Gilloise y Vitória de Guimarães: su registro de copas europeas no estaba conectado con el de su liga.
  - Verona, Clermont y Saint-Étienne: cada partido suyo de Serie A o Ligue 1 estaba **duplicado** (182 en total), uno de FotMob y otro de football-data. El rival de cada jornada "jugaba dos veces".

  La causa era que, en las ligas ligeras con FotMob, football-data creaba el partido en vez de buscarlo. Además, Gladbach nunca tenía enlazadas sus cuotas de football-data y quedaba sin ratings del mercado; ahora sí las tiene.

  La ingesta fusiona sola los pares seguros: nombre igual tras normalizar, fuentes distintas, sin enfrentamientos entre ellos y sin partidos distintos el mismo día. Los dudosos se listan con `apuestas equipos duplicados`, por ejemplo Aris (Grecia) frente a Aris Limassol (Chipre), que son clubes distintos.

  | Log-loss 1X2 del modelo | Antes | Después de fusionar |
  |---|---|---|
  | Ligas (2.132 partidos) | 0,9811 | **0,9801** (bet365 0,9749) |
  | Champions | 0,903 | 0,902 |
  | Europa League | 0,984 | 0,986 |
  | Conference | 1,021 | 1,015 |

  En el backtest de apuestas, solo modelo: 1.594 apuestas, ROI −6,3 % (antes −6,8 %), una diferencia que es ruido.
- El modelo solo se entrena con las competiciones definidas en `core/competitions.py`. La BD es compartida, y una rama puede cargar ligas nuevas que aún no se han validado.

| Estadísticas (log-verosimilitud del total por partido) | Mejora frente a la media de la liga |
|---|---|
| Faltas | +0,160 (árbitro: +0,006 más) |
| Remates | +0,036 |
| Remates a puerta | +0,024 |
| Tarjetas | +0,022 (árbitro: +0,004 más) |
| Córners | +0,008 |

**Contracción de las estadísticas** (21-10-2026; `apuestas backtest --europa`, frente a `--count-l2 1` para la L2 fija de antes). Log-verosimilitud por partido, del total y de los dos equipos por separado (`<stat> por equipo`), en 2.132 partidos de liga y 378 de Champions. En la Champions, 108 partidos tienen un equipo con menos de 10 partidos con estadísticas ("pocos datos"; `:pocos_datos` en la salida). Diferencia frente a la L2 fija, con el error estándar pareado:

| Estadística (K) | Ligas: total | Ligas: por equipo | Champions: total | Champions: por equipo | Pocos datos: total | Pocos datos: por equipo |
|---|---|---|---|---|---|---|
| Córners (5) | +0,0030 ± 0,0011 | +0,0008 ± 0,0040 | +0,019 ± 0,008 | −0,004 ± 0,023 | +0,043 ± 0,022 | +0,014 ± 0,056 |
| Tarjetas (10) | +0,0082 ± 0,0019 | +0,0111 ± 0,0024 | +0,015 ± 0,012 | +0,025 ± 0,015 | +0,026 ± 0,038 | +0,056 ± 0,045 |
| Faltas (5) | +0,0028 ± 0,0018 | +0,0081 ± 0,0027 | +0,045 ± 0,018 | +0,044 ± 0,027 | +0,111 ± 0,059 | +0,137 ± 0,082 |
| Remates (1) | +0,0014 ± 0,0005 | −0,0022 ± 0,0023 | +0,014 ± 0,006 | +0,004 ± 0,023 | +0,038 ± 0,019 | +0,065 ± 0,052 |
| Remates a puerta (1) | +0,0013 ± 0,0004 | −0,0022 ± 0,0015 | +0,022 ± 0,008 | +0,019 ± 0,014 | +0,070 ± 0,028 | +0,114 ± 0,040 |

K se eligió con una rejilla (0,5 a 30) en ese mismo walk-forward: el valor que mejora el total sin empeorar "por equipo" en las ligas. Más contracción sigue mejorando el total, pero empeora el reparto entre los dos equipos: en córners, con K = 20, "por equipo" baja −0,005 en ligas y −0,12 con pocos datos. El orden coincide con el que da la variación real entre equipos (empírico: K ≈ 2-3 en remates, 8 en córners, 30-60 en tarjetas), con más contracción donde los equipos se parecen más entre sí. En remates, "por equipo" en ligas baja un poco con cualquier K (−0,002, a 1-1,5 errores estándar); se acepta por la mejora en la Champions, que alimenta las props de jugadores de esos rivales. El 1X2 y las apuestas no cambian (el modelo de goles es el mismo). Antes, el total de córners en la Champions predecía peor que la media de la liga (−0,002); ahora, +0,017. (Después, los remates y los córners pasaron a contraerse hacia la fuerza del modelo de goles, con otra K: ver abajo.)

Comprobación con las cuotas guardadas de Pinnacle (47 partidos del 19 al 21-10-2026 con córners y 38 con tarjetas; modelo entrenado hasta el 19-10): error medio de la media de córners de cada equipo frente a la de Pinnacle (raíz del error cuadrático en logaritmo) 0,158 → 0,128, y en equipos con menos de 10 partidos, 0,281 → 0,167. En el total, 0,105 → 0,068. En tarjetas, 0,212 → 0,162 por equipo y 0,170 → 0,128 en el total.

**Córners y remates entre ligas: la fuerza del modelo de goles como guía** (21-10-2026; `apuestas backtest --europa`, frente a `--no-count-strength` para el modelo anterior). Con la contracción de arriba seguía un problema con equipos bien conocidos: frente a Pinnacle, el error por equipo en córners era 0,178 en la Champions y 0,095 en las ligas. Betis-Feyenoord daba 4,2 córners al Betis y 5,6 al Feyenoord (Pinnacle: 5,3 y 4,1). La causa es la de la sección 3: las ligas solo se cruzan en estas estadísticas por la Champions, y el nivel de cada liga lo fijaba la contracción.

Se probaron dos arreglos en el mismo walk-forward: un **nivel por liga** (fuerza = nivel de la liga + desviación del equipo, con la contracción solo en la desviación y la liga de su último partido de liga, como el experimento de goles), y la **fuerza del modelo de goles como guía** (sección 3). En la salida, `:entre_ligas` son los 260 partidos de Champions entre equipos conocidos de ligas distintas, y `:pocos_datos` los 108 con un equipo de menos de 10 partidos. Diferencia de log-verosimilitud por partido frente al modelo anterior, con el error estándar pareado:

| Córners: variante (K) | Ligas: total | Ligas: por equipo | Entre ligas: total | Entre ligas: por equipo | Pocos datos: total | Pocos datos: por equipo |
|---|---|---|---|---|---|---|
| Nivel por liga (5) | +0,0007 ± 0,0004 | +0,0074 ± 0,0022 | −0,0025 ± 0,0036 | +0,007 ± 0,031 | −0,020 ± 0,013 | +0,064 ± 0,044 |
| Nivel por liga y fuerza (5) | +0,0011 ± 0,0006 | +0,0124 ± 0,0036 | −0,0029 ± 0,0041 | +0,012 ± 0,031 | −0,018 ± 0,015 | +0,065 ± 0,051 |
| Fuerza (5) | +0,0014 ± 0,0006 | +0,0132 ± 0,0036 | −0,0016 ± 0,0031 | +0,041 ± 0,014 | +0,003 ± 0,006 | +0,060 ± 0,029 |
| Fuerza (10) | +0,0034 ± 0,0009 | +0,0205 ± 0,0037 | +0,0005 ± 0,0033 | +0,047 ± 0,014 | −0,001 ± 0,009 | +0,053 ± 0,029 |
| **Fuerza (20, aplicada)** | **+0,0045 ± 0,0016** | **+0,0275 ± 0,0043** | **+0,0019 ± 0,0050** | **+0,053 ± 0,015** | **−0,009 ± 0,014** | **+0,039 ± 0,033** |
| Fuerza (40) | +0,0034 ± 0,0026 | +0,0311 ± 0,0054 | +0,0015 ± 0,0075 | +0,056 ± 0,017 | −0,018 ± 0,018 | +0,023 ± 0,037 |

| Otras estadísticas: variante (K) | Ligas: total | Ligas: por equipo | Entre ligas: total | Entre ligas: por equipo | Pocos datos: total | Pocos datos: por equipo |
|---|---|---|---|---|---|---|
| **Remates: fuerza (8, aplicada)** | +0,0062 ± 0,0015 | +0,0230 ± 0,0033 | −0,0029 ± 0,0041 | +0,043 ± 0,014 | +0,034 ± 0,019 | +0,114 ± 0,045 |
| **A puerta: fuerza (8, aplicada)** | +0,0067 ± 0,0015 | +0,0161 ± 0,0023 | −0,0014 ± 0,0048 | +0,025 ± 0,011 | +0,089 ± 0,034 | +0,147 ± 0,044 |
| Tarjetas: fuerza (10, no aplicada) | −0,0002 ± 0,0003 | +0,0024 ± 0,0011 | +0,0000 ± 0,0021 | −0,003 ± 0,004 | −0,002 ± 0,002 | +0,009 ± 0,007 |
| Faltas: fuerza (5, no aplicada) | +0,0010 ± 0,0005 | +0,0014 ± 0,0006 | −0,0048 ± 0,0031 | −0,008 ± 0,004 | +0,005 ± 0,005 | −0,001 ± 0,006 |

Con la fuerza como guía, más contracción mejora, al revés que antes: sin la fuerza, K = 10 en córners empeora el reparto (−0,0008 ± 0,0019 por equipo en ligas y −0,054 ± 0,018 con pocos datos). Se eligió el K que mejora las ligas y los partidos entre ligas sin empeorar de forma apreciable los de pocos datos; estos, además, se mezclan con la casa (sección 6). En toda la Champions (378 partidos), córners por equipo +0,047 ± 0,014, remates +0,061 ± 0,016 y a puerta +0,059 ± 0,015; el total no empeora en ninguno. Usar ataque y defensa de goles por separado (cuatro coeficientes en vez de dos) da lo mismo que su suma. El 1X2, las apuestas del backtest, las tarjetas y las faltas no cambian.

Comprobación con las cuotas guardadas (modelo entrenado hasta el 20-10-2026; la media de cada equipo sale de todas las líneas de más/menos y hándicap de córners de la casa, sin margen). Error de la media de córners de cada equipo (raíz del error cuadrático en logaritmo):

| Córners, error por equipo | Ligas | Champions, equipos conocidos | Champions, pocos datos | Todos | Total del partido |
|---|---|---|---|---|---|
| Pinnacle (41 partidos: 25 / 9 / 7), modelo anterior | 0,095 | 0,178 | 0,170 | 0,132 | 0,068 |
| Pinnacle, nivel por liga (5) | 0,090 | 0,160 | 0,150 | 0,120 | 0,069 |
| Pinnacle, nivel por liga (10) | 0,087 | 0,151 | 0,139 | 0,114 | 0,059 |
| **Pinnacle, fuerza (20)** | **0,072** | **0,120** | **0,083** | **0,086** | **0,049** |
| Betano (47 partidos: 29 / 11 / 7), modelo anterior | 0,083 | 0,180 | 0,147 | 0,123 | 0,062 |
| **Betano, fuerza (20)** | **0,058** | **0,131** | **0,066** | **0,082** | **0,046** |

| Córners (local-visitante) | Pinnacle | Modelo anterior | Nivel por liga | Fuerza |
|---|---|---|---|---|
| Betis-Feyenoord | 5,3-4,1 | 4,2-5,6 | 4,6-5,2 | 4,8-4,9 |
| Porto-PSV | 5,6-4,2 | 5,0-4,6 | 4,3-5,2 | 5,2-4,2 |
| Brujas-Lens | 5,5-4,6 | 5,5-4,8 | 4,5-5,8 | 5,4-4,6 |
| Real Madrid-Leipzig | 7,0-3,5 | 7,2-4,3 | 7,2-4,2 | 7,0-3,9 |
| Manchester City-AEK | 7,8-2,2 | 5,5-3,5 | 7,9-2,4 | 6,4-3,1 |
| Napoli-Bodø/Glimt | 6,2-3,7 | 8,2-3,0 | 8,8-2,7 | 6,7-3,5 |

**Por qué no el nivel por liga.** Con tan pocos partidos entre ligas, el nivel de cada liga sale con mucho ruido: la Eredivisie, con 14 partidos ponderados, queda casi al nivel de la Segunda española, y la belga sale tan baja que el Brujas tendría menos córners que el Lens en su campo. Mejora el reparto de las ligas, pero en la Champions apenas (+0,007 ± 0,031 entre ligas) y estropea casos que estaban bien (Porto-PSV, Brujas-Lens). Con la fuerza como guía, el nivel de cada liga sale del modelo de goles, que tiene muchos más datos para comparar ligas (cuotas de cierre y todos los partidos de las tres copas europeas). Juntar las dos cosas es peor que la fuerza sola. (Se volvió a probar con las estadísticas de la Europa League y la Conference, con casi el doble de cruces, y tampoco mejora: ver "Nivel por liga con los cruces de la Europa League y la Conference" abajo.)

**Lo que queda.** Con equipos grandes aún hay diferencias con Pinnacle: Betis-Feyenoord (4,8-4,9 frente a 5,3-4,1) y Bayern-Arsenal (4,6-4,2 frente a 5,5-4,2). En el análisis del 21-10, "Córners de Feyenoord: Más de 7.5" a 9,00 pasa de +108 % a +41 %, pero su confianza sube de 0,36 a 0,73, porque el modelo y la casa discrepan menos (sección 6). Los córners no pueden ser apuesta del día (solo los mercados de goles). (Explicado y corregido en parte el 22-10-2026: ver "Córners del local grande en la Champions" más abajo.)

**Estadísticas de la Europa League y la Conference** (21-10-2026). FotMob trae de estas copas las mismas estadísticas que de la Champions. Se bajaron los 1.020 partidos jugados desde 2023-24 a una copia de la base de datos y se midió con el mismo walk-forward, en los mismos partidos, quitando sus estadísticas solo de los datos de entrenamiento. Diferencia de log-verosimilitud por partido (positivo = mejor), con el error estándar pareado:

| Con las estadísticas de UEL/UECL | Ligas: total | Ligas: por equipo | Champions: por equipo | Entre ligas: total | Entre ligas: por equipo | Pocos datos: por equipo |
|---|---|---|---|---|---|---|
| Córners | +0,0000 ± 0,0004 | +0,0012 ± 0,0008 | +0,0015 ± 0,0036 | +0,0025 ± 0,0012 | +0,0043 ± 0,0023 | −0,005 ± 0,012 |
| Remates | +0,0001 ± 0,0006 | +0,0051 ± 0,0013 | +0,0079 ± 0,0075 | +0,0011 ± 0,0022 | +0,0129 ± 0,0046 | −0,003 ± 0,024 |
| A puerta | +0,0008 ± 0,0007 | +0,0029 ± 0,0010 | +0,0040 ± 0,0091 | −0,0013 ± 0,0026 | +0,0024 ± 0,0039 | +0,008 ± 0,031 |
| Faltas | −0,0011 ± 0,0010 | +0,0004 ± 0,0012 | +0,0202 ± 0,0066 | +0,0010 ± 0,0031 | +0,0076 ± 0,0052 | +0,052 ± 0,019 |
| Tarjetas | +0,0012 ± 0,0009 | +0,0012 ± 0,0009 | +0,0023 ± 0,0036 | +0,0005 ± 0,0022 | +0,0021 ± 0,0025 | +0,002 ± 0,011 |

(Los grupos de la Champions se definen con el modelo sin las copas: 260 partidos entre ligas y 108 con pocos datos.) La mejora es pequeña pero va en la misma dirección en casi todo: sobre todo remates y faltas, y córners entre ligas. En los partidos de las dos copas, que antes ni se podían medir, la mejora es grande (remates por equipo +0,082 ± 0,024 en la Europa League y +0,130 ± 0,057 en la Conference; faltas +0,10 en las dos), pero esos partidos no se analizan en el panel.

- **El xG de las copas, fuera del modelo de goles.** Si su xG entra con el peso normal (85 %), la log-loss 1X2 del modelo empeora en la Champions (+0,0062 ± 0,0025 por partido; 0,9018 → 0,9079 en `apuestas backtest --europa`) y en la Europa League (+0,0071 ± 0,0070), mejora en la Conference (−0,027 ± 0,014) y no cambia en las ligas (+0,0001 ± 0,0001). Como los partidos que se analizan son los de liga y Champions, sus partidos entran en el modelo de goles solo con el resultado, como antes. Con eso, el 1X2, la log-loss por competición y las apuestas del backtest no cambian (0,9801; Champions 0,9018 → 0,9017 por los resultados nuevos).
- **K y fuerza.** Con estos datos, la fuerza del modelo de goles sigue haciendo falta: sin ella, córners por equipo −0,024 ± 0,004 en las ligas y −0,036 ± 0,013 entre ligas frente al modelo actual. Duplicar K mejora las ligas (córners por equipo +0,0045 ± 0,0018) pero empeora los equipos con pocos datos (−0,019 ± 0,010), igual que sin las copas; K se queda como estaba.
- **Frente a las casas** (los mismos 41 partidos con cuotas de Pinnacle y 47 de Betano de arriba, modelo hasta el 20-10): casi igual. Error por equipo en córners con Pinnacle: ligas 0,072 → 0,072, Champions con equipos conocidos 0,120 → 0,119, pocos datos 0,083 → 0,081; con Betano 0,058 → 0,060, 0,130 → 0,128 y 0,066 → 0,066. Betis-Feyenoord pasa de 4,8-4,9 a 4,6-4,7 (Pinnacle 5,3-4,1): la falta de datos de la Europa League no explicaba esas diferencias.

Reproducir: `apuestas backtest --europa` con y sin las estadísticas en la base de datos (salidas en `var/backtests/uel_stats_{antes,final}_2024_2026.json`; `uel_stats_despues` es la variante con el xG de las copas).

**Nivel por liga con los cruces de la Europa League y la Conference** (21-10-2026; probado y **no aplicado**). Con las estadísticas de las dos copas, las ligas se cruzan en córners y remates casi el doble que antes. Partidos entre ligas ponderados por antigüedad a 20-10-2026: Portugal 29, Eredivisie 26, Bélgica 18, Turquía 18, Grecia 16 y Escocia 10; las cinco grandes, de 42 a 58. Se repitió la prueba del nivel por liga en el mismo walk-forward 2024-26, con todas las estadísticas en el entrenamiento. Igual que antes: fuerza = nivel de la liga + desviación del equipo, contracción solo en la desviación, y la liga de cada equipo es la de su último partido de liga. Variantes:

- **Nivel por liga** sin la fuerza de goles, con la K de antes (5 en córners, 1 en remates) o con la de la fuerza (20 y 8).
- **Nivel y fuerza**: nivel por liga más la fuerza de goles como guía. G es la contracción del nivel de cada liga hacia 0, en partidos equivalentes: con G = 0,1 el nivel queda casi libre; con G = 30 solo se aparta de 0 si los cruces lo piden.
- **Ritmo y fuerza**: solo el ritmo de cada liga (más o menos córners para los dos equipos, sin tocar cuánto domina una liga a otra), más la fuerza.
- **Nivel solo para equipos sin liga**: los equipos de ligas que no se descargan (Bodø/Glimt, Slavia...) comparten un nivel; los demás, como ahora.

Diferencia de log-verosimilitud por partido frente al modelo de ese día (fuerza de goles como guía, antes del reparto por el 1X2 del 22-10; positivo = mejor), con el error estándar pareado. Con las estadísticas de las copas, en la Champions hay 260 partidos entre ligas y 96 con pocos datos. La última columna son los 199 partidos de Europa League y Conference entre equipos conocidos de ligas distintas (no se analizan en el panel):

| Córners: variante | Ligas: total | Ligas: por equipo | Entre ligas: total | Entre ligas: por equipo | Pocos datos: total | Pocos datos: por equipo | UEL/UECL entre ligas: por equipo |
|---|---|---|---|---|---|---|---|
| Nivel por liga (K de antes) | −0,0032 ± 0,0016 | −0,0201 ± 0,0033 | −0,0010 ± 0,0053 | −0,008 ± 0,019 | −0,012 ± 0,013 | +0,023 ± 0,027 | −0,003 ± 0,021 |
| Nivel por liga (K de la fuerza) | −0,0029 ± 0,0010 | −0,0253 ± 0,0052 | −0,0008 ± 0,0053 | −0,013 ± 0,019 | −0,020 ± 0,008 | +0,028 ± 0,029 | +0,007 ± 0,022 |
| Nivel y fuerza (G 0,1) | −0,0007 ± 0,0006 | −0,0018 ± 0,0008 | +0,0007 ± 0,0022 | +0,004 ± 0,016 | −0,017 ± 0,009 | +0,040 ± 0,027 | +0,013 ± 0,017 |
| Nivel y fuerza (G 30) | −0,0005 ± 0,0005 | −0,0009 ± 0,0006 | +0,0007 ± 0,0014 | +0,006 ± 0,008 | −0,005 ± 0,003 | +0,019 ± 0,009 | +0,016 ± 0,008 |
| Ritmo y fuerza | −0,0008 ± 0,0006 | −0,0010 ± 0,0006 | −0,0001 ± 0,0009 | +0,000 ± 0,001 | −0,014 ± 0,008 | −0,012 ± 0,008 | −0,001 ± 0,001 |
| Nivel solo para equipos sin liga | −0,0000 ± 0,0001 | −0,0002 ± 0,0002 | −0,0003 ± 0,0003 | −0,000 ± 0,001 | −0,012 ± 0,007 | +0,016 ± 0,018 | −0,001 ± 0,001 |

| Remates y a puerta: variante | Ligas: total | Ligas: por equipo | Entre ligas: total | Entre ligas: por equipo | Pocos datos: total | Pocos datos: por equipo | UEL/UECL entre ligas: por equipo |
|---|---|---|---|---|---|---|---|
| Remates: nivel por liga (K de la fuerza) | −0,0020 ± 0,0010 | −0,0185 ± 0,0047 | +0,0061 ± 0,0038 | +0,011 ± 0,021 | +0,010 ± 0,010 | +0,097 ± 0,036 | +0,055 ± 0,031 |
| Remates: nivel y fuerza (G 0,1) | −0,0011 ± 0,0006 | −0,0008 ± 0,0012 | −0,0009 ± 0,0024 | +0,011 ± 0,019 | +0,008 ± 0,009 | +0,089 ± 0,031 | +0,040 ± 0,028 |
| Remates: nivel y fuerza (G 30) | −0,0009 ± 0,0004 | −0,0003 ± 0,0007 | −0,0005 ± 0,0012 | +0,010 ± 0,009 | +0,005 ± 0,003 | +0,039 ± 0,010 | +0,029 ± 0,011 |
| Remates: nivel solo para equipos sin liga | +0,0002 ± 0,0001 | +0,0001 ± 0,0003 | +0,0000 ± 0,0002 | −0,000 ± 0,001 | +0,002 ± 0,006 | +0,034 ± 0,017 | −0,002 ± 0,001 |
| A puerta: nivel por liga (K de la fuerza) | −0,0003 ± 0,0011 | −0,0088 ± 0,0037 | +0,0055 ± 0,0037 | +0,007 ± 0,013 | +0,008 ± 0,012 | +0,029 ± 0,031 | +0,015 ± 0,025 |
| A puerta: nivel y fuerza (G 30) | −0,0005 ± 0,0005 | +0,0004 ± 0,0006 | −0,0007 ± 0,0011 | +0,004 ± 0,004 | +0,005 ± 0,003 | +0,018 ± 0,008 | +0,009 ± 0,008 |

Comprobación con las cuotas guardadas (los mismos partidos que arriba; modelo entrenado hasta el 20-10-2026). Error de la media de córners de cada equipo:

| Córners, error por equipo | Pinnacle: ligas | Champions, conocidos | Champions, pocos datos | Todos | Betano: ligas | Champions, conocidos | Champions, pocos datos | Todos |
|---|---|---|---|---|---|---|---|---|
| **Modelo actual (fuerza)** | 0,073 | **0,119** | **0,081** | **0,086** | 0,060 | **0,128** | **0,066** | **0,082** |
| Nivel por liga (K de antes) | 0,089 | 0,141 | 0,177 | 0,120 | 0,077 | 0,160 | 0,172 | 0,119 |
| Nivel y fuerza (G 0,1) | 0,071 | 0,122 | 0,132 | 0,097 | 0,058 | 0,142 | 0,137 | 0,098 |
| Nivel y fuerza (G 30) | 0,072 | 0,120 | 0,084 | 0,087 | 0,059 | 0,133 | 0,080 | 0,085 |
| Ritmo y fuerza | 0,071 | 0,119 | 0,088 | 0,087 | 0,059 | 0,129 | 0,074 | 0,083 |

| Córners (local-visitante) | Pinnacle | Modelo actual | Nivel por liga | Nivel y fuerza (G 30) |
|---|---|---|---|---|
| Betis-Feyenoord | 5,3-4,1 | 4,6-4,7 | 4,4-4,9 | 4,6-4,8 |
| Bayern-Arsenal | 5,5-4,2 | 4,8-4,1 | 4,6-4,2 | 4,7-4,2 |
| Porto-PSV | 5,6-4,2 | 5,2-4,2 | 4,5-5,0 | 4,8-4,5 |
| Brujas-Lens | 5,5-4,6 | 5,4-4,6 | 4,9-5,3 | 5,2-4,8 |
| Manchester City-AEK | 7,8-2,2 | 6,5-3,1 | 7,3-2,7 | 6,8-2,9 |
| Napoli-Bodø/Glimt | 6,2-3,7 | 6,8-3,4 | 9,1-2,5 | 7,2-3,2 |

**Por qué sigue sin servir.** Ahora el nivel de cada liga sí se distingue cuando va solo. Remuestreando los partidos (bootstrap a 20-10-2026), la ventaja en córners de una liga frente a las demás (nivel de ataque + nivel de defensa, relativo a la Premier) es −0,29 ± 0,10 en LaLiga, −0,58 ± 0,10 en la Eredivisie, −0,84 ± 0,11 en Portugal y −0,98 ± 0,12 en Escocia. Pero casi todo eso ya lo explica la fuerza del modelo de goles. Lo que queda por liga encima de la fuerza va de +0,04 a −0,44, con errores de ±0,04 a ±0,15, y no predice mejor:
- **Córners**: ninguna variante mejora entre ligas (la mejor, +0,006 ± 0,008 por equipo) y todas empeoran un poco las ligas. El nivel por liga sin la fuerza queda muy por debajo (−0,020 ± 0,003 por equipo en las ligas). Además estropea Porto-PSV y Brujas-Lens, igual que sin las copas.
- **Remates y a puerta**: con nivel y fuerza mejora el reparto entre los dos equipos de la Champions cuando uno tiene pocos datos (remates +0,039 ± 0,010 con G = 30) y en las copas. Pero el total no mejora en ningún grupo, en las ligas empeora un poco (−0,0009 ± 0,0004) y G se eligió mirando estos mismos partidos. Parte de esa mejora la da solo el nivel compartido de los equipos sin liga (+0,034 ± 0,017). No hay cuotas de remates guardadas para comprobarlo con las casas.
- **Frente a Pinnacle y Betano**, ninguna variante mejora en la Champions, y Betis-Feyenoord y Bayern-Arsenal casi no cambian. Lo que falta en esos dos partidos tampoco es la contracción: con K = 40 en córners salen 4,8-4,6 y 4,8-4,2. Tampoco es un sesgo de local: en los 16 partidos de Champions, la media del local en el modelo queda solo un 2,5 % ± 2,4 % por debajo de la de Pinnacle. La causa resultó ser otra y se corrigió el 22-10-2026: ver "Córners del local grande en la Champions frente a Pinnacle" abajo.

Se queda la fuerza de goles como guía, sin nivel por liga. La versión de `ratings.fit` con nivel por liga para los conteos no se ha guardado en el código.

**Serie A y Ligue 1 como ligas completas** (21-10-2026, a petición del usuario). Hasta entonces eran ligas ligeras: entraban en el modelo con el resultado, los conteos de football-data y las cuotas de cierre, pero sin xG (football-data no lo trae hasta 2026-27), sin árbitro, sin alineaciones y sin jugadores. Ahora tienen lo mismo que la Premier, la Bundesliga y LaLiga: xG de FotMob y de Understat, estadísticas Opta, árbitro, alineaciones y jugadores. Se bajaron los 2.191 partidos jugados desde 2023-24 a una copia de la base de datos y se repitió el walk-forward de siempre (2024-25 y 2025-26) sobre la copia de antes y la de después, en los mismos partidos. `apuestas backtest` evalúa ahora por defecto las cinco ligas y da la log-loss de cada una; `--ligas EPL,BUN,LAL` repite las cifras anteriores.

Log-loss 1X2 del modelo por competición, en todos los partidos con rating (diferencia pareada después − antes; negativo = mejor). El "antes" de la Premier, la Bundesliga, LaLiga y las copas es el backtest de antes, con tres ligas; el de la Serie A y la Ligue 1, la copia de antes evaluando también esas dos ligas:

| Competición | Partidos | Antes | Después | Diferencia |
|---|---|---|---|---|
| Premier | 760 | 0,9935 | 0,9938 | +0,0003 ± 0,0002 |
| Bundesliga | 612 | 0,9801 | 0,9800 | −0,0001 ± 0,0002 |
| LaLiga | 760 | 0,9648 | 0,9647 | −0,0001 ± 0,0002 |
| Serie A | 755 | 0,9695 | 0,9695 | −0,0001 ± 0,0009 |
| Ligue 1 | 608 | 0,9664 | 0,9670 | +0,0007 ± 0,0011 |
| Champions | 377 | 0,9017 | 0,9022 | +0,0005 ± 0,0005 |
| Europa League | 371 | 0,9858 | 0,9855 | −0,0003 ± 0,0004 |
| Conference | 282 | 1,0149 | 1,0151 | +0,0003 ± 0,0004 |

De la Premier, +0,0002 sale solo de estimar ρ (Dixon-Coles) con cinco ligas en vez de tres. Ninguna diferencia llega a dos errores estándar.

Frente a las casas (partidos con cuotas de bet365 y Pinnacle):

| Log-loss 1X2 | Modelo antes | Modelo después | bet365 | Pinnacle | Mezcla 25/75 |
|---|---|---|---|---|---|
| Premier | 0,9975 | 0,9978 | 0,9995 | 0,9974 | 0,9966 |
| Bundesliga | 0,9749 | 0,9748 | 0,9652 | 0,9669 | 0,9681 |
| LaLiga | 0,9668 | 0,9667 | 0,9578 | 0,9585 | 0,9595 |
| Serie A | 0,9657 | 0,9656 | 0,9623 | 0,9602 | 0,9608 |
| Ligue 1 | 0,9644 | 0,9651 | 0,9646 | 0,9649 | 0,9639 |
| Las cinco (3.495) | 0,9743 | 0,9744 | 0,9704 | 0,9700 | 0,9702 |

Apuestas del backtest (solo modelo, valor ≥ 3 %): Serie A, de 565 apuestas con ROI −3,4 % a 562 con +2,7 % (CLV +0,3 % → +0,5 %); Ligue 1, de 437 con −4,2 % a 422 con −7,4 % (CLV +1,3 % en los dos). Las cinco ligas juntas: 2.584 apuestas, ROI −4,1 %, CLV +0,6 %. Con unas 500 apuestas a cuota ~2, el error estándar del ROI es de 4-5 puntos: ninguna de estas diferencias es significativa.

El xG casi no mueve el 1X2 porque el modelo ya seguía las cuotas de cierre de esas dos ligas (ratings del mercado, sección 1), que son lo que más pesa. En la Ligue 1 el modelo queda a la par de las casas (0,9651 frente a 0,9646 de bet365), pero, como en las demás ligas, eso no da apuestas rentables.

Estadísticas (mejora de la log-verosimilitud por partido frente a la media de la liga; "por equipo" = los dos equipos por separado; el árbitro, frente al mismo modelo sin árbitro):

| Después | Premier | Bundesliga | LaLiga | Serie A | Ligue 1 |
|---|---|---|---|---|---|
| Córners por equipo | +0,191 | +0,109 | +0,123 | +0,126 | +0,130 |
| Remates por equipo | +0,347 | +0,257 | +0,352 | +0,283 | +0,317 |
| A puerta por equipo | +0,150 | +0,236 | +0,234 | +0,191 | +0,255 |
| Faltas por equipo | +0,200 | +0,273 | +0,248 | +0,266 | +0,098 |
| Tarjetas por equipo | +0,048 | +0,046 | +0,023 | +0,078 | +0,038 |
| Árbitro en tarjetas | −0,004 ± 0,002 | +0,004 ± 0,003 | +0,011 ± 0,004 | +0,013 ± 0,002 | +0,003 ± 0,002 |
| Árbitro en faltas | +0,007 ± 0,005 | −0,005 ± 0,006 | +0,014 ± 0,006 | +0,006 ± 0,005 | +0,024 ± 0,008 |

Los modelos de la Serie A y la Ligue 1 mejoran a la media de la liga tanto como los de las otras ligas, y ya lo hacían antes con los conteos de football-data (FotMob y football-data dan casi siempre las mismas cifras; difieren en el 13-14 % de las filas, como en LaLiga). Lo nuevo es el árbitro, que football-data no trae fuera de Inglaterra: ayuda claramente en las tarjetas de la Serie A y en las faltas de la Ligue 1. En las ligas de siempre las estadísticas no cambian (±0,0002), y en la Champions mejoran un poco los remates (por equipo +0,0026 ± 0,0008; entre ligas +0,0032 ± 0,0011), sin que nada empeore más allá del ruido.

Jugadores, fuera de muestra (modelo entrenado hasta el día de corte; partidos con once confirmado de los 90 días siguientes; esperado / real y log-loss frente a la tasa media):

| Corte | Liga | Jugador-partidos | Gol | Asistencia | Gol o asistencia | Log-loss del gol |
|---|---|---|---|---|---|---|
| 15-01-2026 | Serie A | 5.612 | 275 / 292 | 195 / 192 | 448 / 461 | 0,168 (media 0,205) |
| | Ligue 1 | 4.184 | 265 / 251 | 193 / 193 | 433 / 417 | 0,183 (media 0,227) |
| | Las seis competiciones | 27.220 | 1.623 / 1.633 | 1.175 / 1.171 | 2.645 / 2.654 | 0,185 (media 0,227) |
| 23-07-2026 | Serie A | 3.360 | 178 / 184 | 127 / 141 | 289 / 310 | 0,182 (media 0,212) |
| | Ligue 1 | 1.957 | 132 / 122 | 99 / 93 | 218 / 200 | 0,197 (media 0,233) |

Los goles y las asistencias de jugador salen igual de bien calibrados que en las otras ligas. **Los remates de jugador, en cambio, salen cortos en todas las ligas** (15-01-2026: 13.868 esperados frente a 16.401 reales; Serie A −12 %, Ligue 1 −10 %, Premier −22 %). No viene de las ligas nuevas: las tasas por 90' de cada jugador están bien (con los minutos reales, 0,99 de lo real), pero el paso del equipo al jugador divide los remates esperados del equipo entre su media frente a un "rival promedio" de toda la base de datos, con las ligas de segunda y las ligeras, y ese factor vale de media 0,82. Es el mismo problema que tenían los goles de jugador hasta el 20-10 (sección 4). Corregido el 22-10-2026 con la parte de los remates del equipo (sección 4).

Alineaciones: con las cinco ligas, la regresión da β ataque 0,13 ± 0,04 y β defensa 0,10 ± 0,05 en goles (7.694 equipo-partido), coherente con el 0,10 que se usa. En la Serie A el ajuste por once no cambia la log-loss (+0,0001) y en la Ligue 1 la mejora poco (−0,0006), como en la Premier.

Reproducir: `apuestas backtest --lineups --europa` con el código de antes y el de ahora (`--ligas EPL,BUN,LAL`) sobre la base de datos de antes y la de después (salidas por partido en `var/backtests/ligue1_serie_a_{antes3,antes5,despues5}_2024_2026.json`).

**Córners del local grande en la Champions frente a Pinnacle** (22-10-2026). Con la fuerza de goles como guía y las estadísticas de las copas, el modelo seguía dando al local unos 0,7 córners menos que Pinnacle en Betis-Feyenoord (4,6-4,7 frente a 5,3-4,1; Betano 5,4-4,1) y Bayern-Arsenal (4,8-4,1 frente a 5,5-4,2; Betano 5,7-4,1). Ya estaban descartados el nivel por liga, más contracción (K 40) y un sesgo del local en toda la Champions.

*De dónde sale cada número.* Bayern-Arsenal: 4,79 = exp(media 1,457 + local 0,202 + ataque del Bayern 0,500 − defensa del Arsenal 0,593). El Arsenal es el equipo que menos córners concede (2,8 en casa y 3,8 fuera en la Premier) y, en el modelo de goles, más fuerte que el Bayern (1,83 frente a 1,62; 1X2 del modelo 38/24/38, Pinnacle 43/26/32). Betis-Feyenoord: solo con la fuerza de goles salía 5,2-4,3; las desviaciones de cada equipo lo llevaban a 4,6-4,7, porque el Betis saca en LaLiga menos córners de los que le tocan por su fuerza (−0,08 de dominio) y el Feyenoord en la Eredivisie más (+0,13). Su fuerza de goles es casi igual (0,63 y 0,67), así que el modelo los veía parejos, y Pinnacle no (1X2 60/20/20).

*Descartado, con los córners reales* (walk-forward semanal 2024-08 → 2026-10, mismo modelo de producción; 2.344 partidos de liga, 414 de Champions y 738 de las otras dos copas):
- **Un sesgo del local grande.** Real frente a esperado en la Champions: local +1,8 % y visitante −0,6 %. Por fuerza del local no sale un patrón: 0,5-1,0 → −12,7 % ± 4,7 %; 1,0-1,4 → +9,7 % ± 5,3 %; más de 1,4 → +1,7 % ± 7,1 %. Entre dos grandes (fuerza ≥ 1), +8,5 % ± 5,9 % (93 partidos) y en las ligas +4,9 % ± 6,6 % (63): ruido. Esta temporada (36 partidos de Champions hasta el 19-10) el local saca un 16 % **menos** de lo esperado, al revés de lo que dice Pinnacle.
- **Que la desviación de cada equipo no sirva en Europa.** Con m(λ) = solo fuerza × (modelo / solo fuerza)^λ, el λ que mejor predice en la Champions entre ligas es 0,91 ± 0,24 (1 = la desviación se cumple entera); en las copas, 0,75 ± 0,28. Quitarla en esos partidos empeora los córners por equipo (−0,024 ± 0,014 en la Champions entre ligas). El Feyenoord en concreto rinde por debajo del modelo en Europa (−10 % de córners a favor), pero un efecto "Europa" por equipo sería ruido para casi todos.
- **Una pendiente distinta por liga** (que el fuerte domine más en una liga floja): ninguna se distingue de la general (Eredivisie +0,06 ± 0,05, LaLiga −0,02 ± 0,04, Premier +0,09 ± 0,05).
- **Una memoria más corta.** El Bayern lleva 9,7 córners por partido en la Bundesliga 2026-27 (el modelo esperaba 7,3), y Pinnacle parece pesar más esa racha: con una vida media de 120 días en vez de 240, el error por equipo frente a Pinnacle baja de 0,087 a 0,078 en los 41 partidos y el Bayern sube a 5,1. Pero predice peor los córners reales: Champions por equipo −0,0058 ± 0,0042, copas −0,0063 ± 0,0028, y esta temporada, Champions entre ligas −0,038 ± 0,019. Con 180 días, casi igual que ahora.

*La causa: la diferencia de fuerza del modelo de goles.* Si la diferencia de fuerza entre los dos fuera la del 1X2 de Pinnacle, Betis-Feyenoord saldría 5,1-4,2 y Bayern-Arsenal 5,0-3,9. Las casas ven la diferencia mejor que el modelo de goles (no le ganamos al mercado en 1X2), y los conteos la heredan. Se probó mover el reparto hacia la del 1X2 de cierre del partido (sección 3) en el mismo walk-forward, con las cuotas de cierre de Pinnacle o bet365 de 14 ligas (las tres principales y 11 ligas "light" que traen estadísticas); en la Champions y las otras copas no hay cuotas de cierre guardadas, así que ahí no se puede medir con resultados. Diferencia de log-verosimilitud por equipo y partido frente al modelo actual (el total queda igual por construcción: −0,0001 ± 0,0000 o menos):

| Peso del 1X2 | Córners: 3 ligas (2.342) | Córners: otras 11 (8.227) | Remates: 3 ligas | Remates: otras 11 | A puerta: 3 ligas | A puerta: otras 11 |
|---|---|---|---|---|---|---|
| 0,5 | +0,0062 ± 0,0017 | +0,0083 ± 0,0009 | +0,0149 ± 0,0025 | +0,0161 ± 0,0014 | +0,0085 ± 0,0019 | +0,0106 ± 0,0011 |
| **0,75 (aplicado)** | **+0,0074 ± 0,0026** | **+0,0105 ± 0,0013** | **+0,0183 ± 0,0037** | **+0,0196 ± 0,0021** | **+0,0098 ± 0,0028** | **+0,0126 ± 0,0016** |
| 1 | +0,0075 ± 0,0034 | +0,0115 ± 0,0018 | +0,0190 ± 0,0050 | +0,0200 ± 0,0028 | +0,0091 ± 0,0037 | +0,0124 ± 0,0022 |

La mejora se concentra donde la casa y el modelo de goles discrepan mucho (|δ| > 0,2, 317 partidos: córners +0,107 ± 0,020, remates +0,167 ± 0,032 por partido), que es lo habitual en la Champions (Betis-Feyenoord 0,18; Manchester City-AEK 0,34). Es igual en las tres temporadas (córners en las otras 11 ligas, con peso 1 y sin fijar el total: 2024-25 +0,0121 ± 0,0027, 2025-26 +0,0109 ± 0,0026, 2026-27 +0,0096 ± 0,0062). Con `apuestas backtest --europa` (2.132 partidos de liga, frente a `--no-count-market`): córners por equipo −4,6526 → −4,6458 (+0,0068), remates −5,8053 → −5,7897 (+0,0156), a puerta −4,3054 → −4,2967 (+0,0087); los totales, el 1X2 (0,9801), las apuestas, las tarjetas y las faltas, idénticos.

Frente a las cuotas guardadas (modelo hasta el 20-10; δ del 1X2 de Pinnacle), error de la media de córners de cada equipo:

| Córners, error por equipo | Ligas | Champions, equipos conocidos | Champions, pocos datos | Todos |
|---|---|---|---|---|
| Pinnacle (41 partidos: 25 / 9 / 7), antes | 0,073 | 0,119 | 0,082 | 0,087 |
| **Pinnacle, con el 1X2 (0,75)** | **0,072** | **0,070** | **0,075** | **0,072** |
| Betano (47 partidos: 29 / 11 / 7), antes | 0,060 | 0,129 | 0,066 | 0,082 |
| **Betano, con el 1X2 (0,75)** | **0,059** | **0,091** | **0,077** | **0,071** |

En la Champions, el error de la diferencia local − visitante frente a Pinnacle baja de 0,99 a 0,59 córners. Los equipos con pocos datos apenas cambian (y en sus mercados ya se mezcla con la casa, sección 6). En los 17 de esos partidos que ya se jugaron no se distingue nada (−0,003 ± 0,024 por partido frente al modelo actual; son muy pocos).

| Córners (local-visitante) | Pinnacle | Betano | Antes | Con el 1X2 | Reales |
|---|---|---|---|---|---|
| Betis-Feyenoord | 5,3-4,1 | 5,4-4,1 | 4,6-4,7 | 5,0-4,3 | 4-4 |
| Bayern-Arsenal | 5,5-4,2 | 5,7-4,1 | 4,8-4,1 | 4,9-4,0 | 3-5 |
| Manchester City-AEK | 7,8-2,2 | 7,9-2,3 | 6,5-3,1 | 7,1-2,5 | 8-3 |
| Porto-PSV | 5,6-4,2 | 5,9-4,0 | 5,2-4,2 | 5,4-4,0 | 2-3 |

*Lo que queda.* En Bayern-Arsenal la diferencia de fuerza apenas cambia (δ = 0,07): lo que falta es el total (Pinnacle 9,7 córners, el modelo 8,9), es decir, la racha del Bayern y que los partidos del Arsenal tienen pocos córners. Los datos no apoyan subirlo (memoria más corta, arriba), así que no se toca. En el análisis real, con las alineaciones confirmadas, "Bayern Menos de 3.5 córners" a 4,25 pasa de +57 % a +42 %: sigue saliendo con valor por ese total (el Bayern sacó 3).

Reproducir: scripts en la carpeta de notas de la sesión (`wf_cor.py` y `wf_stat.py` para el walk-forward, `cmp_cor.py`, `mkt_final.py` y `bins.py` para las cifras, `pindiag.py` y `played.py` para las casas), y `apuestas backtest --europa` con y sin `--no-count-market` (salidas en `var/backtests/conteos_mercado_{antes,despues}_2024_2026.json`).


**Remates de 2026-27: nivel reciente de cada liga** (22-10-2026). Desde julio de 2026 se remata más en casi todas las ligas. Remates por equipo en agosto-octubre de cada temporada (BD, FotMob y football-data dan lo mismo):

| Agosto-octubre | Premier | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions |
|---|---|---|---|---|---|---|
| 2023-24 | 13,5 | 13,7 | 12,6 | 12,5 | 12,7 | 13,8 |
| 2024-25 | 13,5 | 13,8 | 12,1 | 12,8 | 12,4 | 13,3 |
| 2025-26 | 11,9 | 13,3 | 12,4 | 12,3 | 12,4 | 13,6 |
| 2026-27 | 13,7 | 15,6 | 13,5 | 14,6 | 13,7 | 14,8 |

Lo mismo en las demás: Eredivisie 14,0 → 15,0, Escocia 12,4 → 14,4, Turquía 12,9 → 14,0, 2. Bundesliga 13,5 → 15,2; solo Portugal no cambia. A puerta sube en la Bundesliga (4,6 → 5,5), la Serie A (4,0 → 4,9), la Ligue 1, LaLiga y la Champions, no en la Premier. Los córners apenas cambian (Bundesliga 5,0 → 5,4; Premier 4,9 → 4,7).

*Desde cuándo.* Walk-forward semanal (agosto de 2024 a octubre de 2026, el modelo de producción reajustado cada semana con los datos anteriores), real / esperado por temporada:

| Real / esperado | Premier | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions | Otras 11 ligas |
|---|---|---|---|---|---|---|---|
| Remates 2024-25 | 0,97 → 0,99 | 0,97 → 0,99 | 0,99 → 1,00 | 0,96 → 0,99 | 0,99 → 1,00 | 1,02 → 1,01 | 0,99 → 1,00 |
| Remates 2025-26 | 0,99 → 1,01 | 1,01 → 1,01 | 1,02 → 1,00 | 0,99 → 1,00 | 1,00 → 1,01 | 1,05 → 1,02 | 1,01 → 1,01 |
| Remates 2026-27 | 1,06 → 1,01 | 1,16 → 1,05 | 1,07 → 1,05 | 1,14 → 1,06 | 1,08 → 1,01 | 1,10 → 1,05 | 1,07 → 1,02 |
| A puerta 2024-25 | 0,94 → 0,98 | 0,97 → 0,99 | 0,99 → 1,01 | 0,97 → 0,99 | 1,02 → 1,00 | 1,04 → 1,03 | 0,99 → 1,00 |
| A puerta 2025-26 | 0,96 → 1,00 | 1,03 → 1,02 | 1,02 → 1,01 | 0,98 → 1,00 | 0,97 → 1,00 | 1,08 → 1,04 | 1,00 → 1,01 |
| A puerta 2026-27 | 0,98 → 0,98 | 1,15 → 1,05 | 1,07 → 1,04 | 1,16 → 1,09 | 1,08 → 1,04 | 1,17 → 1,10 | 1,05 → 1,02 |

(antes → con el nivel). Mes a mes, el hueco aparece de golpe en agosto-septiembre de 2026; antes, en toda una temporada ninguna liga se separaba más de un 3-4 % (la Premier, la Bundesliga y la Serie A de 2024-25, en las que el modelo esperaba un 3 % de más). En las cinco ligas, por equipo: en 2026-27, 12,9 remates esperados → 13,7 (reales 14,1); en octubre de 2026, 13,1 → 14,1 (reales 14,3); a puerta en octubre, 4,5 → 4,8 (reales 5,0). Lo que queda corto es sobre todo el arranque de la temporada (agosto), hasta que el nivel tiene partidos nuevos, y los remates a puerta de la Serie A y la Champions, que siguieron subiendo en octubre.

*Variantes* (mejora de la log-verosimilitud por equipo y partido frente al modelo de antes, en el mismo walk-forward; positivo = mejor):

| Variante | Remates, 5 ligas: 24-25 / 25-26 / 26-27 | A puerta, Champions: 24-25 / 25-26 / 26-27 |
|---|---|---|
| Todo el modelo con vida media de 120 días | +0,0095 / +0,0022 / +0,0306 | +0,0078 / −0,0238 / −0,0175 |
| Nivel de liga, vida media 120 días (K 10) | +0,0016 / −0,0000 / +0,0172 | −0,0089 / +0,0026 / +0,0124 |
| Nivel de liga, 60 días (K 10) | +0,0037 / +0,0003 / +0,0388 | −0,0142 / +0,0009 / +0,0316 |
| Nivel de liga, 45 días (K 10) | +0,0042 / +0,0002 / +0,0472 | −0,0164 / +0,0000 / +0,0389 |
| 45 días, contraído hacia todas, más desvío de copa | +0,0043 / +0,0003 / +0,0548 | −0,0058 / +0,0243 / +0,0640 |
| **30 días, contraído hacia todas, más desvío de copa (aplicada)** | **+0,0050 / +0,0000 / +0,0665** | **−0,0078 / +0,0220 / +0,0714** |
| 20 días, ídem | +0,0054 / −0,0007 / +0,0711 | −0,0098 / +0,0244 / +0,0720 |
| Nivel por temporada (solo la actual, K 10), más desvío de copa | +0,0014 / −0,0014 / +0,0647 | −0,0092 / +0,0228 / +0,0649 |
| Techo: el desvío real de cada liga y temporada, sabido de antemano | +0,0059 / +0,0010 / +0,0904 | +0,0080 / +0,0284 / +0,1224 |

- **Memoria corta solo para el nivel, no para todo el modelo.** Acortar la vida media de todo el modelo de remates (120 días) también ayuda en 2026-27, pero mucho menos y empeora la Champions (a puerta −0,024 en 2025-26 y −0,018 en 2026-27): la fuerza de cada equipo necesita memoria larga; el nivel de la liga, no.
- **Contraído hacia todas las competiciones** mejora 2026-27 (+0,044 frente a +0,039 con 60 días) sin cambiar nada antes: el cambio es común a casi todas las ligas.
- **Desvío de copa.** Si la copa solo toma la media de las ligas, en la Champions empeoran los remates a puerta de 2024-25 (−0,014 ± 0,003), porque ese año las ligas remataban a puerta menos de lo esperado y la Champions más. Con el desvío propio queda en −0,008 ± 0,004 (ruido) y mejora 2025-26 y 2026-27. Su vida media (120 días) y K (30) son más largas que las de las ligas porque la Champions tiene pocos partidos y su desvío se repite de temporada en temporada.
- **30 días** es el mejor compromiso: 20 días mejora un poco más 2026-27 pero empieza a empeorar 2025-26 y la Champions de 2024-25. K entre 3 y 30 casi no cambia nada (con 60 días: +0,042, +0,039 y +0,032 en 2026-27).
- **Por temporada** (todos los partidos de la temporada actual con el mismo peso) da lo mismo en 2026-27, pero empeora un poco 2025-26 y las otras 11 ligas (−0,003 ± 0,001 en 2024-26).
- **Córners**: con el mismo nivel, −0,0012, −0,0005 y −0,0019 en las cinco ligas y −0,023 ± 0,007 en la Europa League y la Conference de 2026-27. No se aplica.

Resultado de la variante aplicada, con el error estándar pareado (remates · a puerta, por equipo):

| Grupo | 2024-25 | 2025-26 | 2026-27 |
|---|---|---|---|
| 5 ligas | +0,0050 ± 0,0025 · +0,0015 ± 0,0024 | +0,0000 ± 0,0016 · −0,0002 ± 0,0028 | +0,067 ± 0,016 · +0,023 ± 0,010 |
| Champions | +0,0027 ± 0,0052 · −0,0078 ± 0,0043 | +0,0069 ± 0,0088 · +0,022 ± 0,012 | +0,060 ± 0,026 · +0,071 ± 0,028 |
| Otras 11 ligas | +0,0009 ± 0,0012 · +0,0001 ± 0,0015 (2024-26) | | +0,038 ± 0,009 · +0,008 ± 0,005 |
| Europa League y Conference | −0,0012 ± 0,0030 · −0,0052 ± 0,0029 (2024-26) | | +0,027 ± 0,016 · +0,014 ± 0,010 |

En la Europa League y la Conference los remates a puerta de 2024-26 empeoran un poco (−0,005 ± 0,003); esas copas solo sirven para entrenar, no se analizan en el panel.

Con `apuestas backtest --europa` por temporada, frente a `--no-count-level` (log-verosimilitud por equipo y partido): remates en las ligas −5,7730 → −5,7680 (2024-25), −5,7756 → −5,7758 (2025-26) y −6,0711 → −6,0047 (2026-27, 346 partidos hasta el 21-10); a puerta −4,2910 → −4,2895, −4,2961 → −4,2962 y −4,4723 → −4,4501; en la Champions, remates −6,0336 → −6,0309, −5,8715 → −5,8638 y −5,9200 → −5,8691, y a puerta −4,5514 → −4,5592, −4,6298 → −4,6056 y −4,6036 → −4,5384. El 1X2 (0,9708, 0,9790 y 0,9561), las apuestas, los córners, las faltas y las tarjetas, idénticos.

*Faltas y tarjetas*: un nivel de liga de 60 días, sin desvío de copa, mejora las cinco ligas (tarjetas +0,0051 ± 0,0021 en 2024-25 y +0,0086 ± 0,0059 en 2026-27; faltas +0,0065 ± 0,0026 en 2025-26 y +0,017 ± 0,007 en 2026-27), pero empeora las copas (tarjetas en la Champions de 2024-25 −0,007 ± 0,004, faltas en la de 2026-27 −0,014 ± 0,014) y las dos pasan por el factor del árbitro. El modelo de tarjetas, además, espera de más en casi todas las ligas (real / esperado 0,93-1,00 en 2024-26 y 0,86-0,89 en la Serie A, la Ligue 1 y la Bundesliga de 2026-27). Las faltas quedan sin aplicar ("Próximas mejoras"); las tarjetas lo llevan desde el 22-10-2026, con sus propios parámetros (abajo, "Tarjetas: nivel reciente de cada liga").

Reproducir: scripts en la carpeta de notas de la sesión (`nivel-liga/`: `wf.py` para el walk-forward en paralelo, `ana.py` para las cifras, `oraculo.py` para el techo y `nivel_hoy.py` para los niveles de hoy), y `apuestas backtest --europa --start … --end …` con y sin `--no-count-level`.

**Tarjetas: nivel reciente de cada liga** (22-10-2026). El modelo de tarjetas del equipo se pasaba en casi todas las competiciones: en el walk-forward semanal de 2024-08 a 2026-10, 1,049 de lo real en las ligas (Premier 1,048, Bundesliga 1,061, LaLiga 1,020, Serie A 1,079, Ligue 1 1,045) y 1,075 en la Champions. No es el árbitro (su factor vale de media 1,00 en cada liga), sino que las tarjetas bajan de temporada en temporada y, dentro de cada temporada, de la primera vuelta a la segunda (Serie A 2023-24: 2,29 y 2,04 por equipo; 2026-27: 1,68), y el modelo, con 240 días de vida media, va por detrás.

*Primera exploración* (nivel de la competición del partido, contraído hacia 1; solo el modelo de tarjetas, en el mismo walk-forward; diferencia de log-verosimilitud por equipo y partido, con el árbitro, frente al modelo actual; ligas: 3.849 partidos, Champions: 423):

| Variante | Ligas (esperadas / reales) | Premier | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions |
|---|---|---|---|---|---|---|---|
| Modelo actual | 1,049 | | | | | | |
| Nivel de 30 días, K 20 | +0,0049 ± 0,0015 (1,027) | +0,0084 ± 0,0042 | +0,0020 ± 0,0031 | +0,0018 ± 0,0030 | +0,0086 ± 0,0032 | +0,0025 ± 0,0028 | +0,0032 ± 0,0039 |
| Nivel de 30 días, K 10 | +0,0047 ± 0,0018 (1,022) | +0,0085 | +0,0013 | +0,0013 | +0,0093 | +0,0022 | +0,0028 |
| Nivel de 60 días, K 20 | +0,0039 ± 0,0013 (1,025) | +0,0047 | +0,0023 | +0,0004 | +0,0088 | +0,0028 | +0,0038 |
| Nivel de 120 días, K 20 | +0,0032 ± 0,0009 (1,027) | +0,0028 | +0,0033 | −0,0003 | +0,0075 | +0,0024 | +0,0042 |
| Nivel de 180 días, K 20 | +0,0025 ± 0,0007 (1,032) | +0,0015 | +0,0032 | −0,0004 | +0,0061 | +0,0023 | +0,0028 |
| Solo un nivel largo (365 días) | +0,0003 ± 0,0004 (1,044) | −0,0030 | +0,0015 | −0,0008 | +0,0023 | +0,0024 | −0,0022 |
| 30 días, contraído hacia el de 365 | +0,0049 ± 0,0015 (1,025) | +0,0078 | +0,0024 | +0,0015 | +0,0090 | +0,0029 | +0,0020 |
| Modelo con vida media de 120 días | −0,0009 ± 0,0012 (1,043) | −0,0013 | +0,0019 | −0,0025 | −0,0030 | +0,0013 | −0,0035 |

Memoria corta (30 días) para el nivel, sí; para todo el modelo, no; un nivel largo no aporta (el de cada liga ya lo recogen sus equipos). Lo que queda es sobre todo el retraso de un nivel que no deja de bajar; el mes a mes es muy ruidoso (septiembre suele tener más tarjetas y agosto menos), así que no se ajusta por fecha de la temporada.

*Con el nivel de los remates* (`fitting.count_levels`, fusionado el mismo día; el nivel por liga va dentro del modelo de conteo). Se probaron sus parámetros en las tarjetas con `apuestas backtest --europa` frente a `--no-count-level` (3.504 partidos de liga y 378 de Champions en 2024-26; 345 y 45 en 2026-27; diferencia de log-verosimilitud por equipo y partido):

| Variante | Ligas 2024-26 | Ligas 2026-27 | Champions 2024-26 | Champions 2026-27 | Ligas, con árbitro 2024-26 |
|---|---|---|---|---|---|
| Como los remates (K 10; copas: media de las ligas más su desvío, 120 días, K 30) | +0,0042 ± 0,0020 | +0,0105 ± 0,0093 | −0,0059 ± 0,0046 | +0,0024 ± 0,021 | +0,0050 |
| K 20 | +0,0050 ± 0,0017 | +0,0123 ± 0,0086 | −0,0043 ± 0,0043 | +0,0060 ± 0,020 | +0,0056 |
| K 20, desvío de copa de 30 días y K 20 | +0,0050 | +0,0123 | −0,0048 ± 0,0051 | +0,0047 | +0,0056 |
| 60 días, K 10 | +0,0028 ± 0,0015 | +0,0099 ± 0,0065 | −0,0039 ± 0,0042 | +0,0044 | +0,0034 |
| K 20, en las copas solo el nivel de la copa (30 días, K 20) | +0,0050 | +0,0123 | +0,0013 ± 0,0040 | +0,0100 ± 0,0066 | +0,0056 |
| **K 20, en las copas solo el de la copa (120 días, K 30; aplicada)** | **+0,0050 ± 0,0017** | **+0,0123 ± 0,0086** | **+0,0016 ± 0,0032** | **+0,0167 ± 0,0106** | **+0,0056 ± 0,0017** |
| Primera exploración (nivel de la competición, 30 días, K 20, hacia 1) | +0,0041 ± 0,0016 | +0,0066 ± 0,0057 | +0,0011 ± 0,0043 | +0,0107 ± 0,0073 | +0,0047 |

- **Contraído hacia todas las competiciones** (como los remates) es mejor que hacia 1 en las ligas, sobre todo en 2026-27: las tarjetas bajan en casi todas a la vez.
- **En las copas, solo el nivel de la copa** (`cup_alone` en el modelo de tarjetas). Con la media de las ligas de los dos equipos, la Champions empeora en 2024-26 (−0,004 a −0,006), con cualquier desvío de copa: en tarjetas, la Champions no sigue a las ligas de sus equipos (en las eliminatorias, de febrero a abril, se ven 1,3-1,8 por equipo; en las ligas, 1,9-2,1).
- **Árbitro.** Se ajusta frente al modelo sin el nivel (`RatingModel.expected(..., level=False)`): el nivel de hoy no vale para partidos de hace años. En la primera exploración, ajustarlo frente al nivel de la fecha de cada partido daba lo mismo (+0,0050 frente a +0,0049).

Variante aplicada, por liga (por equipo, 2024-26): Premier +0,0080 ± 0,0050, Bundesliga +0,0015 ± 0,0034, LaLiga +0,0042 ± 0,0034, Serie A +0,0078 ± 0,0034, Ligue 1 +0,0021 ± 0,0032; Europa League −0,0029 ± 0,0019 y Conference −0,0030 ± 0,0031 (no se analizan en el panel). En 2026-27: Serie A +0,032 ± 0,024, Ligue 1 +0,033 ± 0,023, Bundesliga +0,007 ± 0,027, Premier −0,004 ± 0,012, LaLiga −0,002 ± 0,011; Conference −0,039 ± 0,015 (18 partidos). En valores: tarjetas por equipo en las ligas −3,3214 → −3,3165 (2024-26) y −3,2199 → −3,2076 (2026-27); total −2,1103 → −2,1053; con el árbitro −2,1063 → −2,1006; Champions por equipo −3,2432 → −3,2415 y −3,1788 → −3,1621. El 1X2 (0,9727), las apuestas y el resto de estadísticas, idénticos.

Reproducir: `wf_tarj.py` y `wf_tarj2.py` (primera exploración), `ana_tabla.py` (su tabla), `bt_tarj2.py` + `cmp_var.py` (`apuestas backtest --europa` partido a partido con los parámetros de tarjetas) y `medir_tarjetas.py --semanal` (jugadores, sección 4), en las notas de la sesión del 22-10-2026.

**Lectura**:
1. En los mercados principales, **bet365 sigue siendo más preciso que el modelo**, también con los ratings del mercado. Ahora el modelo está mucho más cerca (lo que hacen los profesionales), pero no hay ninguna estrategia rentable en 1X2, goles o hándicap. Con el modelo tan cerca del mercado, las pocas "apuestas con valor" que quedan son sobre todo ruido: el ROI no mejora aunque el CLV sí lo haga un poco.
2. bet365 casi nunca paga más que la probabilidad justa de Pinnacle en 1X2 o goles 2.5 (4 casos en dos años), así que comparar casas no sirve con bet365 en esos mercados.
3. El cierre de Pinnacle (0,963) es mucho mejor que su cuota previa (0,976): entre la previa y el partido llega mucha información (alineaciones, noticias). El índice de calidad del once solo capta una parte (β = 0,10).
4. Donde el modelo sí aporta información (faltas, remates, tarjetas, jugadores) es justo donde las casas tienen menos precisión. Ahí hay que comparar las cuotas de Betano con la **cuota mínima** que da el sistema. El árbitro ayuda en las tarjetas de LaLiga, la Serie A y la Bundesliga, no en las de la Premier, y en las faltas de la Ligue 1.

Reproducir: `apuestas backtest --lineups --europa --out var/backtests/x.json` (desde el 21-10-2026 evalúa por defecto las cinco ligas completas; `--ligas EPL,BUN,LAL` para las cifras de antes; `--market-weight 0` para el modelo sin mercado; `--no-count-strength` para las estadísticas sin la fuerza de goles, `--no-count-market` para remates y córners sin el 1X2 de la casa, `--no-count-level` para remates, a puerta y tarjetas sin el nivel reciente de cada liga, y `--count-l2 1` para la L2 fija de antes).

## 8. Resumen de la semana: sorpresa frente a lo esperado (`models/surprise.py`, `services/weekly.py`)

No cambia el modelo ni las apuestas (no hace falta backtest): resume cada semana quién superó lo esperado.

- **Puntuación de cada dato**: `P(X < real) − P(X > real)` con la distribución esperada, de −1 a +1 (0 = lo
  esperado). Cuenta el margen: con 9,9 córners esperados, 10 suma +0,09, 12 +0,43, 15 +0,77 y 6 −0,65.
- **Resultado**: `(puntos − puntos esperados) / 3`, con el 1X2 sin margen. Ganar con un 15 % de probabilidad suma
  +0,77; ganar con un 75 %, +0,19; empatar siendo ese favorito, −0,47.
- **Equipos, frente a la casa** (la última cuota antes del inicio de cada tipo; el cierre primero):
  - Resultado: 1X2 de Pinnacle, Betfair, bet365, Betano o la media, en ese orden; si no hay, el de la previa.
  - Goles y córners de cada equipo: la línea principal (la más cercana al 50 % sin margen) de Pinnacle o Betano. Con
    esa línea y su probabilidad se despeja la media de una Poisson (goles) o de la binomial negativa del modelo
    (córners, con su alfa). Sin línea de goles por equipo, los goles implícitos en el 1X2 y el más/menos 2.5
    (`fitting.prematch_market_goals`); si tampoco, la previa del modelo.
  - Los remates a puerta no cuentan: ninguna casa los cotiza.
- **Jugadores, frente a la previa del modelo** (`services/predictions.py`): remates y remates a puerta (binomial
  negativa, alfa 0,15), goles y asistencias (Poisson). La tasa se ajusta a los minutos jugados (`λ × minutos /
  minutos esperados`), para medir cómo jugó y no que entrara en el once por sorpresa. Hacen falta 30 minutos.
  Porteros y defensas con 60 minutos o más suman además los goles recibidos frente a la vara de goles del rival, con
  el signo cambiado.
- **Semana**: la suma de los partidos (se muestran también los partidos jugados y la media). Once en 4-3-3 por
  posición.
- **Límites**: el dato tiene techo (un gol con λ 0,08 suma +0,92 y dos +0,997), así que el detalle muestra lo real
  y lo esperado. Sumar favorece a quien jugó dos partidos. El jugador de la semana suele ser un delantero: tiene más
  datos con recorrido al alza. Una semana buena es en parte suerte: no predice la siguiente.

### Mes, radar y avisos (`services/radar.py`, desde el 29-10-2026)

- **Mes**: las 4 semanas completas que terminan en la semana elegida, con la misma puntuación (`weekly.score_range`).
  Se abre cuando sus 4 semanas tienen previa (la primera, del 26-10 al 22-11-2026).
- **Radar**, sobre los últimos 28 días: un equipo está **en racha** con una suma de +1,0 o un **batacazo** (ganar cuando
  el 1X2 sin margen de la vara daba un 25 % o menos) y **en baja** con −1,0 o un **pinchazo** (perder con un 60 % o
  más). Jugadores en racha: +1,5 y 90 minutos. Figuras: hasta 2 jugadores del equipo con +1,5 en sus partidos. Como
  mucho 8 por lista.
- **Avisos**: la ficha del radar de cada equipo de un partido próximo, con sus figuras en el once o no. **No cambian
  la probabilidad, la confianza ni el corte**: falta medir si los que dan la sorpresa la repiten.
- **Por qué falló**: la previa frente a lo que pasó en la apuesta del día perdida, con la misma puntuación, y si el
  radar marcaba a alguno de los equipos cuando se generó la apuesta. Ejemplo real: Sassuolo +1 (3 vías) del 27-10
  perdió 2-6; Lazio estaba en racha tras ganar 0-3 en Turín con un 17 % y su figura Kenneth Taylor jugó.

## Próximas mejoras previstas

- **¿Se repiten las sorpresas?** Con el historial de equipos (desde 2023, con cuotas de cierre), medir si los que dan un batacazo o un pinchazo siguen sorprendiendo en los partidos siguientes o vuelven a la media. Si se repite, proponer que el aviso del radar baje la confianza; si no, que el aviso lo diga.
- **Propuestas de la auditoría de octubre de 2026** ([auditoria-modelo.md](auditoria-modelo.md), experimentos en `experimentos/auditoria/`), por orden: arreglar el valor de las líneas de cuarto y guardar fija la apuesta anunciada; fuerza de goles dinámica (filtro de Kalman, −0,0047 ± 0,0007 de log-loss frente a `ratings.fit` con los mismos datos, −0,0062 si además observa los remates a puerta); dispersión del total calibrada fuera de muestra en los conteos (+0,004 a +0,006 por partido en remates, córners, faltas y tarjetas); apilado aprendido con el mercado en lugar de `W_MODEL`; y decidir por la probabilidad de valor positivo con Kelly contraído. Todo con datos públicos sin xG ni Pinnacle: cada cambio necesita su `apuestas backtest` con la BD antes de entrar.
- Un nivel por liga en el modelo de fuerza (nivel de la liga + desviación del equipo) y, si el backtest lo confirma, entrenar con las ligas extra de football-data, que ya se descargan (ver "Copas europeas" arriba).
- Guardar cuotas de 1X2 de la Champions antes de cada partido (ya se guardan las de OddsPapi desde el 19-10-2026) para medir con resultados el reparto de remates y córners movido por el 1X2 en las copas, que hoy solo se mide en las ligas.
- Guardar el historial de onces previstos para calibrar su β por separado.
- Un índice de calidad del once más informativo (contribución reciente en xG/xA, minutos), porque el cierre muestra mucha más información de alineación de la que capta el índice actual.
- Medir la antigüedad de las observaciones del mercado en jornadas en lugar de días, para no perder el mercado durante el parón de verano.
- Backtest de props cuando haya cuotas guardadas de Betano (OddsPapi).
- Faltas con el nivel reciente de cada liga (como los remates y las tarjetas desde el 22-10-2026): mejora las cinco ligas pero empeora las copas, y pasa por el factor del árbitro (sección 7, "Remates de 2026-27").
- Tarjetas del equipo en 2026-27: con el nivel de cada liga, la Serie A y la Bundesliga quedan en 1,04-1,05 y la Champions en 1,09 (aún algo altas: las tarjetas siguen bajando), y la Premier en 0,94 (en 2026-27 sube, al revés que las demás, y el nivel la contrae hacia el de todas). Volver a medirlo cuando haya más partidos de la temporada.
- Suplentes del once confirmado: el modelo supone que cada uno sale el 55 % de las veces y juega 22 minutos; de julio a octubre de 2026 salió el 45 % y jugó 20 (todos sus mercados salen algo altos). Y las apuestas a un suplente que no sale se anulan, así que su probabilidad debería ser la de si sale; hoy cuenta que puede no salir («Sí» sale bajo y «No» alto).
- Minutos sin alineación de un jugador que vuelve de una lesión larga: los partidos en que estuvo de baja cuentan como 0 (sección 4). Con el histórico de bajas que se guarda desde el 19-10-2026 se podrán quitar de su ventana; medirlo con `medir_minutos.py` cuando haya unos meses.
