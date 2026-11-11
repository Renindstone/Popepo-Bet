# Faltantes tras el cambio de PC: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar el repositorio y la PC nueva (Fedora) sin huecos conocidos: que la documentación diga la verdad sobre lo que se perdió y que las herramientas de la IA (capturas del panel y auditoría de diseño, en español e inglés) vuelvan a funcionar.

**Architecture:** No cambia la arquitectura. Son cinco tareas independientes: tres de documentación y dos sobre `driver.mjs`, el script que abre el panel sin ventana. Nada toca el modelo, la base de datos ni la API.

**Tech Stack:** Markdown, Node.js 22 con `playwright-core` (ya instalado en `web/node_modules`), Chromium del sistema.

**Spec:** no hay documento aparte. La especificación es el inventario de abajo, hecho el 10-11-2026 a las 21:50 sobre `main` en `bd69a4a`.

## Inventario: qué falta

### A. Se puede hacer ya (tareas de este plan)

| # | Falta | Cómo se comprobó |
|---|---|---|
| 1 | `docs/estado.md` habla de contadores, copias y ramas que ya no existen en esta PC | Tablas `pick`, `user_bet`, `user_bet_leg`, `prediction`, `pick_review`, `ai_note`, `odds_capture` y `availability` con 0 filas; no hay cuotas de Betano en `odds_snapshot`; no existe `var/backups/`; la rama `claude/rating-fotmob` no está en `origin` |
| 2 | El driver de capturas no arranca: busca Brave en `/usr/bin/brave-origin` y en Fedora no hay Brave ni Chromium | `command -v brave chromium firefox` no da nada; `driver.mjs:24` |
| 3 | El driver solo abre en español: no se puede repetir la auditoría en inglés del 31-10 | `driver.mjs:117` fija `locale: "es-PE"`; los textos `ready` están en español |
| 4 | `.impeccable/design.json` y el contrato de Hoy no mencionan el selector de idioma, el veredicto ni «Frente a Pinnacle» | `grep -ciE "veredicto\|idioma\|pinnacle"` da 0 en los dos |
| 5 | `docs/modelos.md` manda a reproducir cifras con scripts que nunca estuvieron en el repositorio (`bt.py`, `cmp.py`, `wf.py`… 23 menciones) | Ninguno existe; eran notas de sesión de la PC anterior |

### B. Necesita al dueño (no son tareas: son preguntas)

| Falta | Qué tiene que hacer o decidir el dueño |
|---|---|
| **Los datos propios de la base de datos anterior**: historial de la apuesta del día (7 de 10, +4,07 u), las 40 que pasaban el corte y su CLV, apuestas registradas y banca, cuotas de Betano y Pinnacle de OddsPapi desde el 19-10, previas guardadas (Sorpresas) y capturas | Decir si conserva el disco de CachyOS o alguna copia de `~/.local/share/apuestas/pgdata` o de `var/backups/*.dump`. Si existe, se restaura. Si no, todo eso empieza de cero el 11-11-2026 |
| Chromium para el driver (tarea 2) | `sudo dnf install chromium` |
| Lectura de capturas con IA local: Ollama no está instalado (`captures_engine = "local"`, modelo `qwen2.5vl:7b`, unos 6 GB) | Elegir: instalar Ollama, o dejar solo Claude con `APUESTAS_CAPTURES_ENGINE=claude_code` en `.env` |
| ADR 0008 | Recordar de qué trataba. No hay ninguna mención en el código ni en los commits |
| Rama remota `claude/wizardly-davinci-mrc9zr` (su contenido ya está en `main`) | OK para borrarla |
| Claves de acceso de los conocidos (solo queda el usuario por defecto) y la banca inicial | Decir a quién volver a dar clave (`apuestas user`); poner la banca en Mis apuestas |
| Telegram | Crear el bot con @BotFather y poner el token en `.env` |

### C. Necesita tiempo o datos (se comprueba solo, más adelante)

