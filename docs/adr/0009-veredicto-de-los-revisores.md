# ADR 0009: Veredicto de los revisores

**Estado**: aceptada (2026-11-06). Reconstruida el 10-11-2026 a partir del código, los commits del 6 y 7-11 y
`docs/estado.md`: el original solo vivía en la PC del dueño y se perdió.

## Contexto
El dueño duda de algunas apuestas del día por dos motivos que se repiten:

- **La confianza.** Su regla personal es apostar solo si la cifra «confianza» de la ficha llega al 80 %.
- **Ir contra un equipo en racha.** El radar de Sorpresas no basta: con la fecha del partido no marcaba al PSG
  contra el Villarreal, que llegaba con 5 victorias en 5 partidos.

Además apuesta después de ver la alineación, y antes de eso la confianza casi nunca llega al 80 %. Quería una
segunda opinión que reuniera noticias, alineación, forma y esas dos cifras, sin que la IA pudiera inventar o
cambiar los números.

## Decisión
- **Tres papeles de Claude por separado** (no modelos de otra empresa; Sonnet con esfuerzo alto,
  `verdict_cli_model` y `verdict_effort`), cada uno en su propio `claude -p` aislado (`ai_notes.claude_command`:
  sin archivos ni terminal, carpeta vacía, MCP del proyecto en modo motor):
  - **A favor** y **En contra** pueden buscar y leer noticias, y ninguno ve el texto del otro, para que no se
    contagien. Si un revisor escribe también la parte del otro, falla: el veredicto nunca sale de un solo revisor.
  - **Juez**, sin internet: lee los dos textos como datos (no como instrucciones) y deja «Apostar», «Dudosa» o
    «Mejor no» con 2 a 4 motivos. Así una página de noticias no puede darle órdenes directamente.
  - Herramientas MCP `datos_veredicto`, `guardar_revisor` y `guardar_veredicto`, que solo existen en el MCP del
    motor. Se rechazan textos que prometan («apuesta segura», «sin riesgo», «garantizado»).
- **Los números los pone el código.** La confianza frente al 80 % (`verdict_min_confidence`) y la racha (3
  victorias seguidas o 4 de las últimas 5, en todas las competiciones, del equipo contra el que va la apuesta) se
  calculan en `services/verdict.py` y se guardan en la copia `numbers` de la revisión. El juez no puede usar las
  etiquetas «Confianza» ni «Racha»: esos motivos los añade el sistema.
- **Cuándo se escribe.** Tarea `job_verdict` del worker, cada 5 minutos y aparte de la generación de apuestas (un
  fallo aquí no la toca). Se revisa la apuesta del día cuando su alineación está confirmada o, si no llega, a 30
  minutos del partido. No hay revisión de la mañana: gastaría la suscripción en algo que el dueño no usa. Como
  mucho 3 por día, contando las descartadas que ya gastaron la suscripción, y solo si algún usuario de los motores
  tiene la IA encendida. Sin once confirmado basta con una; otra solo vale la pena con la alineación de verdad.
- **Descartes y reintentos.** Si la apuesta cambia o el partido empieza a mitad, la revisión se descarta. Si
  falta un papel, se reintenta una vez y si no, no hay veredicto. Al arrancar el worker, las que se cortaron
  vuelven a la cola.
- **Qué se ve** (`GET /picks/{pick_id}/review`, `verdict.for_user`; opción A de tres maquetas): debajo de la
  apuesta del día en Hoy, la palabra y sus motivos a la vista y la discusión plegada. Hoy se muestra la confianza
  actual y se avisa si cruzó el 80 % o si la cuota se movió más de un 5 % desde la revisión; los días pasados se
  ven como se revisaron. Con la IA apagada no se escribe ni se ve nada.

## Consecuencias
- **Es una opinión, no un cálculo.** No cambia la probabilidad, la confianza, el corte ni qué apuesta sale. La
  decisión sigue siendo del dueño, y el panel lo dice.
- Gasta la suscripción de Claude de la PC: unas 9 ejecuciones al día como mucho (3 revisiones × 3 papeles), más
  los reintentos. Falta medir cuánto tarda y cuánto gasta una revisión real.
- **Sin medir todavía.** Cada veredicto se guarda para comprobar si «Mejor no» pierde de verdad más que
  «Apostar» (`experimentos/validacion/veredicto.py`). Hasta tener unas 30 apuestas del día contadas no se usa
  para nada automático, y usarlo así necesita el OK del dueño.
