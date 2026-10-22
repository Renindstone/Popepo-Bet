# Fuentes de datos (todas gratis)

| Fuente | Qué aporta | Competiciones | Cómo |
|---|---|---|---|
| **football-data.co.uk** | Resultados, remates, a puerta, faltas, córners, tarjetas, árbitro (Inglaterra), xG (desde 2026-27). **Cuotas bet365** previas y de cierre, Betfair Exchange, Pinnacle (hasta 2025-26), media y máxima. `fixtures.csv` con cuotas de próximos partidos | EPL, BUN, LAL, SA, L1 y 9 ligas "ligeras" | CSV públicos (`mmz4281/2627/E0.csv`) |
| **football-data.co.uk, ligas extra** | Solo resultado y **1X2 de cierre**: Pinnacle (hasta mediados de 2025), bet365 (desde 2025), Betfair Exchange, media y máxima. Sin estadísticas, sin árbitro y sin más/menos | Austria, Dinamarca, Noruega, Suiza, Polonia, Suecia, Rumanía, Finlandia e Irlanda | Un CSV por liga con todas las temporadas (`new/AUT.csv`) |
| **FotMob** | Estadísticas Opta del partido (xG, remates, córners, tarjetas, faltas, paradas…), **alineación prevista y confirmada** con valor de mercado y rating, **lesionados y sancionados** con fecha estimada de vuelta, **árbitro**, estadísticas por jugador | EPL, BUN, LAL, SA, L1, UCL; UEL y UECL: resultados y, de los partidos jugados, árbitro y estadísticas de equipo | Endpoints que usa su web, 1 petición cada 1,5 s |
| **Understat** | Segundo modelo de xG por partido (se promedia con el de Opta) | EPL, BUN, LAL, SA, L1 | JSON público |
| **OddsPapi** *(opcional)* | Cuotas de **Betano** (la de Perú es espejo de la global) y Pinnacle | Todas | API con clave gratuita (experimental); como mucho 5 competiciones por petición |

**Si una fuente no responde**: `ingest/http.py` reintenta tres veces. Si aun así no puede conectar con el host, lo da por caído durante 30 minutos (`HOST_DOWN_PAUSE`): las demás descargas de ese host fallan al momento con «no responde» y la ingesta sigue con las otras fuentes. En *Datos* se ve el motivo y el último dato bueno. Caso real: **football-data.co.uk no acepta conexiones desde el 21-10-2026 a las 10:47 (Lima)**, ni por IPv4 ni por IPv6. Tampoco se abría desde fuera de esta red y no había avisos públicos, así que es el sitio (alojado en IONOS) y no un bloqueo a esta IP. Coincide con PHP2Shell (CVE-2026-109618 y CVE-2026-109619, dos fallos críticos del núcleo de PHP publicados el 21-10 hacia las 14:00 UTC): la caída empezó a las 15:47 UTC y ese día IONOS anunció un mantenimiento de seguridad de sus servicios PHP. Como el servidor ni siquiera acepta conexiones, lo más probable es que lo hayan apagado o aislado para parchearlo; no está confirmado. Cuando vuelva, conviene mirar las discrepancias con FotMob de los primeros resultados descargados (`store.py` las anota) por si los archivos se hubieran alterado. Mientras siga así faltan las cuotas de bet365 de los próximos partidos (`fixtures.csv`), las cuotas de cierre de los partidos nuevos (los ratings del mercado se quedan con las de antes) y los resultados de las ligas extra. Los resultados y las estadísticas de las ligas principales llegan igual por FotMob.

**Tipos de alineación de FotMob** (`content.lineup.lineupType`, comprobado en la caché el 22-10-2026): `standard` es el once oficial (el de los partidos jugados y el que sale una hora antes), `predicted` el probable y `lastStarting11` el último once titular del equipo, que FotMob enseña unos días antes cuando aún no tiene probable (`source = lastStartingLineups`). Solo `standard` se guarda como confirmado (`fotmob.LINEUP_CONFIRMED`); lo demás, como probable, y un tipo desconocido deja un aviso en el registro.

**Europa League y Conference en FotMob** (comprobado el 21-10-2026): sus partidos traen las mismas estadísticas Opta que los de la Champions (remates, a puerta, córners, faltas, tarjetas, xG) y el árbitro. Se descargan solo los partidos jugados (`fotmob_stats` en `core/competitions.py`), con `store.apply_fotmob_details(stats_only=True)`: resultado, árbitro y estadísticas de equipo, sin alineaciones, bajas ni estadísticas de jugadores (los onces rotados de estas copas cambiarían el once típico de los equipos de liga). Son unos 1.020 partidos desde 2023-24, una petición cada uno, que quedan en la caché para siempre; el worker los baja poco a poco con el historial de cada día. A 24 de ellos les falta el árbitro.

**Serie A y Ligue 1** (ligas completas desde el 21-10-2026). Antes eran ligas "ligeras": de FotMob solo se bajaba el calendario y el resultado, y de football-data los conteos, el 1X2 de cierre y las cuotas (sin xG hasta 2026-27). Ahora se descargan como las demás ligas completas: detalles de FotMob (xG, estadísticas, alineaciones, bajas, árbitro y jugadores), xG de Understat (`Serie_A`, `Ligue_1`), las cuotas de los próximos partidos de `fixtures.csv` y las de Betano y Pinnacle por OddsPapi (torneos `serie-a` y `ligue-1`, en la misma petición que las demás ligas). El historial son 2.191 partidos jugados desde 2023-24, una petición de FotMob cada uno, que quedan en la caché para siempre; todos traen xG, estadísticas, árbitro, once y jugadores. Understat enlaza todos menos 3 (suspendidos o aplazados y vueltos a jugar otro día), y no aparecen equipos duplicados nuevos entre fuentes.

**Escudos de los equipos:** las imágenes públicas de FotMob (`images.fotmob.com`, por el id de FotMob del equipo). Se descargan con el cliente educado y se guardan 30 días en la caché; la previa de las 08:30 baja de antemano las de los equipos que juegan en los próximos 10 días. La API los sirve en `GET /teams/{id}/logo`, sin clave (son públicas y un `<img>` no puede mandar `X-API-Key`).

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
