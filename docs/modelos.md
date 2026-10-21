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

| Estadísticas (log-verosimilitud por partido) | Mejora frente a la media de la liga |
|---|---|
| Faltas | +0,151 (árbitro: +0,006 más) |
| Remates | +0,035 |
| Remates a puerta | +0,023 |
| Tarjetas | +0,013 (árbitro: +0,004 más) |
| Córners | +0,007 |

**Lectura**:
1. En los mercados principales, **bet365 sigue siendo más preciso que el modelo**, también con los ratings del mercado. Ahora el modelo está mucho más cerca (lo que hacen los profesionales), pero no hay ninguna estrategia rentable en 1X2, goles o hándicap. Con el modelo tan cerca del mercado, las pocas "apuestas con valor" que quedan son sobre todo ruido: el ROI no mejora aunque el CLV sí lo haga un poco.
2. bet365 casi nunca paga más que la probabilidad justa de Pinnacle en 1X2 o goles 2.5 (4 casos en dos años), así que comparar casas no sirve con bet365 en esos mercados.
3. El cierre de Pinnacle (0,963) es mucho mejor que su cuota previa (0,976): entre la previa y el partido llega mucha información (alineaciones, noticias). El índice de calidad del once solo capta una parte (β = 0,10).
4. Donde el modelo sí aporta información (faltas, remates, tarjetas, jugadores) es justo donde las casas tienen menos precisión. Ahí hay que comparar las cuotas de Betano con la **cuota mínima** que da el sistema. El árbitro ayuda en las tarjetas de LaLiga y la Bundesliga, no en las de la Premier.

Reproducir: `apuestas backtest --lineups --europa --out var/backtests/x.json` (`--market-weight 0` para el modelo sin mercado).

## Próximas mejoras previstas

- Un nivel por liga en el modelo de fuerza (nivel de la liga + desviación del equipo) y, si el backtest lo confirma, entrenar con las ligas extra de football-data, que ya se descargan (ver "Copas europeas" arriba).
- Guardar el historial de onces previstos para calibrar su β por separado.
- Un índice de calidad del once más informativo (contribución reciente en xG/xA, minutos), porque el cierre muestra mucha más información de alineación de la que capta el índice actual.
- Medir la antigüedad de las observaciones del mercado en jornadas en lugar de días, para no perder el mercado durante el parón de verano.
- Backtest de props cuando haya cuotas guardadas de Betano (OddsPapi).
