# Estado del proyecto

Última actualización: 22 de octubre de 2026. Actualízalo cada vez que termines un cambio: qué cambió, qué decidió el usuario y qué queda pendiente.

## Qué funciona hoy

- **Ingesta diaria** de football-data, FotMob y Understat para Premier League, Bundesliga, LaLiga y Champions, más 9 ligas extra de football-data (solo para ratings del mercado de los rivales europeos). De la Europa League y la Conference, FotMob da además el árbitro y las estadísticas de equipo de los partidos jugados, sin alineaciones ni jugadores (desde el 2026-10-21). Equipos duplicados entre fuentes se fusionan solos cuando es seguro.
- **Modelo** de goles con fuerza de ataque y defensa, xG promediado y ratings implícitos de las cuotas de cierre; estadísticas (remates, córners, tarjetas, faltas) y proyecciones de jugadores. Ajuste por alineación y bajas. Las estadísticas de equipos con pocos partidos se contraen hacia la media, y en sus mercados la probabilidad se mezcla con la de la casa (desde el 2026-10-21: Aston Villa-Viking daba córners con +232 %, ahora como mucho +11 %). Los remates y los córners se guían además por la fuerza del modelo de goles, para comparar bien equipos de ligas distintas (desde el 2026-10-21: Betis-Feyenoord daba 4,3-5,6 córners frente a 5,3-4,1 de Pinnacle; ahora 4,9-4,9). Las estadísticas de la Europa League y la Conference entran en esos modelos (casi el doble de partidos entre ligas), pero su xG no entra en el de goles porque empeoraba la Champions. El reparto de remates, a puerta y córners entre los dos equipos se mueve hacia la diferencia de fuerza del 1X2 de la casa (Pinnacle, bet365 o Betano), sin cambiar el total (desde el 2026-10-22: Betis-Feyenoord daba 4,6-4,7 córners frente a 5,3-4,1 de Pinnacle; ahora 5,0-4,3).
- **Apuesta del día** a las 09:00 (solo mercados de goles), con un contador de aciertos desde el inicio en Hoy y en Mis apuestas (`GET /picks/record`; las retiradas al recalcular no cuentan) y **liquidación automática** de picks y apuestas después de cada partido (tarea `post_match`, a los :15 y :45).
- **Apuestas que pasan el corte** (desde el 2026-10-22): todas las apuestas con valor que pasan el corte de la apuesta del día se marcan al guardarse (`pick.qualifies`), salen primero en «Con valor» de Hoy y se liquidan solas. Tienen su propio contador en Hoy y en Mis apuestas, con las de los últimos 60 días y su resultado (`GET /picks/qualified`). Las guardadas antes del 22-10 se marcaron con el corte vigente ese día: el 22-10 iban 6 aciertos de 15 (40 %), −4,55 unidades.
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
| 2026-10-21 | Las estadísticas de la Europa League y la Conference entran en los modelos de remates, córners, faltas y tarjetas; su xG no entra en el modelo de goles (empeoraba la Champions). |
| 2026-10-22 | El 1X2 de la casa (Pinnacle, bet365 o Betano) mueve el reparto de remates, a puerta y córners entre los dos equipos (peso 0,75, el total no cambia). |
| 2026-10-22 | Las apuestas con valor que pasan el corte salen primero y se guardan con su resultado, con un contador de aciertos aparte del de la apuesta del día. |

## Pendiente o por decidir

- **Ramas de otras sesiones sin fusionar** (necesitan backtest y el OK del usuario):
  - `claude/competent-bartik-bb3a15`: nivel por liga en el modelo de goles y prudencia para ligas que apenas juegan contra otras.
  - `claude/focused-newton-7f7dce`: lo anterior más ligas extra en el modelo **por defecto**, lo que contradice la decisión del 2026-10-19.
  - `claude/precio-afilado-mercados`: Pinnacle como precio de referencia en todos los mercados de goles (incluye la rama anterior).
  - `claude/eloquent-murdock-250aed`: calidad de jugador con el rating de FotMob y `backtest --lineups`.
  - `claude/interesting-napier-01869b` (21-10-2026, solo documentación): el nivel por liga en córners con los cruces de la Europa League y la Conference no mejora. Choca con main en `docs/modelos.md` y en este archivo (añade un apartado en el mismo sitio que el reparto por el 1X2 del 2026-10-22).
