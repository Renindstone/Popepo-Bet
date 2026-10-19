"""Bot de Telegram: alertas (apuesta del día, alineaciones, cambios) y consultas rápidas.

Solo responde a los chat_id autorizados (APUESTAS_TELEGRAM_CHAT_ID, separados por comas).
Comandos: /hoy, /apuesta, /partido <equipos>, /bajas <equipo>, /rendimiento, /ayuda
"""

from __future__ import annotations

import logging
import time

import httpx

from apuestas.config import get_settings
from apuestas.services import queries

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


def enabled() -> bool:
    st = get_settings()
    return bool(st.telegram_token and st.telegram_chat_id)


def _allowed() -> set[str]:
    return {c.strip() for c in get_settings().telegram_chat_id.split(",") if c.strip()}


def _call(method: str, **payload) -> dict:
    url = API.format(token=get_settings().telegram_token, method=method)
    r = httpx.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def send(text: str, chat_id: str | None = None) -> None:
    if not enabled():
        log.info("Telegram desactivado. Mensaje: %s", text[:200])
        return
    targets = [chat_id] if chat_id else sorted(_allowed())
    for cid in targets:
        for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
            _call("sendMessage", chat_id=cid, text=chunk, parse_mode="HTML", disable_web_page_preview=True)


# --------------------------------------------------------------------------- formato


def fmt_pick_report(rep: dict) -> str:
    lines = [f"<b>⚽ Apuestas {rep['date']}</b>"]
    pod = rep.get("pick_of_day")
    if pod:
        line = f" {pod['line']:+g}" if pod.get("line") is not None and pod["market"].startswith("ah") else (
            f" {pod['line']:g}" if pod.get("line") is not None else "")
        lines += [
            "",
            "<b>🎯 Apuesta del día</b>",
            f"{pod['match']} ({pod['competition']}, {pod['kickoff_local']})",
            f"{pod['market']} → <b>{pod['selection']}{line}</b> @ {pod['odds']} ({pod['bookmaker']})",
            f"Prob. {pod['prob']:.0%} · cuota justa {pod['fair_odds']} · valor {pod['ev']:+.1%} · "
            f"confianza {pod['confidence']:.0%}",
            f"Stake sugerido: {pod['stake_pct']:.1%} de la banca · alineación: {pod['stage']}",
        ]
    for note in rep.get("notes", []):
        lines += ["", f"ℹ️ {note}"]
    others = [v for v in rep.get("value_bets", []) if v.get("qualifies")][:5]
    if others:
        lines += ["", "<b>Otras con valor</b>"]
        lines += [f"• {v['match']}: {v['label']} @ {v['odds']} ({v['ev']:+.1%})" for v in others]
    props = rep.get("props_to_check", [])[:6]
    if props:
        lines += ["", "<b>Para revisar en Betano (cuota mínima)</b>"]
        for p in props:
            who = p.get("player") or ""
            ln = f" {p['line']:g}" if p.get("line") is not None else ""
            lines.append(f"• {p['match']}: {p['market']} {who} {p['selection']}{ln} → ≥ {p['min_odds']}")
    return "\n".join(lines)


def fmt_analysis(a: dict) -> str:
    md = a["model"]
    p = md["1x2"]
    lines = [
        f"<b>{a['home']} vs {a['away']}</b> ({a['competition']}, {a['kickoff_local']})",
        f"1: {p['home']:.0%} · X: {p['draw']:.0%} · 2: {p['away']:.0%}  (xG {md['expected_goals']['home']}-{md['expected_goals']['away']})",
        f"Más de 2.5: {md['over_goals']['2.5']:.0%} · Ambos marcan: {md['btts_yes']:.0%}",
        f"Dificultad {a['home']}: {a['difficulty']['home']['ajustada']} · {a['away']}: {a['difficulty']['away']['ajustada']}",
    ]
    if a.get("referee"):
        r = a["referee"]
        lines.append(f"Árbitro: {r['name']} ({r.get('cards_per_match', '?')} tarjetas/partido)")
    for side in ("home", "away"):
        miss = a["lineups_and_absences"][side]["missing_regulars"][:4]
        if miss:
            team = a["home"] if side == "home" else a["away"]
            lines.append(f"Bajas {team}: " + ", ".join(m["name"] for m in miss))
    vb = a.get("value_bets", [])[:4]
    if vb:
        lines.append("<b>Valor</b>: " + "; ".join(f"{v['label']} @ {v['odds']} ({v['ev']:+.1%})" for v in vb))
    return "\n".join(lines)


# --------------------------------------------------------------------------- comandos


def handle(text: str) -> str:
    cmd, _, arg = text.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()
    try:
        if cmd in ("/start", "/ayuda", "/help"):
            return __doc__ or ""
        if cmd == "/hoy":
            ms = queries.upcoming(1)
            return "\n".join(f"{x['kickoff_local']} {x['competition']} · {x['home']} vs {x['away']}" for x in ms) or "Sin partidos"
        if cmd == "/apuesta":
            return fmt_pick_report(queries.pick_of_day(refresh=True))
        if cmd == "/partido" and arg:
            return fmt_analysis(queries.match_analysis(arg))
        if cmd == "/bajas" and arg:
            b = queries.absences(arg)
            return f"<b>{b['team']}</b>\n" + "\n".join(
                f"• {x['player']} ({x['kind']}) {x['expected_return'] or ''}" for x in b["absences"]) or "Sin bajas"
        if cmd == "/rendimiento":
            t = queries.performance(get_settings().default_user)["total"]
            return f"Apuestas: {t['bets']} · Beneficio: {t['profit']} · ROI: {t['roi']} · CLV medio: {t['avg_clv']}"
    except queries.NotFound as exc:
        return str(exc)
    return "Comando no reconocido. /ayuda"


def poll_forever() -> None:
    if not enabled():
        log.warning("Telegram no configurado (APUESTAS_TELEGRAM_TOKEN / APUESTAS_TELEGRAM_CHAT_ID)")
        return
    offset = 0
    allowed = _allowed()
    while True:
        try:
            upd = _call("getUpdates", offset=offset, timeout=50)
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                cid = str((msg.get("chat") or {}).get("id", ""))
                if cid not in allowed or not msg.get("text"):
                    continue
                send(handle(msg["text"]), cid)
        except Exception:  # noqa: BLE001 - el bot no debe morir por un error puntual
            log.exception("Error en el bot de Telegram")
            time.sleep(10)
