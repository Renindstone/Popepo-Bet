# ADR 0002: Free sources only, without bypassing protections

**English** · [Español](../es/adr/0002-fuentes-gratuitas.md)

**Status**: accepted (2026-10-19)

## Context
A budget of 0 for the first month. The request was to use FotMob, Opta and SofaScore, and bet365 and Betano odds.

## Decision
- FotMob (which shows Opta data), football-data.co.uk and Understat, with a disk cache and one request every 1.5 s. (Understat was dropped on 19-11-2026: it had been down since 3-11-2026, and football-data has brought xG since 2026-27.)
- bet365 odds through football-data.co.uk. Betano through OddsPapi (free key, optional) and, meanwhile, through manual evaluation (`evaluar_cuota`).
- SofaScore discarded because it blocks (403). **No techniques are used to get around anti-bot protections.**

## Consequences
- If a source changes its format, only that task fails (logged in `ingestion_run`).
- The data is for personal use. To monetise it, a licensed source would be needed: the design (`ingest/` per source + `store.py`) allows it by adding an adapter.