- **Validar córners, tarjetas y props** con las cuotas de Betano que ya se guardan, antes de dejarlos entrar en la apuesta del día.
- **Córners de Champions entre ligas** (mejorado el 2026-10-21, con el OK del usuario): con la fuerza del modelo de goles como guía, el error por equipo frente a Pinnacle baja de 0,178 a 0,120 en la Champions y de 0,095 a 0,072 en las ligas, y "Córners de Feyenoord: Más de 7.5" pasa de +108 % a +41 %. Aún quedan diferencias con equipos grandes (Betis-Feyenoord 4,9-4,9 frente a 5,3-4,1; Bayern-Arsenal 4,6-4,2 frente a 5,5-4,2). El nivel por liga se probó y no mejora tanto (ruido: había muy pocos partidos entre ligas con estadísticas). Las estadísticas de la Europa League y la Conference (fusionadas el 2026-10-21 con el OK del usuario) mejoran un poco remates, faltas y córners en la Champions (remates por equipo entre ligas +0,013 ± 0,005; faltas por equipo +0,020 ± 0,007), pero frente a Pinnacle casi no cambian (0,120 → 0,119; Betis-Feyenoord 4,6-4,7). El nivel por liga con estos cruces tampoco mejora (rama `claude/interesting-napier-01869b`). **Causa encontrada y corregida el 2026-10-22** (fusionado con el OK del usuario): no es un sesgo del local grande ni de la Champions (con los córners reales, el local de la Champions sale +1,8 % y esta temporada −16 %), sino la diferencia de fuerza del modelo de goles, que los córners heredan: en Betis-Feyenoord el modelo de goles veía a los dos parejos (1X2 46/22/32) y Pinnacle al Betis claro favorito (60/20/20). Moviendo el reparto hacia el 1X2 de la casa (peso 0,75, el total no cambia): en el backtest, por equipo en las ligas, córners +0,0068, remates +0,0156 y a puerta +0,0087 (1X2, apuestas, tarjetas y faltas idénticos); frente a Pinnacle en la Champions con equipos conocidos, 0,119 → 0,070; Betis-Feyenoord 4,6-4,7 → 5,0-4,3. En la Champions no se puede medir con resultados (no hay cuotas de cierre guardadas). Queda Bayern-Arsenal (4,9-4,0 frente a 5,5-4,2): es el total, por la racha del Bayern; una memoria más corta se acerca a Pinnacle pero predice peor los córners reales, así que no se toca. Detalle en `docs/modelos.md`, sección 7.
- **Telegram**: falta crear el bot y poner el token en `.env`.
- **Diseño del panel**: los pendientes que la auditoría no mide están en la skill `disenio-panel` (tamaños grandes de texto sueltos, columnas de las cuotas de Betano, colores sueltos del campo de alineaciones).
- `loginctl enable-linger` para que los servicios sigan corriendo sin sesión iniciada (lo ejecuta el usuario).
- Más ideas del modelo en `docs/modelos.md`, "Próximas mejoras previstas".

## Limitaciones conocidas

- El modelo no le gana a bet365 en 1X2, goles ni hándicap asiático (ver el backtest en `docs/modelos.md`).
- Los mercados de estadísticas y jugadores no tienen backtest con cuotas reales. Los goles y asistencias de jugadores sí se comprobaron fuera de muestra (bien calibrados en 90 días; en los últimos 45, un 9 % cortos).
- OddsPapi: 250 peticiones al mes en el plan gratis.
- Los rivales europeos de ligas que football-data no cubre (Chequia, Croacia, Serbia…) no tienen ratings del mercado.
