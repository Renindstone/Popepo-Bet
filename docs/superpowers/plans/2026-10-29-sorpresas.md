# Sorpresas: radar, avisos, «Por qué falló» e interruptor de la IA — plan de construcción

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renombrar «Semana» a «Sorpresas» con vista Mes, añadir el radar (equipos en racha y en baja, jugadores en racha), los avisos en apuestas y partidos, «Por qué falló» con explicación de Claude y un interruptor de la IA por usuario.

**Architecture:** Todo sale de la puntuación por sorpresa que ya calcula `services/weekly.py`, generalizada a un rango de fechas. Un servicio nuevo `services/radar.py` calcula el radar sobre los últimos 28 días y produce los avisos; `services/failure.py` compara la previa guardada con lo que pasó; `services/ai_notes.py` lanza `claude -p` (como el motor de capturas) para escribir explicaciones en la tabla nueva `ai_note`. El panel consume campos nuevos (`alerts`, `/me`, `/radar`, `/picks/{id}/failure`).

**Tech Stack:** Python 3.14, SQLAlchemy, Alembic, FastAPI, servidor MCP del proyecto, APScheduler; Next.js 16 + Tailwind (panel).

**Spec:** `docs/superpowers/specs/2026-10-29-sorpresas-design.md` (aprobado el 29-10-2026). Léelo junto a este plan.

## Global Constraints

