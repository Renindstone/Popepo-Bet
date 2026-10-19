# Modelos y validación

## 1. Fuerza de equipos (`models/ratings.py`)

Modelo multiplicativo tipo Poisson ajustado **a la vez para 17 ligas**:

```
log E[goles_local]     = mu + ventaja_local + ataque[local]     - defensa[visitante]
log E[goles_visitante] = mu                 + ataque[visitante] - defensa[local]
```

- **Objetivo**: 15 % goles + 85 % xG (el xG predice mejor que los goles; el peso se eligió con el backtest).
- **Antigüedad**: vida media de 240 días (probados 120, 240 y 400).
- **Regularización L2**: los equipos con pocos partidos (ascendidos, rivales exóticos de Champions) se acercan a la media.
- **Escala común**: los partidos de Champions/Europa y los ascensos/descensos (Championship, 2. Bundesliga, Segunda) conectan las ligas. Así un ascendido o un rival portugués de Champions tienen un rating comparable.
- **Fichajes**: el ajuste por alineación (abajo) usa el valor de mercado y el rating de cada jugador. Un fichaje entra en la alineación con su calidad, aunque el equipo aún tenga pocos partidos con él. Los fichajes se detectan cuando un jugador aparece con otro equipo (tabla `transfer`).

## 2. Goles y mercados (`models/distributions.py`, `services/match_model.py`)

Matriz de marcadores **Dixon-Coles**, con ρ estimado sobre los datos. De ahí salen 1X2, doble oportunidad, empate no válido, hándicap asiático (incluidas las líneas de cuarto, con medias ganadas o perdidas), hándicap europeo, más/menos goles (total y por equipo) y ambos marcan.

## 3. Estadísticas: remates, a puerta, córners, faltas y tarjetas

Mismo modelo de fuerza aplicado a cada estadística (cuánto genera cada equipo y cuánto concede), con distribución **binomial negativa** (la sobredispersión se estima de los datos). Los totales del partido salen de la convolución de ambos equipos.

- **Árbitro**: factor = (observado + K) / (esperado + K), con K en partidos "neutros". En **faltas** mejora la predicción (K = 20). En **tarjetas**, con datos sobre todo de la Premier, el backtest no mostró mejora, así que se aplica muy contraído (K = 120). Se volverá a medir cuando estén los árbitros de LaLiga y la Bundesliga.
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
`goles_a_favor × exp(0,30 × Δataque)` y `goles_en_contra × exp(−0,30 × Δdefensa)`.
Sin alineación publicada, se parte del once típico y se resta a los titulares habituales que están de baja.
El coeficiente 0,30 es una estimación prudente. Se calibrará con los picks reales, porque no existen alineaciones *previstas* históricas para hacer backtest.

## 6. Valor, confianza y apuesta del día

- **Probabilidad final** = 25 % modelo + 75 % mercado afilado (Pinnacle/Betfair sin margen) cuando existe. Si no existe, solo el modelo.
- **Valor esperado** = prob × cuota − 1 (corregido por la probabilidad de devolución en líneas asiáticas).
- **Confianza** (0-1) = alineación (confirmada 1 · prevista 0,85 · solo bajas 0,72) × muestra × tipo de mercado (principal 1 / estadísticas 0,75 / jugador 0,65) × acuerdo modelo-mercado × riesgo de rotación.
- **Apuesta del día**: máxima `valor × confianza` con cuota entre 1,50 y 2,60, prob ≥ 42 %, valor ≥ 3 % y confianza ≥ 0,60. **Si ninguna cumple, no hay apuesta del día.**
- **Stake**: Kelly × 0,25, con tope del 3 % de la banca. Límites de pérdida: 5 % diario y 10 % semanal.

## 7. Backtest (`backtest/engine.py`)

Walk-forward: cada 1-2 semanas se reajusta con datos anteriores y se apuesta contra la **cuota previa de bet365**. CLV contra el cierre de bet365.

**Temporadas 2024-25 y 2025-26** (≈2.100 partidos de EPL, BUN y LAL; modelo base sin alineaciones):

| Log-loss 1X2 | Modelo | bet365 | Pinnacle | Mezcla 25/75 |
|---|---|---|---|---|
| | 0,992 | 0,975 | 0,975 | 0,977 |

| Estrategia (valor ≥ 3 %) | Apuestas | ROI | CLV medio |
|---|---|---|---|
| Solo modelo | 2.835 | −4,8 % | 0,0 % |
| · hándicap asiático | 1.215 | −0,8 % | |
| · más/menos 2.5 | 962 | −6,1 % | |
| · 1X2 | 657 | −10,0 % | |
| Modelo + mercado | 313 | −8,8 % | +1,0 % |
| bet365 frente a Pinnacle (sin margen) | 4 | — | — |

| Estadísticas (log-verosimilitud por partido) | Mejora frente a la media de la liga |
|---|---|
| Faltas | +0,148 |
| Remates | +0,030 |
| Remates a puerta | +0,018 |
| Tarjetas | +0,014 |
| Córners | +0,005 |

**Lectura**:
1. En los mercados principales, **bet365 es más preciso que el modelo**. El sistema no debe buscar valor ahí por su cuenta, y por eso la mezcla da tanto peso al mercado.
2. bet365 casi nunca paga más que la probabilidad justa de Pinnacle en 1X2 o goles 2.5 (4 casos en dos años), así que comparar casas no sirve con bet365 en esos mercados.
3. Donde el modelo sí aporta información (faltas, remates, tarjetas, jugadores) es justo donde las casas tienen menos precisión. Ahí hay que comparar las cuotas de Betano con la **cuota mínima** que da el sistema.

Reproducir: `apuestas backtest --out var/backtests/x.json`.

## Próximas mejoras previstas

- **Ratings implícitos del mercado**: usar las cuotas de cierre históricas como observaciones del modelo (lo que hacen los profesionales) y añadir encima la información de alineaciones.
- Calibrar el coeficiente de alineación (0,30) con los partidos jugados desde ahora.
- Volver a medir el factor del árbitro con LaLiga y la Bundesliga.
- Backtest de props cuando haya cuotas guardadas de Betano (OddsPapi).
