---
name: Popepo-Bet
description: Análisis de apuestas de fútbol prepartido con la cara de la portada de un diario deportivo
colors:
  papel: "#ffffff"
  hoja: "#ffffff"
  tinta: "#111111"
  grafito: "#5e5e5e"
  regla: "#cfcfcf"
  regla-suave: "#e6e6e6"
  boli: "#111111"
  boli-suave: "#ffd400"
  rojo: "#d7141a"
  rojo-suave: "#fff0f0"
  tarjeta: "#8c6500"
  tarjeta-suave: "#fff2b8"
  amarillo: "#ffd400"
  negro: "#111111"
  rojo-portada: "#d7141a"
  papel-noche: "#111111"
  hoja-noche: "#1a1a1a"
  tinta-noche: "#f2f2f2"
  grafito-noche: "#a6a6a6"
  regla-noche: "#3a3a3a"
  regla-suave-noche: "#262626"
  boli-noche: "#ffd400"
  boli-suave-noche: "#3b3200"
  rojo-noche: "#ff6b6b"
  rojo-suave-noche: "#3d1a1a"
  tarjeta-noche: "#ffb13b"
  tarjeta-suave-noche: "#3a2a10"
typography:
  titular:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "clamp(3rem, 7vw, 6rem)"
    fontWeight: 900
    lineHeight: 0.88
    letterSpacing: "-0.01em"
  logotipo:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "4rem"
    fontWeight: 900
    lineHeight: 0.8
    letterSpacing: "-0.01em"
  titulo-pagina:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "4rem"
    fontWeight: 900
    lineHeight: 0.9
    letterSpacing: "-0.01em"
  titulo-seccion:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "2rem"
    fontWeight: 900
    lineHeight: 1
  cuota-portada:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "4.5rem"
    fontWeight: 900
    lineHeight: 0.85
  cifra:
    fontFamily: "Sofia Sans Extra Condensed, Sofia Sans, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 800
    lineHeight: 1
  titulo-tarjeta:
    fontFamily: "Sofia Sans Condensed, Sofia Sans, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.25
  entradilla:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.375
  lectura:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  interfaz:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.5
  nota:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  etiqueta:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 600
    lineHeight: 1.25
rounded:
  none: "0px"
  campo: "6px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  cabecera:
    backgroundColor: "{colors.amarillo}"
    textColor: "{colors.negro}"
  button-primary:
    backgroundColor: "{colors.boli}"
    textColor: "{colors.papel}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.hoja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.tinta}"
    textColor: "{colors.papel}"
  etiqueta-senal:
    backgroundColor: "{colors.negro}"
    textColor: "{colors.amarillo}"
    typography: "{typography.etiqueta}"
    rounded: "{rounded.none}"
    padding: "1px 6px"
  etiqueta-confirmada:
    backgroundColor: "{colors.amarillo}"
    textColor: "{colors.negro}"
    typography: "{typography.etiqueta}"
    rounded: "{rounded.none}"
    padding: "1px 6px"
  etiqueta-portada:
    backgroundColor: "{colors.rojo-portada}"
    textColor: "#ffffff"
    typography: "{typography.etiqueta}"
    padding: "0 8px"
  resalte:
    backgroundColor: "{colors.amarillo}"
    textColor: "{colors.negro}"
    typography: "{typography.cuota-portada}"
    padding: "4px 8px 0"
  caja-honesta:
    backgroundColor: "{colors.negro}"
    textColor: "#ffffff"
    padding: "20px"
---

# Design System: Popepo-Bet

## Overview

**Creative North Star: "La portada del diario deportivo"**

El panel se lee como la portada de un diario deportivo peruano de quiosco: una banda amarilla con el logotipo, papel blanco, tinta negra y filetes gruesos que abren cada sección. La apuesta del día es el titular, en mayúsculas extracondensadas a todo lo ancho; sus cifras forman la ficha de debajo, y los partidos del día son «La jornada», la tabla de la columna lateral. Es una herramienta para decidir con calma en la PC, no un casino: el periódico informa, no empuja a apostar.

La densidad es una virtud cuando está ordenada por reglas y por el ancho de la letra, no por cajas. El color tiene pocos trabajos y los hace siempre igual: amarillo para la marca y para lo que el modelo resalta, rojo para la etiqueta de portada y para las pérdidas, negro para todo lo demás.

**Key Characteristics:**
- Banda amarilla de cabecera con POPEPO●BET en extracondensada 900 y un punto rojo.
- Titulares y cifras en Sofia Sans Extra Condensed; lectura en Sofia Sans.
- Filete negro de 3 px que abre cada sección; reglas finas entre filas.
- Esquinas rectas en todo salvo puntos, escudos y el campo de alineaciones.
- La cuota de la apuesta del día, pasada por el resaltador amarillo.

