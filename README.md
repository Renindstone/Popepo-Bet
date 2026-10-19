# App Apuestas ⚽

Análisis de apuestas de fútbol con modelos estadísticos para **Premier League, Bundesliga, LaLiga y Champions League** (solo prepartido).
Pensado para usarlo desde Claude (u otro agente) mediante **MCP**, por Telegram o por API REST.

## Qué hace

- **Recoge datos gratis** de football-data.co.uk (resultados, estadísticas, cuotas de bet365, Betfair Exchange y Pinnacle), FotMob (datos Opta: estadísticas, alineaciones previstas y confirmadas, lesiones, sanciones, árbitros, estadísticas por jugador) y Understat (segundo modelo de xG). Ver [docs/fuentes.md](docs/fuentes.md).
- **Valida las fuentes entre sí**: los conteos (remates, córners, tarjetas…) se comparan y se marcan discrepancias; el xG se promedia entre proveedores.
- **Modelos**: fuerza de ataque/defensa conjunta para 17 ligas (las ligas secundarias conectan la escala para rivales de Champions y equipos ascendidos), Dixon-Coles para goles y binomial negativa para remates, remates a puerta, córners, faltas y tarjetas. Además, **factor de árbitro** para tarjetas y faltas y **tasas por 90'** de cada jugador. Ver [docs/modelos.md](docs/modelos.md).
- **Alineaciones y bajas**: compara el once (previsto o confirmado) con el once típico del equipo según el valor de mercado y el rating de cada jugador, con pesos por posición. Que falte un Szoboszlai baja el ataque y la defensa del Liverpool.
- **Dificultad del rival** para cada equipo (Fácil → Difícil), con fuerza base y con la alineación real.
- **Contexto**: días de descanso, calendario cargado y riesgo de rotación si juega Champions en ≤4 días.
- **Valor esperado** contra las cuotas de bet365/Betano, mezclando el modelo con el mercado afilado (Pinnacle/Betfair).
- **Apuesta del día**: la de mayor valor × confianza entre las que pasan los umbrales. Si ninguna los pasa, **no hay apuesta del día**.
- **Cuotas mínimas** para props (remates, tarjetas, córners, jugadores): la cuota a partir de la cual vale la pena en Betano.
- **Seguimiento** de tus apuestas: liquidación automática, ROI, CLV, rendimiento por mercado/competición/casa y límites de pérdida.
- **Almacenamiento por niveles** (temporada actual / historial / archivo Parquet) con resúmenes de temporada. Ver [docs/adr/0003-almacenamiento-por-niveles.md](docs/adr/0003-almacenamiento-por-niveles.md).

## Puesta en marcha

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
scripts/db.sh init                      # crea un PostgreSQL propio del proyecto (puerto 5433) y el .env
.venv/bin/alembic upgrade head          # crea las tablas
.venv/bin/apuestas ingest all --seasons 3 --backfill 6000   # historial (tarda ~2-3 h la primera vez)
.venv/bin/apuestas train                # entrena los modelos
.venv/bin/apuestas picks                # apuestas con valor de hoy
```

Servicios permanentes en tu PC (systemd de usuario): `scripts/install-services.sh`.

## Uso diario

| Comando | Para qué |
|---|---|
| `apuestas picks` | Apuesta del día + otras con valor + props para revisar |
| `apuestas analyze "Arsenal vs Chelsea"` | Análisis completo de un partido (`--json` para todo el detalle) |
| `apuestas evaluate "Arsenal vs Chelsea" ou_cards over 1.85 --line 4.5` | ¿Vale la pena esta cuota de Betano? |
| `apuestas status` | Frescura de las fuentes y del modelo |
| `apuestas backtest` | Valida el modelo contra cuotas históricas de bet365 |
| `apuestas archive report` | Espacio usado |

### Conectar Claude (MCP)

El repo incluye [.mcp.json](.mcp.json): al abrir Claude Code en esta carpeta aparece el servidor `apuestas`. Para Claude Desktop, añade el mismo bloque en su configuración. Herramientas: `apuesta_del_dia`, `analizar_partido`, `evaluar_cuota`, `bajas_equipo`, `registrar_baja`, `perfil_arbitro`, `proyeccion_jugador`, `registrar_apuesta`, `mi_rendimiento`, etc.

### Amigos (cada uno con su agente)

```bash
apuestas user create-key pedro          # genera su clave (se muestra una vez)
apuestas mcp --http --port 8765         # servidor MCP con autenticación por clave
```

Tu amigo añade el servidor con su clave como `Authorization: Bearer apk_...`. Por ejemplo, en Claude Code:
`claude mcp add --transport http apuestas https://TU_HOST/mcp --header "Authorization: Bearer apk_..."`.
Para exponerlo fuera de tu red usa un túnel (Cloudflare Tunnel o Tailscale Funnel). Ver [docs/adr/0004-mcp-y-multiusuario.md](docs/adr/0004-mcp-y-multiusuario.md).

### Telegram (opcional)

Crea un bot con @BotFather y pon `APUESTAS_TELEGRAM_TOKEN` y `APUESTAS_TELEGRAM_CHAT_ID` en `.env`. El worker envía la apuesta del día a las 9:00 (Lima) y avisa si cambia al salir las alineaciones.

### Betano (opcional)

Las cuotas de bet365 llegan gratis vía football-data.co.uk (1X2, goles 2.5 y hándicap asiático). Para Betano, regístrate gratis en [OddsPapi](https://oddspapi.io) y pon `APUESTAS_ODDSPAPI_KEY`. Ese conector es **experimental** porque se escribió sin clave para probarlo. Mientras tanto, usa `evaluar_cuota` con la cuota que ves en la app.

## Resultado del backtest (honesto)

Con datos de 2024-25 y 2025-26 (≈2.100 partidos de EPL, Bundesliga y LaLiga):

- En **1X2, goles 2.5 y hándicap asiático** el modelo **no le gana a bet365**. Con los ratings implícitos del mercado (cuotas de cierre de partidos anteriores), la log-loss bajó de 0,993 a 0,981, pero bet365 está en 0,975. Ninguna estrategia en esos mercados es rentable: "solo modelo" da un ROI del −6,8 % (antes −4,2 %, diferencia dentro del ruido), con un CLV de +0,5 %.
- Los modelos de **faltas, remates y tarjetas** sí mejoran claramente a la media de la liga, pero no hay cuotas históricas gratuitas para medir su ROI. El árbitro ayuda en las tarjetas de LaLiga y la Bundesliga, no en las de la Premier.
- El **once confirmado** aporta poco con el índice actual: el efecto calibrado es un tercio del supuesto al principio (0,10 en lugar de 0,30).

Conclusión: el valor hay que buscarlo en **props, tarjetas con árbitro, remates y noticias de alineaciones**, no en el 1X2. Detalle en [docs/modelos.md](docs/modelos.md).

## Arquitectura

Monolito modular más un worker (tareas programadas). Ver [docs/arquitectura.md](docs/arquitectura.md) y las [decisiones (ADR)](docs/adr/).

## Aviso

Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas permitirte perder. Los datos de fuentes no oficiales se usan con ritmo moderado y no se redistribuyen.
