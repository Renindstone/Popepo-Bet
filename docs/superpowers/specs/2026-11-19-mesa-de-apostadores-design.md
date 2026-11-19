# La mesa de apostadores: votación con pesos sobre la apuesta del día

Diseño aprobado por el dueño el 19-11-2026 («OK, lo recomendado»). Lo marcado *(decisión mía)* lo decidió quien escribe
el documento y el dueño puede cambiarlo; lo demás lo decidió él.

## Intención

El dueño quiere que varias personalidades de apostador conversen sobre la apuesta del día y voten sí o no, y ver arriba
el resultado: «Aprobado por los agentes», «Medianamente aprobado» o «Desaprobado por los agentes», con el motivo de cada
uno. Además, que el voto de quien acierta pese más con el tiempo, hasta valer como el de dos agentes.

Ya existe el «Veredicto de los revisores» (ADR 0009): A favor y En contra buscan noticias y un Juez deja «Apostar»,
«Dudosa» o «Mejor no». Nunca se ha ejecutado en la PC actual (la base de datos empieza el 12-11 y no hay ninguna
revisión). La mesa **reemplaza al Juez**; A favor y En contra se quedan para traer las noticias.

## Objetivos

- Siete agentes con personalidad propia votan la apuesta del día en dos rondas y dejan su motivo en español e inglés.
- Resultado con pesos y tres palabras, a la vista debajo de la apuesta del día en Hoy.
- Pesos que se mueven con lo que habría ganado o perdido cada voto, calculados del historial al liquidarse la apuesta.
- Medición por resultado y por agente en `experimentos/validacion/veredicto.py`.

## No objetivos

- **No cambia la probabilidad, la confianza, el corte ni qué apuesta sale.** Es una opinión, como el veredicto de hoy.
- Los pesos no se usan para nada automático. Usarlos así necesita medir antes (unas 30 apuestas del día contadas) y el
  OK del dueño.
- No hay mesa para las apuestas que pasan el corte ni para las del usuario: solo la apuesta del día.

## Anti-objetivos (sería un fracaso aunque funcione)

- Que «Aprobado por los agentes» parezca una garantía. El panel sigue diciendo «La decisión es tuya» y que es una
  opinión sin medir; los textos que prometen («apuesta segura», «sin riesgo», «garantizado») se rechazan.
- Que una página de internet pueda dictar un voto. Solo los dos reporteros tienen internet y no votan; cada agente
  solo puede guardar su propio voto.
- Que la IA invente o cambie números: las cifras salen de `datos_veredicto`.

## Enfoques considerados

1. **La mesa reemplaza al Juez** *(elegido)*. Los reporteros (A favor y En contra) traen noticias; los agentes, sin
   internet, las leen como datos. Un solo veredicto, se reutiliza casi todo `services/verdict.py`.
2. La mesa aparte del veredicto actual: dos veredictos que pueden contradecirse y el doble de gasto.
3. Todos los agentes con internet: más gasto, más riesgo de que una página les dé órdenes y se contagian entre sí.

## Los agentes

Claves en el código, nombre en español y en inglés. Todos leen `datos_veredicto` y los textos de los reporteros.

| Clave | Nombre | English | Cuándo dice sí |
|---|---|---|---|
| `precavida` | La Precavida | The Cautious One | Solo si es muy probable ganar: probabilidad del modelo del 70 % o más, confianza en el umbral del dueño (80 %, `verdict_min_confidence`) o más, alineación confirmada, sin rival en racha y sin trampas al liquidar. Casi siempre dice no. |
| `cazadora` | La Cazadora de cuotas | The Odds Hunter | Si Betano paga claramente más que la cuota justa y que las otras casas, aunque la probabilidad no sea alta: le importa lo que se gana. |
| `estadistica` | La Estadística | The Statistician | Si los números aguantan el detalle: xG, forma, once frente al habitual, bajas, partidos con cuotas de cierre del equipo, cómo se liquida. |
| `desconfiado` | El Desconfiado | The Sceptic | Piensa como la casa: si el modelo ve mucha más ventaja que bet365, sospecha que le falta algo (el backtest dice que el modelo no le gana a bet365). |
| `reportero` | El Reportero | The Reporter | Según el contexto: rotaciones, motivación, Champions a mitad de semana, derbis, entrenador. |
| `rachero` | El Rachero | The Streak Rider | Nunca contra un equipo en racha; sigue la forma y los avisos del radar de Sorpresas. |
| `contraria` | El Llevacontraria | The Contrarian | Desconfía de la apuesta «obvia» al favorito grande y busca por qué podría fallar. |

Las tres primeras las pidió el dueño; las otras cuatro son propuesta aprobada.

## La conversación

1. **Reporteros** (sin cambios): A favor y En contra, con internet y sin ver el texto del otro.
2. **Ronda 1**: cada agente, solo, lee los datos y los dos textos y guarda voto (sí o no) y motivo.
3. **Ronda 2**: cada agente lee los votos y motivos de la ronda 1 de los demás (como datos), puede contestar a uno por
   su nombre y guarda su voto final. Cuenta el de la ronda 2.

Cada motivo tiene de 1 a 3 frases (hasta 300 caracteres), en español y su traducción al inglés en la misma llamada.

## El resultado

