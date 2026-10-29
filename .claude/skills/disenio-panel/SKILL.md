---
name: disenio-panel
description: Mejorar o revisar el diseño del panel web de App Apuestas (web/) - paleta de colores, tipografía y fuentes, formas, animaciones, UI/UX, usabilidad, accesibilidad, versión celular y tema oscuro. Úsala al pedir "mejora el diseño", "rediseña", "cambia colores o fuentes", "añade una animación", "revisa la usabilidad", "audita el diseño" o al crear una pantalla o componente nuevo.
---

# Diseño del panel

Cómo cambiar el aspecto del panel sin perder su identidad, y cómo **comprobar** cada cambio con capturas y una
auditoría automática. Rutas relativas a la raíz del repositorio. Antes de tocar `web/` lee `web/AGENTS.md`
(Next.js 16) y la skill `run-app-apuestas` (arranque y driver).

## Flujo de trabajo (siempre)

1. **Antes:** capturas y auditoría de las páginas que vas a tocar, para comparar después.
   ```bash
   node .claude/skills/run-app-apuestas/driver.mjs audit --pages hoy,evaluar --schemes light,dark
   node .claude/skills/disenio-panel/paleta.mjs --fallos
   ```
   Mira las capturas de `/tmp/apuestas-shots/` (escritorio y celular, claro y oscuro).
2. **Decide contra el sistema de abajo:** usa los tokens, la escala de texto y los componentes que existen. Si
   algo no encaja, amplía el sistema (un token nuevo en `globals.css`, una variante en `ui.tsx`), no lo esquives
   con valores sueltos.
3. **Implementa** en `web/src/`. Colores y medidas, con clases de Tailwind sobre los tokens (`text-tinta`,
   `bg-hoja`, `border-regla`…).
4. **Después:** `systemctl --user restart apuestas-web`, espera a `driver.mjs check`, repite el paso 1 y compara:
   ninguna cifra de la auditoría puede empeorar (desborde, texto < 12 px, contraste, toques < 24 px, errores de
   consola). Mira las cuatro variantes de cada página tocada; el tema oscuro y el celular son donde más se rompe.
5. `cd web && npm run lint && npx tsc --noEmit`, commit en español con el porqué.

## Identidad: "portada del diario deportivo"

Rediseño del 28-10-2026 (elegido por el dueño entre tres propuestas). El sistema completo, con tokens y reglas, está
en **`DESIGN.md`** (raíz) y su complemento `.impeccable/design.json`; el contrato de la portada, en
`.impeccable/surfaces/`. Resumen: banda amarilla de cabecera con el logotipo POPEPO●BET, papel blanco, tinta negra,
filetes de 3 px que abren cada sección y la apuesta del día como titular. Es una herramienta de análisis honesta, no un
casino: nada de neón, dorados, degradados de adorno, confeti ni "¡ganancia segura!".

## Paleta (`web/src/app/globals.css`)

| Token | Claro | Oscuro | Para qué |
|---|---|---|---|
| `papel` / `hoja` | `#ffffff` / `#ffffff` | `#111111` / `#1a1a1a` | Fondo de la página / campos y tablas |
| `tinta` | `#111111` | `#f2f2f2` | Texto principal y filetes |
| `grafito` | `#5e5e5e` | `#a6a6a6` | Texto secundario, metadatos |
| `regla` / `regla-suave` | `#cfcfcf` / `#e6e6e6` | `#3a3a3a` / `#262626` | Bordes y separadores |
| `boli` / `boli-suave` | `#111111` / `#ffd400` | `#ffd400` / `#3b3200` | Lo que el modelo señala: valor positivo, enlaces, foco, botón principal / resaltador |
| `rojo` / `rojo-suave` | `#d7141a` / `#fff0f0` | `#ff6b6b` / `#3d1a1a` | Pérdida, valor negativo, error |
| `tarjeta` / `tarjeta-suave` | `#8c6500` / `#fff2b8` | `#ffb13b` / `#3a2a10` | Avisos y precaución |
| `amarillo`, `negro`, `rojo-portada` | `#ffd400`, `#111111`, `#d7141a` | iguales | Cabecera, resaltador, etiquetas de señal y la etiqueta «Apuesta del día» |

Reglas:
- **Nunca hex sueltos en componentes.** El campo usa `cesped` y `ficha` (fijos en los dos temas); la ficha del
  visitante va en negro con número amarillo, como el resto de la portada (decisión del dueño, 29-10-2026).
- **Nunca tamaños sueltos** (`text-[1.3rem]`): usa la escala de tokens de la tabla de tipografía.
- **Dos tintas sobre el papel:** amarillo y rojo. El amarillo nunca va como letra sobre blanco (no llega al contraste):
  de día va de fondo; de noche `boli` ya es amarillo.
