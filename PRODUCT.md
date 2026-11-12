# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **El dueño**: apostador de fútbol en Perú que apuesta en Betano y bet365. Usa el panel sobre todo **en la PC**, con calma, analizando los partidos antes de apostar. Conoce bien las reglas de su casa y los nombres de mercado de Betano.
- **Algunos conocidos**: gente de confianza con su propia clave de acceso, que sabe de apuestas pero no conoce el modelo por dentro. Cada uno ve sus propias apuestas y su rendimiento.
- **Quien encuentre el repositorio**: el código es público (licencia MIT) y cada persona lo instala en su propia PC. El panel está en español e inglés para que el proyecto llegue también a quien habla inglés (ADR 0007).
- No hay un servicio alojado para el público. La monetización con anuncios es una idea a futuro, no una decisión.

## Product Purpose

Popepo-Bet analiza apuestas de fútbol **prepartido** (Premier League, Bundesliga, LaLiga, Serie A, Ligue 1, Primeira Liga, Pro League de Bélgica, Süper Lig y Champions League; y, de selecciones, la UEFA Nations League, que se analiza pero no entra en la apuesta del día). Estima con un modelo estadístico la probabilidad de cada mercado, la compara con la cuota de la casa y señala las apuestas con valor, entre ellas una apuesta del día. Liquida solo las apuestas registradas y mide el rendimiento (aciertos, ROI, CLV y banca).

El éxito es decidir mejor qué apostar y qué no, con números honestos: "no apostar" es un resultado válido.

## Positioning

Un modelo propio con datos gratuitos (FotMob, football-data, Understat y, opcionalmente, OddsPapi) que dice la probabilidad, la cuota justa y el valor esperado de cada mercado, incluidos córners, tarjetas, remates y props de jugador. Además reconoce con honestidad dónde no le gana a la casa: el backtest muestra que no supera a bet365 en 1X2, goles ni hándicap asiático.

## Operating Context

- Rutina diaria: por la mañana, la apuesta del día y las apuestas con valor de Hoy (solo las de 60 % de probabilidad o más), y la pestaña «Frente a Pinnacle», que compara las cuotas de Betano con la justa de Pinnacle sin usar el modelo. Cuando sale la alineación, el veredicto de los revisores debajo de la apuesta del día («Apostar», «Dudosa» o «Mejor no»): una opinión de Claude, no un cálculo; el dueño decide con su regla de 80 % de confianza. Antes de apostar, el análisis de un partido (alineaciones, probabilidades, estadísticas, cuotas, jugadores). Después, la evaluación de una cuota vista en Betano, por formulario o con una captura de pantalla, y su registro.
- Revisión periódica: Mis apuestas (banca, ROI, CLV), Sorpresas (equipo, jugador y once de la semana o del mes, y el radar de equipos en racha y en baja) y Datos (estado de las fuentes, sincronización y el interruptor de la IA de cada usuario).
- También se usa desde Claude (MCP), la API REST y, si se configura, Telegram.
- Horas en hora de Lima. Cuotas decimales. Dinero siempre en soles (S/).
- Idioma: español o inglés, con el selector ES / EN de la cabecera (sin elegir, el del navegador). En inglés los mercados llevan los nombres de Betano en inglés (Over/Under, Both Teams To Score, Asian Handicap, Handicap (3-way)). Las explicaciones de Claude y los resúmenes de capturas quedan en el idioma en que se escribieron. El bot de Telegram y el MCP, solo en español.

## Capabilities and Constraints

- Páginas actuales: Hoy, Partidos (y el análisis de cada partido), Sorpresas, Evaluar cuota, Capturas (se esconde con la IA apagada), Mis apuestas y Datos.
- Mercados con los nombres de Betano: Resultado, Doble oportunidad, Empate no válido, Ambos equipos marcan, Más/Menos, Hándicap (3 vías) y Hándicap asiático, más córners, tarjetas, remates, faltas y props de jugador (gol, asistencia, gol o asistencia).
- Panel Next.js (web/) que consume la API local. Desde la propia PC la API no pide clave; desde fuera, cada usuario usa su clave.
- El dueño no programa: la IA hace todos los cambios.

## Brand Commitments

- Nombre: **Popepo-Bet**, con el logotipo POPEPO●BET de la cabecera amarilla.
- Voz: español sencillo, directo y honesto, y lo mismo en inglés. Nunca "apuesta segura" ni promesas de ganancia. El modelo no le gana a bet365 en 1X2, goles ni hándicap asiático, y el producto lo dice.
- No es un casino: nada de presión ni de incentivos para apostar más.

## Evidence on Hand

- Datos reales del modelo y de la base de datos: partidos, probabilidades, cuotas de Betano y Pinnacle, alineaciones de FotMob, escudos de los equipos, el historial de la apuesta del día y de las que pasan el corte, y el resumen semanal.
- No hay testimonios, usuarios externos, cifras de negocio ni resultados que prometan ganancias, y no se deben inventar.

## Product Principles

1. **Honestidad antes que entusiasmo**: mostrar la incertidumbre, el valor negativo y la opción de no apostar con el mismo peso que el valor positivo.
2. **El número manda**: probabilidad, cuota justa, cuota de la casa y valor esperado deben poder compararse de un vistazo.
3. **Análisis en calma**: el uso principal es en la PC, revisando con detalle; la densidad de información es una virtud si está ordenada.
4. **Lenguaje del apostador**: los nombres de mercado de Betano y los conceptos que el dueño ya usa, sin jerga del modelo cuando no hace falta.

## Accessibility & Inclusion

Contraste AA en tema claro y oscuro, toques de al menos 24 px en el celular y un panel que siga usable en el celular aunque el uso principal sea la PC.
