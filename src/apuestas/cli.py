"""Línea de comandos: `apuestas --help`."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import typer
from rich.console import Console

app = typer.Typer(help="Análisis de apuestas de fútbol", no_args_is_help=True)
ingest_app = typer.Typer(help="Descarga de datos", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
console = Console()


def _logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@ingest_app.command("all")
def ingest_all(
    seasons: int = typer.Option(None, help="Temporadas de historial además de la actual"),
    backfill: int = typer.Option(300, help="Máximo de partidos jugados sin detalle a descargar"),
    verbose: bool = False,
) -> None:
    """Sincroniza todas las fuentes (calendario, resultados, estadísticas, cuotas)."""
    from apuestas.core.competitions import season_start_year
    from apuestas.ingest import pipeline

    _logging(verbose)
    years = None
    if seasons is not None:
        cur = season_start_year(datetime.now(UTC).date())
        years = list(range(cur - seasons, cur + 1))
    pipeline.full_sync(years, backfill_limit=backfill)
    console.print("[green]Ingesta completa[/green]")


@ingest_app.command("details")
def ingest_details(days: int = 4, backfill: int = 300, force: bool = False, verbose: bool = False) -> None:
    """Detalles FotMob: alineaciones, bajas, árbitro y estadísticas."""
    from apuestas.ingest import pipeline

    _logging(verbose)
    n = pipeline.sync_fotmob_details(days_ahead=days, backfill_limit=backfill, force_upcoming=force)
    console.print(f"{n} partidos actualizados")


@ingest_app.command("odds")
def ingest_odds(verbose: bool = False) -> None:
    """Cuotas de los próximos partidos."""
    from apuestas.ingest import pipeline

    _logging(verbose)
    pipeline.sync_upcoming_odds()


@ingest_app.command("oddspapi")
def ingest_oddspapi(estado: bool = typer.Option(False, "--estado", help="Solo muestra la cuota mensual usada"),
                    verbose: bool = False) -> None:
    """Cuotas de Betano (u otras casas de tu suscripción) desde OddsPapi. Cada llamada gasta cuota."""
    from apuestas.ingest import oddspapi, pipeline

    _logging(verbose)
    if estado:
        _print_json(oddspapi.account_status())
        return
    n = pipeline._run("oddspapi", "upcoming odds", oddspapi.sync_upcoming)
    console.print(f"{n} cuotas nuevas guardadas")
    _print_json(oddspapi.account_status())


def _print_json(data) -> None:
    import json

    console.print_json(json.dumps(data, ensure_ascii=False, default=str))


@app.command()
def train(verbose: bool = False) -> None:
    """Reentrena todos los modelos con los datos actuales."""
    from apuestas.models.fitting import fit_all, save_bundle, store_team_ratings

    _logging(verbose)
    bundle = fit_all()
    path = save_bundle(bundle)
    store_team_ratings(bundle)
    console.print(f"Modelos guardados en {path} (equipos: {len(bundle.goals.teams)}, jugadores: {len(bundle.players)}, "
                  f"árbitros: {len(bundle.referees)}, rho={bundle.rho:.3f})")


@app.command()
def backtest(
    start: str = "2024-08-01",
    end: str = "2026-06-30",
    half_life: float = 240.0,
    xg_weight: float = 0.85,
    min_ev: float = 0.03,
    w_model: float = 0.25,
    market_weight: float = typer.Option(None, help="Peso de los goles implícitos del cierre (por defecto el del modelo)"),
    lineups: bool = typer.Option(False, help="Mide también el ajuste por once confirmado (log-loss y regresión)"),
    europa: bool = typer.Option(False, help="Mide también la log-loss del modelo en Champions/Europa/Conference"),
    count_l2: float = typer.Option(None, help="L2 fija de los modelos de conteo (1 = la anterior al 21-10-2026); "
                                              "por defecto, la contracción en partidos de COUNT_PRIOR_MATCHES"),
    count_strength: bool = typer.Option(True, help="Remates y córners guiados por la fuerza del modelo de goles; "
                                                   "--no-count-strength = el modelo anterior al 21-10-2026"),
    count_market: bool = typer.Option(True, help="Reparto de remates y córners movido hacia el 1X2 de cierre; "
                                                 "--no-count-market = el modelo anterior al 22-10-2026"),
    count_level: bool = typer.Option(True, help="Remates y a puerta con el nivel reciente de cada liga; "
                                                "--no-count-level = el modelo anterior al 22-10-2026"),
    home_by_league: bool = typer.Option(True, help="Ventaja local propia de cada competición en el modelo de goles; "
                                                   "--no-home-by-league = una sola, como antes del 29-10-2026"),
    ligas: str = typer.Option(None, help="Ligas con cuotas a evaluar, separadas por comas (por defecto las completas: "
                                         "EPL,BUN,LAL,SA,L1; EPL,BUN,LAL = las de antes del 21-10-2026)"),
    out: str = "",
) -> None:
    """Backtest walk-forward contra cuotas históricas de bet365."""
    import json
    from datetime import date

    from apuestas.backtest import engine

    _logging(False)
    leagues = tuple(c.strip().upper() for c in ligas.split(",") if c.strip()) if ligas else engine.LEAGUES
    res = engine.run(date.fromisoformat(start), date.fromisoformat(end), competitions=leagues, half_life_days=half_life,
                     xg_weight=xg_weight, min_ev=min_ev, w_model=w_model, market_weight=market_weight,
                     lineups=lineups, extra_competitions=("UCL", "UEL", "UECL") if europa else (),
                     count_l2=count_l2, count_strength=count_strength, count_market=count_market,
                     count_level=count_level, home_by_league=home_by_league)
    summary = res.summary()
    if out:
        with open(out, "w") as fh:
            json.dump(summary, fh, indent=1, default=str)
    _print_json(summary)


@app.command()
def picks(day: str = typer.Option(None, help="AAAA-MM-DD (hoy por defecto)"), send: bool = False) -> None:
    """Calcula las apuestas con valor y la apuesta del día."""
    from datetime import date

    from apuestas.bot import telegram
    from apuestas.services import picks as picks_service

    _logging(False)
    rep = picks_service.generate(date.fromisoformat(day) if day else None)
    text = telegram.fmt_pick_report(rep)
    console.print(text.replace("<b>", "").replace("</b>", ""))
    if send:
        telegram.send(text)


@app.command()
def semana(dia: str = typer.Option(None, "--semana", help="AAAA-MM-DD de cualquier día de la semana (esta por defecto)"),
           mes: bool = typer.Option(False, "--mes", help="Las 4 semanas completas que terminan en esa semana"),
           as_json: bool = typer.Option(False, "--json")) -> None:
    """Equipo, jugador y once de la semana (o del mes): quién superó lo que esperaban la casa y el modelo."""
    from apuestas.services import queries

    _logging(False)
    data = queries.week_recap(dia, period="mes" if mes else "semana")
    if as_json:
        _print_json(data)
        return
    if not data["available"]:
        console.print(f"El mes aún no está disponible: desde el {data['available_from'] or 'cuando haya previas'}.")
        return
    cov = data["coverage"]
    titulo = "Mes" if mes else "Semana"
    console.print(f"{titulo} del {data['week_start']} al {data['week_end']} ({data['status']}): {cov['played']} jugados, "
                  f"{cov['with_prediction']} con previa, {cov['scheduled']} por jugarse")
    for title, rows in (("Equipos", data["teams"]), ("Jugadores", data["players"])):
        console.print(f"\n{title}:")
        for i, r in enumerate(rows, 1):
            console.print(f"  {i:>2}. {r['name']}: {r['score']:+.2f} ({r['n_matches']} partido/s)")
    console.print(f"\n{data['note']}")


@app.command()
def analyze(match: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Analiza un partido: 'Arsenal vs Chelsea', 'Arsenal' o un id."""
    from apuestas.bot import telegram
    from apuestas.services import queries

    _logging(False)
    data = queries.match_analysis(match)
    if as_json:
        _print_json(data)
    else:
        console.print(telegram.fmt_analysis(data).replace("<b>", "").replace("</b>", ""))


