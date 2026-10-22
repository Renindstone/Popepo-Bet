# Estado del proyecto

Última actualización: 21 de octubre de 2026. Actualízalo cada vez que termines un cambio: qué cambió, qué decidió el usuario y qué queda pendiente.

## Qué funciona hoy

- **Ingesta diaria** de football-data, FotMob y Understat para Premier League, Bundesliga, LaLiga y Champions, más 9 ligas extra de football-data (solo para ratings del mercado de los rivales europeos). Equipos duplicados entre fuentes se fusionan solos cuando es seguro.
- **Modelo** de goles con fuerza de ataque y defensa, xG promediado y ratings implícitos de las cuotas de cierre; estadísticas (remates, córners, tarjetas, faltas) y proyecciones de jugadores. Ajuste por alineación y bajas. Las estadísticas de equipos con pocos partidos se contraen hacia la media, y en sus mercados la probabilidad se mezcla con la de la casa (desde el 2026-10-21: Aston Villa-Viking daba córners con +232 %, ahora como mucho +11 %). Los remates y los córners se guían además por la fuerza del modelo de goles, para comparar bien equipos de ligas distintas (desde el 2026-10-21: Betis-Feyenoord daba 4,3-5,6 córners frente a 5,3-4,1 de Pinnacle; ahora 4,9-4,9).
- **Apuesta del día** a las 09:00 (solo mercados de goles), con un contador de aciertos desde el inicio en Hoy y en Mis apuestas (`GET /picks/record`; las retiradas al recalcular no cuentan) y **liquidación automática** de picks y apuestas después de cada partido (tarea `post_match`, a los :15 y :45).
- **Cuotas de Betano y Pinnacle** con OddsPapi a las 08:30 (una petición por casa y día), descartando las que vienen con local y visitante invertidos.
- **Panel web** (`web/`): apuesta del día, partidos del día, análisis, evaluar una cuota (con las **cuotas de Betano ya descargadas** de cada partido, evaluadas y listas para el cupón), mis apuestas y **capturas**: el usuario sube una imagen de Betano o bet365 y la lee la **IA local** (Ollama, qwen2.5vl:7b) o, con el botón «Leer con Claude», Claude Code; incluidas combinadas y Bet Builders.
- **Diseño del panel** con un sistema propio (skill `disenio-panel`: paleta, escala de texto con tokens `text-etiqueta`/`text-nota`/`text-interfaz`, formas, movimiento) y una auditoría automática (skill `run-app-apuestas`) que sale limpia en escritorio y celular, claro y oscuro: sin desborde, sin texto de menos de 12 px, contraste AA y toques de al menos 24 px (desde el 2026-10-21). Las cuotas de Betano de hándicap de córners y tarjetas ya salen con nombre. La página de un partido va en **pestañas** (Alineaciones, Probabilidades, Estadísticas, Cuotas y Jugadores; de 13.400 px de alto en el celular a 3.500 como máximo), y Hoy también: debajo de la apuesta del día, Partidos, Con valor y Props (un sábado de 14 partidos, de 7.800 px a unos 4.200; desde el 2026-10-21). El menú del celular muestra una flecha cuando hay más secciones a un lado.
- **Mercados de jugador**: gol (también 2 o más), asistencia y gol o asistencia, con xG y xA; en Bet Builders se calculan junto con el resultado. Córners y tarjetas en un Bet Builder salen "aproximados" (desde el 2026-10-20).
- **Registrar desde una captura** (`POST /captures/{id}/bet`): una cuota o la combinada entera, con el importe que Claude leyó si se ve; la captura recuerda lo registrado (`engine_info.bets`) para no duplicarlo.
- **Cupón en Evaluar cuota**: varias selecciones de uno o varios partidos (Bet Builders y combinada), evaluadas juntas (`POST /combos/evaluate`) y registradas como una apuesta `combo` con sus selecciones en `user_bet_leg` (`POST /combos`); se liquidan solas.
- **Alineaciones en el campo** en cada partido (`GET /matches/{id}/lineups`): probables y luego confirmadas, con formación, entrenador, dorsales, posición (de FotMob), suplentes y bajas. La confirmada se busca 70, 50, 35, 20 y 10 minutos antes del inicio (desde el 2026-10-21).
- **Escudos de los equipos** junto a sus nombres en Hoy, Partidos, el partido y las alineaciones (de FotMob, en caché).
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
| 2026-10-21 | La página de un partido va en pestañas y el menú del celular avisa con una flecha de que se desplaza. |
| 2026-10-21 | Hoy va en pestañas (Partidos, Con valor, Props) debajo de la apuesta del día; Aciertos, «¿Viste una cuota?» y «Antes de apostar» siguen justo debajo de la apuesta también en el celular. |
| 2026-10-21 | Las capturas las lee por defecto una IA local (Ollama) que solo transcribe; Claude queda como respaldo con un botón. En Evaluar cuota se muestran las cuotas de Betano guardadas para no necesitar captura. |

## Pendiente o por decidir

- **Ramas de otras sesiones sin fusionar** (necesitan backtest y el OK del usuario):
  - `claude/competent-bartik-bb3a15`: nivel por liga en el modelo de goles y prudencia para ligas que apenas juegan contra otras.
  - `claude/focused-newton-7f7dce`: lo anterior más ligas extra en el modelo **por defecto**, lo que contradice la decisión del 2026-10-19.
  - `claude/precio-afilado-mercados`: Pinnacle como precio de referencia en todos los mercados de goles (incluye la rama anterior).
  - `claude/eloquent-murdock-250aed`: calidad de jugador con el rating de FotMob y `backtest --lineups`.
- **Validar córners, tarjetas y props** con las cuotas de Betano que ya se guardan, antes de dejarlos entrar en la apuesta del día.
- **Córners de Champions entre ligas** (mejorado el 2026-10-21, con el OK del usuario): con la fuerza del modelo de goles como guía, el error por equipo frente a Pinnacle baja de 0,178 a 0,120 en la Champions y de 0,095 a 0,072 en las ligas, y "Córners de Feyenoord: Más de 7.5" pasa de +108 % a +41 %. Aún quedan diferencias con equipos grandes (Betis-Feyenoord 4,9-4,9 frente a 5,3-4,1; Bayern-Arsenal 4,6-4,2 frente a 5,5-4,2). El nivel por liga se probó y no mejora tanto (ruido: hay muy pocos partidos entre ligas con estadísticas). Lo que más ayudaría: estadísticas de la Europa League y la Conference, de las que hoy solo se descargan los resultados.
- **Telegram**: falta crear el bot y poner el token en `.env`.
- **Diseño del panel**: los pendientes que la auditoría no mide están en la skill `disenio-panel` (tamaños grandes de texto sueltos, columnas de las cuotas de Betano, colores sueltos del campo de alineaciones).
- `loginctl enable-linger` para que los servicios sigan corriendo sin sesión iniciada (lo ejecuta el usuario).
- Más ideas del modelo en `docs/modelos.md`, "Próximas mejoras previstas".

## Limitaciones conocidas

- El modelo no le gana a bet365 en 1X2, goles ni hándicap asiático (ver el backtest en `docs/modelos.md`).
- Los mercados de estadísticas y jugadores no tienen backtest con cuotas reales. Los goles y asistencias de jugadores sí se comprobaron fuera de muestra (bien calibrados en 90 días; en los últimos 45, un 9 % cortos).
- OddsPapi: 250 peticiones al mes en el plan gratis.
- Los rivales europeos de ligas que football-data no cubre (Chequia, Croacia, Serbia…) no tienen ratings del mercado.
