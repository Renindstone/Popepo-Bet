# ADR 0006: Previa guardada y resumen de la semana

**Estado**: aceptada (2026-10-24)

## Contexto
El usuario quiere ver cada semana el equipo, el jugador y el once que más superaron lo esperado: el equipo que
pasó su línea de córners o de goles, el que ganó siendo el que menos opciones tenía, el jugador que superó sus
remates, goles o asistencias. Para eso hace falta saber **qué se esperaba antes del partido**:

- De los equipos sí hay vara: las cuotas de la casa guardadas antes del inicio (1X2 de cierre de football-data y
  las líneas de goles y córners de cada equipo de Pinnacle y Betano por OddsPapi, desde el 19-10-2026).
- De los jugadores no hay líneas de ninguna casa. La única vara es nuestro modelo, y lo que esperaba antes de cada
  partido no se guardaba: la tabla `prediction` existía, pero nadie la escribía.

Rehacer el análisis de un partido ya jugado no sirve: las alineaciones probables se reemplazan por las
confirmadas, las bajas activas son las de hoy y el modelo se reentrena cada día con ese mismo partido.

## Decisión
- **Previa guardada** (`services/predictions.py`): una fila por partido en `prediction` (restricción única en
  `match_id`). La escribe `picks.generate`, que corre a las 09:00, en cada búsqueda de la alineación confirmada y
  al abrir Hoy. Se reescribe solo si cambió y **nunca después del inicio**, así que queda la última previa antes
  del partido, con el once confirmado si llegó. Guarda, por lado (local o visitante, no por id de equipo, para que
  la fusión de equipos duplicados no la deje desfasada): goles esperados, 1X2, la media y la dispersión de cada
  estadística y la proyección de todos los jugadores. Ocupa unos 6 KB por partido; se borra con el partido.
- **Resumen calculado al leerlo** (`services/weekly.py`, `models/surprise.py`; `GET /week`, MCP `resumen_semana`,
  `apuestas semana`, página Semana). No se guarda nada más: si el cierre de football-data o las estadísticas
  llegan tarde, la semana se completa sola.
- **Vara**, como pidió el usuario: los equipos frente a la casa (resultado, goles y córners; los remates a puerta
  no, porque ninguna casa los cotiza) y los jugadores frente a la previa del modelo.
- **Puntuación por sorpresa**: P(menos) − P(más) con la distribución esperada, de −1 a +1, para que cuente el
  margen. Detalle en `docs/modelos.md`, sección 8.

## Consecuencias
- El historial de jugadores empieza el 24-10-2026: las semanas anteriores no tienen jugadores ni once (los equipos
  sí, con las cuotas guardadas).
- Si el equipo está apagado todo el día de un partido y no se abrió Hoy antes, ese partido no tiene previa: sus
  jugadores no cuentan (la cobertura de la página lo dice).
- Es un resumen de lo que pasó, no una señal para apostar: una semana buena es en parte suerte.
- La previa guardada sirve también para medir más adelante la calibración de los mercados de jugadores y de
  estadísticas con lo que realmente se esperaba antes de cada partido.