@app.command()
def evaluate(match: str, market: str, selection: str, odds: float, line: float = typer.Option(None),
             bookmaker: str = "betano", player: str = typer.Option(None)) -> None:
    """Evalúa una cuota: apuestas evaluate "Arsenal vs Chelsea" ou_corners over 1.85 --line 9.5"""
    from apuestas.services import queries

    _logging(False)
    _print_json(queries.evaluate_odds(match, market, selection, odds, line, bookmaker, player))


@app.command()
def settle() -> None:
    """Liquida picks y apuestas de partidos terminados."""
    from apuestas.services.picks import settle_all

    _logging(False)
    _print_json(settle_all())


@app.command()
def status() -> None:
    """Estado de las fuentes de datos y del modelo."""
    from apuestas.services import queries

    _print_json(queries.data_status())


@app.command()
def mcp(http: bool = False, host: str = "127.0.0.1", port: int = 8765, public_url: str = typer.Option(None)) -> None:
    """Servidor MCP (stdio por defecto; --http para otros usuarios, cada uno con su clave)."""
    from apuestas.mcp_server.server import run

    logging.basicConfig(level=logging.WARNING)
    run(http=http, host=host, port=port, public_url=public_url)


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """API REST (documentación en /docs)."""
    import uvicorn

    uvicorn.run("apuestas.api.app:app", host=host, port=port)


@app.command()
def bot() -> None:
    """Bot de Telegram (consultas)."""
    from apuestas.bot.telegram import poll_forever

    _logging(False)
    poll_forever()


@app.command()
def worker() -> None:
    """Tareas programadas (ingesta diaria, apuesta del día, alineaciones, archivo)."""
    from apuestas.jobs.scheduler import run

    _logging(False)
    run()


