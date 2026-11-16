# Ficha de traspaso

Resumen de lo que se hizo del 10 al 15 de noviembre de 2026, para que cualquier sesión de IA (o el dueño en otra
máquina) siga sin depender de conversaciones que se pierden. El detalle vive en los documentos enlazados; esta ficha
es el índice. Actualízala al cambiar de PC o de sistema.

## Por qué existe

- **31-10 al 10-11**: las instrucciones de la IA solo vivían en la PC del dueño (CachyOS) y se perdieron al cambiarla.
- **10-11**: el dueño pasó a Fedora. Se reinstaló todo desde cero; la base de datos anterior **se perdió sin copia**
  (confirmado por el dueño el 12-11): historial de la apuesta del día, CLV, apuestas registradas, banca, cuotas de
  Betano guardadas y previas. Todo eso empezó de cero el 11-11-2026.
- **15-11**: el dueño va a cambiar otra vez de distro. Esta vez hay copia de la base de datos (abajo).

## Qué se hizo (en `main`)

| Fecha | Qué | Dónde está el detalle |
|---|---|---|
| 10-11 | Instrucciones de la IA, skills, `DESIGN.md`, `PRODUCT.md`, `.impeccable/` y ADR 0001-0006 recuperados del historial y publicados | `AGENTS.md`, `docs/estado.md` (decisión del 10-11) |
| 10-11 | ADR 0007 (panel en español e inglés) y 0009 (veredicto de los revisores) rehechos con el código. El 0008 sigue perdido | `docs/adr/` |
| 10-11 | Regla del dueño: **todo el contexto de la IA va al repositorio** | `AGENTS.md` |
| 10-11 | Instalación en Fedora probada: los scripts funcionan sin cambios. La descarga de FotMob se cortó y se completó con un servicio temporal (10.604 partidos con detalle) | `docs/instalacion.md`, `docs/estado.md` |
| 10-11 | Una fuente en mantenimiento sale en una línea y la descarga larga avisa cada 100 partidos | commit `0fa1c50` |
| 10-11 | `DESIGN.md`, `PRODUCT.md` y las skills de diseño al día con el selector ES/EN, el veredicto y «Frente a Pinnacle» | commit `55d0a2a` |
| 10-11 | Prueba `test_qualified_picks` corregida: dependía de la fecha | commit `55d0a2a` |
| 10-12-11 | Plan de faltantes tras el cambio de PC, con sus cinco tareas hechas | `docs/superpowers/plans/2026-11-10-faltantes-tras-cambio-de-pc.md` |
| 11-11 | El driver de capturas busca solo el navegador (Brave, Chromium o Chrome), no se cae sin partidos y abre en inglés con `--lang en`. Auditoría limpia en los dos idiomas salvo un enlace de 19 px | skills `run-app-apuestas` y `disenio-panel` |
| 12-11 | **UEFA Nations League** (selecciones): datos y análisis, sin apuesta del día ni mercados de jugador | `AGENTS.md` («Conceptos que se confunden»), `docs/modelos.md` sección 7 |
| 14-11 | Medidos otros índices de calidad del once: la nota y el xG+xA recientes no aportan; los titulares habituales rozan su margen y **no entran** (el dueño decidió esperar al final de la temporada) | `docs/modelos.md` sección 7, `experimentos/validacion/calidad_once.py` |
| 15-11 | **La PC pasó a Windows 11, sin WSL.** Restaurada la copia del 15-11 (27.791 partidos, 1,08 M de cuotas, 461 apuestas guardadas), el modelo y la caché. `db.sh`, `instalar.sh` y `arrancar.sh` funcionan en Git Bash; se arranca con `scripts/arrancar.sh` (nada arranca solo al encender) | `docs/instalacion.md` («Windows sin WSL»), `docs/estado.md` |

## Lo que el dueño preguntó y la respuesta corta (14-11)

¿Se puede mejorar ya la apuesta del día o hay que esperar datos? Las dos cosas. Subir el porcentaje de acierto no es
la meta: exigir más probabilidad solo elige cuotas más bajas. Lo que cuenta es el CLV, que se acumula desde el 11-11.
Analizar una apuesta perdida suelta es casi siempre ruido. Lo que se puede medir ya se mide con el historial
(backtest). Pistas por orden: calidad del once (hecha, no entra), córners y tarjetas frente a Pinnacle (hacia enero,
cuando haya ~150 partidos), fuerza de goles dinámica (poco prometedora) y el veredicto de los revisores (con ~30
apuestas del día contadas).

## Pendiente (resumen; la lista viva está en `docs/estado.md`)

- Decisiones del dueño: Ollama para leer capturas o solo Claude; borrar la rama `claude/wizardly-davinci-mrc9zr`;
  claves de los conocidos y banca inicial; de qué trataba el ADR 0008; bot de Telegram.
- Por medir con datos: comparador frente a Pinnacle y córners/tarjetas (enero), CLV, suplentes, Turquía, veredicto de
  los revisores, titulares habituales (final de la temporada 2026-27).
- Diseño: un enlace de 19 px en Mis apuestas en el celular (skill `disenio-panel`).

## Cambio de distro: qué guardar y cómo volver

Lo que **no** está en el repositorio y hay que copiar a un disco externo o a otra partición antes de formatear:

| Qué | Por qué |
|---|---|
| `.env` | Claves (OddsPapi) y configuración. Nunca va al repositorio |
| `var/backups/traspaso-20261115.dump` | La base de datos completa del 15-11-2026 (24 MB): partidos, cuotas, apuestas del día desde el 11-11, previas |
| `var/models/latest.json` | El modelo entrenado. Si está, `instalar.sh` se salta la descarga de 3-4 horas |
| `var/cache/` (opcional, ~330 MB) | Caché de FotMob y football-data: evita volver a pedir lo ya bajado |

Para volver en el sistema nuevo:

1. Instalar los requisitos del sistema (`docs/instalacion.md`, paso 1) y clonar el repositorio.
2. Copiar `.env` a la raíz y `var/` (con `backups/`, `models/` y, si se guardó, `cache/`) dentro del proyecto.
3. `scripts/instalar.sh`: crea el entorno y una base de datos vacía; con el modelo en su sitio no descarga el historial.
4. Restaurar la copia sobre esa base vacía:

   ```bash
   pg_restore --clean --if-exists --no-owner -d "$(grep '^APUESTAS_DATABASE_URL=' .env | cut -d= -f2- | sed 's#+psycopg##')" var/backups/traspaso-20261115.dump
   ```

   En Windows sin WSL (Git Bash), antes: `export PATH="/c/Program Files/PostgreSQL/18/bin:$PATH"`, y en el paso 5
   `scripts/arrancar.sh` en lugar de `install-services.sh` y `loginctl` (ver `docs/instalacion.md`).

5. `.venv/bin/alembic upgrade head`, `scripts/install-services.sh --with-web` y `loginctl enable-linger "$USER"`.
6. Comprobar: `systemctl --user is-active apuestas-db apuestas-worker apuestas-api apuestas-web`, el panel en
   `http://localhost:3000` y `.venv/bin/pytest`. El worker recupera solo los días que la PC estuvo apagada.

Si la copia se pierde, `scripts/instalar.sh` lo rehace todo desde las fuentes públicas (3-4 horas), pero lo propio
(apuestas, CLV, previas, cuotas de Betano) vuelve a empezar de cero.
