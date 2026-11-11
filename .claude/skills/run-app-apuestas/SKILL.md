---
name: run-app-apuestas
description: Arrancar, comprobar y manejar el panel web de App Apuestas (Next.js en :3000 + API FastAPI en :8000), sacar capturas de pantalla de sus páginas (escritorio y celular, tema claro y oscuro) y auditar diseño y usabilidad (contraste, tamaños de texto, objetivos táctiles, desbordes, errores de consola). Úsala para run, start, screenshot, test o revisar visualmente el panel.
---

# Run: panel de App Apuestas

El panel (`web/`, Next.js) y la API (`src/apuestas`, FastAPI) corren como servicios systemd de usuario. Un agente los
maneja con **`.claude/skills/run-app-apuestas/driver.mjs`**: abre las páginas en Brave o Chromium sin ventana mediante
`playwright-core`, espera a que carguen los datos, saca capturas y audita el diseño. Las rutas son relativas a la
raíz del repositorio.

## Requisitos

- Servicios instalados (`docs/instalacion.md`): `apuestas-db`, `apuestas-api` (:8000), `apuestas-web` (:3000).
- Un navegador de la familia Chromium. El driver usa el primero que encuentre de `/usr/bin/brave-origin`,
  `brave-browser`, `chromium-browser`, `chromium` y `google-chrome`; otro se indica con `BROWSER=/ruta`. Si no hay
  ninguno, lo dice y no sigue: `sudo dnf install chromium` (Fedora) o `sudo pacman -S chromium` (Arch).
- `playwright-core` ya está en las dependencias de desarrollo del panel (no descarga navegadores):

```bash
cd web && npm install
```

## Arrancar y comprobar

```bash
systemctl --user start apuestas-db apuestas-api apuestas-web
node .claude/skills/run-app-apuestas/driver.mjs check
```

`check` debe decir `panel: http://localhost:3000 → 200`, `api: http://127.0.0.1:8000/health → 200` y
`navegador: <ruta>`. El panel se
recompila al arrancar el servicio: tras tocar `web/`, `systemctl --user restart apuestas-web` y espera a que
`check` dé 200 (unos 30-60 s).

## Manejar el panel (camino del agente)

```bash
# Capturas de todas las páginas: escritorio y celular, claro y oscuro (72 imágenes, ~2 min)
node .claude/skills/run-app-apuestas/driver.mjs shots

# Solo algunas
node .claude/skills/run-app-apuestas/driver.mjs shots --pages hoy,partido --devices mobile --schemes dark

# Una ruta concreta; --viewport recorta a la pantalla (Hoy en celular mide unos 8.000 px de captura)
node .claude/skills/run-app-apuestas/driver.mjs shot "/evaluar?partido=4821" --mobile --dark --viewport --name evaluar-real --ready "Cuotas de Betano"

# Auditoría de diseño y usabilidad (por defecto tema claro; añade --schemes light,dark)
node .claude/skills/run-app-apuestas/driver.mjs audit
```

Las capturas quedan en `/tmp/apuestas-shots/<página>-<desktop|mobile>-<light|dark>.png` y la auditoría en
`/tmp/apuestas-shots/audit.json`. Mira las capturas con la herramienta de leer imágenes: si una sale vacía o con
«No se pudo cargar», no está bien.

| Página (`--pages`) | Ruta | Espera el texto |
|---|---|---|
| `hoy` | `/` | La jornada |
| `hoy-valor` | `/?dia=<día del primer partido>#valor` | Otras apuestas con valor |
| `hoy-props` | `/?dia=<día del primer partido>#props` | Props con cuota mínima |
| `hoy-precio` | `/?dia=<día del primer partido>#precio` | Betano frente a Pinnacle |
| `partidos` | `/partidos` | vs |
| `partido` | `/partidos/<primer partido>` (pestaña Alineaciones) | Alineación y bajas |
| `partido-probabilidades` | `/partidos/<primer partido>#probabilidades` | Dificultad del rival |
| `partido-estadisticas` | `/partidos/<primer partido>#estadisticas` | Estadísticas esperadas |
| `partido-cuotas` | `/partidos/<primer partido>#cuotas` | Props: cuota mínima |
| `partido-jugadores` | `/partidos/<primer partido>#jugadores` | Proyección para este partido |
| `evaluar` | `/evaluar?partido=<primer partido>` | Cuotas de Betano |
| `capturas` | `/capturas` | Arrastra aquí la captura |
| `sorpresas` | `/sorpresas` (semana, radar y pestaña Once) | En el radar |
| `sorpresas-mes` | `/sorpresas?periodo=mes` | En el radar |
| `sorpresas-equipos` | `/sorpresas?semana=<última semana con partidos jugados>#equipos` | Resultado, goles y córners |
| `sorpresas-jugadores` | `/sorpresas?semana=<última semana con partidos jugados>#jugadores` | Remates, remates a puerta |
| `rendimiento` | `/rendimiento` | Banca |
| `datos` | `/datos` | Fuentes |