archive_app = typer.Typer(help="Almacenamiento por niveles y archivo histórico", no_args_is_help=True)
app.add_typer(archive_app, name="archive")


@archive_app.command("tiers")
def archive_tiers() -> None:
    """Aplica hot/warm/cold a las temporadas (resumen + poda de cuotas + exportación a Parquet)."""
    from apuestas.archive.seasons import apply_tiers

    _logging(False)
    _print_json(apply_tiers())


@archive_app.command("report")
def archive_report() -> None:
    """Espacio usado en PostgreSQL y en los archivos Parquet."""
    from apuestas.archive.seasons import storage_report

    _print_json(storage_report())


@archive_app.command("query")
def archive_query(sql: str) -> None:
    """SQL DuckDB sobre el archivo: "select count(*) from 'archive://*/EPL/match.parquet'" """
    from apuestas.archive.seasons import query_archive

    console.print(query_archive(sql).to_string())


user_app = typer.Typer(help="Usuarios y sus claves de acceso", no_args_is_help=True)
app.add_typer(user_app, name="user")


@user_app.command("create-key")
def user_create_key(username: str) -> None:
    """Crea (o renueva) la clave de un usuario. Se muestra una sola vez."""
    from apuestas.db.session import session_scope
    from apuestas.services.tracker import create_api_key

    with session_scope() as s:
        key = create_api_key(s, username)
    console.print(f"Clave para [bold]{username}[/bold]: {key}\nGuárdala: no se puede volver a mostrar.")


@user_app.command("bankroll")
def user_bankroll(username: str, amount: float, currency: str = "PEN") -> None:
    """Fija la banca de un usuario."""
    from apuestas.services import queries

    _print_json(queries.set_bankroll(username, amount, currency))


teams_app = typer.Typer(help="Equipos duplicados entre fuentes", no_args_is_help=True)
app.add_typer(teams_app, name="equipos")


@teams_app.command("duplicados")
def teams_duplicates() -> None:
    """Pares que parecen el mismo club. Los seguros se fusionan solos en cada ingesta; el resto, a mano."""
    from apuestas.db.session import session_scope
    from apuestas.ingest import dedupe

    with session_scope() as s:
        _print_json([c.to_dict() for c in dedupe.candidates(s)])


@teams_app.command("fusionar")
def teams_merge(keep_id: int, drop_id: int, si: bool = typer.Option(False, "--si", help="Sin confirmar")) -> None:
    """Fusiona el equipo DROP_ID en KEEP_ID (partidos duplicados, cuotas, alias…). No se puede deshacer."""
    from apuestas.db import models as m
    from apuestas.db.session import session_scope
    from apuestas.ingest import dedupe

    with session_scope() as s:
        keep, drop = s.get(m.Team, keep_id), s.get(m.Team, drop_id)
        if keep is None or drop is None:
            raise typer.BadParameter("No existe alguno de los dos equipos")
        if not si and not typer.confirm(f"¿Fusionar «{drop.name}» ({drop_id}) en «{keep.name}» ({keep_id})?"):
            raise typer.Abort()
        _print_json(dedupe.merge_teams(s, keep_id, drop_id))
    console.print("Vuelve a entrenar el modelo: apuestas train")


@teams_app.command("fusionar-seguros")
def teams_merge_safe() -> None:
    """Fusiona ahora los pares seguros (lo mismo que hace la ingesta al terminar)."""
    from apuestas.ingest import pipeline

    _logging(False)
    console.print(f"{pipeline.merge_duplicate_teams()} equipos fusionados. Vuelve a entrenar: apuestas train")


captures_app = typer.Typer(help="Capturas de cuotas que lee una IA", no_args_is_help=True)
app.add_typer(captures_app, name="capturas")


@captures_app.command("lista")
def captures_list(user: str = typer.Option(None, help="Usuario (por defecto el principal)")) -> None:
    """Últimas capturas subidas y su estado."""
    from apuestas.config import get_settings
    from apuestas.services import captures

    rows = captures.list_for(user or get_settings().default_user, 20)
    _print_json([{k: r[k] for k in ("id", "status", "created_local", "match_hint", "summary", "error")} for r in rows])


@captures_app.command("procesar")
def captures_process(capture_id: int) -> None:
    """Procesa ahora una captura pendiente o con error, con el motor configurado (sin pasar por la API)."""
    from apuestas.config import get_settings
    from apuestas.services import capture_engines, captures

    _logging(False)
    owner = captures.owner(capture_id)
    if owner is None:
        raise typer.BadParameter(f"No existe la captura {capture_id}")
    if captures.get(owner, capture_id)["status"] == "error":
        captures.reset_for_retry(owner, capture_id)
    info = capture_engines.process(capture_id)
    _print_json({"motor": get_settings().captures_engine, **info, "captura": captures.get(owner, capture_id)})


if __name__ == "__main__":
    app()
