# ADR 0004: MCP como interfaz principal para agentes de IA

**Estado**: aceptada (2026-10-19)

## Decisión
- Servidor MCP con herramientas en español (`analizar_partido`, `apuesta_del_dia`, `evaluar_cuota`, …).
- **Local (stdio)** para el dueño: `.mcp.json` en el repo para Claude Code.
- **HTTP con clave** para otros usuarios: `apuestas user create-key <nombre>` + `apuestas mcp --http`. Cada clave identifica al usuario, así sus apuestas y su rendimiento quedan separados. Las claves se guardan como hash SHA-256.
- MCP es un estándar abierto: sirve para Claude, ChatGPT, Gemini CLI, Cursor, etc.

## Pendiente
- OAuth completo (necesario para los conectores de claude.ai/ChatGPT web). Por ahora: token Bearer, que vale para Claude Code, Claude Desktop (vía `mcp-remote`) y la mayoría de clientes.
- Exposición a internet mediante túnel (Cloudflare Tunnel / Tailscale Funnel), sin abrir puertos del router.
