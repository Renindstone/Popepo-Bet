# ADR 0003: Tiered storage instead of deleting seasons

**English** · [Español](../es/adr/0003-almacenamiento-por-niveles.md)

**Status**: accepted (2026-10-19)

## Context
The initial idea was to delete each season when it ended and keep a summary. But the models need about 3 seasons of history and the backtest needs even more.

## Decision
- **hot**: current season, full detail.
- **warm**: seasons within `history_seasons` (3). Intermediate odds are deleted, keeping the opening, closing, and first and last snapshot of each selection.
- **cold**: older seasons. Line-ups, player stats, observations and odds are exported to Parquet (zstd) in `var/archive/` and deleted from PostgreSQL. The match, the team stats and the **season summary** (team/player) are kept, which serves as the starting point for the next season.
- Odds are only saved **when they change**.

## Consequences
What takes the most space is the odds, not the stats. With this everything fits in a few GB for years. The Parquet files are queried with DuckDB (`apuestas archive query`).
