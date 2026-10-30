# Popepo-Bet ⚽

Análisis de apuestas de fútbol **prepartido** con modelos estadísticos para la **Premier League, Bundesliga, LaLiga, Serie A, Ligue 1, Primeira Liga (Portugal), Pro League (Bélgica) y Champions League**.
Calcula la probabilidad de cada mercado, la compara con la cuota de la casa (bet365, Betano) y propone una apuesta del día. Se usa desde un **panel web**, desde Claude (u otro agente) por **MCP**, por **API REST** o por **Telegram**.

No promete ganancias: el backtest dice con honestidad dónde el modelo no le gana a la casa (ver [más abajo](#resultado-del-backtest-honesto)).

## Qué hace

- **Recoge datos gratis**: football-data.co.uk (resultados, estadísticas y cuotas de cierre de bet365), FotMob (datos Opta: estadísticas, alineaciones previstas y confirmadas, lesiones, sanciones, árbitros y estadísticas por jugador; de la Europa League y la Conference solo el árbitro y las estadísticas de equipo de los partidos jugados, sin alineaciones ni jugadores) y Understat (segundo modelo de xG). Opcional: OddsPapi para las cuotas de **Betano** y Pinnacle antes de cada partido. Ver [docs/fuentes.md](docs/fuentes.md).
- **Valida las fuentes entre sí**: los conteos (remates, córners, tarjetas…) se comparan y se marcan discrepancias; el xG se promedia entre proveedores. Si una fuente se cae, las demás siguen y el panel muestra el motivo.
- **Modelos**: fuerza de ataque y defensa conjunta para 17 competiciones (las cinco grandes ligas, Portugal, Bélgica, la Champions, la Europa League, la Conference y siete ligas más que conectan la escala para rivales europeos y equipos ascendidos), con los ratings implícitos de las cuotas de cierre. Dixon-Coles para goles y binomial negativa para remates, remates a puerta, córners, faltas y tarjetas, con el **factor de árbitro** y el reparto entre los dos equipos guiado por el 1X2 de la casa. Ver [docs/modelos.md](docs/modelos.md).
- **Jugadores**: goles, asistencias y «gol o asistencia» como parte de los goles de su equipo; remates, remates a puerta, faltas y tarjetas por jugador, con sus minutos esperados.
- **Alineaciones y bajas**: compara el once (previsto o confirmado) con el once típico del equipo según el valor de mercado y el rating de cada jugador. Que falte un Szoboszlai baja el ataque y la defensa del Liverpool. El once confirmado se busca 70, 50, 35, 20 y 10 minutos antes del inicio.
- **Dificultad del rival** para cada equipo (Fácil → Difícil) y **contexto**: descanso, calendario cargado y riesgo de rotación si juega Champions en ≤4 días.
- **Valor esperado** contra las cuotas de bet365 y Betano, mezclando el modelo con el mercado afilado (Pinnacle, Betfair).
- **Apuesta del día**: la de mayor valor × confianza entre las que pasan el corte. Si ninguna lo pasa, **no hay apuesta del día**. Todas las que pasan el corte se guardan y se liquidan solas, con su propio contador de aciertos. Los contadores miden la cuota y el valor que se anunciaron, aunque un recálculo posterior los cambie o retire la apuesta.
- **Combinadas y Bet Builders**: las selecciones de un mismo partido se evalúan juntas con la matriz de marcadores (están correlacionadas) y las de partidos distintos se multiplican.
- **Capturas**: subes una captura de Betano o bet365 y una IA local la lee; el modelo da el veredicto de cada cuota.
- **Sorpresas**: el equipo, el jugador y el once de la semana o del mes que más superaron lo esperado, el radar de los que van en racha o en baja, avisos en las apuestas cuando juega uno de ellos y «Por qué falló» cuando se pierde la apuesta del día.
- **Cuotas mínimas** para props (remates, tarjetas, córners, jugadores): la cuota a partir de la cual vale la pena en Betano.
- **Seguimiento** de tus apuestas: liquidación automática, ROI, CLV, banca, rendimiento por mercado, competición y casa, y límites de pérdida.
- **Almacenamiento por niveles** (temporada actual / historial / archivo Parquet) con resúmenes de temporada. Ver [docs/adr/0003-almacenamiento-por-niveles.md](docs/adr/0003-almacenamiento-por-niveles.md).

## Puesta en marcha

Funciona en Linux (Arch, Fedora, Debian, Ubuntu…), Mac y Windows (con WSL). La guía con los pasos de cada sistema, la actualización y los problemas frecuentes está en **[docs/instalacion.md](docs/instalacion.md)**. Resumen:

1. Instala Git, Python 3.12 o superior, PostgreSQL y Node.js 20.9 o superior (el comando de tu sistema está en la guía).
2. Descarga e instala; la primera vez tarda 3 o 4 horas porque baja el historial:

```bash
git clone https://github.com/Renindstone/Popepo-Bet.git && cd Popepo-Bet
scripts/instalar.sh
```

3. Arráncalo y abre el panel en http://localhost:3000:

```bash
scripts/install-services.sh --with-web   # Linux y Windows: BD, worker, API y panel quedan funcionando solos
scripts/arrancar.sh                      # Mac: todo en esa terminal; Ctrl+C lo para
```

## Uso diario

| Comando | Para qué |
|---|---|
| `apuestas picks` | Apuesta del día + otras con valor + props para revisar |
| `apuestas analyze "Arsenal vs Chelsea"` | Análisis completo de un partido (`--json` para todo el detalle) |
| `apuestas semana` | Equipo, jugador y once de la semana (`--semana AAAA-MM-DD` para otra, `--mes` para las 4 semanas que terminan en ella, `--json` para el detalle) |
| `apuestas evaluate "Arsenal vs Chelsea" ou_cards over 1.85 --line 4.5` | ¿Vale la pena esta cuota de Betano? |
| `apuestas status` | Frescura de las fuentes y del modelo |
| `apuestas settle` | Liquida ahora los picks y apuestas de partidos terminados (el worker lo hace solo) |
| `apuestas ingest oddspapi --estado` | Peticiones de OddsPapi usadas este mes (cupo gratis: 250) |
| `apuestas backtest` | Valida el modelo contra cuotas históricas de bet365 |
| `apuestas archive report` | Espacio usado |
| `apuestas equipos duplicados` | Equipos que parecen el mismo club en dos fuentes (los seguros se fusionan solos en cada ingesta) |

### Conectar Claude (MCP)

El repo incluye [.mcp.json](.mcp.json): al abrir Claude Code en esta carpeta aparece el servidor `apuestas`. Para Claude Desktop, añade el mismo bloque en su configuración. Herramientas: `apuesta_del_dia`, `comparar_casas`, `historial_apuesta_del_dia`, `analizar_partido`, `evaluar_cuota`, `evaluar_combinada`, `resumen_semana`, `datos_radar`, `datos_fallo`, `bajas_equipo`, `registrar_baja`, `perfil_arbitro`, `proyeccion_jugador`, `registrar_apuesta`, `mis_apuestas`, `mi_rendimiento`, `estado_datos`, `capturas_pendientes`, `ver_captura`, `evaluar_captura`, etc.

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

Interfaz visual en [web/](web/) (Next.js + ECharts). Necesita Node.js 20.9 o superior. Tiene siete páginas:
- **Hoy**: la portada. La apuesta del día como titular, con su ficha de cifras (cuota, probabilidad, cuota justa, valor esperado, confianza y banca); al lado, **La jornada** (los partidos del día por competición, con el 1X2 del modelo). Debajo, tres pestañas con cuántas filas tiene cada una: **Con valor** (otras apuestas con valor, por defecto primero las que **pasan el corte** de valor, probabilidad y confianza, con su propio contador de aciertos; en los días pasados, con su resultado. Un selector las ordena también por **más probables**, **más confianza** o **más valor**, y el navegador recuerda la elección. No salen las cuotas de menos de 1.20, `APUESTAS_VALUE_LIST_MIN_ODDS`), **Props** (cuota mínima) y **Frente a Pinnacle** (las cuotas de Betano que pagan al menos un 2 % más que la justa de Pinnacle, sin modelo: comparar precios; pasa sobre todo en córners y tarjetas). La pestaña queda en la dirección (`#valor`, `#props`, `#precio`) y se mantiene al pasar al día anterior o al siguiente. El aspecto del panel (portada de diario deportivo) está descrito en [`DESIGN.md`](DESIGN.md). Además, un acceso rápido para subir capturas y el **contador de aciertos** de la apuesta del día desde el inicio (aciertos, falladas, devueltas, por jugarse y beneficio con 1 unidad por apuesta).
- **Partidos**: próximos partidos con filtros por competición y días, y un buscador (lupa) que filtra mientras escribes el nombre de cualquiera de los dos equipos; no distingue tildes y entiende iniciales como "psg". Al elegir uno, análisis completo del partido en cinco pestañas: **Alineaciones** (en el campo como FotMob: las probables hasta que se confirman, que se buscan 70, 50, 35, 20 y 10 minutos antes del inicio, con formación, entrenador, dorsales, suplentes, bajas y cómo cambian los goles esperados), **Probabilidades**, **Estadísticas** (con el árbitro y el contexto), **Cuotas** (las que tienen valor y la cuota mínima de los props) y **Jugadores**. La pestaña queda en la dirección (por ejemplo `#cuotas`), así que se puede guardar o compartir.
- **Sorpresas** (antes «Semana»; `/semana` lleva aquí): el **equipo**, el **jugador** y el **once de la semana** o **del mes** (las 4 semanas completas que terminan en la elegida; se abre cuando hay 4 semanas con la previa guardada, desde el 23-11-2026), y los 10 primeros de cada uno. Los equipos se miden frente a la casa (resultado, goles y córners contra el 1X2 sin margen y la línea principal antes del partido) y los jugadores frente a lo que esperaba el modelo antes del partido (remates, a puerta, goles y asistencias, ajustados a sus minutos). Cada dato suma de −1 a +1 según lo raro que fue: superar 9.5 córners con 15 vale más que con 10, y ganar de punto más que de favorito. Es un resumen, no una predicción. Las semanas se recorren con las flechas; los jugadores cuentan desde el 24-10-2026, cuando se empezó a guardar la previa.
  - **En el radar**: los equipos en racha y en baja y los jugadores en racha de las últimas 4 semanas, con el porqué (un **batacazo** es ganar cuando la casa daba un 25 % o menos; un **pinchazo**, perder cuando daba un 60 % o más), sus figuras y su próximo partido. El dueño puede pedir «Investigar con Claude».
  - **Avisos**: en la apuesta del día, «Con valor», la lista de partidos y la página del partido, cuando juega un equipo del radar, con sus figuras en el once o no. Son avisos: no cambian la probabilidad ni el corte.
  - **Por qué falló**: cuando se pierde la apuesta del día, lo que esperaba la previa frente a lo que pasó, si «Sorpresas» ya lo avisaba y una explicación escrita por Claude a partir de noticias, con sus fuentes (con la suscripción de la PC, como las capturas).
- **Interruptor de la IA**: al final de Datos, cada usuario decide si usa la IA. Apagada, desaparecen las capturas y las explicaciones de Claude; los números del modelo no cambian.
- **Evaluar cuota**: comprobar una cuota de Betano y registrar la apuesta. Al elegir un partido, debajo salen **las cuotas de Betano que ya se descargaron** esa mañana, evaluadas por el modelo (primero las que tienen valor): **Evaluar** las pasa al formulario y **+ Cupón** las añade al cupón, sin captura. Con **Añadir al cupón** se juntan varias selecciones: varias de un mismo partido forman un Bet Builder (escribe la cuota que te da la casa) y las de partidos distintos, una combinada. **Evaluar cupón** calcula cada partido y el total con el modelo, y **Registrar cupón** la guarda como una sola apuesta que se liquida sola: basta una selección perdida para perderla, y si una se anula, la cuota total se ajusta.
- **Capturas**: subir o pegar una captura de cuotas. Una IA la lee (local por defecto, o Claude con un botón) y el modelo da el veredicto de cada cuota (ver más abajo).
- **Mis apuestas**: ROI, CLV, desglose y banca, el historial de la apuesta del día (desde el inicio y en el último año) y el de **todas las que pasan el corte** (aciertos desde el inicio y las de los últimos 60 días con su resultado y su **CLV**: la cuota tomada frente a la justa de Pinnacle, sin margen, unos 15 minutos antes del partido). La **banca inicial** (y su moneda) se edita ahí mismo; de ella salen el stake sugerido y los límites de pérdida, y la banca actual es la inicial más lo ganado o perdido.
- **Datos**: frescura de las fuentes y del modelo. El botón **Sincronizar** (junto a «Fuentes») descarga en ese momento lo de las 05:30 y las 08:30 de FotMob, football-data y Understat, liquida y reentrena el modelo (`POST /sync`; tarda unos minutos, no gasta peticiones de OddsPapi y se puede repetir cada 10 minutos).

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

**Registrar desde la captura.** Si ya hiciste la apuesta, pulsa **Registrar** junto a la cuota, o **Registrar esta combinada** debajo de una combinada, y escribe el importe (si la IA lo vio en la captura, ya viene puesto). Queda en **Mis apuestas** y se liquida sola, sin pasar por Evaluar cuota. Cada cuota o combinada se registra una sola vez, aunque vuelvas a leer o corrijas la captura. Una combinada con selecciones que el sistema no puede liquidar (atajadas, primer goleador…) hay que armarla sin ellas en Evaluar cuota.

**Combinadas y Bet Builders.** Si la captura es una combinada (una sola cuota para varias selecciones):
- Se separa por partidos.
- Dentro de un partido, la probabilidad conjunta sale de la matriz de marcadores, porque "gana el City" y "más de 2,5 goles" dependen entre sí. Los **goles y asistencias de jugadores** ("Kane anotará o asistirá", "gol de Mbappé", "2 o más goles") entran en ese mismo cálculo: cada gol del equipo se reparte entre sus jugadores según su parte de goles, xG, asistencias y xA.
- Córners, tarjetas, remates y faltas dentro de un Bet Builder se combinan como si no dependieran del resultado: el bloque sale marcado como **aproximado**.
- Los partidos distintos se multiplican, y el resultado se compara con la cuota de cada bloque y con la total.

Lo que el modelo no puede calcular aparece marcado con su motivo, sin inventar: atajadas, primer goleador, resultado exacto, o jugadores que no figuran en la alineación prevista. Si en la captura no hay nada evaluable, queda como **No evaluable**, con el motivo.

Con **Leer con Claude** (o `APUESTAS_CAPTURES_ENGINE=claude_code`) la lee Claude Code:

- Usa **tu suscripción de Claude**: cuenta para tu límite de uso, sin coste extra. Necesita el CLI `claude` con la sesión iniciada en esta PC y la API corriendo.
- La IA corre aislada: sin acceso a archivos ni a la terminal, solo con las tres herramientas de capturas.
- Por defecto solo se procesan automáticamente **tus** capturas (`APUESTAS_DEFAULT_USER`), porque la suscripción es personal. Los demás usuarios conectan su propio agente al MCP y le piden «procesa mis capturas pendientes».
- Para pasar a la API de Claude (de pago, por captura): `.venv/bin/pip install -e ".[api]"`, y en `.env` pon `APUESTAS_CAPTURES_ENGINE=api` y `APUESTAS_ANTHROPIC_API_KEY=...`. Ese motor está preparado pero **aún no se ha probado con una clave real**.
- Desde la terminal: `apuestas capturas lista` y `apuestas capturas procesar <id>`.
- Detalles y alternativas: [docs/adr/0005-capturas-con-ia.md](docs/adr/0005-capturas-con-ia.md).

### Telegram (opcional)

Crea un bot con @BotFather y pon `APUESTAS_TELEGRAM_TOKEN` y `APUESTAS_TELEGRAM_CHAT_ID` en `.env`. El worker envía la apuesta del día a las 9:00 (Lima) y avisa si cambia al salir las alineaciones.

### Betano (opcional)

Las cuotas de bet365 llegan gratis vía football-data.co.uk (1X2, goles 2.5 y hándicap asiático; las de Pinnacle, solo hasta 2025-26), pero solo para las ligas, no para las copas europeas. Las de **Betano Perú** y Pinnacle antes de cada partido (también de la Champions, con goles por equipo, córners, tarjetas y hándicap de 3 vías) llegan por [OddsPapi](https://oddspapi.io), que tiene cuenta gratuita:

1. Crea la cuenta en oddspapi.io y copia la clave de API de tu cuenta.
2. Pégala en `.env`: `APUESTAS_ODDSPAPI_KEY=...`.
3. Comprueba la clave con `.venv/bin/apuestas ingest oddspapi --estado` (muestra las peticiones usadas y el límite del mes) y haz la primera descarga con `.venv/bin/apuestas ingest oddspapi`.
4. Reinicia el worker: `systemctl --user restart apuestas-worker apuestas-api`. Desde entonces baja las cuotas cada día a las 08:30.

Por defecto descarga **Betano Perú y Pinnacle** (`APUESTAS_ODDSPAPI_BOOKMAKERS=betano.pe,pinnacle`). Pinnacle sirve de referencia del mercado afilado en la Champions. La API solo admite una casa y 5 competiciones por petición, así que solo se piden las competiciones que juegan en los próximos 3 días (`APUESTAS_ODDSPAPI_WINDOW_DAYS`): 1 petición por casa y día si son 5 o menos, y 2 si son más (con Portugal y Bélgica, casi cada día). Con dos casas son unas 70-106 peticiones al mes (con el calendario de 2025-26), más ~12 de catálogos y, para el CLV, hasta 3 de Pinnacle al día: unas 120-210 en total (equipos, torneos y mercados, una vez por semana). El plan gratuito da 250 al mes. Para añadir bet365 (sus cuotas de Champions), pon `betano.pe,pinnacle,bet365` (+30 al mes).

## Resultado del backtest (honesto)

Con datos de 2024-25 y 2025-26 (≈2.100 partidos de EPL, Bundesliga y LaLiga; desde el 21-10-2026, además, ≈1.360 de la Serie A y la Ligue 1):

- En **1X2, goles 2.5 y hándicap asiático** el modelo **no le gana a bet365**. Con los ratings implícitos del mercado (cuotas de cierre de partidos anteriores), la log-loss bajó de 0,993 a 0,981, pero bet365 está en 0,975. Ninguna estrategia en esos mercados es rentable: "solo modelo" da un ROI del −6,8 % (antes −4,2 %, diferencia dentro del ruido), con un CLV de +0,5 %. En la Serie A y la Ligue 1 pasa lo mismo: el modelo queda cerca de bet365 (en la Ligue 1, a la par), pero no le gana.
- Los modelos de **faltas, remates y tarjetas** sí mejoran claramente a la media de la liga, pero no hay cuotas históricas gratuitas para medir su ROI. El árbitro ayuda en las tarjetas de LaLiga, la Serie A y la Bundesliga, no en las de la Premier, y en las faltas de la Ligue 1.
- En los **rivales europeos con pocos partidos** (por ejemplo, Viking), las estadísticas se acercan a la media y, en sus mercados, la probabilidad se mezcla con la de la casa. Así no salen valores absurdos, pero esas cuotas no son de fiar. Los remates y los córners se guían por la fuerza del modelo de goles para comparar equipos de ligas distintas, pero en la Champions aún quedan diferencias con Pinnacle (ver `docs/modelos.md`).
- El **once confirmado** aporta poco con el índice actual: el efecto calibrado es un tercio del supuesto al principio (0,10 en lugar de 0,30).

Conclusión: el valor hay que buscarlo en **props, tarjetas con árbitro, remates y noticias de alineaciones**, no en el 1X2. Detalle en [docs/modelos.md](docs/modelos.md).

Hay además una auditoría con datos públicos de 14 ligas (octubre de 2026), con propuestas para mejorar el modelo y experimentos que cualquiera puede repetir: [docs/auditoria-modelo.md](docs/auditoria-modelo.md) y [experimentos/auditoria/](experimentos/auditoria/).

## Arquitectura

Monolito modular más un worker (tareas programadas). Ver [docs/arquitectura.md](docs/arquitectura.md) y las [decisiones (ADR)](docs/adr/).

Si trabajas en el código con una IA (Claude Code, Codex, Cursor…), [AGENTS.md](AGENTS.md) explica cómo debe trabajar y [docs/estado.md](docs/estado.md) en qué punto está el proyecto.

## Aviso

Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas permitirte perder. Los datos de fuentes no oficiales se usan con ritmo moderado y no se redistribuyen.