Qué mide `audit` en cada página: desborde horizontal (px y elementos), textos de menos de 12 px, contraste por
debajo de WCAG AA (4,5:1; 3:1 en texto grande; el texto decorativo con `aria-hidden`, como el «0.00» tachado de
«Hoy no hay apuesta del día», no cuenta, igual que en WCAG), objetivos táctiles de menos de 24 px en celular, imágenes sin `alt`,
controles sin nombre, errores de consola y respuestas HTTP ≥ 400. Además guarda un **inventario de diseño**:
fuentes, tamaños, pesos, colores de texto y de fondo, radios de borde, sombras, animaciones y si existe una regla
`prefers-reduced-motion`.

## Camino humano

Abrir `http://localhost:3000` en el navegador. Para desarrollar con recarga en caliente: `.claude/launch.json`
(api y panel en los mismos puertos; antes `systemctl --user stop apuestas-web apuestas-api`).

## Pruebas

```bash
.venv/bin/pytest -q
cd web && npm run lint && npx tsc --noEmit
```

## Gotchas

- **Playwright no tiene navegadores descargados**: el driver usa `playwright-core` con el navegador del sistema
  (ver Requisitos). No hace falta `npx playwright install`.
- **Páginas que dependen de los datos**: `partido*`, `evaluar` y `hoy-*` usan el primer partido de los próximos 14
  días; si no hay ninguno (parón de verano), el driver lo dice y saca las demás. Las pestañas `sorpresas-equipos` y
  `sorpresas-jugadores` solo existen en una semana con partidos jugados, así que van a la última que los tenga (un
  lunes o en una fecha FIFA, la semana en curso no tiene).
- **Los datos llegan después del HTML** (SWR en el navegador): esperar a `networkidle` no basta; el driver espera
  un texto de cada página (`--ready` en `shot`). Sin eso, la captura sale con el esqueleto de carga.
- **Escudos y gráficos cargan perezosamente** (`loading="lazy"`): el driver recorre la página antes de la captura;
  si no, salen huecos donde van los escudos.
- **Tema oscuro** = `prefers-color-scheme: dark` (`web/src/app/globals.css`); el driver lo emula con
  `colorScheme`. No hay un interruptor de tema en la página.
- **Idioma:** el panel está en español e inglés (selector ES / EN en la cabecera, recordado en `localStorage` como
  `apuestas.idioma`; sin elegir, sigue al navegador). El driver abre siempre en español (`locale: "es-PE"`) y sus
  textos de espera están en español: todavía no saca capturas ni audita en inglés (pendiente en `disenio-panel`).
- **El veredicto de los revisores** (debajo de la apuesta del día de Hoy) solo se pinta con la IA encendida en Datos y
  una revisión hecha; antes de la alineación se ve «Los revisores la leerán cuando salga la alineación».
- **Los radios y el campo de archivo son `sr-only` (1×1 px)**: se tocan por su `<label>`. La auditoría los ignora.
- **Las pestañas `hoy-valor` y `hoy-props` usan el día del primer partido próximo**, no hoy: hoy puede no tener
  partidos y saldrían vacías. `hoy` sí es `/`, como la ve el dueño.
- **El menú superior y las pestañas del partido se desplazan de lado en el celular** (`ScrollRow`): la auditoría no
  lo cuenta como desborde; en la captura se ven cortados con un difuminado y una flecha, que es lo esperado.
- **Desde localhost la API no pide clave**; si el panel se abriera desde otro host, pediría la clave en pantalla.

## Problemas

- **`panel … → SIN RESPUESTA (ECONNREFUSED)`**: el servicio está parado o recompilando.
  `systemctl --user status apuestas-web` y, si hace falta, `journalctl --user -u apuestas-web -n 50`.
- **`no cargó: locator.waitFor: Timeout`** en una página: la API respondió error o la página cambió su texto. Mira
  `problemas:` en la salida (errores de consola y HTTP) y actualiza `ready` en `PAGES` del driver si cambió el texto.
- **`La API no tiene partidos próximos …: se saltan partido, evaluar…`**: no hay partidos en 14 días o falta la
  ingesta (`.venv/bin/apuestas ingest …`, ver `docs/instalacion.md`). Las demás páginas se sacan igual.
