# ADR 0010: La mesa de apostadores (votación con pesos sobre la apuesta del día)

[English](../../adr/0010-mesa-de-apostadores.md) · **Español**

**Estado**: aceptada (2026-11-19). Reemplaza al Juez del [ADR 0009](0009-veredicto-de-los-revisores.md); lo demás del
ADR 0009 (A favor y En contra, cuándo se escribe, los números que pone el código) sigue valiendo.

## Contexto
El dueño quería que varias personalidades de apostador conversaran sobre la apuesta del día y votaran sí o no, con el
resultado a la vista: «Aprobado por los agentes», «Medianamente aprobado» o «Desaprobado por los agentes». Además, que
el voto de quien acierta pese más con el tiempo, hasta valer como el de dos agentes.

El veredicto de los revisores (ADR 0009) ya tenía a A favor y En contra leyendo noticias y a un Juez que escribía
«Apostar», «Dudosa» o «Mejor no». Nunca se había ejecutado en la PC actual: la base de datos empieza el 12-11 y no tiene
ninguna revisión.

## Decisión
- **La mesa reemplaza al Juez.** A favor y En contra siguen trayendo las noticias (son los únicos con internet y no
  votan). Después, siete agentes de Claude sin internet leen `datos_veredicto` y los dos textos como datos, y votan:
  - Los tres del dueño: **La Precavida** (sí solo con probabilidad del modelo del 70 % o más, confianza en la regla del
    80 % del dueño, alineación confirmada, sin racha en contra y sin trampas al liquidar), **La Cazadora de cuotas** (sí
    si la casa paga claramente más que la cuota justa y que las otras casas, aunque la probabilidad no sea alta) y
    **La Estadística** (sí si los números aguantan el detalle).
  - Cuatro más, propuestos y aprobados: **El Desconfiado** (piensa como la casa: mucha ventaja sin motivo le hace
    sospechar que al modelo le falta algo), **El Reportero** (el contexto: rotaciones, motivación, Champions entre
    semana), **El Rachero** (nunca contra un equipo en racha) y **El Llevacontraria** (desconfía de la apuesta «obvia» al
    favorito grande).
- **Dos rondas.** En la 1 cada agente vota solo; en la 2 cada uno lee los votos y motivos de la ronda 1 de los demás y
  da su voto final, que es el que cuenta. Cada motivo tiene de 1 a 3 frases, en español y en inglés.
- **Resultado.** Parte del sí = peso de los que dicen sí ÷ peso total. 2/3 o más: aprobado; más de la mitad:
  medianamente; la mitad o menos: desaprobado (el empate se desaprueba, por prudencia). Con siete votos iguales: 5 o
  más, 4, o 3 o menos.
- **Pesos.** Cada agente empieza en ×1, con tope ×2 y piso ×0,5. Al liquidarse la apuesta del día, cada voto final
  mueve su peso un 5 % por unidad que habría ganado o perdido apostando 1 a esa cuota (`settlement.profit`): sí y gana a
  1,72, +3,6 %; sí y pierde, −5 %; **el no cuenta al revés** (no y pierde, +5 %; no y gana a 1,72, −3,6 %); las medias
  cuentan la mitad y las devueltas nada. Los pesos se calculan del historial (`verdict.weights`: las apuestas del día
  contadas con su última revisión antes del inicio) y cada revisión guarda los pesos con que se votó.
- **Cada agente solo vota en su asiento.** Su `claude -p` pasa el asiento a su servidor MCP en `APUESTAS_MCP_AGENT`
  («agente:ronda») y `guardar_voto` no recibe ni el agente ni la ronda. Un texto leído por los revisores no puede hacer
  que un agente vote por otro ni que adelante la ronda 2.
- **Gasto y hora.** Unas 16 llamadas a `claude -p` por revisión (2 revisores + 7 agentes × 2 rondas). Los agentes de
  cada ronda van de 4 en 4, con esfuerzo medio. Como mucho 2 revisiones al día (antes 3) y, sin alineación confirmada,
  a 40 minutos del inicio (antes 30).
- Datos: tabla nueva `review_vote`; se añade `pick_review.weights`; se quitan `pick_review.word` y `motives` (los del
  Juez).

## Consecuencias
- **Sigue siendo una opinión.** No cambia la probabilidad, la confianza, el corte ni qué apuesta sale, y el panel lo
  dice.
- **Fallos que se aceptan y se dicen:** los siete votan la misma apuesta cada día y leen los mismos números, así que
  sus votos se parecen; con pocas apuestas, los pesos miden sobre todo la suerte. Llegar a ×2 exige +20 unidades netas
  en los votos de un agente: tarda meses.
- La primera revisión real dirá cuánto tarda y cuánto gasta de la suscripción; nadie lo ha medido todavía.
- `experimentos/validacion/veredicto.py` mide los aciertos por resultado e imprime los pesos. Usar la mesa para algo
  automático necesita unas 30 apuestas del día contadas y el OK del dueño.

## Alternativas consideradas
- **La mesa junto al veredicto viejo:** dos veredictos que pueden contradecirse y el doble de gasto.
- **Todos los agentes con internet:** más gasto, más riesgo de que una página les dé órdenes y se copiarían entre sí.
- **La primera regla de pesos del dueño** (solo cambia el peso de quien dice sí, con pasos fijos): un agente que
  siempre dice no nunca arriesga nada, y uno que dice sí a todo gana peso con apuestas que pierden dinero a su cuota.