- Los avisos **no cambian** probabilidad, confianza ni corte; el texto lo dice: «Es un aviso para mirarlo con más cuidado: no cambia la probabilidad ni el corte.»
- Batacazo: ganar con `p_win <= 0.25`. Pinchazo: perder con `p_win >= 0.60` (`p_win` = `p_over` del dato `result` de `weekly.team_items`).
- En racha: suma `>= 1.0` en 28 días o un batacazo. En baja: suma `<= -1.0` o un pinchazo. Jugadores en racha: suma `>= 1.5` y `>= 90` minutos en la ventana. Figuras: jugadores del equipo con `>= 1.5` en sus partidos sorprendentes, como mucho 2. Como mucho 8 filas por lista.
- Mes = las 4 semanas completas que terminan en la semana elegida; disponible cuando esas 4 semanas son completas y empiezan en o después de la primera semana completa con previa (lunes 26-10-2026 con los datos actuales).
- Explicación de Claude: de 3 a 6 frases, en español sencillo, con fuentes (título y enlace http/https); como mucho 1.200 caracteres de texto y 6 fuentes; se muestra como texto plano con «Explicación de Claude», sus fuentes y la hora (Lima).
- Claude: `claude -p` con la suscripción de la PC, sin archivos ni terminal; solo `WebSearch`, `WebFetch` y las herramientas MCP `datos_fallo`, `datos_radar`, `guardar_explicacion`.
- `guardar_explicacion` solo existe con `APUESTAS_MCP_ENGINE=true` y en modo stdio.
- La explicación automática solo se pide si algún usuario de `captures_engine_users` (por defecto `default_user`) tiene la IA encendida. «Investigar con Claude» solo para esos usuarios con la IA encendida.
- Interruptor por usuario: `app_user.ai_enabled`, por defecto verdadero.
- Panel: `DESIGN.md`, `.impeccable/design.json`, skill `disenio-panel`; avisos con filete arriba (`border-t-[3px]`), nunca borde lateral grueso; etiquetas con palabra. Condición del dueño: mismo patrón del rediseño con impeccable y revisión de diseño al final.
- Se trabaja en la rama `claude/sorpresas`; se fusiona en `main` y se sube solo con el OK del dueño en el chat.
- Código y comentarios en español; commits en español que explican el porqué, terminados en `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Un partido con los dos equipos en el radar** (uno en racha y otro en baja): dos avisos, uno por equipo, sin duplicar. Prueba en la Tarea 3.
2. **Equipo del radar sin partido en los próximos 14 días**: la fila sale con `next_matches` vacío y el panel dice «Sin partido próximo». Prueba en la Tarea 2.
3. **Apuesta del día perdida sin previa guardada** (anterior al 24-10): `has_preview` falso y el panel dice «No hay previa guardada de este partido», sin error. Prueba en la Tarea 4.
4. **Usuario con la IA apagada** que pide `/picks/{id}/failure` o `/radar`: la respuesta no trae `note`. Prueba en la Tarea 6.
5. **Sin el programa `claude` en la PC**: la nota queda en `error` con el motivo y no se queda en `pendiente` para siempre. Prueba en la Tarea 6.

---

### Task 1: Puntuación por rango de fechas y vista Mes

**Files:**
- Modify: `src/apuestas/services/weekly.py`
- Modify: `src/apuestas/services/queries.py:163-168` (`week_recap`)
- Modify: `src/apuestas/api/app.py:220-223` (`/week`)
- Modify: `src/apuestas/mcp_server/server.py:175-181` (`resumen_semana`)
- Modify: `src/apuestas/cli.py` (comando `semana`)
- Test: `tests/test_weekly.py`

**Interfaces:**
- Produces: `weekly.score_range(s: Session, start: datetime, end: datetime, now: datetime | None = None) -> dict` con claves `teams: list[dict]` y `players: list[dict]` (ordenadas con `_rank_key`, **sin cortar a TOP_N**, cada una con `matches` e `items` como hoy) y `coverage: dict`.
- Produces: `weekly.recap(s, monday, now=None, detail=True, weeks: int = 1) -> dict`; con `weeks=4` el rango va de `monday - 21 días` a `monday + 7 días`. Añade claves `period` (`"semana"` | `"mes"`) y `weeks`.
- Produces: `weekly.first_full_week(s: Session) -> date | None` (lunes de la primera semana completa con previa) y `weekly.month_available(s, last_monday: date, now: datetime) -> bool`.
- Produces: `queries.week_recap(day: str | None = None, detail: bool = True, period: str = "semana") -> dict`; con `period="mes"` y sin disponibilidad devuelve `{"period": "mes", "available": False, "available_from": "AAAA-MM-DD"}`.

- [ ] **Step 1: Write the failing tests** en `tests/test_weekly.py`, con los helpers de ese archivo:
  - `test_score_range_sin_cortar`: 12 equipos con partido en el rango → `len(score_range(...)["teams"]) == 12`.
  - `test_recap_mes_suma_cuatro_semanas`: un equipo con un partido en la semana 1 y otro en la semana 4 → en `recap(..., weeks=4)` su `n_matches == 2` y `score` = suma de los dos; `period == "mes"`.
  - `test_mes_disponible`: con la primera previa el sábado 24-10-2026, `first_full_week == date(2026, 10, 26)`; `month_available(s, date(2026, 11, 16), now=23-11-2026 05:00 Lima)` es verdadero y `month_available(s, date(2026, 11, 9), ...)` falso.
  - `test_week_recap_mes_no_disponible`: `queries.week_recap("2026-10-30", period="mes")["available"] is False` y `available_from == "2026-11-23"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_weekly.py -q` — Expected: FAIL (`score_range` no existe).
- [ ] **Step 3: Implement** `score_range` sacando de `recap` el bucle de partidos (sin cambiar cómo puntúa); `recap` lo llama y sigue devolviendo lo de hoy (TOP_N, once, cobertura). Mes: `available_from` es el lunes `first_full_week + 28 días`. Sin `day`, el mes termina en la última semana completa (`week_start(hoy) - 7`).
- [ ] **Step 4: Wire** `/week?period=semana|mes`, `resumen_semana(semana=None, periodo="semana")` y `apuestas semana --mes`.
- [ ] **Step 5: Run** `.venv/bin/pytest tests/test_weekly.py -q && .venv/bin/ruff check src tests` — Expected: PASS, sin avisos.
- [ ] **Step 6: Commit** `git commit -m "Sorpresas: puntuación por rango y vista Mes de 4 semanas"`

### Task 2: Radar

**Files:**
- Create: `src/apuestas/services/radar.py`
- Modify: `src/apuestas/api/app.py` (`GET /radar`)
- Test: `tests/test_radar.py`

**Interfaces:**
- Consumes: `weekly.score_range` (Tarea 1).
- Produces: constantes `WINDOW_DAYS = 28`, `UPSET_MAX = 0.25`, `FLOP_MIN = 0.60`, `TEAM_SUM = 1.0`, `PLAYER_SUM = 1.5`, `PLAYER_MIN_MINUTES = 90`, `FIGURE_MIN = 1.5`, `MAX_ROWS = 8`, `NEXT_DAYS = 14`, `CACHE_S = 300`.
- Produces: `radar.build(s: Session, as_of: datetime) -> dict` con `window_start`, `window_end`, `racha: list[TeamRow]`, `baja: list[TeamRow]`, `jugadores: list[PlayerRow]`.
  - `TeamRow = {"team_id", "name", "competition", "kind": "racha"|"baja", "score", "n_matches", "reason": {"type": "batacazo"|"pinchazo"|"suma", "match_id", "label", "date", "p_win"}, "figures": [{"player_id", "name", "score"}], "next_matches": [{"match_id", "label", "kickoff_local"}]}`
  - `PlayerRow = {"player_id", "name", "team_id", "team", "score", "minutes", "n_matches", "best": {"match_id", "label", "items"}, "next_matches": [...]}`
- Produces: `radar.status(s: Session, as_of: datetime) -> dict[int, TeamRow]` (equipos del radar por id) y `radar.get(as_of: datetime | None = None) -> dict` (con sesión y caché de `CACHE_S` por día de Lima).
- `reason`: el batacazo o pinchazo con menor/mayor `p_win`; si no hay, `type="suma"` con el partido de mayor `|score|`. `next_matches`: hasta 2 partidos `scheduled` en `NEXT_DAYS` días.

- [ ] **Step 1: Write the failing tests** (`tests/test_radar.py`, datos en SQLite como `test_weekly.py`):
  - `test_batacazo_entra_en_racha`: gana con `p_win = 0.20` y suma 0,4 → en `racha` con `reason["type"] == "batacazo"`.
  - `test_pinchazo_entra_en_baja`: pierde con `p_win = 0.65` → en `baja` con `type == "pinchazo"`.
  - `test_limites_de_suma`: suma exacta 1.0 entra en racha; 0.99 sin batacazo no entra; −1.0 entra en baja.
  - `test_ventana_de_28_dias`: un batacazo de hace 29 días no cuenta.
  - `test_figuras_y_jugadores`: jugador con 1,6 y 120 min → en `jugadores` y en `figures` de su equipo en racha; con 80 min no entra en `jugadores`.
  - `test_sin_partido_proximo` (Review Focus 2): `next_matches == []`.
  - `test_maximo_8_por_lista`: 10 equipos en racha → `len(racha) == 8`, ordenados por `score`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_radar.py -q` — Expected: FAIL (módulo no existe).
