# La mesa de apostadores: plan de implementación

> **Para agentes:** sub-skill obligatoria: superpowers:executing-plans (o superpowers:subagent-driven-development).
> Los pasos usan casillas (`- [ ]`).

**Objetivo:** siete agentes de Claude votan la apuesta del día en dos rondas; el resultado con pesos sale debajo de la
apuesta en Hoy.

**Arquitectura:** todo vive en `src/apuestas/services/verdict.py`, que ya orquesta a los reporteros (A favor y En
contra) y deja de lanzar al Juez. Los votos van a una tabla nueva `review_vote`; los pesos se calculan del historial y
se copian en la revisión al crearla. El panel cambia el componente `Veredicto.tsx` sin tocar su sitio en Hoy.

**Tecnologías:** Python 3.14, SQLAlchemy, Alembic, FastMCP, `claude -p`; Next.js 16 + TypeScript + Tailwind.

**Diseño:** `docs/superpowers/specs/2026-11-19-mesa-de-apostadores-design.md` (léelo antes).

## Restricciones globales

- Agentes y su orden: `precavida`, `cazadora`, `estadistica`, `desconfiado`, `reportero`, `rachero`, `contraria`, con
  los nombres en español e inglés del diseño.
- Resultado: parte del sí ≥ 2/3 → `aprobado`; > 1/2 → `medianamente`; si no → `desaprobado`.
- Pesos: empiezan en 1,0; paso 0,05 por unidad de `settlement.profit(result, 1, picks.taken_odds(pick))`; el no, con
  el signo cambiado; tope 2,0 y piso 0,5 en cada paso.
- `MAX_PER_DAY = 2`, `LAST_CALL_MIN = 40`, `PARALLEL = 4`, `AGENT_EFFORT = "medium"`, motivo de 1 a 300 caracteres.
- Textos prometedores (`PROMISES`) se rechazan en voto y motivo, como hoy.
- Código, comentarios y pruebas en español. Docs en inglés primero y copia en español en el mismo commit.
- **No compilar `web/`** (`npm run build`): rompe el panel del puerto 3000 hasta reiniciar `arrancar.sh`, que ya compila
  al arrancar. Basta `npm run lint` y `npx tsc --noEmit`.
- **No aplicar la migración a la BD compartida hasta la tarea 6**, justo antes de pedir el reinicio: quita columnas que
  el código en marcha todavía lee.

## Foco de revisión

1. Un texto de los reporteros pide a un agente votar por otro o adelantar la ronda 2: el voto solo se guarda para el
   asiento del entorno (`APUESTAS_MCP_AGENT`). → prueba en la tarea 2.
2. La apuesta cambia o el partido empieza entre la ronda 1 y la 2: la revisión se descarta y no se enseña. → tarea 3.
3. Un agente de siete falla en la ronda 2: la revisión vuelve a pendiente, el reintento solo lanza a ese agente y al
   segundo fallo queda en error; si había una revisión lista antes, se sigue viendo. → tarea 3.
4. Pesos con devueltas, medias, tope y piso; las revisiones después del inicio o de apuestas no contadas no mueven
   pesos. → tarea 2.
5. Fronteras exactas: 4 de 6 iguales es aprobado, la mitad exacta es desaprobado, con pesos decimales. → tarea 2.

---

### Task 1: datos (modelo y migración)

**Archivos:**
- Modificar: `src/apuestas/db/models.py` (`PickReview`, clase nueva `ReviewVote`)
- Crear: `migrations/versions/<rev>_mesa_de_apostadores.py` (con `alembic revision --autogenerate`)
- Modificar: `src/apuestas/config.py` (campo `mcp_agent: str = ""`, junto a `mcp_engine`)

**Interfaces:**
- Produce: `m.ReviewVote(id, review_id, agent: str(16), round: int, vote: bool, text: str, text_en: str, created_at)`,
  `UniqueConstraint(review_id, agent, round)`, FK a `pick_review.id` con `ondelete="CASCADE"`;
  `m.PickReview.votes` (relación ordenada por `ReviewVote.id`); `m.PickReview.weights: dict | None` (JSON).
  `PickReview.word` y `PickReview.motives` desaparecen. `get_settings().mcp_agent`.

- [ ] Paso 1: cambiar los modelos y el ajuste; generar la migración con
  `.venv/Scripts/alembic revision --autogenerate -m "mesa de apostadores"` y revisar que solo crea `review_vote`,
  añade `pick_review.weights` y quita `word` y `motives` (con su `downgrade`).
