"""Consultas de alto nivel compartidas por la API REST, el servidor MCP y el bot de Telegram.

Todas devuelven diccionarios serializables (JSON) en español.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.core import names
from apuestas.core.competitions import FULL
from apuestas.db import models as m
from apuestas.db.session import session_scope
from apuestas.models.fitting import load_bundle
from apuestas.services import analysis, picks, tracker


class NotFound(LookupError):
    pass


# --------------------------------------------------------------------------- búsqueda


def _team_candidates(s: Session) -> dict[int, str]:
    return dict(s.execute(select(m.Team.id, m.Team.name)).all())


def find_team(s: Session, text: str, among: dict[int, str] | None = None) -> m.Team:
    cands = among if among is not None else _team_candidates(s)
    best = max(cands.items(), key=lambda kv: names.search_score(text, kv[1]), default=None)
    if best is None or names.search_score(text, best[1]) < 75:
        if among is not None:
            return find_team(s, text)
        raise NotFound(f"No encuentro el equipo '{text}'")
    return s.get(m.Team, best[0])


def _split_teams(text: str) -> list[str]:
    low = text.lower()
    for sep in (" vs ", " v ", " - ", " contra ", " x "):
        if sep in low:
            idx = low.index(sep)
            return [text[:idx].strip(), text[idx + len(sep):].strip()]
    return [text.strip()]


def find_match(s: Session, ref: str | int, days_ahead: int = 10) -> m.Match:
    """Acepta un id de partido o texto tipo 'Arsenal vs Chelsea' / 'Arsenal' / 'Rayo'."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
        match = s.get(m.Match, int(ref))
        if match is None:
            raise NotFound(f"No existe el partido {ref}")
        return match
    parts = _split_teams(str(ref))
    now = datetime.now(UTC)
    upcoming = s.scalars(select(m.Match).where(
        m.Match.kickoff_utc >= now - timedelta(hours=3), m.Match.kickoff_utc <= now + timedelta(days=days_ahead))
        .order_by(m.Match.kickoff_utc)).all()
    best, best_score = None, 0.0
    for mt in upcoming:
        names_ = (mt.home_team.name, mt.away_team.name)
        if len(parts) == 2:
            sc = min(names.search_score(parts[0], names_[0]), names.search_score(parts[1], names_[1]))
            sc = max(sc, min(names.search_score(parts[0], names_[1]), names.search_score(parts[1], names_[0])) - 1)
        else:
            sc = max(names.search_score(parts[0], n) for n in names_)
        if sc > best_score + 1e-9:  # a igualdad, el más próximo en el tiempo
            best, best_score = mt, sc
    if best is None or best_score < 75:
        raise NotFound(f"No hay partido próximo para '{ref}' en los próximos {days_ahead} días")
    return best


def find_player(s: Session, text: str, team_id: int | None = None) -> m.Player:
    q = select(m.Player.id, m.Player.name)
    if team_id:
        q = q.where(m.Player.current_team_id == team_id)
    cands = dict(s.execute(q).all())
    best, best_score = None, 0.0
    for pid, pname in cands.items():
        sc = names.person_similarity(text, pname)
        if names.normalize(text) in names.normalize(pname):
            sc = max(sc, 92)
        if sc > best_score:
            best, best_score = pid, sc
    if best is None or best_score < 80:
        raise NotFound(f"No encuentro al jugador '{text}'")
    return s.get(m.Player, best)


# --------------------------------------------------------------------------- consultas


def competition_code(text: str) -> str:
    """Código de una competición completa a partir del código o del nombre: "sa", "Serie A" -> "SA"."""
    key = names.strip_accents(text).lower().replace(" ", "")
    for c in FULL:
        if key in (c.code.lower(), names.strip_accents(c.name).lower().replace(" ", "")):
            return c.code
    return text.upper()


def upcoming(days: int = 3, competition: str | None = None) -> list[dict]:
    now = datetime.now(UTC)
    codes = [competition_code(competition)] if competition else [c.code for c in FULL]
    with session_scope() as s:
        rows = s.scalars(
            select(m.Match).join(m.Competition).where(
                m.Competition.code.in_(codes), m.Match.status == "scheduled",
                m.Match.kickoff_utc >= now - timedelta(hours=2), m.Match.kickoff_utc <= now + timedelta(days=days))
            .order_by(m.Match.kickoff_utc)).all()
        tz = get_settings().tz
        dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

        def local(dt: datetime) -> str:
            loc = dt.astimezone(tz)
            return f"{dias[loc.weekday()]} {loc:%d/%m %H:%M}"

        return [{"match_id": r.id, "competition": r.competition.code,
                 "kickoff_local": local(r.kickoff_utc),
                 "home": r.home_team.name, "away": r.away_team.name,
                 "home_id": r.home_team_id, "away_id": r.away_team_id,
                 "referee": r.referee.name if r.referee else None, "lineups": r.lineup_status} for r in rows]


