# ADR 0004: MCP as the main interface for AI agents

**English** · [Español](../es/adr/0004-mcp-y-multiusuario.md)

**Status**: accepted (2026-10-19)

## Decision
- MCP server with tools named in Spanish (`analizar_partido`, `apuesta_del_dia`, `evaluar_cuota`, …).
- **Local (stdio)** for the owner: `.mcp.json` in the repository for Claude Code.
- **HTTP with a key** for other users: `apuestas user create-key <name>` + `apuestas mcp --http`. Each key identifies the user, so their bets and performance stay separate. Keys are stored as SHA-256 hashes.
- MCP is an open standard: it works with Claude, ChatGPT, Gemini CLI, Cursor, etc.

## Pending
- Full OAuth (needed for the claude.ai/ChatGPT web connectors). For now: a Bearer token, which works for Claude Code, Claude Desktop (through `mcp-remote`) and most clients.
- Exposure to the internet through a tunnel (Cloudflare Tunnel / Tailscale Funnel), without opening router ports.
