# Sorpresas: radar, avisos, «Por qué falló» y el interruptor de la IA

Diseño acordado con el dueño el 29-10-2026 (conversación de diseño con bocetos). Lo marcado *(decisión mía)* lo decidió
quien escribe el documento y el dueño puede cambiarlo; lo demás lo decidió él.

## Intención

La página «Semana» ya mide qué equipos y jugadores superaron lo esperado (puntuación por sorpresa, `services/weekly.py`,
ADR 0006). El dueño quiere sacarle partido de tres maneras:

1. **Seguir de cerca** a los equipos y jugadores que rinden muy por encima o muy por debajo de lo esperado.
2. **Que le avisen a tiempo**: cuando una apuesta (la del día o una que pasa el corte) involucra a un equipo que viene
   de dar un batacazo o que viene en baja, y si las figuras de esa sorpresa están en el once.
3. **Entender por qué falló** la apuesta del día cuando la culpa es de uno de esos equipos, con lo que se salió de lo
   esperado y, si quiere, una explicación escrita por Claude a partir de noticias.

El caso que lo motivó: un favorito que pierde contra un rival que acababa de dar la sorpresa, con las mismas figuras en
el once.

## Objetivos

- Renombrar «Semana» a **«Sorpresas»** y añadir la vista **Mes** (las últimas 4 semanas).
- **En el radar**: equipos en racha y en baja, y jugadores en racha, con su próximo partido.
- **Avisos** en la apuesta del día, en «Con valor» (las que pasan el corte), en la lista de partidos y en la página del
  partido.
- **«Por qué falló»** en la apuesta del día perdida, con los números y la explicación de Claude.
- **Interruptor de la IA por usuario**: cada persona que entra con su clave decide si usa la IA.

## No objetivos

- **Los avisos no cambian la probabilidad, la confianza ni el corte.** Antes hay que medir con el historial si los
  equipos que dan la sorpresa la repiten (o si vuelven a la media). Eso es un paso aparte, con `apuestas backtest` y
  el OK del dueño (regla 5 de AGENTS.md).
- No se cambia cómo se calcula la puntuación por sorpresa (ADR 0006).
- No hay explicación de Claude para las apuestas que pasan el corte ni para las apuestas del usuario: solo para la
  apuesta del día perdida y para lo que se pida a mano en el radar.

## Anti-objetivos (sería un fracaso aunque funcione)

- Que un aviso parezca una predicción o una «apuesta segura» en contra. El texto dice qué pasó, con qué probabilidad
  lo daba la casa, y que es un aviso.
- Que la IA calcule números. Las cifras salen siempre del modelo y de la base de datos; Claude solo escribe la
  explicación.
- Que la explicación de Claude se presente como un hecho: va firmada («Explicación de Claude»), con sus fuentes y la
  hora a la que se escribió.
- Que con la IA apagada quede rastro de la IA en el panel de ese usuario.
- Gastar la suscripción del dueño sin control: como mucho una explicación automática al día más las que él pida.

## Restricciones

- Repositorio público, reglas de AGENTS.md. Hora de Lima en todo lo visible.
- Diseño del panel: `DESIGN.md` (portada de diario deportivo) y la skill `disenio-panel`. Avisos con el filete arriba,
  nunca con borde lateral grueso; etiquetas con palabra, nunca solo color.
- Claude se lanza como ya se hace con las capturas (`services/capture_engines.py`, `claude -p` con la suscripción de
  la PC, aislado y sin archivos ni terminal).
- Los jugadores solo tienen sorpresa desde el 24-10-2026 (la previa se empezó a guardar ese día). Los equipos tienen
  historial completo, porque su vara es la cuota de la casa.

## 1. Página «Sorpresas»

- Ruta `/sorpresas`; `/semana` redirige a ella (con su `?semana=`). En el menú, «Sorpresas» en lugar de «Semana».
- Selector **Semana / Mes** arriba. Semana es lo que hay hoy (equipo, jugador, once y los 10 primeros).
- **Mes = las últimas 4 semanas completas** *(decisión mía: 4 semanas seguidas en vez del mes del calendario, que en
  octubre saldría a medias)*. Muestra lo mismo que la semana (equipo, jugador y once del mes, y los 10 primeros),
  sumando las 4 semanas, con la media por partido como en la semana. *(Decisión mía:)* son las 4 semanas completas
  que terminan en la semana elegida (el mismo `?semana=` de la vista Semana); por defecto, la última semana completa,
  así que la semana en curso no entra. «Anterior» y «Siguiente» se mueven de 4 en 4 semanas.
- El Mes se activa cuando hay 4 semanas completas con la previa guardada (la primera: del 26-10 al 22-11, visible desde
  el 23-11). Antes, el selector lo enseña apagado con la fecha.
- **En el radar** va en la misma página, debajo (ver 2).
- MCP: `resumen_semana` acepta `periodo` (`semana` o `mes`). CLI: `apuestas semana --mes` *(decisión mía: se mantienen
  los nombres para no romper lo que ya los usa)*.

## 2. En el radar