- Worker a las 05:00 del 11-11: que arranque con su temporizador y recupere las tareas.
- OddsPapi a las 08:30: primera descarga de Betano y Pinnacle en esta PC (la clave está puesta). Mirar después el cupo con `apuestas ingest oddspapi --estado`: lo gastado en noviembre desde la PC anterior cuenta.
- Primera apuesta del día y primer veredicto real: no hay partidos de clubes hasta el 20-11 (fecha FIFA).
- Las mediciones «por revisar con datos» de `docs/estado.md` (comparador, CLV, suplentes, Turquía) vuelven a empezar si no se recupera la base de datos anterior.

## Global Constraints

- Todo en español sencillo; código y comentarios en español con el estilo del archivo.
- El repositorio es público: nada de claves, `.env`, `var/` ni datos personales.
- No se gasta cupo de OddsPapi en este plan.
- Al terminar cada tarea: `.venv/bin/pytest -q` y `.venv/bin/ruff check src tests` limpios, commit en español y `git push origin main`.
- La sesión «Añadir la UEFA Nations League» trabaja en el mismo directorio: antes de cada commit, `git pull --rebase origin main`.

## Review Focus

1. **No hay ningún navegador instalado**: el driver debe terminar con un mensaje que diga qué instalar, no con una traza de Playwright. (Tarea 2, paso 3.)
2. **No hay partidos en los próximos días** (ahora mismo: ninguno hasta el 20-11): `shots` y `audit` deben seguir sacando las páginas que no dependen de un partido y decir con claridad cuáles se saltan. (Tarea 2, paso 5.)
3. **Un texto `ready` que ya no existe en el panel**: la página se da por no cargada tras el tiempo de espera; hay que corregir el texto, no subir el tiempo. (Tarea 2, paso 5, y tarea 3, paso 2.)
4. **Texto en inglés más largo que el español**: puede desbordar en el celular; lo detecta `audit --lang en` (desborde horizontal). (Tarea 3, paso 4.)
5. **Idioma elegido que se queda guardado**: cada pasada usa un contexto nuevo del navegador, así que `--lang es` después de `--lang en` debe volver a español. (Tarea 3, paso 4.)

---

### Task 1: `docs/estado.md` dice lo que se perdió

**Files:**
- Modify: `docs/estado.md` (cabecera, «Qué funciona hoy», «Pendiente o por decidir»)

- [ ] **Step 1:** Añadir al principio de «Pendiente o por decidir» un punto «**Datos de la PC anterior, perdidos**» con la primera fila de la tabla B de este plan y la fecha desde la que todo empieza de cero (11-11-2026).
- [ ] **Step 2:** En «Qué funciona hoy», en los puntos de la apuesta del día, las que pasan el corte, el comparador y Sorpresas, añadir al final «(cifras de la base de datos anterior; en la PC nueva el contador empieza de cero el 11-11-2026)». No borrar las cifras: son el registro de lo que pasó.
- [ ] **Step 3:** Corregir las tres frases que ya no son ciertas: las copias en `var/backups/` (no existen en esta PC), «la rama `claude/rating-fotmob` se conserva» (se perdió, no estaba en `origin`) y las copias privadas en `~/Proyectos/Claude/popepo-ia`.
- [ ] **Step 4:** Añadir en «Pendiente» las filas restantes de la tabla B como un solo punto «**Por decidir con el dueño tras el cambio de PC**».
- [ ] **Step 5:** Verificar: `grep -n "var/backups\|rating-fotmob\|popepo-ia" docs/estado.md` solo devuelve frases en pasado o marcadas como perdidas. Commit: `Estado: lo que se perdió con la PC anterior`.

### Task 2: el driver encuentra un navegador en Fedora

**Files:**
- Modify: `.claude/skills/run-app-apuestas/driver.mjs:11,24,242` y la función `check`
- Modify: `.claude/skills/run-app-apuestas/SKILL.md` (Requisitos, Gotchas, tabla de páginas)

**Interfaces:**
- Produces: `findBrowser(): string` en `driver.mjs`. Devuelve la primera ruta que exista de, en este orden: `process.env.BROWSER`, `/usr/bin/brave-origin`, `/usr/bin/brave-browser`, `/usr/bin/chromium-browser`, `/usr/bin/chromium`, `/usr/bin/google-chrome`. Si no existe ninguna, escribe en stderr `No hay navegador para el driver. Instala Chromium (Fedora: sudo dnf install chromium; Arch: sudo pacman -S chromium) o indica uno con BROWSER=/ruta.` y sale con código 1.

