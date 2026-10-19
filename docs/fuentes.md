# Fuentes de datos (todas gratis)

| Fuente | Qué aporta | Competiciones | Cómo |
|---|---|---|---|
| **football-data.co.uk** | Resultados, remates, a puerta, faltas, córners, tarjetas, árbitro (Inglaterra), xG (desde 2026-27). **Cuotas bet365** previas y de cierre, Betfair Exchange, Pinnacle (hasta 2025-26), media y máxima. `fixtures.csv` con cuotas de próximos partidos | EPL, BUN, LAL y 14 ligas "ligeras" | CSV públicos |
| **FotMob** | Estadísticas Opta del partido (xG, remates, córners, tarjetas, faltas, paradas…), **alineación prevista y confirmada** con valor de mercado y rating, **lesionados y sancionados** con fecha estimada de vuelta, **árbitro**, estadísticas por jugador | EPL, BUN, LAL, UCL (+ UEL/UECL solo resultados) | Endpoints que usa su web, 1 petición cada 1,5 s |
| **Understat** | Segundo modelo de xG por partido (se promedia con el de Opta) | EPL, BUN, LAL | JSON público |
| **OddsPapi** *(opcional)* | Cuotas de **Betano** (la de Perú es espejo de la global) y Pinnacle | Todas | API con clave gratuita (experimental) |

## Descartadas

- **SofaScore**: responde 403 a peticiones automáticas. No se intenta saltar la protección.
- **Opta directo**: es de pago (Stats Perform). Sus datos llegan a través de FotMob.
- **FBref**: desde enero de 2026 ya no tiene los datos avanzados de Opta.
- **ClubElo**: la API no respondía durante el desarrollo. El sistema calcula su propia fuerza de equipos.
- **Scraping de bet365/Betano**: va contra sus términos y bet365 bloquea agresivamente. Se usan agregadores.

## Validación entre fuentes

Cada valor de cada fuente se guarda en `stat_observation`. `store.reconcile()` construye `team_match_stats`:

- **Conteos** (remates, córners, tarjetas…): prioridad FotMob > football-data. Si difieren, se anota en `discrepancies`.
- **xG**: promedio de los proveedores disponibles (Opta/FotMob, Understat y football-data). Cada uno es un modelo distinto, y promediarlos suele predecir mejor que uno solo.

## Uso responsable

Peticiones con ritmo moderado y caché en disco (los partidos terminados no se vuelven a descargar). Uso personal: no se redistribuyen datos crudos. Si algún día se monetiza, hará falta una fuente con licencia (API-Football, Sportmonks…).