def match_analysis(ref: str | int) -> dict:
    bundle = load_bundle()
    with session_scope() as s:
        match = find_match(s, ref)
        return analysis.analyze(s, bundle, match).to_dict()


def evaluate_odds(ref: str | int, market: str, selection: str, odds: float, line: float | None = None,
                  bookmaker: str = "betano", player: str | None = None) -> dict:
    bundle = load_bundle()
    with session_scope() as s:
        match = find_match(s, ref)
        player_id = None
        if player:
            player_id = find_player(s, player).id
        an, ev = analysis.evaluate_user_odds(s, bundle, match, market, selection, line, odds, bookmaker, player_id)
        return {
            "match": f"{match.home_team.name} vs {match.away_team.name}",
            "bet": ev.label(match.home_team.name, match.away_team.name, player),
            **verdict_fields(ev),
            "lineup_status": an.stage,
        }


def verdict_fields(ev: analysis.BetEval) -> dict:
    """Números de una cuota evaluada + veredicto (lo comparten evaluar_cuota y las capturas)."""
    st = get_settings()
    verdict = "APOSTAR" if picks.qualifies(ev) else ("valor pequeño o poca confianza" if ev.ev > 0 else "NO apostar")
    return {**ev.to_dict(), "verdict": verdict,
            "min_odds_for_value": round((1 + st.pick_min_ev) / ev.prob, 2) if ev.prob > 0 else None}


def pick_of_day(day: str | None = None, refresh: bool = False) -> dict:
    d = date.fromisoformat(day) if day else picks.today_local()
    if refresh or d >= picks.today_local():
        return picks.generate(d)
    with session_scope() as s:
        # Primero las que pasaron el corte (y no se retiraron), luego el resto por valor esperado
        rows = sorted(s.scalars(select(m.Pick).where(m.Pick.pick_date == d,
                                                     m.Pick.odds >= get_settings().value_list_min_odds)),
                      key=lambda p: (not (p.qualifies and p.status != "withdrawn"), -p.ev))
        pod = next((p for p in rows if p.is_pick_of_day), None)
        return {
            "date": d.isoformat(),
            "pick_of_day": None if pod is None else {
                "match": f"{pod.match.home_team.name} vs {pod.match.away_team.name}", "market": pod.market,
                "selection": pod.selection, "line": pod.line, "odds": pod.odds, "ev": pod.ev,
                "result": pod.result, "clv": pod.clv},
            "value_bets": [{"match": f"{p.match.home_team.name} vs {p.match.away_team.name}", "market": p.market,
                            "selection": p.selection, "line": p.line, "odds": p.odds, "ev": round(p.ev, 3),
                            "prob": round(p.model_prob, 3), "confidence": round(p.confidence, 2),
                            "status": p.status, "result": p.result, "qualifies": p.qualifies,
                            "is_pick_of_day": p.is_pick_of_day} for p in rows],
        }


def absences(team: str) -> dict:
    with session_scope() as s:
        t = find_team(s, team)
        rows = s.execute(select(m.Availability, m.Player).join(m.Player)
                         .where(m.Availability.team_id == t.id, m.Availability.active.is_(True))).all()
        return {"team": t.name, "absences": [
            {"player": p.name, "position": p.position, "kind": a.kind, "reason": a.reason,
             "expected_return": a.expected_return, "source": a.source,
             "market_value_m": round((p.market_value_eur or 0) / 1e6, 1)} for a, p in rows]}


def add_absence(team: str, player: str, kind: str = "injury", reason: str | None = None,
                expected_return: str | None = None) -> dict:
    """Baja manual (p.ej. leída en una rueda de prensa antes de que la publique FotMob)."""
    with session_scope() as s:
        t = find_team(s, team)
        p = find_player(s, player, team_id=t.id)
        s.add(m.Availability(player_id=p.id, team_id=t.id, kind=kind, reason=reason,
                             expected_return=expected_return, source="manual"))
        return {"ok": True, "team": t.name, "player": p.name, "kind": kind}