- [ ] **Step 1:** El dueño ejecuta `sudo dnf install chromium`. Comprobar: `ls /usr/bin/chromium-browser`.
- [ ] **Step 2:** Comprobar el fallo actual: `node .claude/skills/run-app-apuestas/driver.mjs shot /datos` termina con un error de Playwright sobre `/usr/bin/brave-origin`.
- [ ] **Step 3:** Implementar `findBrowser()` con `fs.existsSync`, usarla en `chromium.launch` y hacer que `check` imprima una tercera línea `navegador: <ruta>`. Comprobar el mensaje sin navegador: `BROWSER=/no/existe PATH= /usr/bin/node …/driver.mjs check` no aplica (BROWSER inexistente pasa al siguiente); probarlo renombrando la lista en una copia temporal en el scratchpad, no en el repositorio.
- [ ] **Step 4:** `node .claude/skills/run-app-apuestas/driver.mjs check` imprime `panel … → 200`, `api … → 200` y `navegador: /usr/bin/chromium-browser`.
- [ ] **Step 5:** `node .claude/skills/run-app-apuestas/driver.mjs shots` y luego `audit --schemes light,dark`. Por cada página con `no cargó`, abrir su componente en `web/src` y poner en `PAGES` el texto que hoy pinta (sospechoso conocido: `hoy` espera «Partidos del día», que ahora solo es un `aria-label`; el título visible es «La jornada»). Si las páginas `partido*` y `evaluar` fallan con `La API no tiene partidos próximos`, es la fecha FIFA: ampliar la ventana de búsqueda del primer partido en el driver a 14 días y anotarlo en Gotchas.
- [ ] **Step 6:** Mirar con la herramienta de leer imágenes 4 capturas de `/tmp/apuestas-shots/` (hoy y datos, escritorio y celular): ninguna vacía ni con «No se pudo cargar».
- [ ] **Step 7:** `SKILL.md`: en Requisitos, la lista de navegadores y el paquete por sistema; corregir «52 imágenes» por el número real que imprima `shots`; quitar la frase de que no hay navegadores salvo Brave. Commit: `El driver de capturas encuentra Chromium en Fedora`.

### Task 3: el driver abre el panel en inglés

**Files:**
- Modify: `.claude/skills/run-app-apuestas/driver.mjs` (`PAGES`, `args`, creación del contexto, nombres de archivo)
- Modify: `.claude/skills/run-app-apuestas/SKILL.md` y `.claude/skills/disenio-panel/SKILL.md` («Pendientes conocidos» y la lista de «Antes de dar un cambio por terminado»)
- Modify: `docs/estado.md` (quitar «falta rehacer la auditoría en inglés»)

**Interfaces:**
- Consumes: `findBrowser()` de la tarea 2.
- Produces: opción `--lang es|en` (por defecto `es`) en `shots`, `shot` y `audit`. Con `en`: el contexto usa `locale: "en-GB"`, un `addInitScript` pone `localStorage["apuestas.idioma"] = "en"`, las capturas se llaman `<página>-<dispositivo>-<tema>-en.png` y la auditoría se guarda en `/tmp/apuestas-shots/audit-en.json`. `PAGES[x].ready` pasa a ser un par `[español, inglés]`.