- **El color nunca va solo:** valor esperado con signo (`+20.4 %`), corte con palabra («Pasa»), resultado con etiqueta
  («Ganada»). Sin pares rojo/verde.
- Al cambiar un color: `paleta.mjs` debe decir "Todas las combinaciones usadas cumplen" en los dos temas.

## Tipografía

**Sofia Sans** en tres anchos (`next/font` en `layout.tsx`): `.cond` = Sofia Sans Extra Condensed (titulares, títulos de
página y sección, cifras), `.semi` = Sofia Sans Condensed (menú, títulos de tarjeta) y normal para leer. `.num`: **toda
cifra en columnas**.

| Uso | Clase | Tamaño | Peso |
|---|---|---|---|
| Solo nombres y notas sobre el campo de alineaciones | `text-xs` | 0,75 rem (12 px), **mínimo absoluto** | 500 |
| Etiquetas (`Tag`), leyendas bajo barras | `text-etiqueta` | 0,8 rem | 600 |
| Metadatos, notas, etiquetas de formulario, cabeceras de tabla | `text-nota` | 0,875 rem | 400 (600 en etiquetas) |
| Texto de interfaz: botones, filtros, campos, tablas | `text-interfaz` | 0,95 rem | 400 |
| Lectura / menú | (sin clase) / `text-base` | 1 rem | 400 / 700 |
| Títulos de tarjeta (`.semi`) | `text-lg` | 1,125 rem | 700 |
| Títulos de sección (`.cond`, mayúsculas) | `text-seccion` (`text-lateral` en la columna lateral) | 2 rem (1,75) | 900 |
| Cifras (`.cond`) | `text-cifra`, `text-cifra-grande`, `text-cuota` (portada), `text-destacado` (tablas) | 2,25 / 2,75 / 4,5 / 1,5 rem | 800 |
| Título de página (`.cond`, mayúsculas) | `text-titulo` y `sm:text-titulo-grande` | 3 rem (4 rem desde `sm`) | 900 |
| Titular de la apuesta del día (`.cond`, mayúsculas) | `text-titular` | `clamp(3rem, 7vw, 6rem)` | 900 |
| Entradilla | `text-entradilla` | 1,25 rem | 500 |

## Formas

- **Esquinas rectas** en botones, campos, etiquetas, cajas y tablas. `rounded-full` solo para puntos, escudos, el punto
  del logotipo y las fichas de jugador; el campo de alineaciones conserva sus 6 px.
- **Filetes, no cajas:** cada `Section` abre con `border-t-[3px] border-tinta`; entre filas, `divide-regla-suave`. Los
  avisos llevan el filete arriba (`border-t-[3px] border-tarjeta bg-tarjeta-suave`), **nunca un borde lateral grueso**.
- **Sin sombras**, salvo las fichas de jugador sobre el césped.
- **Nada de etiquetas pequeñas encima de un título:** la etiqueta roja «Apuesta del día» va dentro de la entradilla.
- **Iconos:** SVG en línea, trazo 2, `currentColor`, `aria-hidden`.

## Movimiento

- Con propósito: confirmar una acción, mostrar que algo carga o guiar la vista. Nada decorativo en bucle.
- **Duraciones:** 150 ms para color en hover y foco (`transition-colors`); 200-250 ms para abrir y cerrar;
  650 ms para la pasada del resaltador sobre la cuota de la apuesta del día (`.resalte`, una vez por página) y 900 ms
  para el trazo de bolígrafo que queda en el veredicto de Evaluar (`.trazo`). Curva estándar `cubic-bezier(0.4, 0, 0.2, 1)`.
- **Carga:** `.esqueleto` (brillo de 1,4 s) mientras llegan los datos, con la forma de lo que va a aparecer.
- **Siempre** con su regla `@media (prefers-reduced-motion: reduce)` en `globals.css` (hoy la tienen `.resalte`,
  `.trazo` y `.esqueleto`). La auditoría comprueba que exista.
- Nada de rebotes, números que cuentan solos con dinero ni animaciones al hacer scroll.

## UI/UX y usabilidad

- **Estructura de página:** `PageTitle` → contenido principal → `Section`s con su filete. Ancho máximo 1280 px,
  márgenes `px-4 sm:px-6`. Lo más importante arriba (la apuesta del día en Hoy, el veredicto en Evaluar). Hoy no lleva
  `PageTitle`: una tira con el día y sus botones, y la apuesta del día como titular.
- **Páginas largas:** si una página mezcla temas y pasa de unos 4.000 px en el celular, repártela en `Tabs` (como la
  de un partido) y monta solo la pestaña activa; las listas largas se cortan en 12 filas con «Mostrar las N».
