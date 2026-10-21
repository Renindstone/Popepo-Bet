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

Guía completa, con requisitos, servicios, actualización y problemas frecuentes: **[docs/instalacion.md](docs/instalacion.md)**. Resumen:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
scripts/db.sh init                      # crea un PostgreSQL propio del proyecto (puerto 5433) y el .env
.venv/bin/alembic upgrade head          # crea las tablas
.venv/bin/apuestas ingest all --seasons 3 --backfill 6000   # historial (tarda ~2-3 h la primera vez)
.venv/bin/apuestas train                # entrena los modelos
.venv/bin/apuestas picks                # apuestas con valor de hoy
```

Servicios permanentes en tu PC (systemd de usuario), con panel web incluido:

```bash
scripts/install-services.sh --with-web   # BD + worker + API + panel en http://localhost:3000
```

## Uso diario

| Comando | Para qué |
|---|---|
| `apuestas picks` | Apuesta del día + otras con valor + props para revisar |
| `apuestas analyze "Arsenal vs Chelsea"` | Análisis completo de un partido (`--json` para todo el detalle) |
| `apuestas evaluate "Arsenal vs Chelsea" ou_cards over 1.85 --line 4.5` | ¿Vale la pena esta cuota de Betano? |
| `apuestas status` | Frescura de las fuentes y del modelo |
| `apuestas backtest` | Valida el modelo contra cuotas históricas de bet365 |
| `apuestas archive report` | Espacio usado |
| `apuestas equipos duplicados` | Equipos que parecen el mismo club en dos fuentes (los seguros se fusionan solos en cada ingesta) |

### Conectar Claude (MCP)

El repo incluye [.mcp.json](.mcp.json): al abrir Claude Code en esta carpeta aparece el servidor `apuestas`. Para Claude Desktop, añade el mismo bloque en su configuración. Herramientas: `apuesta_del_dia`, `analizar_partido`, `evaluar_cuota`, `bajas_equipo`, `registrar_baja`, `perfil_arbitro`, `proyeccion_jugador`, `registrar_apuesta`, `mi_rendimiento`, `capturas_pendientes`, `ver_captura`, `evaluar_captura`, etc.

### Varios usuarios (cada uno con su agente)

Cualquiera puede instalar su propia copia siguiendo [docs/instalacion.md](docs/instalacion.md). Si prefieres que otras personas usen **tu** instalación, cada una con su propio agente de IA, dale a cada una su propia clave:

```bash
apuestas user create-key pedro          # genera la clave de ese usuario (se muestra una vez)
apuestas mcp --http --port 8765         # servidor MCP con autenticación por clave
```

Cada usuario añade el servidor con su clave como `Authorization: Bearer apk_...`, y sus apuestas y su rendimiento quedan separados de los demás. Por ejemplo, en Claude Code:
`claude mcp add --transport http apuestas https://TU_HOST/mcp --header "Authorization: Bearer apk_..."`.
Para exponerlo fuera de tu red usa un túnel (Cloudflare Tunnel o Tailscale Funnel). Ver [docs/adr/0004-mcp-y-multiusuario.md](docs/adr/0004-mcp-y-multiusuario.md).

### Panel web

Interfaz visual en [web/](web/) (Next.js + ECharts). Necesita Node.js 20.9 o superior. Tiene seis páginas:
- **Hoy**: apuesta del día arriba, partidos del día debajo, luego otras apuestas con valor y props con cuota mínima, más un acceso rápido para subir capturas y el **contador de aciertos** de la apuesta del día desde el inicio (aciertos, falladas, devueltas, por jugarse y beneficio con 1 unidad por apuesta).
- **Partidos**: próximos partidos con filtros por competición y días, y un buscador (lupa) que filtra mientras escribes el nombre de cualquiera de los dos equipos; no distingue tildes y entiende iniciales como "psg". Al elegir uno, análisis completo del partido. En cada partido, **Alineaciones** las muestra en el campo como FotMob: las probables hasta que se confirman (se buscan 70, 50, 35, 20 y 10 minutos antes del inicio), con formación, entrenador, dorsales, suplentes y bajas.
- **Evaluar cuota**: comprobar una cuota de Betano y registrar la apuesta. Al elegir un partido, debajo salen **las cuotas de Betano que ya se descargaron** esa mañana, evaluadas por el modelo (primero las que tienen valor): **Evaluar** las pasa al formulario y **+ Cupón** las añade al cupón, sin captura. Con **Añadir al cupón** se juntan varias selecciones: varias de un mismo partido forman un Bet Builder (escribe la cuota que te da la casa) y las de partidos distintos, una combinada. **Evaluar cupón** calcula cada partido y el total con el modelo, y **Registrar cupón** la guarda como una sola apuesta que se liquida sola: basta una selección perdida para perderla, y si una se anula, la cuota total se ajusta.
- **Capturas**: subir o pegar una captura de cuotas. Claude la lee y el modelo da el veredicto de cada cuota (ver más abajo).
- **Mis apuestas**: ROI, CLV, desglose y banca, y el historial de la apuesta del día (desde el inicio y en el último año). La **banca inicial** (y su moneda) se edita ahí mismo; de ella salen el stake sugerido y los límites de pérdida, y la banca actual es la inicial más lo ganado o perdido.
- **Datos**: frescura de las fuentes y del modelo.