- [ ] **Step 1:** Comprobar que hoy no existe: `driver.mjs shot /datos --lang en --ready "Sources"` saca la página en español y no carga.
- [ ] **Step 2:** Pasar cada `ready` a par. El texto inglés se copia de la misma llamada `tr("…", "…")` de `web/src`, nunca se traduce a mano. Ya localizados: «Alineación y bajas» → «Line-up and absences», «Arrastra aquí la captura» → «Drag the screenshot here», «Banca» → «Bankroll», «Dificultad del rival» → «Opponent difficulty», «En el radar» → «On the radar», «Estadísticas esperadas» → «Expected stats», «Fuentes» → «Sources», «La jornada» → «Fixtures», «Otras apuestas con valor» → «Other value bets», «Props con cuota mínima» → «Props with minimum odds», «Props: cuota mínima» → «Props: minimum odds», «Betano frente a Pinnacle» → «Betano against Pinnacle». Faltan por buscar: «Proyección para este partido», «Cuotas de Betano», «Resultado, goles y córners» y «Remates, remates a puerta».
- [ ] **Step 3:** Implementar `--lang` como dice Interfaces.
- [ ] **Step 4:** `driver.mjs audit --lang en --schemes light,dark` y después `driver.mjs audit --schemes light,dark`: las dos cargan todas las páginas; la segunda sale en español. Comparar el resumen con lo que dice `disenio-panel/SKILL.md` (sin desborde, sin texto de menos de 12 px, contraste AA, toques de 24 px o más).
- [ ] **Step 5:** Si la auditoría en inglés encuentra fallos, apuntarlos uno por línea en «Pendientes conocidos» de `disenio-panel/SKILL.md`. No se arreglan en este plan: son trabajo de diseño y siguen esa skill.
- [ ] **Step 6:** Actualizar las dos skills (ejemplo de `--lang en`, borrar el pendiente «la auditoría en inglés hay que rehacerla») y `docs/estado.md`. Commit: `El driver saca capturas y audita en inglés`.

### Task 4: `.impeccable/` al día

**Files:**
- Modify: `.impeccable/design.json` (lista de componentes)
- Modify: `.impeccable/surfaces/web-src-components-hoy-hoyview-tsx.md`

- [ ] **Step 1:** Leer los dos archivos y las secciones «Navigation», «Veredicto de los revisores» y «Frente a Pinnacle» de `DESIGN.md`.
- [ ] **Step 2:** Añadir a `design.json`, con la misma forma que las entradas de componentes que ya tiene, tres entradas: selector de idioma, veredicto de los revisores y comparador. El texto sale de `DESIGN.md`; no se inventan tokens nuevos.
- [ ] **Step 3:** En el contrato de Hoy, añadir el orden real de la portada: titular → ficha → razones → veredicto de los revisores → pestañas (Con valor, Props, Frente a Pinnacle), y la regla de que el veredicto no lleva recuadro ni pesa más que la ficha.
- [ ] **Step 4:** Verificar: `python3 -c "import json;json.load(open('.impeccable/design.json'))"` sin error y `grep -ciE "veredicto|idioma|pinnacle"` mayor que 0 en los dos archivos. Commit: `Contexto de diseño de impeccable al día`.

### Task 5: `docs/modelos.md` no manda a scripts que no existen

**Files:**
- Modify: `docs/modelos.md` (una nota al principio de la sección 7 y las frases «Reproducir: scripts …»)

- [ ] **Step 1:** `grep -nE '\`[a-z_0-9]+\.py\`' docs/modelos.md docs/auditoria-modelo.md` y, por cada nombre, `find . -name <nombre> -not -path './.venv/*'`. Los que existen en `experimentos/` se quedan con su ruta completa.
- [ ] **Step 2:** Para los que no existen, una sola nota al principio de la sección 7: «Los scripts citados por nombre suelto (`bt.py`, `cmp.py`, `wf.py`…) eran notas de las sesiones en la PC anterior y no se conservan. Las cifras quedan como registro; para volver a medir, usa `apuestas backtest` y los scripts de `experimentos/`.» No se borra ninguna cifra.
- [ ] **Step 3:** Verificar que la nota está y que `AGENTS.md` no cita ninguno de esos scripts (hoy cita uno: corregirlo o quitarlo). Commit: `Modelos: los scripts de sesión citados ya no existen`.

---

## Fuera de este plan

- Crear `graphify-out/`: no se sube al repositorio, es opcional y la guía ya funciona sin él.
- Arreglar lo que encuentre la auditoría en inglés (tarea 3, paso 5).
- Restaurar la base de datos anterior: depende de la respuesta del dueño; si hay copia, es un plan aparte con `pg_dump` previo de la actual.