## Colors

Una paleta de quiosco: papel, tinta y dos tintas de imprenta (amarillo y rojo). De noche la página pasa a papel negro y el amarillo se convierte en la tinta de lo que el modelo señala.

### Primary
- **Amarillo de portada** (amarillo): la banda de la cabecera, el resaltador de la cuota, la selección de texto, la etiqueta «Alineación confirmada» y la letra de las etiquetas de señal. No cambia con el tema.

### Secondary
- **Rojo de portada** (rojo-portada): la etiqueta «Apuesta del día» de la entradilla y el punto del logotipo. Fijo en los dos temas.
- **Rojo** (rojo / rojo-noche): pérdidas, valor negativo y errores. Su fondo suave (rojo-suave) solo para avisos de error.

### Tertiary
- **Tarjeta** (tarjeta / tarjeta-suave): avisos y precaución («Por jugarse», «Valor pequeño», notas del día). Ocre de día, ámbar de noche.

### Neutral
- **Papel** (papel, hoja): el fondo; de día las dos son blancas y las superficies se separan con reglas, no con tonos.
- **Tinta** (tinta, negro): texto, filetes, botón principal de día y la caja «Antes de apostar».
- **Grafito** (grafito): texto secundario, metadatos y las cifras que no son la favorita.
- **Regla** (regla, regla-suave): bordes de campos y separadores entre filas.
- **Boli** (boli, boli-suave): el nombre viene del diseño anterior; hoy es «lo que el modelo señala». De día boli es tinta negra (valor positivo, enlaces, foco, botón principal) y boli-suave el amarillo del resaltador; de noche boli es amarillo y boli-suave un oliva oscuro.

### Named Rules
**The Two Inks Rule.** Solo dos tintas de color sobre el papel: amarillo y rojo. Cualquier otro color nuevo necesita un trabajo que ninguna de las dos pueda hacer.
**The Never Alone Rule.** El color nunca va solo: el valor esperado lleva su signo, el corte dice «Pasa» o «No llega» y el resultado dice «Ganada» o «Perdida».

## Typography

**Display Font:** Sofia Sans Extra Condensed (con Sofia Sans de respaldo)
**Title Font:** Sofia Sans Condensed
**Body Font:** Sofia Sans

Una sola familia en tres anchos, servida desde el propio proyecto con `next/font`. El ancho marca la jerarquía: extracondensada para titulares, títulos de sección y cifras; condensada para el menú y los títulos de tarjeta; normal para leer.

### Hierarchy
- **Titular** (900, de 3 a 6 rem, interlineado 0.88, mayúsculas, `text-wrap: balance`): solo la apuesta del día, o «Hoy no hay apuesta del día».
- **Título de página** (900, 3 rem y 4 rem desde `sm`, mayúsculas): una vez por página.
- **Título de sección** (900, 2 rem, mayúsculas): siempre bajo un filete de 3 px; en la columna lateral, 1.75 rem.
- **Cifras** (800, 2.25 rem; 4.5 rem para la cuota de portada; tabulares): cuotas, porcentajes, valor esperado.
- **Entradilla** (500, 1.25 rem, hasta 62 caracteres por línea): la frase que explica el titular.
- **Lectura / interfaz / nota / etiqueta** (1 / 0.95 / 0.875 / 0.8 rem): texto corrido, controles, metadatos y etiquetas. 12 px es el mínimo absoluto.

### Named Rules
**The Width Ladder Rule.** La jerarquía la da el ancho y el peso de la letra, no el color: si un título necesita destacar, sube un peldaño de ancho o de peso.
**The Tabular Rule.** Toda cifra que se compara en columna usa números tabulares.

## Layout

Columna de contenido de 1280 px como máximo con márgenes de 16 px (24 px desde `sm`). La cabecera amarilla y el menú van a todo el ancho de la ventana.

La portada de Hoy usa dos columnas desde `lg`: la principal (titular, ficha, razones y las pestañas «Con valor» / «Props») y una lateral de 340 px con «La jornada», el récord, la captura rápida y la caja «Antes de apostar». En el celular todo va en una columna, en ese orden, y «La jornada» se corta en 8 partidos con «Mostrar los N». Las listas largas se cortan en 12 filas.

**The Rule Opens Rule.** Cada sección empieza con un filete negro de 3 px y el título justo debajo; entre filas, reglas finas de 1 px. Las cajas con borde quedan para campos, el soltador de capturas y los grupos de cuotas.

## Elevation & Depth

