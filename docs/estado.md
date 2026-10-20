# Estado del proyecto

Última actualización: 20 de octubre de 2026. Actualízalo cada vez que termines un cambio: qué cambió, qué decidió el usuario y qué queda pendiente.

## Qué funciona hoy

- **Ingesta diaria** de football-data, FotMob y Understat para Premier League, Bundesliga, LaLiga y Champions, más 9 ligas extra de football-data (solo para ratings del mercado de los rivales europeos). Equipos duplicados entre fuentes se fusionan solos cuando es seguro.
- **Modelo** de goles con fuerza de ataque y defensa, xG promediado y ratings implícitos de las cuotas de cierre; estadísticas (remates, córners, tarjetas, faltas) y proyecciones de jugadores. Ajuste por alineación y bajas.
- **Apuesta del día** a las 09:00 (solo mercados de goles), con un contador de aciertos desde el inicio en Hoy y en Mis apuestas (`GET /picks/record`; las retiradas al recalcular no cuentan) y **liquidación automática** de picks y apuestas después de cada partido (tarea `post_match`, a los :15 y :45).
- **Cuotas de Betano y Pinnacle** con OddsPapi a las 08:30 (una petición por casa y día), descartando las que vienen con local y visitante invertidos.
- **Panel web** (`web/`): apuesta del día, partidos del día, análisis, evaluar una cuota, mis apuestas y **capturas**: el usuario sube una imagen de Betano o bet365 y Claude Code la lee, incluidas combinadas y Bet Builders.
- **Compartir el panel por un enlace** con un túnel rápido de Cloudflare (README, "Compartir el panel con un enlace"): por el túnel la API siempre pide clave. Usuario `invitado` creado el 2026-10-20.
- **Banca inicial editable** en Mis apuestas (`PUT /bankroll`), con la banca actual al lado.
- **Servidor MCP** para Claude, **API REST** y **bot de Telegram** (este último sin configurar).
- Servicios systemd de usuario: `apuestas-db`, `apuestas-worker`, `apuestas-api` y `apuestas-web`. Si el equipo estuvo apagado a la hora de una tarea diaria, el worker la recupera al arrancar (desde el 2026-10-20).

## Decisiones del usuario (no las cambies sin preguntarle)

| Fecha | Decisión |
|---|---|
| 2026-10 | Solo prepartido; ligas: Premier, Bundesliga, LaLiga y Champions. Solo fuentes gratuitas. |
| 2026-10-19 | Las capturas usan Claude Code con la suscripción del usuario (`claude -p`), preparado para pasar a la API de Anthropic con `APUESTAS_CAPTURES_ENGINE`. |
| 2026-10-19 | Equipos sin ratings del mercado (como Bodø/Glimt): menos confianza y valor esperado. |
| 2026-10-19 | Las ligas extra se descargan, pero **no entrenan el modelo** (`extra_leagues_in_model=False`): el backtest no mejoró. |
| 2026-10-19 | La apuesta del día no usa córners ni tarjetas hasta validarlos; esos mercados bajan de confianza si el modelo y la casa discrepan mucho. |
| 2026-10-19 | Las capturas no evaluables se muestran con su motivo; las combinadas se evalúan con la matriz de marcadores. |
| 2026-10-20 | El README y la documentación hablan de "cualquier persona" que use el código, no de "amigos": el repositorio es público. |
| 2026-10-20 | La versión universitaria con microservicios vive en un repositorio privado aparte. |

## Pendiente o por decidir

- **Ramas de otras sesiones sin fusionar** (necesitan backtest y el OK del usuario):
  - `claude/competent-bartik-bb3a15`: nivel por liga en el modelo de goles y prudencia para ligas que apenas juegan contra otras.
  - `claude/focused-newton-7f7dce`: lo anterior más ligas extra en el modelo **por defecto**, lo que contradice la decisión del 2026-10-19.
  - `claude/precio-afilado-mercados`: Pinnacle como precio de referencia en todos los mercados de goles (incluye la rama anterior).
  - `claude/eloquent-murdock-250aed`: calidad de jugador con el rating de FotMob y `backtest --lineups`.
- **Validar córners, tarjetas y props** con las cuotas de Betano que ya se guardan, antes de dejarlos entrar en la apuesta del día.
- **Telegram**: falta crear el bot y poner el token en `.env`.
- `loginctl enable-linger` para que los servicios sigan corriendo sin sesión iniciada (lo ejecuta el usuario).
- Más ideas del modelo en `docs/modelos.md`, "Próximas mejoras previstas".

## Limitaciones conocidas

- El modelo no le gana a bet365 en 1X2, goles ni hándicap asiático (ver el backtest en `docs/modelos.md`).
- Los mercados de estadísticas y jugadores no tienen backtest con cuotas reales.
- OddsPapi: 250 peticiones al mes en el plan gratis.
- Los rivales europeos de ligas que football-data no cubre (Chequia, Croacia, Serbia…) no tienen ratings del mercado.