- [ ] Paso 2: `.venv/Scripts/pytest tests/test_verdict.py -q` → fallan solo las pruebas del Juez (se rehacen en las
  tareas 2 y 3). No aplicar la migración.

### Task 2: votos, resultado y pesos

**Archivos:**
- Modificar: `src/apuestas/services/verdict.py`
- Prueba: `tests/test_verdict.py` (quitar las del Juez: `test_veredicto_invalido_se_rechaza`,
  `test_veredicto_valido_se_guarda`; añadir las de abajo)

**Interfaces:**
- Consume: tarea 1.
- Produce:
  - `AGENTS: dict[str, tuple[str, str, str]]` — clave → (nombre, nombre en inglés, personalidad para el prompt).
  - `save_vote(ref: str, seat: str, voto: bool, motivo: str, motivo_en: str) -> dict` — `seat` es `"agente:ronda"`;
    rechaza asiento desconocido, ronda fuera de (1, 2), textos vacíos o de más de `MAX_MOTIVE`, promesas, un segundo
    voto del mismo asiento y revisiones que no estén `trabajando`.
  - `tally(votes: dict[str, bool], weights: dict[str, float]) -> dict` —
    `{"outcome", "yes": int, "total": int, "yes_share": float}`; peso que falte = 1,0.
  - `counted_reviews(s) -> list[m.PickReview]` — última revisión lista antes del inicio de cada apuesta del día
    contada (`was_pick_of_day`), en orden de inicio. `measure` usa el mismo paso interno.
  - `weights(s) -> dict[str, float]` — todos los agentes, redondeado a 3 decimales.

- [ ] Paso 1: pruebas que fallan:
  - `test_un_voto_valido_se_guarda` (sí, motivo y motivo_en guardados en `review.votes`).
  - `test_voto_invalido_se_rechaza` parametrizada: asiento `"juez:1"`, `"precavida:3"`, `"precavida"`, motivo vacío,
    motivo de 301, «apuesta segura» en el motivo o en el motivo en inglés, segundo voto del mismo asiento.
  - `test_un_agente_solo_vota_en_su_asiento` (foco 1): con `mcp_agent="precavida:1"`, la herramienta MCP
    `guardar_voto` no tiene parámetro de agente ni de ronda y guarda en `precavida`, ronda 1.
  - `test_resultado_con_votos_iguales`: 5/7 → `aprobado`, 4/7 → `medianamente`, 3/7 → `desaprobado`, 4/5 → `aprobado`,
    3/5 → `medianamente`.
  - `test_fronteras_exactas` (foco 5): 4 de 6 iguales → `aprobado`; 3 de 6 → `desaprobado`; pesos `{a: 2.0}` sí y
    `{b: 1.0, c: 1.0}` no → `desaprobado` (mitad exacta).
  - `test_pesos_desde_el_historial` (foco 4): partiendo de 1,0, sí y gana a 1,72 → 1,036; sí y pierde → 0,95; no y
    pierde → 1,05; no y gana a 1,72 → 0,964; `half_win` a 2,0 → +0,025; `push` → 1,0.
  - `test_pesos_con_tope_y_piso`: 30 pérdidas seguidas con sí → 0,5; luego una ganada a 2,0 → 0,55; 30 ganadas a 2,0
    con sí → 2,0.
  - `test_pesos_ignoran_lo_que_no_cuenta`: revisión creada después del inicio, apuesta con `was_pick_of_day=False` y
    apuesta sin resultado no mueven nada; con dos revisiones de la misma apuesta cuenta solo la última antes del inicio.
- [ ] Paso 2: ejecutarlas → fallan.
- [ ] Paso 3: implementar las interfaces de arriba. Quitar `WORDS`, `RESERVED_LABELS`, `MIN_MOTIVES`, `MAX_LABEL`,
  `save_verdict` y `JUDGE_PROMPT`. Pesos en orden de `match.kickoff_utc`, con `max(MIN_WEIGHT, min(MAX_WEIGHT, ...))`
  en cada paso; fronteras con tolerancia `1e-9`.
- [ ] Paso 4: `.venv/Scripts/pytest tests/test_verdict.py -q` → pasan las nuevas.

### Task 3: las dos rondas, cuándo se pide y reintentos

**Archivos:**
- Modificar: `src/apuestas/services/verdict.py`, `src/apuestas/services/ai_notes.py` (`claude_command`)
- Prueba: `tests/test_verdict.py`

