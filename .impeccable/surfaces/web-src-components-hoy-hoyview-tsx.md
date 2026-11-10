---
version: 1
slug: "web-src-components-hoy-hoyview-tsx"
primary_target: "web/src/components/hoy/HoyView.tsx"
related_targets: ["web/src/app/layout.tsx","web/src/app/globals.css","web/src/components/ui.tsx"]
---

# Hoy (portada) y mundo visual del panel

- Modo: Operate. El dueño, en la PC por la mañana con luz de día, decide qué apostar y qué no; de noche el sistema pasa a tema oscuro.
- Alcance: la portada de Hoy y el mundo que heredan las demás páginas (cabecera, menú, secciones, tablas, etiquetas, botones).
- Momento memorable: la apuesta del día como titular de portada, con la cuota pasada por el resaltador.
- Sin decidir: si el récord de las que pasan el corte va también en el menú.

## Direction contract

THESIS: El panel es la portada de un diario deportivo: la apuesta del día es el titular y sus cifras la ficha. Rechaza el tablero oscuro de casa de apuestas con tarjetas redondeadas, barras y botones verdes.

OWN-WORLD: Banda amarilla #FFD400 con el logotipo POPEPO·BET en Sofia Sans Extra Condensed 900 y punto rojo #D7141A; papel blanco, tinta #111, gris #5E5E5E; filete negro de 3 px que abre cada sección y reglas finas entre filas; esquinas rectas; etiquetas negras con letra amarilla; cifras extracondensadas con números tabulares. De noche, papel #111 y el amarillo como tinta de lo que el modelo señala.

STORY: El dueño abre la portada, entiende de un vistazo qué propone el modelo, cuánto paga, cuánto se fía y que no apostar también vale; luego baja a las otras con valor o abre el partido.

FIRST VIEWPORT: Cabecera amarilla a todo el ancho; menú bajo un filete; tira de edición con el día y sus botones. Izquierda: titular de la apuesta en mayúsculas extracondensadas hasta 6 rem, entradilla con la etiqueta roja «Apuesta del día», el partido y la probabilidad frente a la que implica la cuota, la ficha de cifras entre filetes con la cuota resaltada, razones en dos columnas y los enlaces al partido y a Betano; debajo, «Con valor» y «Props». Derecha (340 px): «La jornada» con el 1X2 del modelo por competición, el récord, la captura rápida y el recuadro negro «Antes de apostar».

FORM: Portada del diario deportivo, 4.ª de mi lista; seed:0de9f4a4a4281d6d. Interacción propia: la pasada del resaltador sobre la cuota al cargar.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