Con los servicios instalados (`scripts/install-services.sh --with-web`), el panel está siempre en **http://localhost:3000**. Para desarrollarlo a mano, detén antes los servicios (`systemctl --user stop apuestas-web apuestas-api`) y lanza:

```bash
.venv/bin/apuestas api        # API en http://127.0.0.1:8000; déjala corriendo en otra terminal
cd web
npm install                   # solo la primera vez
npm run dev                   # panel en http://localhost:3000
```

Para el uso diario, el servicio `apuestas-web` ya compila y sirve la versión de producción (`npm run build && npm start`).

- El panel llama a la API desde el navegador. La API solo acepta peticiones del panel abierto en `http://localhost:3000` o `http://127.0.0.1:3000` (CORS), así que ábrelo en una de esas direcciones.
- Desde la misma máquina la API no pide clave. Si la API corre en otra máquina (por ejemplo, detrás de un túnel), copia `web/.env.example` a `web/.env.local`, pon su dirección en `NEXT_PUBLIC_API_URL` y escribe tu clave en *Datos → Conexión*.
- Cargar **Hoy** recalcula las apuestas del día igual que `apuestas picks`, así que la primera carga puede tardar unos segundos.

### Capturas de cuotas (una IA lee la imagen)

En **Capturas** (o en el recuadro de **Hoy**) arrastra, elige o pega con Ctrl+V una captura de Betano o bet365. La API guarda la imagen y la lee una IA en segundo plano. Por defecto es una **IA local** (gratis, sin que la imagen salga de tu PC):
1. Un modelo de visión en tu PC (Ollama, `qwen2.5vl:7b`) **solo transcribe** la captura: partidos, títulos de mercado, selecciones, cuotas e importe.
2. Unas reglas fijas pasan ese texto a los mercados del sistema ("Doble oportunidad: Como o Empate" → `dc 1x`, "Galatasaray +1" en Hándicap → hándicap de 3 vías, "Anotará o asistirá" → gol o asistencia…).
3. El modelo calcula la probabilidad, el valor esperado y el veredicto, y el resumen sale de una plantilla con esos números (la IA no redacta, así no puede inventar cifras).