**Interfaces:**
- Consume: tarea 2.
- Produce:
  - `ai_notes.claude_command(tools, mcp_tools, model, effort=None, mcp_env: dict[str, str] | None = None)` — se suma al
    `env` del servidor MCP.
  - `command(papel: str, ronda: int | None = None)` — agentes: sin internet, MCP `datos_veredicto` y `guardar_voto`,
    esfuerzo `AGENT_EFFORT`, `mcp_env={"APUESTAS_MCP_AGENT": f"{papel}:{ronda}"}`. Reporteros como hoy.
  - `prompt(review, papel, ronda=None) -> str` — ronda 1: personalidad, reglas y textos de los reporteros entre
    `<a_favor>`/`<en_contra>`; ronda 2: además los votos y motivos de la ronda 1 de los demás entre `<ronda_1>`.
  - `_ask(papel: str, review_id: int, ronda: int | None = None) -> str | None`.
  - `run(review_id)`: reporteros (bucle de hoy) → ronda 1 → ronda 2; en cada ronda lanza solo a los agentes sin voto,
    de `PARALLEL` en `PARALLEL` (si `PARALLEL <= 1`, en el mismo hilo); comprueba `_still_valid` antes y después de
    cada ronda; si falta algún voto, `_failed` con los agentes que faltan; lista cuando están los 7 votos de la ronda 2.
  - `request_due` guarda `weights=weights(s)` en la revisión; `MAX_PER_DAY = 2`, `LAST_CALL_MIN = 40`.
  - `rescue_stuck` usa como límite `(len(SIDES) + len(ROUNDS) * ceil(len(AGENTS) / PARALLEL))` × timeout + margen.

- [ ] Paso 1: rehacer `fake_claude` (cada agente vota sí salvo los de `noes`, cada reportero escribe su texto; el
  fixture pone `PARALLEL = 1`) y escribir o adaptar:
  - `test_los_agentes_no_tienen_internet_y_votan_en_su_asiento`: `command("cazadora", 2)` sin `--tools`, con
    `guardar_voto` permitido, esfuerzo `medium` y `APUESTAS_MCP_AGENT=cazadora:2` en el `--mcp-config`.
  - `test_la_ronda_2_ve_la_ronda_1_y_la_1_no`: el prompt de la ronda 1 no lleva votos de otros; el de la ronda 2 lleva
    los motivos de la ronda 1 de los demás y los textos de los reporteros.
  - `test_la_mesa_completa_deja_la_revision_lista`: lanzados `favor`, `contra`, 7 de ronda 1 y 7 de ronda 2; estado
    `lista`, 14 votos.
  - `test_si_cambia_la_apuesta_entre_rondas_se_descarta` (foco 2).
  - `test_si_falta_un_voto_se_reintenta_solo_ese_agente` (foco 3): primer intento sin `rachero` en ronda 2 →
    `pendiente` con `rachero` en el error; segundo intento lanza solo `rachero:2`; si vuelve a faltar → `error`.
  - Adaptar `test_maximo_tres_revisiones_al_dia` → dos, `test_prevista_a_30_minutos_se_pide` → 40 y 41,
    `test_reinicio_a_mitad_vuelve_a_pendiente` al nuevo límite, `test_un_revisor_que_escribe_la_parte_del_otro_falla`
    y `test_el_tope_cuenta_las_descartadas_que_gastaron` a 2.
  - `test_la_revision_guarda_los_pesos_al_crearse`.
- [ ] Paso 2: ejecutarlas → fallan.
- [ ] Paso 3: implementar. Personalidades en `AGENTS` según la tabla del diseño (la Precavida con 70 % y
  `verdict_min_confidence`).
- [ ] Paso 4: `.venv/Scripts/pytest tests/test_verdict.py tests/test_ai_notes.py -q` → pasan.

### Task 4: MCP, datos para los agentes, lo que ve el usuario y la medición

**Archivos:**
- Modificar: `src/apuestas/mcp_server/server.py`, `src/apuestas/services/verdict.py`,
  `experimentos/validacion/veredicto.py`
- Prueba: `tests/test_verdict.py`

**Interfaces:**
- Consume: tareas 2 y 3.
- Produce:
  - Herramienta del motor `guardar_voto(ref: str, voto: bool, motivo: str, motivo_en: str)` →
    `verdict.save_vote(ref, get_settings().mcp_agent, ...)`; `guardar_veredicto` desaparece;
    `MCP_TOOLS = ("datos_veredicto", "guardar_revisor", "guardar_voto")`.
  - `market_prices(s, pick) -> dict` — `{"bet365": float | None, "pinnacle_justa": float | None}` con la última cuota
    antes de ahora de cada casa para esa selección y línea (`analysis.book_fair_prob` para Pinnacle). `review_data`
    la añade como `otras_casas`.
  - `for_user` lista: en lugar de `word` y `motives`, `outcome`, `yes`, `total`, `yes_share` y
    `votes: [{agent, name, name_en, vote, text, text_en, weight, changed}]` (ronda 2, orden de `AGENTS`; `changed` si
    cambió el voto de la ronda 1) y `round1: [{agent, name, name_en, vote, text, text_en}]`. Lo demás como hoy.
    Sin revisión lista: `outcome: None`.
  - `measure(s) -> {"contados": {outcome: record}, "todos": {...}, "pesos": weights(s)}`; el script imprime por
    resultado y la tabla de pesos.