- **Celular primero:** cero desborde horizontal de la página. Las tablas de consulta anchas van dentro de
  `overflow-x-auto`; si la fila lleva acciones (como «Cuotas de Betano»), mejor recolocar en el celular que esconder
  las acciones a la derecha: columnas secundarias con `hidden sm:table-cell` y su contenido bajo el nombre.
- **Objetivos táctiles:** 40 px (`h-10`, como `Button`) para acciones principales y nunca menos de 24 px. Un enlace o
  botón de texto suelto («Mostrar las 551», «Reintentar») lleva `inline-flex min-h-10 items-center`; dentro de un
  párrafo o de una celda basta su línea (la auditoría no los cuenta).
- **Estados completos:** cargando (`Loading`), vacío con el siguiente paso (`Empty`), error con «Reintentar»
  (`ErrorNote`), éxito con el resultado y un enlace a dónde verlo.
- **Acciones con dinero o que borran:** paso de confirmación con el importe («Sí, registrar S/ 10 a 2.27»), como
  en el registro de apuestas.
- **Formularios:** etiqueta visible siempre, ejemplo en el placeholder, error junto al campo.
- **Cifras:** cuotas con 2 decimales, porcentajes y valor esperado con signo, dinero en soles (`es-PE`), horas en
  Lima.
- **Textos:** español sencillo y los nombres de mercado de Betano. Honestidad: «el modelo no le gana a bet365»
  donde corresponda; nunca «segura».
- **Accesibilidad:** contraste AA, anillo de foco `boli` (ya global), `aria-label` en botones de solo icono, `alt`
  en imágenes (`alt=""` si es decorativa, como los escudos junto al nombre), `role="img"` con descripción para
  gráficos y el campo.

## Componentes que ya existen (reutilizar antes de crear)

`web/src/components/ui.tsx`: `PageTitle`, `Section`, `Loading`, `ErrorNote` (pide la clave si falta), `Empty`,
`Tag` (tonos `neutral`, `boli` = negro con letra amarilla, `rojo`, `tarjeta`, `confirmada` = amarillo), `Figure`, `Button`, `EdgeBar`, `TriBar`,
`ApiKeyForm`. Además: `Crest` (escudos), `PenMark` (trazo, solo en el veredicto de Evaluar), `Avisos.tsx` (`AlertBox`, `AlertList` y `AlertTags`: el aviso del radar, con filete arriba rojo si va en baja y de tinta si va en racha), `semana/Radar.tsx` (`AlertTag`, «Equipo en racha/en baja», y el radar con sus listas cortadas en 3 en el celular), `NotaClaude` (explicación de Claude: firmada, con fuentes y como texto plano) y `PorQueFallo`, `PitchFrame`, `PitchName` y `PitchDisc` (`components/Pitch.tsx`: el campo con sus líneas, para las alineaciones y el once de la semana), `ComboResult` (combinadas), `PickRecord` (aciertos),
`ScrollRow` (fila que se desplaza de lado con difuminado y flecha cuando hay más; la usan el menú y las pestañas) y
`Tabs` + `useHashTab` (pestañas accesibles, fijas arriba al bajar, con la activa en el ancla de la URL y, si se
quiere, cuántas filas hay en cada una con `count`).

## Pendientes conocidos (auditoría del 28-10-2026, tras el rediseño)

La auditoría `--schemes light,dark` sale limpia en las 64 variantes (sin desborde, texto < 12 px, contraste bajo
ni toques < 24 px) y `paleta.mjs --fallos` no da fallos. La página de un partido y la de Hoy van en pestañas (en el
celular, la de un partido mide como mucho unos 3.500 px y Hoy unos 5.500 un sábado de 22 partidos, con «La jornada» cortada en 8) y el
menú del celular avisa con una flecha. Queda lo que la auditoría no mide:

- Nada pendiente de los que la auditoría no mide (29-10-2026: tamaños pasados a tokens, columnas de las cuotas de Betano
  alineadas entre grupos y sin repetir el nombre del mercado, campo con tokens y la ficha del visitante al estilo de
  portada).

Al resolver uno, bórralo de esta lista y añade los nuevos que encuentre la auditoría.

## Antes de dar un cambio por terminado

- [ ] `driver.mjs audit` sin empeorar ninguna cifra, en claro y oscuro y en escritorio y celular.
- [ ] `paleta.mjs --fallos` sin combinaciones nuevas que no lleguen.
- [ ] Capturas revisadas a ojo en las cuatro variantes de las páginas tocadas.
- [ ] Sin hex ni tamaños sueltos nuevos; animaciones con su `prefers-reduced-motion`.
- [ ] `npm run lint` y `npx tsc --noEmit` limpios; servicio `apuestas-web` reiniciado.
