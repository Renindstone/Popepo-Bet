# ADR 0001: Modular monolith + worker instead of microservices

**English** · [Español](../es/adr/0001-monolito-modular.md)

**Status**: accepted (2026-10-19)

## Context
A one-person project (with Claude writing the code), running on a personal PC, with a small volume (~1,500 matches/season in the main competitions) and no separate teams deploying on their own.

## Decision
A single Python package with separate modules (`ingest`, `models`, `features`, `services`, `api`, `mcp_server`, `bot`, `jobs`, `archive`) and three processes: worker, API/MCP and bot. All query logic goes through `services/queries.py`, so the API, MCP and Telegram give the same answers.

## Consequences
- One deployment, one database, simple debugging.
- If a module ever needs to scale on its own (e.g. live odds ingest), it can be extracted because it already has clear boundaries.
- Docker isn't installed on the PC: native PostgreSQL is used (the project's own cluster) and systemd user services. It can move to Docker Compose later without changing the code.