- [ ] Paso 1: pruebas que fallan: `test_herramientas_del_motor` (con `guardar_voto`, sin `guardar_veredicto`);
  `test_datos_traen_otras_casas` (bet365 a 2,05 y Pinnacle a 1,95 en las dos caras → `bet365` 2,05 y
  `pinnacle_justa` 2,0); adaptar `test_veredicto_listo_trae_sus_partes`, `test_hoy_en_marcha_y_en_error`,
  `test_veredicto_anterior_se_mantiene_si_la_nueva_falla_o_esta_en_marcha` (foco 3) y
  `test_medicion_cuenta_la_ultima_valida_antes_del_inicio_y_una_por_dia` a la forma nueva; `test_cambio_de_opinion`
  (no en la ronda 1 y sí en la 2 → `changed`).
- [ ] Paso 2: ejecutarlas → fallan. Paso 3: implementar. Paso 4: `.venv/Scripts/pytest -q` y
  `.venv/Scripts/ruff check src tests experimentos` → todo verde.

### Task 5: el bloque de la mesa en Hoy

**Archivos:**
- Modificar: `web/src/lib/types.ts` (`PickReview`), `web/src/components/hoy/Veredicto.tsx`

**Interfaces:**
- Consume: el JSON de la tarea 4 en `GET /picks/{id}/review`.

- [ ] Paso 1: tipos nuevos y componente: título «La mesa de apostadores» / "The betting table"; palabra grande con
  `tr`: «Aprobado por los agentes»/"Approved by the agents", «Medianamente aprobado»/"Partly approved",
  «Desaprobado por los agentes»/"Rejected by the agents"; «4 de 7 dicen sí · 57 % del voto con pesos»; motivos fijos de
  confianza y racha como hoy; una fila por agente con Sí/No, nombre, `×1,04` y su motivo (`tr(text, text_en)`), y «cambió
  de opinión» si `changed`; plegable «Ver la conversación» con la ronda 1 y los textos de A favor y En contra; avisos y
  nota de opinión sin medir como hoy; textos de espera con «la mesa» en lugar de «los revisores». Seguir la skill
  `disenio-panel` (tonos: aprobado `text-tinta`, medianamente `text-tarjeta`, desaprobado `text-rojo`).
- [ ] Paso 2: `cd web && npm run lint && npx tsc --noEmit` → sin errores. **No** `npm run build`.
- [ ] Paso 3: comprobar el aspecto en escritorio y celular con un servidor de desarrollo en otro puerto y la respuesta
  de `/picks/*/review` simulada con Playwright (sin escribir datos falsos en la BD). Si `next dev` comparte carpeta de
  salida con el panel en marcha, saltar este paso y comprobarlo tras el reinicio.

### Task 6: documentación, migración y entrega

**Archivos:**
- Crear: `docs/adr/0010-mesa-de-apostadores.md` y `docs/es/adr/0010-mesa-de-apostadores.md`
- Modificar: `docs/adr/0009-veredicto-de-los-revisores.md` y su copia (estado: el ADR 0010 reemplaza al Juez),
  `docs/estado.md` y `docs/es/estado.md`, `docs/arquitectura.md` y su copia, `README.md` y `README.es.md` (donde nombran
  el veredicto), `CHANGELOG.md` (Unreleased).

- [ ] Paso 1: escribir la documentación (inglés y español en el mismo commit).
- [ ] Paso 2: `pg_dump` a `var/backups/` y `.venv/Scripts/alembic upgrade head`; comprobar con `\d pick_review` y
  `\d review_vote`.
- [ ] Paso 3: `.venv/Scripts/pytest -q`, `ruff`, `npm run lint`, `npx tsc --noEmit` → verdes.
- [ ] Paso 4: commit en español y `git push` a `main`.
- [ ] Paso 5: pedir al dueño que reinicie `arrancar.sh`; después comprobar Hoy en `localhost:3000` y que la API
  responde `GET /picks/{id}/review` sin error.
