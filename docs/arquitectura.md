# Arquitectura

**Monolito modular + worker.** Un único paquete Python (`src/apuestas`) con módulos de responsabilidades claras, y tres procesos que lo usan: el worker (tareas programadas), la API/MCP (consultas) y el bot.

```
Fuentes gratis                         src/apuestas/
──────────────                         ─────────────
football-data.co.uk ─┐   ingest/      descarga educada (caché en disco, ritmo, reintentos, pausa de hosts caídos)
FotMob (Opta)        ├─► store.py     resolución de entidades entre fuentes + validación de stats
Understat            │   pipeline.py  orden y frecuencia de la ingesta
OddsPapi (opcional) ─┘        │
                              ▼
                    PostgreSQL (cluster propio, puerto 5433)
                              │
         ┌────────────────────┼─────────────────────────────┐
         ▼                    ▼                             ▼
   models/               features/                    archive/
   ratings (ataque/def)  lineup (once vs típico)      niveles hot/warm/cold
   distributions         context (descanso,           resúmenes de temporada
   fitting (paquete)     rotación, dificultad)        Parquet + DuckDB
         └──────────┬─────────┘
                    ▼
   services/  analysis (partido completo) · picks (apuesta del día, liquidación) · predictions (previa) · weekly (semana)
              tracker (usuarios, apuestas, banca) · queries (capa común)
                    │
      ┌─────────────┼──────────────┬───────────────┐
      ▼             ▼              ▼               ▼
  mcp_server/    api/ (FastAPI)  bot/ (Telegram)  jobs/ (worker APScheduler)
  Claude y       /docs           alertas y         05:30 resultados + reentrenar
  agentes de                      consultas        09:00 apuesta del día
  otros usuarios                                   cada 20' alineaciones
```

El **panel web** (`web/`, Next.js + ECharts) es una interfaz más sobre `api/`: el navegador llama a la API REST (CORS abierto solo a `localhost:3000`) y no tiene lógica de apuestas propia.

**Previa guardada y resumen de la semana** (ADR 0006): `picks.generate` guarda en `prediction` lo que el modelo esperaba de cada partido (una fila por partido, la última antes del inicio y nunca después; `services/predictions.py`). `services/weekly.py` compara cada semana lo que pasó con la casa (equipos) y con esa previa (jugadores), al leerlo: `GET /week`, MCP `resumen_semana`, `apuestas semana` y la página Semana.

**Apuestas que pasan el corte:** cada apuesta con valor de un partido que aún no empezó se guarda en `pick` (`picks.generate`) y se actualiza en cada recálculo; `pick.qualifies` dice si pasa el corte de la apuesta del día (`picks.qualifies`: valor, probabilidad, confianza, rango de cuota y, por ahora, solo mercados de goles). Vale el último cálculo antes del partido: si deja de tener valor se retira (`status = "withdrawn"`) y si deja de pasar el corte se desmarca. La liquidación es la de siempre (`picks.settle_all`), y `GET /picks/qualified` da sus aciertos desde el inicio y las de los últimos días.

**Combinadas registradas:** una apuesta con `market = "combo"` en `user_bet`, cuyo partido es el que termina último, y sus selecciones en `user_bet_leg`. La liquidación (`picks.settle_all` y `betting.settlement.combo_profit`) resuelve cada selección y la combinada: una perdida basta para perderla; una anulada divide su cuota de la total.

**Quién es local:** la API solo atiende sin clave las peticiones que llegan desde la propia máquina **sin** cabeceras de proxy o túnel (`X-Forwarded-For`, `CF-Connecting-IP`…). Todo lo demás necesita `X-API-Key`.

**Capturas de cuotas** (`services/captures.py`, `services/capture_engines.py`): el panel sube la imagen a la API. Un hilo de la API lanza Claude Code (`claude -p`), aislado y con el servidor MCP del proyecto. Claude lee la imagen con `ver_captura`, manda las cuotas a `evaluar_captura` (las evalúa el mismo modelo que `evaluar_cuota`) y guarda un resumen. Ver [ADR 0005](adr/0005-capturas-con-ia.md).