- [ ] **Step 3: Implement** `build`, `status` y `get` en `services/radar.py` con las constantes de arriba; `p_win` sale del dato `result` de cada partido de `score_range`.
- [ ] **Step 4: Add** `GET /radar` (con `current_user`) que devuelve `radar.get()`; la nota de Claude se añade en la Tarea 6.
- [ ] **Step 5: Run** `.venv/bin/pytest tests/test_radar.py -q` — Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "Sorpresas: radar de equipos en racha y en baja"`

### Task 3: Avisos en apuestas, partidos y MCP

**Files:**
- Modify: `src/apuestas/services/radar.py` (función de avisos)
- Modify: `src/apuestas/services/picks.py` (`generate`: campo `alerts`)
- Modify: `src/apuestas/services/queries.py` (`upcoming`, `match_analysis`)
- Test: `tests/test_radar.py`

**Interfaces:**
- Consumes: `radar.status` (Tarea 2).
- Produces: `radar.alerts_for_match(s: Session, match: m.Match, as_of: datetime, cached: dict[int, TeamRow] | None = None) -> list[Alert]`, con `Alert = TeamRow + {"side": "home"|"away", "figures": [{"player_id", "name", "score", "lineup": "confirmado"|"probable"|None}], "note": NOTE}` y `radar.NOTE = "Es un aviso para mirarlo con más cuidado: no cambia la probabilidad ni el corte."`. La alineación sale de `lineup` (confirmada si `match.lineup_status` lo dice; si no, probable).
- Produces: en la salida de `picks.generate`, `pick_of_day["alerts"]`, cada fila de `value_bets[]["alerts"]` y cada fila de `matches[]["alerts"]`; en `queries.upcoming` y `queries.match_analysis`, clave `alerts`. Siempre una lista (vacía si no hay).

- [ ] **Step 1: Write the failing tests**:
  - `test_avisos_dos_equipos` (Review Focus 1): local en racha y visitante en baja → `[a["side"] for a in alerts] == ["home", "away"]`, sin repetidos.
  - `test_figura_en_el_once`: figura con fila en `lineup` del partido → `figures[0]["lineup"] == "probable"`.
  - `test_sin_radar_sin_avisos`: `alerts_for_match(...) == []`.
  - `test_generate_lleva_alerts`: con `radar.status` sustituido por un dict con un equipo, `generate()` pone `alerts` en la apuesta del día y en las filas de ese partido; las demás filas llevan `[]`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_radar.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `alerts_for_match`; en `generate` se calcula `radar.status` una vez por llamada y se pasa como `cached`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS (toda la suite: `generate` la usan otras pruebas).
- [ ] **Step 5: Commit** `git commit -m "Sorpresas: avisos del radar en apuestas, partidos y MCP"`

### Task 4: «Por qué falló»

**Files:**
- Create: `src/apuestas/services/failure.py`
- Modify: `src/apuestas/services/queries.py` (`pick_of_day` días pasados: `pick_id`), `src/apuestas/services/picks.py` (`pick_history`: `pick_id` en cada fila)
- Modify: `src/apuestas/api/app.py` (`GET /picks/{pick_id}/failure`)
- Test: `tests/test_failure.py`

**Interfaces:**
- Consumes: `weekly.team_items`, `weekly.player_items`, `predictions.usable`, `radar.build` (Tarea 2).
- Produces: `failure.analyze(s: Session, pick: m.Pick) -> dict` = `{"pick_id", "match", "score": "1-1", "result", "has_preview": bool, "teams": [{"team", "side", "score", "items"}], "players": [{"name", "team", "score", "items"}] (hasta 3, mayor |score|), "flagged": [{"team", "kind", "figures_played": [nombres]}]}`. `flagged` usa `radar.build(s, pick.created_at)`.
- Produces: `failure.get(pick_id: int) -> dict` (sesión; `queries.NotFound` si no existe o si no es la apuesta del día con `result` in `("loss", "half_loss")`).

- [ ] **Step 1: Write the failing tests**:
  - `test_fallo_con_previa`: apuesta del día perdida con previa → `has_preview` y equipos con `items` de goles; `players` como mucho 3.
  - `test_fallo_sin_previa` (Review Focus 3): sin `prediction` → `has_preview is False`, `teams == []`, sin excepción.
  - `test_lo_avisaba`: un equipo del partido en racha a la fecha de la apuesta → aparece en `flagged`.
  - `test_solo_perdidas`: `failure.get` de una ganada lanza `NotFound`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_failure.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `analyze` y `get`; añade `pick_id` donde dice Files.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/test_failure.py tests/test_pick_record.py -q` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Sorpresas: «Por qué falló» con la previa frente a lo que pasó"`