Calculado sobre las **últimas 4 semanas** hasta hoy (no hasta el final de la semana elegida), con los partidos
terminados.

- **En racha** (equipos): suma de sorpresa ≥ +1,0 en las 4 semanas, o al menos un **batacazo**.
- **En baja** (equipos): suma ≤ −1,0, o al menos un **pinchazo**.
- **Batacazo**: ganar cuando la casa le daba un 25 % o menos de ganar (1X2 sin margen antes del partido, la misma vara
  de la puntuación por sorpresa). **Pinchazo**: perder cuando la casa le daba un 60 % o más.
- **Jugadores en racha**: suma ≥ +1,5 en las 4 semanas, con al menos 90 minutos jugados en ellas. Los jugadores en baja
  no se muestran *(decisión mía: el dueño habló de equipos en baja; un jugador «en baja» es casi siempre uno que
  remató poco un día)*.
- *(Decisión mía)* Los umbrales son constantes en el código, fáciles de ajustar; como mucho 8 equipos por lado y 8
  jugadores, ordenados por la suma.
- Cada fila dice **por qué está** (el batacazo o pinchazo más llamativo, con el resultado y la probabilidad de la
  casa, o la suma), su **puntuación** y su **próximo partido** (y el siguiente, si es de las próximas dos semanas).
- **Figuras de un equipo en racha**: hasta 2 jugadores de ese equipo con puntuación ≥ +1,5 en sus partidos
  sorprendentes. Para un partido próximo se marca si cada figura está en el once (confirmado o probable, de `lineup`).
- Botón **«Investigar con Claude»** en cada fila (ver 5).

## 3. Avisos

Un aviso es la ficha del radar de uno de los dos equipos de un partido próximo: «en racha» o «en baja», el porqué
corto y, si está en racha, sus figuras y si están en el once.

Dónde aparece:

- **Apuesta del día (Hoy)**: recuadro bajo la ficha de cifras, uno por equipo del radar.
- **«Con valor» (Hoy)**: en las que pasan el corte, una etiqueta por equipo del radar («Milan en baja», «Genoa en
  racha»); en escritorio en una columna «Aviso» y en el celular bajo la fila. Al tocarla se ve el porqué.
  *(Decisión mía: también en las que no llegan al corte, con el mismo formato; el dueño pidió las que pasan, y
  mostrarlo en todas cuesta lo mismo y no confunde.)*
- **Lista de partidos** (página Partidos y «La jornada» de Hoy): la etiqueta junto al nombre del equipo.
- **Página del partido**: recuadros bajo la cabecera, como en la apuesta del día.

Texto, con datos reales: «Milan viene rindiendo por debajo de lo esperado. Perdió 2-4 con Bologna en casa el 28-10,
cuando la casa le daba un 58 %. Suma −1,19 en las últimas 4 semanas.» Y debajo, siempre: «Es un aviso para mirarlo con
más cuidado: no cambia la probabilidad ni el corte.»

Los avisos dependen solo de los datos, no de la IA: se ven con la IA encendida o apagada. *(Decisión mía:)* también
van en las respuestas de `analizar_partido` y `partidos_proximos` del MCP, para que el agente de cada usuario los vea.

## 4. «Por qué falló»

Cuando la **apuesta del día** se liquida como perdida (o medio perdida), se guarda un análisis con lo que se salió de
lo esperado, comparando la **previa guardada** del partido (`prediction.payload`) con lo que pasó
(`team_match_stats`, `player_match_stats`):

- Goles, remates a puerta y córners de cada equipo frente a lo esperado, con su puntuación (las mismas funciones de
  `weekly.py`).
- Los jugadores con mayor puntuación, por arriba y por abajo (como mucho 3).
- **¿Lo avisaba Sorpresas?**: si alguno de los dos equipos estaba en el radar cuando se generó la apuesta, y si sus
  figuras jugaron.

Se muestra en Hoy (al ver un día pasado con la apuesta perdida) y en Mis apuestas (historial de la apuesta del día,
desplegable en la fila perdida). Sin previa guardada (partidos de antes del 24-10) dice «No hay previa guardada de este
partido».

Los números se ven siempre; la explicación de Claude (5) solo con la IA encendida.

## 5. Explicación de Claude

- **Cuándo**: automáticamente, una vez, cuando se pierde la apuesta del día (después de la liquidación de
  `post_match`). Y a mano con «Investigar con Claude» en una fila del radar. *(Decisión mía:)* la automática solo se
  lanza si alguno de los usuarios que pueden usar el motor (`captures_engine_users`) tiene la IA encendida; si no, no
  se gasta la suscripción.
- **Sin Claude en la PC** (otra máquina sin el programa `claude` o sin sesión iniciada): la nota queda en `error` con
  el motivo, y el panel lo dice en lugar de la explicación.
