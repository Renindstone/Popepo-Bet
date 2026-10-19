# App Apuestas: guía para Claude

Análisis de apuestas de fútbol (EPL, Bundesliga, LaLiga, Champions; solo prepartido). Usuario en Perú: apuesta en bet365 y Betano. Hora local: America/Lima.

## Comandos
- Entorno: `.venv/bin/...` (Python 3.14, sin uv). Instalar: `.venv/bin/pip install -e ".[dev]"`
- Tests: `.venv/bin/pytest` · Lint: `.venv/bin/ruff check src tests`
- BD: `scripts/db.sh start|stop|status|psql` (cluster propio en 127.0.0.1:5433, datos en ~/.local/share/apuestas/pgdata)
- Migraciones: `.venv/bin/alembic revision --autogenerate -m "..."` y `.venv/bin/alembic upgrade head`
- CLI: `.venv/bin/apuestas --help` (ingest, train, picks, analyze, evaluate, backtest, mcp, api, bot, worker, archive, user)

## Estructura
- `src/apuestas/ingest/`: un módulo por fuente + `store.py` (resolución de entidades, validación entre fuentes) + `pipeline.py`
- `src/apuestas/models/`: `ratings.py` (fuerza conjunta), `distributions.py` (mercados y líneas asiáticas), `fitting.py` (paquete de modelos en var/models/latest.json)
- `src/apuestas/features/`: alineación vs once típico, contexto, dificultad
- `src/apuestas/services/`: `analysis.py` (partido completo), `picks.py` (apuesta del día, liquidación), `tracker.py`, `queries.py` (capa común de API/MCP/bot)
- Docs: `docs/arquitectura.md`, `docs/modelos.md` (incluye resultados del backtest), `docs/fuentes.md`, `docs/adr/`

## Convenciones
- Código y comentarios en español. Fechas en UTC en la BD; se muestran en hora de Lima.
- Mercados: `1x2`, `dc`, `dnb`, `btts`, `ah`, `eh`, `ou_<stat>[_home|_away]`, `ah_<stat>`, `1x2_<stat>`, `player_shots|player_sot|player_fouls|player_goal|player_card`. Stats: goals, shots, sot, corners, cards, fouls.
- Ninguna fuente puede tumbar la ingesta: todo pasa por `pipeline._run` (registro en `ingestion_run`).
- No esquivar protecciones anti-bots. Peticiones solo con `ingest.http.client()` (caché + ritmo).
- Cualquier cambio de parámetros del modelo se justifica con `apuestas backtest` y se documenta en `docs/modelos.md`.
- Ser honesto con los resultados: el backtest muestra que el modelo no le gana a bet365 en 1X2/goles/AH. No lo vendas como si lo hiciera.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
