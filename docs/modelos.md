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

Tasas por 90' ponderadas por antigüedad (remates, a puerta, goles, xG, faltas, amarillas), **contraídas hacia la media de su posición** (equivalente a 4 partidos). Minutos esperados según la alineación: confirmado titular, previsto (85 %), suplente o sin alineación (frecuencia de titularidad). La tasa se escala por el volumen esperado del equipo en ese partido.

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
- **Confianza** (0-1) = alineación (confirmada 1 · prevista 0,85 · solo bajas 0,72) × muestra × tipo de mercado (principal 1 / estadísticas 0,75 / jugador 0,65) × acuerdo modelo-mercado × riesgo de rotación.
- **Apuesta del día**: máxima `valor × confianza` con cuota entre 1,50 y 2,60, prob ≥ 42 %, valor ≥ 3 % y confianza ≥ 0,60. **Si ninguna cumple, no hay apuesta del día.**
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

**Árbitro en tarjetas** (mejora de log-verosimilitud por partido frente al modelo sin árbitro; 2.105 partidos):

| K | Total | Premier | Bundesliga | LaLiga |
|---|---|---|---|---|
| 20 | +0,0041 | −0,0105 | +0,0066 | +0,0170 |
| 40 | +0,0048 | −0,0066 | +0,0060 | +0,0155 |
| **80** | **+0,0044** | −0,0034 | +0,0046 | +0,0122 |
| 120 (anterior) | +0,0037 | −0,0022 | +0,0036 | +0,0099 |
| 250 | +0,0024 | −0,0009 | +0,0021 | +0,0061 |

K = 80 mejora a 120 en +0,0006 ± 0,0004. K = 40 da algo más de media, pero con más varianza. En la Premier el historial del árbitro no predice las tarjetas con ningún K (−0,003 ± 0,002 con K = 80). No se ha puesto una excepción por liga para no ajustarla a la misma muestra. En faltas se mantiene K = 20 (con 40 la diferencia es menor que su error).

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

Reproducir: `apuestas backtest --lineups --out var/backtests/x.json` (`--market-weight 0` para el modelo sin mercado).

## Próximas mejoras previstas

- Un índice de calidad del once más informativo (contribución reciente en xG/xA, minutos), porque el cierre muestra mucha más información de alineación de la que capta el índice actual.
- Medir la antigüedad de las observaciones del mercado en jornadas en lugar de días, para no perder el mercado durante el parón de verano.
- Backtest de props cuando haya cuotas guardadas de Betano (OddsPapi).
