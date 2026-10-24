# Popepo-Bet: guía para Claude

La guía completa para cualquier IA está en `AGENTS.md` (se importa aquí). El estado del proyecto y el trabajo pendiente están en `docs/estado.md`.

@AGENTS.md

## Solo para Claude

- Herramientas MCP del proyecto (`apuestas`): analizar partidos, evaluar cuotas, capturas, bajas y mis apuestas. Úsalas para consultar datos reales en vez de inventar números.
- Al terminar cada cambio, actualiza `docs/estado.md` junto con el resto de la documentación.

## graphify

Si existe `graphify-out/` (no se sube al repositorio), hay un grafo de conocimiento del código con nodos centrales, comunidades y relaciones entre archivos.

- Cuando exista `graphify-out/graph.json`, ejecuta `graphify query "<pregunta>"` antes del primer grep o lectura de código, y pon esta regla en el prompt de cada subagente que explore código. Lee archivos solo en las líneas que el grafo o una lectura anterior ya ubicaron. Usa `graphify path "<A>" "<B>"` para relaciones y `graphify explain "<concepto>"` para conceptos.
- Si existe `graphify-out/wiki/index.md`, úsalo para navegar en lugar de recorrer el código.
- Lee `graphify-out/GRAPH_REPORT.md` solo para revisar la arquitectura completa o si query/path/explain no bastan.
- Después de modificar código, ejecuta `graphify update .` (solo AST, sin coste de API).
