# Fuentes de datos (todas gratis)

| Fuente | Qué aporta | Competiciones | Cómo |
|---|---|---|---|
| **football-data.co.uk** | Resultados, remates, a puerta, faltas, córners, tarjetas, árbitro (Inglaterra), xG (desde 2026-27). **Cuotas bet365** previas y de cierre, Betfair Exchange, Pinnacle (hasta 2025-26), media y máxima. `fixtures.csv` con cuotas de próximos partidos | EPL, BUN, LAL y 11 ligas "ligeras" | CSV públicos (`mmz4281/2627/E0.csv`) |
| **football-data.co.uk, ligas extra** | Solo resultado y **1X2 de cierre**: Pinnacle (hasta mediados de 2025), bet365 (desde 2025), Betfair Exchange, media y máxima. Sin estadísticas, sin árbitro y sin más/menos | Austria, Dinamarca, Noruega, Suiza, Polonia, Suecia, Rumanía, Finlandia e Irlanda | Un CSV por liga con todas las temporadas (`new/AUT.csv`) |
| **FotMob** | Estadísticas Opta del partido (xG, remates, córners, tarjetas, faltas, paradas…), **alineación prevista y confirmada** con valor de mercado y rating, **lesionados y sancionados** con fecha estimada de vuelta, **árbitro**, estadísticas por jugador | EPL, BUN, LAL, UCL (+ UEL/UECL solo resultados) | Endpoints que usa su web, 1 petición cada 1,5 s |
| **Understat** | Segundo modelo de xG por partido (se promedia con el de Opta) | EPL, BUN, LAL | JSON público |
| **OddsPapi** *(opcional)* | Cuotas de **Betano** (la de Perú es espejo de la global) y Pinnacle | Todas | API con clave gratuita (experimental) |

## Descartadas

- **SofaScore**: responde 403 a peticiones automáticas. No se intenta saltar la protección.
- **Opta directo**: es de pago (Stats Perform). Sus datos llegan a través de FotMob.
- **FBref**: desde enero de 2026 ya no tiene los datos avanzados de Opta.
- **ClubElo**: la API no respondía durante el desarrollo. El sistema calcula su propia fuerza de equipos.
- **Scraping de bet365/Betano**: va contra sus términos y bet365 bloquea agresivamente. Se usan agregadores.

## Ligas extra de football-data

Sirven para que los rivales de Champions, Europa League y Conference de esas ligas (Bodø/Glimt, Salzburg, Copenhague, Young Boys, Legia, Malmö, FCSB…) tengan **ratings del mercado** como los de las ligas grandes. Se registran en `core/competitions.py` con `fd_extra` (código del archivo `new/XXX.csv`) y se descargan en `pipeline.sync_football_data`, como las demás ligas de football-data.

- **Temporadas**: Noruega, Suecia, Finlandia e Irlanda se juegan de marzo a noviembre (`calendar_year`): su temporada se identifica por el año natural ("2026"). La temporada europea 2026-27 abarca los años 2026 y 2027.
- **Hora**: la del Reino Unido, igual que en los archivos principales.
- **Nombres**: football-data escribe sin tildes ("Bodo/Glimt", "Malmo FF") y a veces de otra forma ("FC Copenhagen", "Legia", "SK Rapid"). La transliteración de `core/names.py` (ø, æ, ł…) y sus variantes conocidas los unen con el equipo de FotMob. Algunos clubes cambian de grafía dentro del mismo archivo según la temporada ("Ham-Kam"/"HamKam", "Din. Bucuresti"/"Dinamo Bucuresti"): `football_data.RENAMES` los unifica.
- **Sin cobertura**: las ligas de los demás rivales europeos (Chequia, Croacia, Serbia, Ucrania, Hungría, Chipre, Israel…) no están en football-data.
- **No se usan para entrenar** salvo con `APUESTAS_EXTRA_LEAGUES_IN_MODEL=true`: con el modelo actual no mejoran el backtest de las copas (resultados en `docs/modelos.md`, "Copas europeas").

## Validación entre fuentes

Cada valor de cada fuente se guarda en `stat_observation`. `store.reconcile()` construye `team_match_stats`:

- **Conteos** (remates, córners, tarjetas…): prioridad FotMob > football-data. Si difieren, se anota en `discrepancies`.
- **xG**: promedio de los proveedores disponibles (Opta/FotMob, Understat y football-data). Cada uno es un modelo distinto, y promediarlos suele predecir mejor que uno solo.
- **Cuotas de OddsPapi**: OddsPapi a veces mete en un partido cuotas de un evento de la casa con local y visitante invertidos (Betano en Atlético - Deportivo, 24-10-2026: 1X2, hándicaps positivos y goles por equipo al revés, hándicaps negativos bien). La respuesta no dice a qué equipo corresponde cada selección, así que no se puede dar la vuelta: se descartan todas las cuotas de esa casa en ese partido, incluidas las guardadas antes desde OddsPapi, si (a) su 1X2 tiene el favorito contrario al de Pinnacle con 25 puntos o más de diferencia en la probabilidad del local, o (b) sus líneas alternativas no son monótonas (un hándicap más a favor o un over más bajo no puede pagar más, con un 10 % de margen). En la descarga del 19-10-2026 solo cayó ese partido, de 77 de Betano y 74 de Pinnacle.

## Uso responsable

Peticiones con ritmo moderado y caché en disco (los partidos terminados no se vuelven a descargar). Uso personal: no se redistribuyen datos crudos. Si algún día se monetiza, hará falta una fuente con licencia (API-Football, Sportmonks…).