### Task 5: Interruptor de la IA por usuario

**Files:**
- Modify: `src/apuestas/db/models.py:345` (`User.ai_enabled`)
- Create: migración con `.venv/bin/alembic revision --autogenerate -m "interruptor de la IA por usuario y notas de Claude"` (incluye también la tabla de la Tarea 6; hazla en esta tarea con las dos)
- Modify: `src/apuestas/db/models.py` (clase `AiNote`, ver Tarea 6), `src/apuestas/services/tracker.py`, `src/apuestas/api/app.py` (`GET/PUT /me`, `POST /captures`), `src/apuestas/services/capture_engines.py` (`submit`), `src/apuestas/services/captures.py` (`stuck_and_pending`)
- Test: `tests/test_ai_switch.py`

**Interfaces:**
- Produces: `User.ai_enabled: Mapped[bool]` (`server_default=true()`).
- Produces: `AiNote` (tabla `ai_note`): `id`, `kind: str(8)` (`fallo`|`radar`), `ref: str(24)` (`"pick:123"`, `"team:16"`, `"player:2479"`), `day: date`, `status: str(12)` (`pendiente`|`trabajando`|`lista`|`error`), `text: str|None`, `sources: JSON|None`, `error: str|None`, `model: str|None`, `created_at`, `updated_at`; `UniqueConstraint("kind", "ref", "day")`.
- Produces: `tracker.ai_enabled(s, username: str) -> bool`, `tracker.set_ai_enabled(s, username: str, on: bool) -> None`, `tracker.can_investigate(s, username: str) -> bool` (IA encendida y usuario en `captures_engine_users`/`default_user`).
- Produces: `GET /me` → `{"username", "ai_enabled", "can_investigate"}`; `PUT /me` con `{"ai_enabled": bool}`; `POST /captures` responde 409 con «La IA está apagada para tu usuario: puedes encenderla al final de Datos.» si está apagada.

