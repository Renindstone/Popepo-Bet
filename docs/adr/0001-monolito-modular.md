# ADR 0001: Monolito modular + worker en lugar de microservicios

**Estado**: aceptada (2026-10-19)

## Contexto
Proyecto de una persona (con Claude escribiendo el código), que corre en un PC personal, con un volumen pequeño (~1.500 partidos/temporada en las competiciones principales) y sin equipos separados que desplieguen por su cuenta.

## Decisión
Un único paquete Python con módulos separados (`ingest`, `models`, `features`, `services`, `api`, `mcp_server`, `bot`, `jobs`, `archive`) y tres procesos: worker, API/MCP y bot. Toda la lógica de consulta pasa por `services/queries.py`, así API, MCP y Telegram dan las mismas respuestas.

## Consecuencias
- Un despliegue, una base de datos, depuración sencilla.
- Si algún módulo necesita escalar por separado (p.ej. la ingesta de cuotas en vivo), puede extraerse porque ya tiene límites claros.
- Docker no está instalado en el PC: se usa PostgreSQL nativo (cluster propio del proyecto) y servicios systemd de usuario. Se puede pasar a Docker Compose más adelante sin cambiar el código.