Plano como el papel impreso: sin sombras. La profundidad la ponen los filetes, el contraste del negro sobre blanco y, en un único sitio, la caja negra «Antes de apostar». La única sombra que queda es la de las fichas de jugador sobre el césped del campo de alineaciones.

## Shapes

Esquinas rectas (0 px) en botones, campos, etiquetas, cajas y tablas: es papel cortado. `rounded-full` solo para el punto del logotipo, los escudos, los puntos de las barras y las fichas de jugador. El campo de alineaciones conserva sus 6 px de esquina.

## Components

### Buttons
- **Principal:** fondo boli (negro de día, amarillo de noche) con letra de papel, 40 px de alto, negrita, esquinas rectas. Uno por vista.
- **Secundario:** papel con borde de tinta; al pasar el ratón se invierte a tinta con letra de papel.
- **Enlaces de acción** («Comprobar la cuota de Betano», «Mostrar las 431»): negrita en boli, subrayados, con 40 px de alto táctil.

### Chips
- **Señal** (etiqueta-senal): negro con letra amarilla para «Pasa el corte», «Ganada» y lo que el modelo marca.
- **Confirmada** (etiqueta-confirmada): amarillo con letra negra para «Alineación confirmada», que es noticia.
- **Aviso:** fondo tarjeta-suave. **Error o pérdida:** rojo sobre rojo-suave. **Neutra:** borde de regla y letra grafito.

### Cards / Containers
No hay tarjetas como estructura de página. Las secciones son filete más contenido. La caja «Antes de apostar» (caja-honesta) es la única caja de color: negra, título en amarillo y texto blanco.

### Inputs / Fields
Campos de 40 a 44 px, borde de regla, fondo hoja, esquinas rectas y borde boli con el foco. El anillo de foco global es de 2 px en boli.

### Navigation
Cabecera amarilla con el logotipo a la izquierda y la fecha de la edición a la derecha (en el celular, el día de la semana y la fecha en dos líneas). Debajo, el menú en condensada negrita de 16 px sobre papel, cerrado por una regla de tinta; la sección activa lleva una barra negra de 4 px debajo. En el celular el menú se desplaza de lado con una flecha.

### Titular de portada
El componente propio de la casa. El titular (h2 visual de 6 rem; el h1 es la tira de la edición) va seguido de la entradilla con la etiqueta roja «Apuesta del día» en línea, el partido con sus escudos y la probabilidad frente a la que implica la cuota. Debajo, la ficha: un filete de 3 px, la cuota de portada con el resaltador y las cifras (probabilidad, cuota justa, valor esperado, confianza y banca), cerrada por una regla de tinta. Luego las razones, con un cuadradito amarillo como viñeta.

### Aviso del radar
Recuadro con el filete de 3 px arriba: **rojo sobre rojo-suave** si el equipo va en baja y **de tinta sobre
tarjeta-suave** si va en racha. Título en condensada («Bologna viene de un batacazo»), el porqué con la probabilidad que
daba la casa, sus figuras con «en el once» o «fuera del once» y, siempre, la nota «Es un aviso…: no cambia la
probabilidad ni el corte». En las listas va como etiqueta con palabra («Milan en baja»), que abre el recuadro.

### Explicación de Claude
Recuadro de tinta sobre tarjeta-suave con el título «Explicación de Claude», el texto plano, las fuentes como enlaces y
la hora a la que se escribió. Nunca lleva cifras propias del recuadro: las cifras van fuera, del modelo.

**The Highlighter Rule.** El resaltador amarillo se usa una vez por página, sobre la cuota de la apuesta del día, y entra con una sola pasada de 650 ms (sin movimiento si se pide reducirlo).

## Do's and Don'ts

### Do:
- **Do** abrir cada sección con el filete de 3 px y el título en extracondensada mayúscula.
- **Do** escribir las cifras en extracondensada con números tabulares y el valor esperado con su signo.
- **Do** poner en negrita la probabilidad favorita del 1X2 y en grafito las otras dos.
- **Do** mantener la caja «Antes de apostar» y la frase de que el modelo no le gana a bet365 donde se proponen apuestas.

### Don't:
- **Don't** usar etiquetas pequeñas encima de un título: la etiqueta de portada va dentro de la entradilla, debajo del titular.
- **Don't** usar bordes laterales gruesos en avisos o filas: los avisos llevan el filete arriba.
- **Don't** añadir sombras, degradados de adorno, neón, dorados ni esquinas redondeadas a cajas y botones.
- **Don't** usar verde para «ganar» ni pares rojo/verde: el valor positivo es tinta (amarillo de noche) y el negativo, rojo.
- **Don't** usar el amarillo como color de texto sobre papel blanco: no llega al contraste; de día va siempre de fondo.