- [ ] **Step 1: Write the failing tests**:
  - `test_me_por_defecto`: `GET /me` local → `ai_enabled is True`.
  - `test_apagar_y_subir_captura`: `PUT /me {"ai_enabled": false}` y `POST /captures` → 409 con ese mensaje.
  - `test_motor_no_procesa`: con la IA apagada, `capture_engines.submit(id, user)` devuelve `False` y `stuck_and_pending()` no la incluye.
  - `test_can_investigate`: dueño con IA → `True`; otro usuario con IA → `False`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_ai_switch.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement**; `pg_dump` a `var/backups/` y luego `.venv/bin/alembic upgrade head` (regla 4 de AGENTS.md).
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Interruptor de la IA por usuario"`

### Task 6: Notas de Claude

**Files:**
- Create: `src/apuestas/services/ai_notes.py`
- Modify: `src/apuestas/config.py` (`mcp_engine: bool = False`, `ai_notes_timeout_s: int = 300`)
- Modify: `src/apuestas/mcp_server/server.py` (`datos_fallo`, `datos_radar`, `guardar_explicacion` solo con `mcp_engine`)
- Modify: `src/apuestas/services/picks.py` (`settle_all`: pide la nota de las apuestas del día perdidas)
- Modify: `src/apuestas/jobs/scheduler.py` (tarea `notas_ia` cada 10 min)
- Modify: `src/apuestas/api/app.py` (`POST /radar/investigate`, `note` en `/radar` y `/picks/{id}/failure`)
- Test: `tests/test_ai_notes.py`

**Interfaces:**
- Consumes: `AiNote`, `tracker.ai_enabled`, `tracker.can_investigate` (Tarea 5); `failure.get` (Tarea 4); `radar.get` (Tarea 2); `capture_engines.parse_claude_output`.
- Produces: `ai_notes.request(s, kind: str, ref: str, day: date) -> m.AiNote` (crea `pendiente` o devuelve la existente), `ai_notes.auto_enabled(s) -> bool`, `ai_notes.claim(note_id: int) -> bool` (UPDATE de `pendiente` a `trabajando` con comprobación de filas), `ai_notes.run(note_id: int) -> None` (estado final `lista` o `error` con motivo), `ai_notes.command(note: m.AiNote) -> tuple[list[str], dict[str, str], Path]`, `ai_notes.save(ref: str, texto: str, fuentes: list[dict]) -> dict`, `ai_notes.public(note: m.AiNote | None, username: str) -> dict | None` (None si el usuario tiene la IA apagada), `ai_notes.submit(note_id: int) -> None` (hilo propio de un solo trabajador).
- `command`: como `capture_engines.claude_code_command` pero con `--tools "WebSearch,WebFetch"`, `--allowedTools` = `WebSearch,WebFetch,mcp__apuestas__datos_fallo,mcp__apuestas__datos_radar,mcp__apuestas__guardar_explicacion` y `env` del MCP con `APUESTAS_MCP_ENGINE=true`. El prompt lleva las reglas de Global Constraints y pide llamar a `guardar_explicacion` una sola vez.
- `save`: rechaza más de 1.200 caracteres, más de 6 fuentes o enlaces que no empiecen por `http://` o `https://`; guarda texto plano.

