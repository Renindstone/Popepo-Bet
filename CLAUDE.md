# Popepo-Bet: guía para Claude

La guía completa para cualquier IA está en `AGENTS.md` (se importa aquí). El estado del proyecto y el trabajo pendiente están en `docs/estado.md`.

@AGENTS.md

## Solo para Claude

- Herramientas MCP del proyecto (`apuestas`): analizar partidos, evaluar cuotas, capturas, bajas y mis apuestas. Úsalas para consultar datos reales en vez de inventar números.
- Al terminar cada cambio, actualiza `docs/estado.md` junto con el resto de la documentación.

## Qué skill usar

El dueño no nombra skills: elige tú según la tarea y dilo en una línea («Uso X para Y»). Las skills `superpowers:` y `ecc:` son plugins de la PC del dueño; si una no está instalada, sigue sin ella. Las del proyecto (`.claude/skills/`) están siempre.

| Tarea | Skill |
|---|---|
| Cambio corto y claro (un texto, un valor, un arreglo de pocas líneas) | Ninguna: hazlo directo, con su prueba si hay lógica nueva |
| Idea nueva o pedido que aún no está definido | `superpowers:brainstorming` |
| Trabajo largo (varios archivos o varios pasos) | `superpowers:writing-plans` y después `superpowers:executing-plans` |
| Algo falla o da un resultado raro | `superpowers:systematic-debugging` |
| Lógica nueva en `src/` | `superpowers:test-driven-development` |
| API (`src/apuestas/api/`) | `ecc:fastapi-patterns` |
| Base de datos o migración de Alembic | `ecc:database-migrations` y `ecc:postgres-patterns` (antes, `pg_dump` a `var/backups/`, regla 4) |
| Aspecto del panel (`web/`): colores, fuentes, componentes, celular | `disenio-panel` |
| Arrancar el panel, capturas o comprobar que un cambio se ve bien | `run-app-apuestas` |
| Revisar código antes de subirlo (cambios grandes) | `ecc:python-review` en `src/`, `ecc:react-review` en `web/` |
| Claves, `is_local`, datos personales o algo que se publica | `ecc:security-review` (reglas 1 y 8) |
| Modelo estadístico | Sin skill: `apuestas backtest` y cifras en `docs/modelos.md` (regla 5) |
| Antes de decir que algo está hecho | `superpowers:verification-before-completion` |

## graphify

Si existe `graphify-out/` (no se sube al repositorio), hay un grafo de conocimiento del código con nodos centrales, comunidades y relaciones entre archivos.

- Cuando exista `graphify-out/graph.json`, ejecuta `graphify query "<pregunta>"` antes del primer grep o lectura de código, y pon esta regla en el prompt de cada subagente que explore código. Lee archivos solo en las líneas que el grafo o una lectura anterior ya ubicaron. Usa `graphify path "<A>" "<B>"` para relaciones y `graphify explain "<concepto>"` para conceptos.
- Si existe `graphify-out/wiki/index.md`, úsalo para navegar en lugar de recorrer el código.
- Lee `graphify-out/GRAPH_REPORT.md` solo para revisar la arquitectura completa o si query/path/explain no bastan.
- Después de modificar código, ejecuta `graphify update .` (solo AST, sin coste de API).
