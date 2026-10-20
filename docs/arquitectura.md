# Arquitectura

**Monolito modular + worker.** Un único paquete Python (`src/apuestas`) con módulos de responsabilidades claras, y tres procesos que lo usan: el worker (tareas programadas), la API/MCP (consultas) y el bot.

```
Fuentes gratis                         src/apuestas/
──────────────                         ─────────────
football-data.co.uk ─┐   ingest/      descarga educada (caché en disco, ritmo, reintentos)
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
   services/  analysis (partido completo) · picks (apuesta del día, liquidación)
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

**Capturas de cuotas** (`services/captures.py`, `services/capture_engines.py`): el panel sube la imagen a la API. Un hilo de la API lanza Claude Code (`claude -p`), aislado y con el servidor MCP del proyecto. Claude lee la imagen con `ver_captura`, manda las cuotas a `evaluar_captura` (las evalúa el mismo modelo que `evaluar_cuota`) y guarda un resumen. Ver [ADR 0005](adr/0005-capturas-con-ia.md).

## Flujo diario (hora de Lima)

1. **05:30**: resultados de ayer (FotMob, football-data, Understat), detalles de partidos jugados, liquidación de picks y apuestas, reentrenamiento (`var/models/latest.json`).
2. **08:30**: detalles de los próximos 4 días (alineación prevista, bajas, árbitro) y cuotas.
3. **09:00**: apuesta del día → Telegram.
4. **Cada 20 min**: si un partido empieza en menos de 100 min y aún no tiene alineación confirmada, se descarga, se recalcula y se avisa si cambia la apuesta del día.
5. **02:00**: descarga de detalles históricos pendientes (400 por noche).
6. **Lunes 04:00**: niveles de almacenamiento (resumen y archivo de temporadas cerradas).

## Principios

- **Los números los calcula el modelo**; el agente de IA interpreta, explica y aporta información cualitativa (por ejemplo, registra bajas leídas en noticias con `registrar_baja`).
- **Ninguna fuente es imprescindible**: cada tarea se registra en `ingestion_run` y un fallo no detiene a las demás.
- **No se esquivan protecciones anti-bots**: si una fuente bloquea (SofaScore lo hace), se descarta.
- **Sin ajustes sin evidencia**: los parámetros (peso del xG, vida media, mezcla con el mercado) se eligieron con el backtest. Los ajustes por alineación usan valores prudentes hasta tener picks reales con los que calibrarlos.