- [ ] **Step 1: Write the failing tests**:
  - `test_una_nota_por_apuesta`: dos `request("fallo", "pick:7", d)` → una fila.
  - `test_claim_una_vez`: el segundo `claim` devuelve `False`.
  - `test_comando_aislado`: `command(...)` contiene `--tools`, `WebSearch,WebFetch`, las tres herramientas MCP y `APUESTAS_MCP_ENGINE=true` en el MCP; no contiene `Bash` ni `Read`.
  - `test_sin_claude` (Review Focus 5): con `claude_bin="no-existe"`, `run(id)` deja la nota en `error` con «No encuentro el CLI de Claude Code».
  - `test_save_valida`: texto de 1.300 caracteres → `ValueError`; fuente `javascript:` → `ValueError`.
  - `test_guardar_solo_en_motor`: `build()` sin `mcp_engine` no tiene `guardar_explicacion`; con `mcp_engine=True` sí.
  - `test_settle_pide_nota`: apuesta del día liquidada `loss` con el dueño con IA → una nota `pendiente`; con la IA del dueño apagada → ninguna.
  - `test_ia_apagada_sin_nota` (Review Focus 4): `public(nota, usuario_sin_ia) is None`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_ai_notes.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `ai_notes.py`, las herramientas MCP, el gancho en `settle_all`, la tarea `notas_ia` del worker (procesa las `pendiente` de una en una con `claim`) y `POST /radar/investigate {"kind": "team"|"player", "id": int}` (403 si no `can_investigate`; crea la nota y llama a `submit`).
- [ ] **Step 4: Run** `.venv/bin/pytest -q && .venv/bin/ruff check src tests` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Notas de Claude: por qué falló la apuesta del día e investigar el radar"`

### Task 7: Panel — página Sorpresas

**Files:**
- Move: `web/src/app/semana/page.tsx` → `web/src/app/sorpresas/page.tsx`; nuevo `web/src/app/semana/page.tsx` que redirige con `redirect()` a `/sorpresas` conservando `?semana=`
- Modify: `web/src/components/Nav.tsx` (enlace «Sorpresas» a `/sorpresas`), `web/src/components/semana/SemanaView.tsx` (selector Semana/Mes con `?periodo=mes`, título «Sorpresas»)
- Create: `web/src/components/semana/Radar.tsx` (dos columnas «En racha» / «En baja» y la lista de jugadores; botón «Investigar con Claude» si `can_investigate`; la nota debajo de la fila)
- Create: `web/src/lib/me.ts` (`useMe()` sobre `GET /me`)
- Modify: `web/src/lib/types.ts` (`Alert`, `RadarReport`, `TeamRow`, `PlayerRow`, `AiNote`, `Me`, `period` en `WeekRecap`)
- Modify: `.claude/skills/run-app-apuestas/driver.mjs` (páginas `sorpresas`, `sorpresas-mes`; `semana` pasa a `/sorpresas`)

**Interfaces:**
- Consumes: `GET /week?period=`, `GET /radar`, `POST /radar/investigate`, `GET /me`.
- Produces: `useMe(): { me?: Me; mutate }`, `type Alert`, componente `AlertTag({ alert })` exportado desde `Radar.tsx` (lo usa la Tarea 8).

- [ ] **Step 1: Implement** según `DESIGN.md`: filete de 3 px, títulos extracondensados en mayúsculas, etiquetas «En racha» (negra con letra amarilla, `Tag tone="boli"`) y «En baja» (`Tag tone="rojo"`), «Batacazo»/«Pinchazo» como palabra. Mes apagado muestra «Mes · desde el {available_from}». La nota: «Explicación de Claude» + texto plano + fuentes + hora.
- [ ] **Step 2: Verify** `cd web && npm run lint && npx tsc --noEmit`, `systemctl --user restart apuestas-api apuestas-web` y `node .claude/skills/run-app-apuestas/driver.mjs audit --pages sorpresas,sorpresas-mes --schemes light,dark` — Expected: sin desborde, texto < 12 px, contraste bajo ni toques < 24 px; `/semana` abre `/sorpresas`.
- [ ] **Step 3: Commit** `git commit -m "Panel: Sorpresas con Mes y el radar"`

### Task 8: Panel — avisos