def remove_absence(team: str, player: str) -> dict:
    with session_scope() as s:
        t = find_team(s, team)
        p = find_player(s, player, team_id=t.id)
        n = 0
        for a in s.scalars(select(m.Availability).where(m.Availability.player_id == p.id,
                                                        m.Availability.active.is_(True))):
            a.active = False
            n += 1
        return {"ok": True, "deactivated": n, "player": p.name}


def referee_profile(name: str) -> dict:
    bundle = load_bundle()
    with session_scope() as s:
        refs = dict(s.execute(select(m.Referee.id, m.Referee.name)).all())
        best = max(refs.items(), key=lambda kv: names.person_similarity(name, kv[1]), default=None)
        if best is None or names.person_similarity(name, best[1]) < 80:
            raise NotFound(f"No encuentro al árbitro '{name}'")
        stats = bundle.referees.get(best[0], {})
        upcoming_matches = s.scalars(select(m.Match).where(m.Match.referee_id == best[0], m.Match.status == "scheduled")
                                     .order_by(m.Match.kickoff_utc).limit(3)).all()
        factor = stats.get("cards_factor", 1.0)
        verdict = ("muy tarjetero" if factor >= 1.15 else "tarjetero" if factor >= 1.05 else
                   "permisivo" if factor <= 0.9 else "normal")
        return {"referee": best[1], **stats, "profile": verdict,
                "upcoming": [f"{x.home_team.name} vs {x.away_team.name}" for x in upcoming_matches]}


def player_projection(player: str, match_ref: str | int | None = None) -> dict:
    bundle = load_bundle()
    with session_scope() as s:
        p = find_player(s, player)
        info = bundle.players.get(p.id, {})
        out = {"player": p.name, "position": p.position, "team": p.current_team_id and s.get(m.Team, p.current_team_id).name,
               "market_value_m": round((p.market_value_eur or 0) / 1e6, 1), "season_rating": p.season_rating,
               "per90": info.get("per90"), "minutes90": info.get("minutes90"), "starts": info.get("starts")}
        if match_ref is None and p.current_team_id:
            try:
                match_ref = find_match(s, s.get(m.Team, p.current_team_id).name).id
            except NotFound:
                match_ref = None
        if match_ref is not None:
            match = find_match(s, match_ref)
            an = analysis.analyze(s, bundle, match)
            pp = an.model.players.get(p.id)
            out["next_match"] = f"{match.home_team.name} vs {match.away_team.name}"
            if pp:
                mm = an.model
                out["projection"] = {
                    **pp.to_dict(),
                    "p_shots_over_0_5": round(mm.outcome("player_shots", "over", 0.5, p.id).effective_prob(), 3),
                    "p_shots_over_1_5": round(mm.outcome("player_shots", "over", 1.5, p.id).effective_prob(), 3),
                    "p_shots_over_2_5": round(mm.outcome("player_shots", "over", 2.5, p.id).effective_prob(), 3),
                    "p_sot_over_0_5": round(mm.outcome("player_sot", "over", 0.5, p.id).effective_prob(), 3),
                    "p_sot_over_1_5": round(mm.outcome("player_sot", "over", 1.5, p.id).effective_prob(), 3),
                    "p_goal": round(mm.outcome("player_goal", "yes", None, p.id).effective_prob(), 3),
                    "p_assist": round(mm.outcome("player_assist", "yes", None, p.id).effective_prob(), 3),
                    "p_goal_assist": round(mm.outcome("player_goal_assist", "yes", None, p.id).effective_prob(), 3),
                    "p_card": round(mm.outcome("player_card", "yes", None, p.id).effective_prob(), 3),
                }
            else:
                out["projection"] = None
                out["note"] = "No figura en la alineación (o está de baja)"
        return out


def register_bet(username: str, match_ref: str | int, market: str, selection: str, odds: float, stake: float,
                 line: float | None = None, bookmaker: str = "betano", player: str | None = None,
                 notes: str | None = None) -> dict:
    bundle = load_bundle()
    with session_scope() as s:
        user = tracker.get_or_create_user(s, username)
        match = find_match(s, match_ref)
        player_id = find_player(s, player).id if player else None
        prob = None
        try:
            _, ev = analysis.evaluate_user_odds(s, bundle, match, market, selection, line, odds, bookmaker, player_id)
            prob = ev.prob
        except ValueError:
            ev = None
        bet = tracker.register_bet(s, user, match, bookmaker, market, selection, line, odds, stake, player_id,
                                   prob, notes=notes)
        status = tracker.bankroll_status(s, user)
        return {"bet_id": bet.id, "match": f"{match.home_team.name} vs {match.away_team.name}",
                "market": market, "selection": selection, "line": line, "odds": odds, "stake": stake,
                "model_prob": round(prob, 3) if prob else None, "ev": round(ev.ev, 3) if ev else None,
                "bankroll": status}