- **Quién la escribe**: `claude -p` con la suscripción iniciada en la PC, como el motor de capturas, y aislado igual
  (sin archivos ni terminal). Esta vez con **WebSearch y WebFetch** para leer noticias, más dos herramientas MCP nuevas
  de solo lectura y una de guardar:
  - `datos_fallo(pick_id)`: el análisis de 4 y los onces;
  - `datos_radar(equipo o jugador)`: la ficha del radar con sus partidos;
  - `guardar_explicacion(ref, texto, fuentes)`.

  *(Decisión mía:)* `guardar_explicacion` solo existe cuando el servidor MCP corre para el motor, igual que el resto de
  su configuración aislada; el MCP normal de cada usuario no la tiene, para que el agente de otro usuario no pueda
  escribir notas. Las dos de lectura sí están en el MCP normal.
- **Qué escribe**: de 3 a 6 frases en español sencillo sobre por qué pasó, con las fuentes (título y enlace) que usó.
  No puede escribir cifras que no vengan de las herramientas; si no encuentra nada, lo dice.
- **Dónde se guarda**: tabla nueva `ai_note` (tipo `fallo` o `radar`, referencia, texto, fuentes, estado `pendiente`,
  `lista` o `error`, modelo, cuándo). Una nota por apuesta del día; en el radar, una por equipo o jugador y día (pedir
  otra el mismo día devuelve la que hay).
- **Quién la puede pedir**: la automática se escribe una sola vez y la ven todos los usuarios con la IA encendida. «Investigar
  con Claude» solo lo pueden pulsar los usuarios a los que el motor ya procesa capturas (`captures_engine_users`, por
  defecto el dueño) *(decisión mía: usa la suscripción del dueño, igual que las capturas)*; los demás no ven el botón.
- **Seguridad**: las páginas de noticias pueden traer instrucciones escondidas. Con lo que tiene Claude, lo peor que
  pueden conseguir es una explicación mala. Por eso el texto se muestra como texto plano, firmado y con sus fuentes.
- Una a la vez, en un hilo aparte de la API, con el mismo tiempo máximo que las capturas.

## 6. Interruptor de la IA (por usuario)

- **Dónde**: al final de la página **Datos**, sección «Inteligencia artificial», con un interruptor «Usar IA en el
  panel: Encendida / Apagada» y la lista de lo que apaga. *(Decisión mía, que el dueño aceptó: junto al logo ensuciaba
  la cabecera y se podía pulsar sin querer.)*
- **Por usuario**: cada persona que entra con su clave decide (decisión del dueño). Se guarda en `app_user`
  (`ai_enabled`, por defecto encendida). El dueño, desde su PC sin clave, cambia el suyo (`default_user`).
- **Qué apaga, para ese usuario**:
  - «Capturas» desaparece del menú y «¿Viste una cuota?» de Hoy;
  - la API rechaza sus subidas de capturas con un mensaje que explica cómo encenderla, y el motor no procesa sus
    capturas pendientes;
  - no se le muestran las explicaciones de Claude ni el botón «Investigar con Claude».
- **Qué no apaga**: los números del modelo, el radar, los avisos y «Por qué falló» sin la explicación.
- API: `GET /me` y `PUT /me` con `ai_enabled` *(decisión mía: un recurso del usuario para próximos ajustes; la banca
  sigue en `/bankroll`)*.

## Datos y migraciones

- `app_user.ai_enabled` (booleano, por defecto verdadero).
- Tabla `ai_note` (ver 5).
- El análisis de «Por qué falló» se calcula al vuelo desde la previa y las estadísticas *(decisión mía: no hace falta
  guardarlo; solo se guarda la explicación de Claude)*.
- El radar se calcula al vuelo, con una caché en memoria de unos minutos por día *(decisión mía)*.

## Pruebas

- Radar: batacazo (gana con 25 % o menos), pinchazo (pierde con 60 % o más), sumas en el límite, 4 semanas exactas,
  figuras con y sin once.
- Mes: suma de 4 semanas, disponibilidad desde la cuarta semana completa con previa, navegación de 4 en 4.
- Avisos: un partido con un equipo en racha y otro en baja; sin radar no hay aviso.
- «Por qué falló»: con previa, sin previa, push y medio perdida; «¿Lo avisaba?» con el radar en la fecha de la apuesta.
- IA: con `ai_enabled` falso la API rechaza capturas, el motor no las procesa y las respuestas no traen la explicación.
  El comando de Claude solo permite WebSearch, WebFetch y las tres herramientas MCP; una explicación por apuesta.
- Panel: capturas con `driver.mjs` de `sorpresas`, `sorpresas-mes`, Hoy con avisos y Datos con el interruptor, en
  escritorio y celular, claro y oscuro; auditoría sin empeorar.

## Siguiente paso (fuera de este trabajo)

Medir con el historial de equipos (desde 2023, con cuotas de cierre) si los que dan un batacazo o un pinchazo siguen
sorprendiendo en los partidos siguientes o vuelven a la media. Si se repite, proponer al dueño que el aviso baje la
confianza; si no, el aviso se queda como aviso y se dice así en el panel.

## Lo que queda al constructor

El orden de las piezas, la forma exacta de las respuestas de la API, los nombres internos, el diseño fino dentro de
`DESIGN.md`, el texto del prompt de Claude (con las reglas de arriba) y cómo se integra el radar en las consultas
existentes sin hacer el panel más lento.