**Files:**
- Create: `web/src/components/Avisos.tsx` (`AlertBox({ alert })` y `AlertList({ alerts })`: recuadro con `border-t-[3px]` rojo para baja y de tinta para racha, porqué, figuras con «en el once» y la nota fija)
- Modify: `web/src/components/hoy/HoyView.tsx` (bajo la ficha de la apuesta del día; columna «Aviso» en «Con valor» de escritorio y línea en el celular; etiquetas en «La jornada»), `web/src/components/partidos/PartidosView.tsx` (etiqueta junto al equipo), `web/src/components/partido/PartidoView.tsx` (`AlertList` bajo la cabecera)

**Interfaces:**
- Consumes: `alerts` de `/picks`, `/matches` y `/matches/{ref}/analysis` (Tarea 3); `AlertTag` (Tarea 7).

- [ ] **Step 1: Implement**; la etiqueta dice «{equipo} en racha» o «{equipo} en baja»; al tocarla en «Con valor» despliega `AlertBox`.
- [ ] **Step 2: Verify** lint, tsc, reinicio y `driver.mjs audit --pages hoy,partidos,partido --schemes light,dark` — Expected: auditoría sin empeorar.
- [ ] **Step 3: Commit** `git commit -m "Panel: avisos del radar en Hoy, Partidos y el partido"`

### Task 9: Panel — «Por qué falló» e interruptor de la IA

**Files:**
- Create: `web/src/components/PorQueFallo.tsx` (`PorQueFallo({ pickId })` sobre `GET /picks/{id}/failure`: tabla de lo que se salió de lo esperado, «¿Lo avisaba Sorpresas?» y la nota de Claude o su estado)
- Modify: `web/src/components/hoy/HoyView.tsx` (día pasado con la apuesta del día perdida), `web/src/components/rendimiento/RendimientoView.tsx` (fila perdida del historial de la apuesta del día, desplegable)
- Modify: `web/src/components/datos/DatosView.tsx` (sección «Inteligencia artificial» al final con el interruptor y la lista de lo que apaga), `web/src/components/Nav.tsx` (sin «Capturas» si `ai_enabled` es falso), `web/src/components/hoy/HoyView.tsx` (sin `CaptureQuick` si es falso), `web/src/app/capturas/page.tsx` (con la IA apagada: «La IA está apagada para tu usuario: puedes encenderla al final de Datos.»)

**Interfaces:**
- Consumes: `GET /picks/{id}/failure`, `GET/PUT /me` (Tareas 4-6), `useMe` (Tarea 7).

- [ ] **Step 1: Implement**; el interruptor es un grupo de dos botones «Encendida»/«Apagada» con `aria-pressed`, como el selector de orden de «Con valor».
- [ ] **Step 2: Verify** lint, tsc, reinicio y `driver.mjs audit --pages hoy,rendimiento,datos,capturas --schemes light,dark`; con la IA apagada, captura de Hoy y del menú sin «Capturas».
- [ ] **Step 3: Commit** `git commit -m "Panel: «Por qué falló» y el interruptor de la IA en Datos"`

### Task 10: Revisión de diseño, documentación y puesta en marcha

**Files:**
- Modify: `README.md`, `docs/estado.md`, `docs/arquitectura.md`, `docs/modelos.md` (sección 8: radar, umbrales, Mes), `AGENTS.md` (comandos y estructura), `.claude/skills/disenio-panel/SKILL.md` (componentes nuevos), `DESIGN.md` y `.impeccable/design.json` si aparece un componente nuevo (aviso)
- Create: `docs/adr/0007-sorpresas-y-notas-de-claude.md`

- [ ] **Step 1: Design review (condición del dueño)**: `impeccable detect --json` sobre los archivos del panel tocados, capturas de escritorio, 1280 px y celular en `.impeccable/review/`, y revisión contra `DESIGN.md` y el contrato de `.impeccable/surfaces/`; arreglar lo material en una tanda y volver a capturar.
- [ ] **Step 2: Run** `.venv/bin/pytest -q`, `.venv/bin/ruff check src tests`, `cd web && npm run lint && npm run build`, `node .claude/skills/disenio-panel/paleta.mjs --fallos` — Expected: todo limpio.
- [ ] **Step 3: Restart** `systemctl --user restart apuestas-api apuestas-worker apuestas-web` (mirar antes el registro del worker) y comprobar `active`; `graphify update .`.
- [ ] **Step 4: Commit** en la rama y pedir al dueño el OK para fusionarla en `main` y subirla.