- Parte del sí = suma de los pesos de quienes dicen sí ÷ suma de todos los pesos (ronda 2).
- **2/3 o más → «Aprobado por los agentes»**; **más de la mitad → «Medianamente aprobado»**; **la mitad o menos →
  «Desaprobado por los agentes»**. El empate se desaprueba, por prudencia.
- Con siete votos iguales: 5 o más sí, 4, o 3 o menos. Con cinco: 4 de 5 y 3 de 5, como pidió el dueño.
- Se calcula al leer, a partir de los votos y de los pesos guardados con la revisión.

## Los pesos

- Cada agente empieza con peso **×1** (0 % extra). Tope **×2**, piso **×0,5**.
- Al liquidarse la apuesta del día, cada voto final mueve el peso **un 5 % por cada unidad** que habría ganado o perdido
  apostando 1 unidad a esa cuota (`settlement.profit` con la cuota anunciada):
  - Sí y gana a 1,72: +3,6 %. Sí y pierde: −5 %. Media ganada o media perdida: la mitad. Devuelta: nada.
  - **El no cuenta al revés**: no y pierde, +5 % (ahorró 1 unidad); no y gana a 1,72, −3,6 %.
- El tope y el piso se aplican en cada paso, en el orden de los partidos.
- **Se calculan del historial**, no se guardan como contador: cuentan las apuestas del día contadas (`was_pick_of_day`)
  y liquidadas, con su última revisión lista antes del inicio (la misma regla que `measure`). Así siempre se pueden
  rehacer.
- **Cada revisión guarda los pesos con que se votó** (al crearla). Los días pasados se ven como fueron.
- Fallos que quedan, y que el panel y la documentación dicen: los siete votan la misma apuesta cada día y leen los
  mismos números, así que sus votos se parecen; con pocas apuestas, el peso mide sobre todo la suerte.

## Cuándo y cuánto

- Igual que hoy: al confirmarse la alineación o, sin confirmar, a **40 minutos** del partido *(decisión mía: antes eran
  30; la mesa tarda más)*. Como mucho **2 revisiones al día** (antes 3), contando las descartadas que gastaron.
- Unas 16 llamadas a `claude -p` por revisión: 2 reporteros y 7 agentes × 2 rondas.
- Los agentes de cada ronda corren **de 4 en 4 en paralelo** *(decisión mía)*, con esfuerzo **medio** *(decisión mía:
  no buscan en internet y su tarea es corta)*; los reporteros siguen con esfuerzo alto.
- Reintentos como hoy: si falta un voto, la revisión vuelve a pendiente y el reintento solo lanza lo que falta; al
  segundo fallo, error.

## Seguridad

- Cada `claude -p` de un agente lleva en el entorno de su servidor MCP el agente y la ronda
  (`APUESTAS_MCP_AGENT=precavida:1`) *(decisión mía)*. `guardar_voto` no recibe el agente: usa ese valor. Así, aunque
  un texto de los reporteros se lo pidiera, un agente no puede votar por otro ni adelantar la otra ronda.
- Los textos de los reporteros y de la ronda 1 van en el prompt entre etiquetas, como datos, no instrucciones.
- Las herramientas del motor pasan a ser `datos_veredicto`, `guardar_revisor` y `guardar_voto`; desaparece
  `guardar_veredicto`.

## Datos

- Tabla nueva `review_vote`: revisión, agente, ronda (1 o 2), voto (sí/no), motivo, motivo en inglés, fecha. Única por
  (revisión, agente, ronda).
- `pick_review`: se añade `weights` (JSON, los pesos con que se votó) y se quitan `word` y `motives` (eran del Juez; la
  tabla está vacía). `pg_dump` a `var/backups/` antes de migrar.
- `datos_veredicto` añade, si las hay en la base de datos, la cuota de bet365 y la justa de Pinnacle para la misma
  selección, para la Cazadora y el Desconfiado.

## Lo que se ve

Debajo de la apuesta del día en Hoy, en lugar del veredicto del Juez (español e inglés):

```
LA MESA DE APOSTADORES                                  La decisión es tuya.
MEDIANAMENTE APROBADO   4 de 7 dicen sí · 57 % del voto con pesos

Confianza   64 %, por debajo de tu 80 %. …          (lo escribe el código, como hoy)
Racha       Va contra …                              (ídem)
Sí  La Cazadora de cuotas   ×1,04   Betano paga 1,72 y la justa es 1,62…
No  La Precavida            ×1,00   64 % de confianza no llega a su 80 %…   (cambió de opinión)
…
▸ Ver la conversación: ronda 1 y las noticias a favor y en contra
Es una opinión escrita por Claude y todavía no está medida. No cambia el cálculo del modelo.
```

Los avisos de hoy siguen igual: revisado sin alineación confirmada, los números cambiaron, hay una revisión en marcha.

## Lo que queda al constructor

- Nombres exactos de funciones y forma del JSON de `GET /picks/{id}/review`.
- El texto de cada personalidad en el prompt, dentro de lo de arriba.
- Cómo se ve la ronda 1 dentro del plegable.
- Documentación: ADR 0010 (reemplaza al Juez del ADR 0009), `docs/estado.md`, `docs/arquitectura.md`, `README` y sus
  copias en español, y `CHANGELOG.md` en Unreleased.
