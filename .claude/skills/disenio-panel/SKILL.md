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

## Identidad: "hoja de análisis marcada a bolígrafo"

Papel gris verdoso, tinta oscura y **un único azul de bolígrafo** para lo que el modelo señala. Es una herramienta
de análisis honesta, no un casino: nada de neón, dorados, degradados llamativos, confeti ni "¡ganancia segura!".
La jerarquía la dan el ancho de la letra, el peso y el espacio, no el color.

## Paleta (`web/src/app/globals.css`)

| Token | Claro | Oscuro | Para qué |
|---|---|---|---|
| `papel` | `#eef1ec` | `#131816` | Fondo de la página |
| `hoja` | `#fafbf8` | `#1b2220` | Tarjetas, tablas, campos |
| `tinta` | `#1c2624` | `#e3e9e5` | Texto principal |
| `grafito` | `#5a6764` | `#97a39f` | Texto secundario, metadatos |
| `regla` / `regla-suave` | `#d3dad4` / `#e3e8e3` | `#2f3936` / `#252e2b` | Bordes y separadores |
| `boli` / `boli-suave` | `#2643c4` / `#dfe4f8` | `#93a6ff` / `#232c4f` | Lo que el modelo señala: valor positivo, enlaces, foco, selección, botón principal |
| `rojo` / `rojo-suave` | `#ad3e29` / `#f4e0da` | `#f08a72` / `#3d2621` | Pérdida, valor negativo, error |
| `tarjeta` / `tarjeta-suave` | `#ad800d` / `#f7ecca` | `#f0c552` / `#3a321c` | Avisos y precaución (como una tarjeta amarilla) |

Reglas:
- **Nunca hex sueltos en componentes.** Excepciones que hoy existen y conviene pasar a tokens: el césped del campo
  de alineaciones (`#2e5d45`) y la etiqueta de alineación confirmada (azul claro `#dbeafe`/`#1e3a8a`).
- **Un solo acento por pantalla:** si todo es azul, nada destaca. Botón principal (`bg-boli`) uno por vista.
- **El color nunca va solo:** valor esperado con signo (`+20.4 %`), veredicto con palabra («Apostar»), resultado
  con etiqueta («Ganada»). Pensado también para daltónicos (rojo/verde no se usan como par).
- Al cambiar un color: `paleta.mjs` debe decir "Todas las combinaciones usadas cumplen" en los dos temas (texto
  4,5:1; texto grande y gráficos 3:1). `tarjeta` en claro es un ocre oscuro para que el borde de aviso llegue a 3:1
  sobre `papel` y `hoja`; el amarillo de verdad lo pone `tarjeta-suave` de fondo.

## Tipografía

**Archivo** (Google Fonts con eje de ancho, `next/font` en `layout.tsx`). El **ancho** marca la jerarquía:
- `.cond` (72 %): cifras grandes, cuotas, títulos de página y nombres de equipo en cabeceras.
- `.semi` (86 %): títulos de sección y de tarjeta.
- normal: todo lo que se lee de corrido.
- `.num`: **toda cifra en columnas** (cuotas, porcentajes, importes), para que se alineen.

Escala a usar. Los tamaños pequeños son tokens de `globals.css` (`--text-*` en `@theme`): úsalos por su nombre y
no escribas `text-[0.9rem]` ni parecidos.

| Uso | Clase | Tamaño | Peso |
|---|---|---|---|
| Solo nombres y notas sobre el campo de alineaciones | `text-xs` | 0,75 rem (12 px), **mínimo absoluto** | 500 |
| Etiquetas (`Tag`), leyendas bajo barras | `text-etiqueta` | 0,8 rem (12,8 px) | 500 |
| Metadatos, notas en `grafito`, etiquetas de formulario, celdas densas, cabeceras de tabla | `text-nota` | 0,875 rem (14 px) | 400 (600 en etiquetas) |
| Texto de interfaz: botones, filtros, campos, tablas principales, menú | `text-interfaz` | 0,95 rem (15,2 px) | 400 |
| Lectura | (sin clase) | 1 rem | 400 |
| Títulos de tarjeta (`.semi`) | `text-lg` | 1,125 rem | 700 |
| Títulos de sección (`.semi`) | `text-xl` | 1,25 rem | 700 |
| Cifras destacadas (`.cond`) | | 1,75 / 2,25 rem | 700 |
| Título de página (`.cond`) | | 2,5 rem (3 rem desde `sm`) | 800 |

Interlineado 1,5 para leer, 1,05-1,2 para títulos `.cond`. Peso 900 solo en el logotipo.