def match_lineups(match_ref: str | int) -> dict:
    """Alineaciones de un partido como las muestra FotMob: probables hasta que se confirman, con formación,
    dorsales y posición en el campo, más suplentes (solo confirmadas) y bajas de cada equipo."""
    tz = get_settings().tz
    with session_scope() as s:
        match = find_match(s, match_ref)
        rows = s.execute(select(m.Lineup, m.Player).join(m.Player, m.Player.id == m.Lineup.player_id)
                         .where(m.Lineup.match_id == match.id)).all()
        info = match.lineup_info or {}
        teams = []
        for side, team in (("home", match.home_team), ("away", match.away_team)):
            mine = [(lu, p) for lu, p in rows if lu.team_id == team.id]

            def player(lu: m.Lineup, p: m.Player) -> dict:
                return {"player_id": p.id, "name": p.name, "shirt": lu.shirt_number, "position": lu.position,
                        "x": lu.pos_x, "y": lu.pos_y, "rating": lu.season_rating}

            starters = sorted((player(lu, p) for lu, p in mine if lu.is_starter),
                              key=lambda d: (d["y"] if d["y"] is not None else 9, d["x"] or 0))
            subs = [player(lu, p) for lu, p in mine if not lu.is_starter]
            out_rows = s.scalars(select(m.Availability).where(
                m.Availability.team_id == team.id, m.Availability.active.is_(True))).all()
            teams.append({
                "side": side, "team_id": team.id, "team": team.name,
                "formation": (info.get(str(team.id)) or {}).get("formation"),
                "coach": (info.get(str(team.id)) or {}).get("coach"),
                "starters": starters, "subs": subs,
                "unavailable": [{"name": a.player.name, "kind": a.kind, "reason": a.reason,
                                 "expected_return": a.expected_return, "source": a.source} for a in out_rows],
            })
        fetched = match.details_fetched_at
        return {
            "match_id": match.id, "match": f"{match.home_team.name} vs {match.away_team.name}",
            "kickoff_local": match.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
            "status": match.lineup_status if rows else None,
            "updated_local": fetched.astimezone(tz).strftime("%Y-%m-%d %H:%M") if fetched else None,
            "teams": teams,
        }


def match_book_odds(match_ref: str | int, bookmaker: str = "betano") -> dict:
    """Las últimas cuotas guardadas de una casa para un partido, ya evaluadas por el modelo (sin captura)."""
    bundle = load_bundle()
    tz = get_settings().tz
    with session_scope() as s:
        match = find_match(s, match_ref)
        rows = [r for r in analysis._latest_odds(s, match.id) if r.bookmaker == bookmaker]
        home, away = match.home_team.name, match.away_team.name
        out = []
        if rows:
            _, evs = analysis.evaluate_user_odds_many(
                s, bundle, match, [(r.market, r.selection, r.line, r.price, bookmaker, None) for r in rows])
            out = [{**verdict_fields(ev), "label": ev.label(home, away)} for ev in evs if not isinstance(ev, Exception)]
        captured = max((r.captured_at for r in rows), default=None)
        return {"match_id": match.id, "match": f"{home} vs {away}", "bookmaker": bookmaker,
                "captured_local": captured.astimezone(tz).strftime("%Y-%m-%d %H:%M") if captured else None,
                "odds": out}


TEAM_LOGO_URL = "https://images.fotmob.com/image_resources/logo/teamlogo/{}.png"
LOGO_TTL = 30 * 86400  # los escudos casi no cambian


def team_logo(team_id: int) -> bytes:
    """Escudo del equipo (PNG de FotMob), descargado una vez con el cliente educado y guardado en la caché."""
    from apuestas.ingest.http import client

    with session_scope() as s:
        fid = s.scalar(select(m.EntityAlias.source_key).where(
            m.EntityAlias.entity_type == "team", m.EntityAlias.source == "fotmob",
            m.EntityAlias.entity_id == team_id).limit(1))
    if not fid or not str(fid).isdigit():
        raise NotFound(f"Sin escudo para el equipo {team_id}")
    return client().get_bytes(TEAM_LOGO_URL.format(fid), ttl=LOGO_TTL)


