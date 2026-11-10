# ADR 0003: Almacenamiento por niveles en vez de borrar temporadas

**Estado**: aceptada (2026-10-19)

## Contexto
La idea inicial era borrar cada temporada al terminar y quedarse con un resumen. Pero los modelos necesitan unas 3 temporadas de historial y el backtest necesita aún más.

## Decisión
- **hot**: temporada actual, todo el detalle.
- **warm**: temporadas dentro de `history_seasons` (3). Se borran las cuotas intermedias y se conservan apertura, cierre y la primera y última captura de cada selección.
- **cold**: temporadas más antiguas. Alineaciones, estadísticas de jugadores, observaciones y cuotas se exportan a Parquet (zstd) en `var/archive/` y se borran de PostgreSQL. Se conservan el partido, las estadísticas de equipo y el **resumen de temporada** (equipo/jugador), que sirve de punto de partida para la temporada siguiente.
- Las cuotas solo se guardan **cuando cambian**.

## Consecuencias
Lo que más espacio ocupa son las cuotas, no las estadísticas. Con esto todo cabe en pocos GB durante años. Los Parquet se consultan con DuckDB (`apuestas archive query`).