Tarda unos 5 a 10 segundos por captura con la tarjeta gráfica. Si lee mal una cuota, usa **Corregir cuotas** (se reevalúa con el modelo sin volver a leerla) o **Leer con Claude** para que la lea Claude Code con tu suscripción. Para instalar la IA local, ver [docs/instalacion.md](docs/instalacion.md#ia-local-para-las-capturas-opcional); sin ella, configura `APUESTAS_CAPTURES_ENGINE=claude_code` en `.env`.

**Registrar desde la captura.** Si ya hiciste la apuesta, pulsa **Registrar** junto a la cuota, o **Registrar esta combinada** debajo de una combinada, y escribe el importe (si Claude lo vio en la captura, ya viene puesto). Queda en **Mis apuestas** y se liquida sola, sin pasar por Evaluar cuota. Cada cuota o combinada se registra una sola vez, aunque vuelvas a leer o corrijas la captura. Una combinada con selecciones que el sistema no puede liquidar (atajadas, primer goleador…) hay que armarla sin ellas en Evaluar cuota.

**Combinadas y Bet Builders.** Si la captura es una combinada (una sola cuota para varias selecciones):
- Claude la separa por partidos.
- Dentro de un partido, la probabilidad conjunta sale de la matriz de marcadores, porque "gana el City" y "más de 2,5 goles" dependen entre sí. Los **goles y asistencias de jugadores** ("Kane anotará o asistirá", "gol de Mbappé", "2 o más goles") entran en ese mismo cálculo: cada gol del equipo se reparte entre sus jugadores según su parte de goles, xG, asistencias y xA.
- Córners, tarjetas, remates y faltas dentro de un Bet Builder se combinan como si no dependieran del resultado: el bloque sale marcado como **aproximado**.
- Los partidos distintos se multiplican, y el resultado se compara con la cuota de cada bloque y con la total.

Lo que el modelo no puede calcular aparece marcado con su motivo, sin inventar: atajadas, primer goleador, resultado exacto, o jugadores que no figuran en la alineación prevista. Si en la captura no hay nada evaluable, queda como **No evaluable**, con la explicación de Claude.

- Usa **tu suscripción de Claude**: cuenta para tu límite de uso, sin coste extra. Necesita el CLI `claude` con la sesión iniciada en esta PC y la API corriendo.
- La IA corre aislada: sin acceso a archivos ni a la terminal, solo con las tres herramientas de capturas.
- Por defecto solo se procesan automáticamente **tus** capturas (`APUESTAS_DEFAULT_USER`), porque la suscripción es personal. Los demás usuarios conectan su propio agente al MCP y le piden «procesa mis capturas pendientes».
- Para pasar a la API de Claude (de pago, por captura): `.venv/bin/pip install -e ".[api]"`, y en `.env` pon `APUESTAS_CAPTURES_ENGINE=api` y `APUESTAS_ANTHROPIC_API_KEY=...`. Ese motor está preparado pero **aún no se ha probado con una clave real**.
- Desde la terminal: `apuestas capturas lista` y `apuestas capturas procesar <id>`.
- Detalles y alternativas: [docs/adr/0005-capturas-con-ia.md](docs/adr/0005-capturas-con-ia.md).

### Telegram (opcional)

Crea un bot con @BotFather y pon `APUESTAS_TELEGRAM_TOKEN` y `APUESTAS_TELEGRAM_CHAT_ID` en `.env`. El worker envía la apuesta del día a las 9:00 (Lima) y avisa si cambia al salir las alineaciones.

### Betano (opcional)

Las cuotas de bet365 y Pinnacle llegan gratis vía football-data.co.uk (1X2, goles 2.5 y hándicap asiático), pero solo para las ligas, no para la Champions. Las de **Betano Perú** (también de la Champions, con córners, tarjetas y hándicap normal) llegan por [OddsPapi](https://oddspapi.io), que tiene cuenta gratuita:

1. Crea la cuenta en oddspapi.io y copia la clave de API de tu cuenta.
2. Pégala en `.env`: `APUESTAS_ODDSPAPI_KEY=...`.
3. Comprueba la clave con `.venv/bin/apuestas ingest oddspapi --estado` (muestra las peticiones usadas y el límite del mes) y haz la primera descarga con `.venv/bin/apuestas ingest oddspapi`.
4. Reinicia el worker: `systemctl --user restart apuestas-worker apuestas-api`. Desde entonces baja las cuotas cada día a las 08:30.

Por defecto descarga **Betano Perú y Pinnacle** (`APUESTAS_ODDSPAPI_BOOKMAKERS=betano.pe,pinnacle`). Pinnacle sirve de referencia del mercado afilado en la Champions. La API solo admite una casa por petición, así que cada casa cuesta 1 petición al día. Con dos casas son unas 60 peticiones al mes, más ~12 de catálogos (equipos, torneos y mercados, una vez por semana). El plan gratuito da 250 al mes. Para añadir bet365 (sus cuotas de Champions), pon `betano.pe,pinnacle,bet365` (+30 al mes).

## Resultado del backtest (honesto)

Con datos de 2024-25 y 2025-26 (≈2.100 partidos de EPL, Bundesliga y LaLiga):

- En **1X2, goles 2.5 y hándicap asiático** el modelo **no le gana a bet365**. Con los ratings implícitos del mercado (cuotas de cierre de partidos anteriores), la log-loss bajó de 0,993 a 0,981, pero bet365 está en 0,975. Ninguna estrategia en esos mercados es rentable: "solo modelo" da un ROI del −6,8 % (antes −4,2 %, diferencia dentro del ruido), con un CLV de +0,5 %.
- Los modelos de **faltas, remates y tarjetas** sí mejoran claramente a la media de la liga, pero no hay cuotas históricas gratuitas para medir su ROI. El árbitro ayuda en las tarjetas de LaLiga y la Bundesliga, no en las de la Premier.
- El **once confirmado** aporta poco con el índice actual: el efecto calibrado es un tercio del supuesto al principio (0,10 en lugar de 0,30).

Conclusión: el valor hay que buscarlo en **props, tarjetas con árbitro, remates y noticias de alineaciones**, no en el 1X2. Detalle en [docs/modelos.md](docs/modelos.md).

## Arquitectura

Monolito modular más un worker (tareas programadas). Ver [docs/arquitectura.md](docs/arquitectura.md) y las [decisiones (ADR)](docs/adr/).

Si trabajas en el código con una IA (Claude Code, Codex, Cursor…), [AGENTS.md](AGENTS.md) explica cómo debe trabajar y [docs/estado.md](docs/estado.md) en qué punto está el proyecto.

## Aviso

Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas permitirte perder. Los datos de fuentes no oficiales se usan con ritmo moderado y no se redistribuyen.