## Flujo diario (hora de Lima)

1. **05:30**: resultados de ayer (FotMob, football-data, Understat), detalles de partidos jugados, fusión de equipos duplicados, liquidación de picks y apuestas, reentrenamiento (`var/models/latest.json`).
2. **08:30**: detalles de los próximos 4 días (alineación prevista, bajas, árbitro), cuotas y, si hay clave, Betano y Pinnacle por OddsPapi.
3. **09:00**: apuesta del día (solo mercados de goles) → Telegram.
4. **70, 50, 35, 20 y 10 minutos antes de cada partido** de las cinco ligas y la Champions (la tarea corre cada 5 min; la Europa League y la Conference no, porque sus alineaciones no se usan): si aún no tiene alineación confirmada (solo cuenta el once oficial de FotMob, no el probable ni el último once titular), se descarga de FotMob, se recalcula y se avisa si cambia la apuesta del día. FotMob suele publicarla una hora antes; la búsqueda de los 50 minutos deja margen si se retrasa.
5. **15 minutos antes de cada partido con apuestas abiertas que pasan el corte** (la tarea corre cada 5 min): Pinnacle por OddsPapi para esas competiciones, la referencia del CLV. Como mucho 3 descargas al día (`APUESTAS_ODDSPAPI_CLOSING_PER_DAY`); las demás se quedan con el último precio guardado.
6. **A los :15 y :45**: si un partido empezó hace más de 3 horas y hay algo pendiente, se descarga su resultado y se liquidan los picks y las apuestas (con su CLV frente a la cuota justa de Pinnacle o del cierre; ver `docs/modelos.md`, sección 6).
7. **Cada 3 horas (:10)**: cuotas de bet365 y Betfair de los próximos partidos (`fixtures.csv` de football-data).
8. **02:00**: descarga de detalles históricos pendientes (400 por noche).
9. **Lunes 04:00**: niveles de almacenamiento (resumen y archivo de temporadas cerradas).

**Horario del worker:** solo funciona de 05:00 a 20:00: a las 20:00 lo apaga `apuestas-worker-stop.timer` y a las 05:00 lo enciende `apuestas-worker-start.timer`; fuera de ese horario no arranca ni al encender el PC (desde el 2026-10-26). Así no gasta recursos por la noche; las tareas de las 02:00 se recuperan al arrancar.

**Si el equipo estaba apagado** a la hora de una tarea diaria (05:30, 08:30, 09:00, 02:00 o la del lunes), el worker la ejecuta al arrancar, en ese orden. La hora del último éxito de cada una se guarda en `var/worker_state.json`. La apuesta del día solo se recupera hasta 12 horas después de las 09:00; las demás, hasta 20 horas. **Si estaba suspendido**, la tarea atrasada corre al despertar si no pasó más de una hora.

**Si no hay internet** (al encender el equipo la red tarda en llegar; el 23-10-2026 la recuperación arrancó sin ella y todas las fuentes fallaron): las tareas que descargan esperan a que se resuelva el nombre de FotMob, Understat o football-data (`scheduler.network_ready`, sin hacer peticiones). Las diarias esperan hasta 10 minutos; si sigue sin haber, no se marcan como hechas y la recuperación vuelve a probar a los 15, sin calcular la apuesta del día con datos viejos. Las periódicas (alineaciones, liquidación, cuotas) se saltan esa vuelta. Un fallo de nombre no da el host por caído (`ingest/http.py`), y una tarea no corre dos veces a la vez.

## Principios

- **Los números los calcula el modelo**; el agente de IA interpreta, explica y aporta información cualitativa (por ejemplo, registra bajas leídas en noticias con `registrar_baja`).
- **Ninguna fuente es imprescindible**: cada tarea se registra en `ingestion_run` y un fallo no detiene a las demás.
- **No se esquivan protecciones anti-bots**: si una fuente bloquea (SofaScore lo hace), se descarta.
- **Sin ajustes sin evidencia**: los parámetros (peso del xG, vida media, mezcla con el mercado) se eligieron con el backtest. Los ajustes por alineación usan valores prudentes hasta tener picks reales con los que calibrarlos.