def warm_team_logos(days: int = 10) -> int:
    """Descarga de antemano los escudos de los equipos con partido en los próximos días (los ya guardados no
    vuelven a pedirse), para que el panel no espere al abrirlo."""
    now = datetime.now(UTC)
    with session_scope() as s:
        rows = s.execute(select(m.Match.home_team_id, m.Match.away_team_id).where(
            m.Match.kickoff_utc >= now - timedelta(days=1), m.Match.kickoff_utc <= now + timedelta(days=days))).all()
    done = 0
    for team_id in sorted({t for row in rows for t in row}):
        try:
            team_logo(team_id)
            done += 1
        except (NotFound, FileNotFoundError, RuntimeError):
            continue
    return done


MAX_SLIP_LEGS = 20


def _slip_blocks(blocks: list[dict]) -> list:
    """Cupón del panel → bloques de combinada (un bloque por partido, con sus selecciones)."""
    from apuestas.services.captures import ComboBlock, ComboLeg

    out = []
    for b in blocks:
        legs = [ComboLeg(mercado=lg["market"], seleccion=lg["selection"], linea=lg.get("line"),
                         jugador=lg.get("player"), cuota=lg.get("odds")) for lg in b.get("legs", [])]
        if legs:
            out.append(ComboBlock(partido=str(b["match"]), selecciones=legs, cuota=b.get("odds")))
    if not out:
        raise ValueError("El cupón está vacío.")
    if sum(len(b.selecciones) for b in out) > MAX_SLIP_LEGS:
        raise ValueError(f"Como máximo {MAX_SLIP_LEGS} selecciones por cupón.")
    return out


def evaluate_slip(blocks: list[dict], total_odds: float | None = None) -> dict:
    """Probabilidad de un cupón armado en el panel: Bet Builders por partido y combinada entre partidos."""
    from apuestas.services.captures import combo_summary, evaluate_blocks

    bundle = load_bundle()
    with session_scope() as s:
        out, _ = evaluate_blocks(s, bundle, _slip_blocks(blocks))
    return {**combo_summary(out, total_odds), "blocks": out}


def register_combo(username: str, blocks: list[dict], total_odds: float, stake: float, bookmaker: str = "betano",
                   notes: str | None = None) -> dict:
    """Registra un cupón como una sola apuesta (market "combo") con sus selecciones; se liquida sola."""
    from apuestas.services.captures import combo_summary, evaluate_blocks

    if not total_odds or total_odds <= 1:
        raise ValueError("Falta la cuota total del cupón (mayor que 1).")
    if not stake or stake <= 0:
        raise ValueError("El importe debe ser mayor que 0.")
    slip = _slip_blocks(blocks)
    if sum(len(b.selecciones) for b in slip) < 2:
        raise ValueError("Un cupón necesita al menos 2 selecciones; para una sola, registra la apuesta normal.")
    bundle = load_bundle()
    with session_scope() as s:
        out, _ = evaluate_blocks(s, bundle, slip)
        unknown = [b["partido"] for b in out if b["match_id"] is None]
        if unknown:
            raise NotFound(f"No se encontró el partido: {', '.join(unknown)}")
        missing_player = [lg["player"] for b in out for lg in b["legs"]
                          if lg["market"].startswith("player_") and lg["player_id"] is None]
        if missing_player:
            raise NotFound(f"No se encontró el jugador: {', '.join(p or '¿?' for p in missing_player)}")
        summary = combo_summary(out, total_odds)
        user = tracker.get_or_create_user(s, username)
        matches = {mt.id: mt for mt in s.scalars(select(m.Match).where(m.Match.id.in_([b["match_id"] for b in out])))}
        last = max(matches.values(), key=lambda mt: mt.kickoff_utc)  # se liquida cuando termina el último
        n_legs = sum(len(b["legs"]) for b in out)
        bet = tracker.register_bet(s, user, last, bookmaker, "combo", f"{n_legs} selecciones", None, total_odds, stake,
                                   model_prob=summary["prob"], notes=notes)
        pos = 0
        for b in out:
            for lg in b["legs"]:
                bet.legs.append(m.UserBetLeg(position=pos, match_id=b["match_id"], market=lg["market"],
                                             selection=lg["selection"], line=lg["line"], player_id=lg["player_id"],
                                             odds=lg["odds"], block_odds=b["odds"] if len(b["legs"]) > 1 else None,
                                             model_prob=lg["prob"]))
                pos += 1
        s.flush()
        return {"bet_id": bet.id, "match": f"Combinada de {n_legs} selecciones", "market": "combo",
                "selection": bet.selection, "line": None, "odds": total_odds, "stake": stake,
                "model_prob": summary["prob"], "ev": summary["ev"], "bankroll": tracker.bankroll_status(s, user)}


