# ADR 0005: Capturas de cuotas leídas por una IA vía MCP

**Estado**: aceptada (2026-10-19)

## Contexto
El usuario ve cuotas en Betano o bet365 (sobre todo props: córners, tarjetas, remates) que no llegan por ninguna fuente gratuita. Escribirlas a mano en *Evaluar cuota* es lento. La idea es subir una captura en el panel y que una IA la lea.

MCP funciona al revés de lo que parece: es la IA la que llama a las herramientas del sistema, no el sistema el que "envía" algo a la IA. Por eso la web no puede mandarle la imagen a Claude por MCP: alguien tiene que lanzar a la IA.

## Decisión
- **Flujo único con estados** (`odds_capture`): pendiente → procesando → evaluada → lista (o error). La imagen se guarda en `var/capturas/<usuario>/` y su tipo real se comprueba por los primeros bytes. Solo se admiten PNG, JPG y WEBP de hasta 10 MB.
- **La IA solo lee.** Manda las cuotas que ve a `evaluar_captura`, y el modelo estadístico calcula la probabilidad, el valor esperado, el stake y el veredicto con el mismo código que `evaluar_cuota` (`analysis.evaluate_user_odds_many`). Después, la IA escribe un resumen con `guardar_veredicto_captura`. Si no lo escribe, la captura queda lista igual, con los números.
- **Motor por defecto: Claude Code con la suscripción del dueño** (`claude -p` lanzado por la API en un hilo aparte, de una captura en una). Corre aislado:
  - sin herramientas propias (`--tools ""`);
  - solo con nuestro servidor MCP (`--strict-mcp-config`);
  - con solo tres herramientas permitidas (`ver_captura`, `evaluar_captura` y `guardar_veredicto_captura`), y `--permission-mode dontAsk` para que el resto se rechace;
  - sin ajustes ni hooks de otros sitios: una carpeta de trabajo vacía y `--setting-sources ""`;
  - sin `ANTHROPIC_API_KEY` en el entorno, para que se use la suscripción.

  El texto de la imagen se trata como datos, no como instrucciones. Coste: cero. Gasta del límite de uso del plan. Una captura tarda unos 10 a 15 segundos.
- **Otros usuarios**: la suscripción es personal, así que por defecto el motor automático solo procesa las capturas de `APUESTAS_DEFAULT_USER`. Las de los demás quedan pendientes, y su propio agente las procesa por MCP: `capturas_pendientes` → `ver_captura` → `evaluar_captura` → `guardar_veredicto_captura`.
- **Motor `api` preparado** (`APUESTAS_CAPTURES_ENGINE=api` + `APUESTAS_ANTHROPIC_API_KEY` + `pip install -e ".[api]"`): mismo flujo con la API de Claude y un bucle de herramientas. Es más rápido y no depende de esta PC, pero cuesta dinero por captura. Cada ejecución con Claude Code guarda en `engine_info.api_equivalent_usd` lo que habría costado por API, para decidir con datos. **Sin probar con una clave real** (solo con un cliente simulado en los tests).

## Ampliación (20-10-2026): combinadas, Bet Builders y "no evaluable"
- **Herramientas nuevas:**
  - `evaluar_combinada`: un bloque por partido con sus selecciones, la cuota del bloque y la total.
  - `marcar_no_evaluable`: guarda el motivo cuando no hay nada evaluable.
- **Cálculo** (`MatchModel.joint_goal_prob`): varias selecciones del mismo partido se combinan celda a celda en la matriz Dixon-Coles. Solo se admiten las que dependen únicamente del marcador y no se devuelven: 1X2, doble oportunidad, ambos marcan, más/menos de goles con línea .5 y hándicaps sin devolución. Una selección sola puede ser de cualquier mercado. Los partidos distintos se multiplican, porque son independientes.
- **Si la IA termina sin evaluar nada,** la captura queda `no_evaluable` con su explicación, no `error`. `error` queda para fallos del motor (tiempo agotado, sesión de Claude caducada…).
- **Caso real que lo motivó:** una combinada de 3 Bet Builders de Betano (cuota 11,03) salía como "No se pudo leer". Ahora City + más de 2,5 sale con 44 % (−41 %) y Roma + Roma más de 1,5 con 77 % (−5,6 %). PSG-Barça se marca no evaluable por las atajadas y por "anota o da asistencia".

## Ampliación (20-10-2026, noche): jugadores en los Bet Builders
- **Mercados nuevos:** `player_assist` (da una asistencia) y `player_goal_assist` (marca o asiste), con xA de FotMob. `player_goal` admite línea (`over 1.5` = 2 o más goles). Se liquidan con los goles y asistencias del jugador.
- **Cálculo:** los goles y asistencias de jugadores se combinan con el marcador repartiendo cada gol del equipo entre sus jugadores (`MatchModel.joint_prob`, detalle en `docs/modelos.md`). Córners, tarjetas, remates y faltas dentro de un Bet Builder se multiplican como independientes y el bloque se marca "aproximado"; antes dejaban el bloque sin evaluar.
- **Caso real:** la combinada de bet365 de 4 partidos (cuota 12,62) tenía dos bloques no evaluables, "Kane anotará o asistirá" y "Real Madrid + gol de Mbappé". Ahora salen con 17 % (cuota justa 5,81 frente a 4,30) y 53 % (1,89 frente a 1,43), y la combinada completa con 2,6 % (justa 37,8): sin valor.

## Alternativas descartadas
- **OCR local (Tesseract)**: es gratis, pero frágil con los diseños de las casas y no sabe pasar "Total de córners Más de 9.5" a `ou_corners/over/9.5`.
- **Mandar la imagen en el prompt de `claude -p`**: también funciona, pero entonces la IA no pasaría por MCP, y los agentes externos necesitan `ver_captura` igualmente.

## Consecuencias
- El panel necesita que la API esté corriendo para procesar capturas. Si la API se reinicia, al arrancar vuelve a encolar las que quedaron a medias.
- Si el 1X2 del modelo está mal calibrado en un partido, por ejemplo en Champions, donde no hay mercado afilado con el que mezclar, la captura lo refleja. Claude lo avisa en su resumen, pero el número sale del modelo.

## Ampliación (20-10-2026, noche): registrar la apuesta desde la captura
- `POST /captures/{id}/bet` registra una cuota de la captura (`line`) o su combinada entera con lo ya guardado en ella, sin rehacer el formulario en Evaluar cuota. Las combinadas usan el mismo registro que el cupón (`queries.register_combo`).
- Las herramientas `evaluar_captura` y `evaluar_combinada` aceptan `importe` (lo apostado, si se ve en la captura) para proponerlo al registrar.
- Lo registrado se guarda en `engine_info.bets`, que no se borra al volver a leer la captura ni al corregir cuotas, así que la misma apuesta no se registra dos veces.
