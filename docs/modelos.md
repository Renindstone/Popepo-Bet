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

- **Árbitro**: factor = (observado + K) / (esperado + K), con K en partidos "neutros". En **faltas** mejora la predicción (K = 20). En **tarjetas**, medido de nuevo con los árbitros de LaLiga y la Bundesliga (FotMob), K = 80. Ayuda claramente en LaLiga y algo en la Bundesliga; en la Premier no ayuda (ver backtest).
- **Alineación**: un once más fuerte de lo habitual genera más remates y córners (efecto atenuado, exponente 0,7).

## 4. Jugadores (`services/analysis.py::_player_projections`)

Tasas por 90' ponderadas por antigüedad (remates, a puerta, goles, xG, asistencias, xA, faltas, amarillas), **contraídas hacia la media de su posición** (equivalente a 4 partidos). Minutos esperados según la alineación: confirmado titular, previsto (85 %), suplente o sin alineación (frecuencia de titularidad). Remates, faltas y tarjetas se escalan por el volumen esperado del equipo en ese partido.

**Goles y asistencias: parte de los goles del equipo** (desde el 20-10-2026). Para cada jugador se calcula qué parte de los goles de su equipo marca, asiste, y su xG y xA, **en los minutos que jugó** (goles del equipo × minutos/90 como exposición), contraída hacia la de su posición con unos 6 goles de equipo de peso. Goles esperados del jugador = (½ parte de goles + ½ parte de xG) × minutos esperados/90 × goles esperados de su equipo en ese partido; igual con asistencias y xA. "Gol o asistencia" suma las dos (un jugador no se asiste a sí mismo).

Antes se usaban las tasas por 90' escaladas contra la media del equipo "frente a un rival promedio". Ese rival promedio sale de todas las ligas de la BD, incluidas las de segunda y las ligas ligeras, y por eso infla la media de los equipos de las ligas grandes: sus goles reales fueron el 78 % (Premier), 91 % (Bundesliga) y 90 % (LaLiga) de esa media. Los goles de jugador salían bajos en todos los equipos. Comprobación fuera de muestra (modelo entrenado antes del periodo, Premier, Bundesliga, LaLiga y Champions):

| Periodo | Mercado | Esperado antes | Esperado ahora | Real | Log-loss antes → ahora |
|---|---|---|---|---|---|
| 90 días (10.969 jugadores-partido) | Gol | 578 | 712 | 731 | 0,2012 → 0,1981 |
| | Asistencia | 427 | 531 | 550 | 0,1759 → 0,1732 |
| | Gol o asistencia | 957 | 1.170 | 1.190 | 0,2840 → 0,2788 |
| 45 días (7.618) | Gol | 390 | 482 | 530 | 0,2098 → 0,2062 |
| | Gol o asistencia | 647 | 793 | 869 | 0,2996 → 0,2929 |

En los últimos 45 días aún se queda un 9 % corto (en 90 días, un 2-3 %). **Ningún mercado de jugador tiene backtest contra cuotas**: esta comprobación mide que las probabilidades estén bien calibradas, no que ganen a las casas.

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
- **Confianza** (0-1) = alineación (confirmada 1 · prevista 0,85 · solo bajas 0,72) × muestra × tipo de mercado (principal 1 / estadísticas 0,75 / jugador 0,65) × acuerdo modelo-mercado × riesgo de rotación × cobertura del mercado (abajo).
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

**Por qué no el nivel por liga.** Con tan pocos partidos entre ligas, el nivel de cada liga sale con mucho ruido: la Eredivisie, con 14 partidos ponderados, queda casi al nivel de la Segunda española, y la belga sale tan baja que el Brujas tendría menos córners que el Lens en su campo. Mejora el reparto de las ligas, pero en la Champions apenas (+0,007 ± 0,031 entre ligas) y estropea casos que estaban bien (Porto-PSV, Brujas-Lens). Con la fuerza como guía, el nivel de cada liga sale del modelo de goles, que tiene muchos más datos para comparar ligas (cuotas de cierre y todos los partidos de las tres copas europeas). Juntar las dos cosas es peor que la fuerza sola.

**Lo que queda.** Con equipos grandes aún hay diferencias con Pinnacle: Betis-Feyenoord (4,8-4,9 frente a 5,3-4,1) y Bayern-Arsenal (4,6-4,2 frente a 5,5-4,2). En el análisis del 21-10, "Córners de Feyenoord: Más de 7.5" a 9,00 pasa de +108 % a +41 %, pero su confianza sube de 0,36 a 0,73, porque el modelo y la casa discrepan menos (sección 6). Los córners no pueden ser apuesta del día (solo los mercados de goles).

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

**Lectura**:
1. En los mercados principales, **bet365 sigue siendo más preciso que el modelo**, también con los ratings del mercado. Ahora el modelo está mucho más cerca (lo que hacen los profesionales), pero no hay ninguna estrategia rentable en 1X2, goles o hándicap. Con el modelo tan cerca del mercado, las pocas "apuestas con valor" que quedan son sobre todo ruido: el ROI no mejora aunque el CLV sí lo haga un poco.
2. bet365 casi nunca paga más que la probabilidad justa de Pinnacle en 1X2 o goles 2.5 (4 casos en dos años), así que comparar casas no sirve con bet365 en esos mercados.
3. El cierre de Pinnacle (0,963) es mucho mejor que su cuota previa (0,976): entre la previa y el partido llega mucha información (alineaciones, noticias). El índice de calidad del once solo capta una parte (β = 0,10).
4. Donde el modelo sí aporta información (faltas, remates, tarjetas, jugadores) es justo donde las casas tienen menos precisión. Ahí hay que comparar las cuotas de Betano con la **cuota mínima** que da el sistema. El árbitro ayuda en las tarjetas de LaLiga y la Bundesliga, no en las de la Premier.

Reproducir: `apuestas backtest --lineups --europa --out var/backtests/x.json` (`--market-weight 0` para el modelo sin mercado; `--no-count-strength` para las estadísticas sin la fuerza de goles, y `--count-l2 1` para la L2 fija de antes).

## Próximas mejoras previstas

- Un nivel por liga en el modelo de fuerza (nivel de la liga + desviación del equipo) y, si el backtest lo confirma, entrenar con las ligas extra de football-data, que ya se descargan (ver "Copas europeas" arriba).
- Con las estadísticas de la Europa League y la Conference (desde el 21-10-2026) hay casi el doble de cruces entre ligas en córners y remates: volver a probar un nivel por liga en esos modelos, que sin ellas no mejoraba frente a la fuerza de goles (ver "Córners y remates entre ligas" arriba).
- Guardar el historial de onces previstos para calibrar su β por separado.
- Un índice de calidad del once más informativo (contribución reciente en xG/xA, minutos), porque el cierre muestra mucha más información de alineación de la que capta el índice actual.
- Medir la antigüedad de las observaciones del mercado en jornadas en lugar de días, para no perder el mercado durante el parón de verano.
- Backtest de props cuando haya cuotas guardadas de Betano (OddsPapi).