def _bet_dict(b: m.UserBet) -> dict:
    out = {"bet_id": b.id, "match": f"{b.match.home_team.name} vs {b.match.away_team.name}",
           "market": b.market, "selection": b.selection, "line": b.line, "odds": b.odds, "stake": b.stake,
           "bookmaker": b.bookmaker, "result": b.result, "profit": b.profit, "clv": b.clv}
    if b.market == "combo":
        out["match"] = f"Combinada de {len(b.legs)} selecciones"
        out["legs"] = [{"match": f"{lg.match.home_team.name} vs {lg.match.away_team.name}", "match_id": lg.match_id,
                        "market": lg.market, "selection": lg.selection, "line": lg.line, "odds": lg.odds,
                        "block_odds": lg.block_odds, "player": lg.player.name if lg.player else None,
                        "result": lg.result} for lg in b.legs]
    return out


def my_bets(username: str, pending_only: bool = False, limit: int = 30) -> list[dict]:
    with session_scope() as s:
        user = tracker.get_or_create_user(s, username)
        q = select(m.UserBet).where(m.UserBet.user_id == user.id)
        if pending_only:
            q = q.where(m.UserBet.result.is_(None))
        rows = s.scalars(q.order_by(m.UserBet.placed_at.desc()).limit(limit)).all()
        return [_bet_dict(b) for b in rows]


def performance(username: str, days: int | None = None) -> dict:
    with session_scope() as s:
        return tracker.performance(s, tracker.get_or_create_user(s, username), days)


CURRENCIES = ("PEN", "USD", "EUR")


def set_bankroll(username: str, bankroll: float, currency: str = "PEN") -> dict:
    """Fija la banca inicial: base del stake sugerido y de los límites de pérdida."""
    currency = currency.upper()
    if not bankroll > 0:
        raise ValueError("La banca debe ser mayor que 0.")
    if currency not in CURRENCIES:
        raise ValueError(f"Moneda no admitida: {currency}. Usa {', '.join(CURRENCIES)}.")
    with session_scope() as s:
        user = tracker.get_or_create_user(s, username)
        user.bankroll, user.currency = bankroll, currency
        return tracker.bankroll_status(s, user)


def failure_reason(error: str | None) -> str | None:
    """Motivo de un fallo de ingesta en una línea, sin el traceback."""
    if not error:
        return None
    first = error.strip().splitlines()[0]
    if "no se pudo resolver" in first or "name resolution" in first:
        return "Sin conexión a internet en este equipo"
    if "no responde" in first or "timed out" in first or "No se pudo descargar" in first:
        return "El sitio no responde"
    return first[:160]


def data_status() -> dict:
    with session_scope() as s:
        last = {}
        for src, task, fin, status, error in s.execute(
                select(m.IngestionRun.source, m.IngestionRun.task, m.IngestionRun.finished_at, m.IngestionRun.status,
                       m.IngestionRun.error)
                .order_by(m.IngestionRun.id.desc()).limit(200)):
            last.setdefault(src, {"task": task, "finished_at": fin.isoformat() if fin else None, "status": status,
                                  "reason": failure_reason(error) if status == "error" else None})
        # Cuándo dio datos por última vez cada fuente (para ver desde cuándo falla)
        for src, fin in s.execute(select(m.IngestionRun.source, func.max(m.IngestionRun.finished_at))
                                  .where(m.IngestionRun.status == "ok").group_by(m.IngestionRun.source)):
            if src in last:
                last[src]["last_ok"] = fin.isoformat() if fin else None
        counts = {
            "matches": s.scalar(select(func.count(m.Match.id))),
            "matches_with_details": s.scalar(select(func.count(m.Match.id)).where(m.Match.details_fetched_at.is_not(None))),
            "players": s.scalar(select(func.count(m.Player.id))),
            "active_absences": s.scalar(select(func.count(m.Availability.id)).where(m.Availability.active.is_(True))),
            "odds_rows": s.scalar(select(func.count(m.OddsSnapshot.id))),
        }
    try:
        model_as_of = load_bundle().as_of.isoformat()
    except FileNotFoundError:
        model_as_of = None
    return {"sources": last, "counts": counts, "model_as_of": model_as_of}