## Formas

- **Radios pequeños, de papel:** 3 px en botones, campos y etiquetas; 4 px en tarjetas; 6 px máximo (campo de
  alineaciones). `rounded-full` solo para puntos, escudos y fichas de jugador.
- **Bordes, no sombras:** las superficies se separan con `border-regla` y fondo `hoja`. Sombra solo en las fichas
  de jugador sobre el césped.
- **Separadores:** `border-t border-regla` entre secciones (`Section`), `divide-regla-suave` en listas.
- **Iconos:** SVG en línea, trazo 2, `currentColor`, `aria-hidden`. El trazo de bolígrafo (`PenMark`) es la marca
  de la casa: solo para la apuesta del día y el veredicto «Apostar».

## Movimiento

- Con propósito: confirmar una acción, mostrar que algo carga o guiar la vista. Nada decorativo en bucle.
- **Duraciones:** 150 ms para color en hover y foco (`transition-colors`); 200-250 ms para abrir y cerrar;
  900 ms para el trazo de bolígrafo (`.trazo`). Curva estándar `cubic-bezier(0.4, 0, 0.2, 1)`.
- **Carga:** `.esqueleto` (brillo de 1,4 s) mientras llegan los datos, con la forma de lo que va a aparecer.
- **Siempre** con su regla `@media (prefers-reduced-motion: reduce)` en `globals.css` (hoy la tienen `.trazo` y
  `.esqueleto`). La auditoría comprueba que exista.
- Nada de rebotes, números que cuentan solos con dinero ni animaciones al hacer scroll.

## UI/UX y usabilidad

- **Estructura de página:** `PageTitle` → contenido principal → `Section`s con `border-t`. Ancho máximo 1180 px,
  márgenes `px-4 sm:px-6`. Lo más importante arriba (la apuesta del día en Hoy, el veredicto en Evaluar).
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
`Tag` (tonos `neutral`, `boli`, `rojo`, `tarjeta`, `confirmada`), `Figure`, `Button`, `EdgeBar`, `TriBar`,
`ApiKeyForm`. Además: `Crest` (escudos), `PenMark` (trazo), `ComboResult` (combinadas), `PickRecord` (aciertos),
`ScrollRow` (fila que se desplaza de lado con difuminado y flecha cuando hay más; la usan el menú y las pestañas) y
`Tabs` + `useHashTab` (pestañas accesibles, fijas arriba al bajar, con la activa en el ancla de la URL).

## Pendientes conocidos (auditoría del 21-10-2026, revisada el mismo día)

La auditoría `--schemes light,dark` sale limpia en las 44 variantes (sin desborde, texto < 12 px, contraste bajo
ni toques < 24 px) y `paleta.mjs --fallos` no da fallos. La página de un partido ya va en pestañas (la más larga mide
unos 3.500 px en el celular) y el menú del celular avisa con una flecha. Queda lo que la auditoría no mide:

- **Hoy mide unos 6.900 px en el celular**, ahora la página más larga (consultar antes al usuario: es su página
  principal).
- **Tamaños grandes sueltos:** `text-[1.05rem]`, `[1.3rem]`, `[1.35rem]`, `[1.6rem]`, `[1.9rem]`, `[2.2rem]`,
  `[2.6rem]`, `[3.4rem]` junto a `text-lg`/`xl`/`2xl`/`4xl`: llevarlos a la escala (cifras 1,75 / 2,25 rem, título
  2,5 / 3 rem) con tokens como los pequeños.
- **Cuotas de Betano en escritorio:** cada mercado es su propia tabla y las columnas no se alinean entre grupos; y el
  nombre de cada fila repite el del grupo («Hándicap (3 vías): Galatasaray +1» bajo «Hándicap (3 vías)»).
- **Hex sueltos** en el campo de alineaciones y en la etiqueta «Confirmadas» (ver Reglas de la paleta).

Al resolver uno, bórralo de esta lista y añade los nuevos que encuentre la auditoría.

## Antes de dar un cambio por terminado

- [ ] `driver.mjs audit` sin empeorar ninguna cifra, en claro y oscuro y en escritorio y celular.
- [ ] `paleta.mjs --fallos` sin combinaciones nuevas que no lleguen.
- [ ] Capturas revisadas a ojo en las cuatro variantes de las páginas tocadas.
- [ ] Sin hex ni tamaños sueltos nuevos; animaciones con su `prefers-reduced-motion`.
- [ ] `npm run lint` y `npx tsc --noEmit` limpios; servicio `apuestas-web` reiniciado.
