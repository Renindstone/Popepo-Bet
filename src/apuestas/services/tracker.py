"""Usuarios, registro de apuestas reales, rendimiento y gestión de banca."""

from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apuestas.config import get_settings
from apuestas.db import models as m


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def get_or_create_user(s: Session, username: str) -> m.User:
    user = s.scalar(select(m.User).where(m.User.username == username))
    if user is None:
        user = m.User(username=username)
        s.add(user)
        s.flush()
    return user


def create_api_key(s: Session, username: str) -> str:
    """Genera una clave nueva (solo se muestra una vez) para que un usuario conecte su agente."""
    user = get_or_create_user(s, username)
    raw = "apk_" + secrets.token_urlsafe(32)
    user.api_key_hash = hash_key(raw)
    return raw


def user_by_key(s: Session, raw: str) -> m.User | None:
    return s.scalar(select(m.User).where(m.User.api_key_hash == hash_key(raw)))


def bankroll_status(s: Session, user: m.User) -> dict:
    """Pérdidas del día/semana frente a los límites configurados."""
    st = get_settings()
    now = datetime.now(UTC)
    tz = st.tz
    day_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    week_start = day_start - timedelta(days=datetime.now(tz).weekday())
    settled = list(s.scalars(select(m.UserBet).where(m.UserBet.user_id == user.id, m.UserBet.profit.is_not(None),
                                                    m.UserBet.placed_at >= week_start)))
    pending = list(s.scalars(select(m.UserBet).where(m.UserBet.user_id == user.id, m.UserBet.result.is_(None))))
    total_pl = s.scalar(select(func.coalesce(func.sum(m.UserBet.profit), 0.0)).where(
        m.UserBet.user_id == user.id, m.UserBet.profit.is_not(None)))
    day_pl = sum(b.profit for b in settled if b.placed_at >= day_start)
    week_pl = sum(b.profit for b in settled)
    day_limit = -st.daily_loss_limit_pct * user.bankroll
    week_limit = -st.weekly_loss_limit_pct * user.bankroll
    warnings = []
    if day_pl <= day_limit:
        warnings.append(f"Llegaste al límite de pérdida diario ({day_pl:.2f} {user.currency}). Para por hoy.")
    if week_pl <= week_limit:
        warnings.append(f"Llegaste al límite de pérdida semanal ({week_pl:.2f} {user.currency}).")
    return {
        # `bankroll` es la banca inicial que declara el usuario; `current` le suma lo ganado o perdido desde entonces
        "bankroll": user.bankroll, "currency": user.currency,
        "current": round(user.bankroll + total_pl, 2), "total_profit": round(total_pl, 2),
        "day_profit": round(day_pl, 2),
        "week_profit": round(week_pl, 2), "pending_bets": len(pending),
        "pending_stake": round(sum(b.stake for b in pending), 2),
        "daily_loss_limit": round(day_limit, 2), "weekly_loss_limit": round(week_limit, 2),
        "warnings": warnings, "as_of": now.isoformat(),
    }


def register_bet(s: Session, user: m.User, match: m.Match, bookmaker: str, market: str, selection: str,
                 line: float | None, odds: float, stake: float, player_id: int | None = None,
                 model_prob: float | None = None, pick_id: int | None = None, notes: str | None = None) -> m.UserBet:
    bet = m.UserBet(user_id=user.id, match_id=match.id, bookmaker=bookmaker, market=market, selection=selection,
                    line=line, odds=odds, stake=stake, player_id=player_id, model_prob=model_prob, pick_id=pick_id,
                    notes=notes)
    s.add(bet)
    s.flush()
    return bet


def _odds_band(o: float) -> str:
    for lo, hi in ((1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.5), (3.5, 1000)):
        if lo <= o < hi:
            return f"{lo:g}-{hi:g}" if hi < 1000 else f"{lo:g}+"
    return "?"


def performance(s: Session, user: m.User, days: int | None = None) -> dict:
    q = select(m.UserBet).where(m.UserBet.user_id == user.id, m.UserBet.profit.is_not(None))
    if days:
        q = q.where(m.UserBet.placed_at >= datetime.now(UTC) - timedelta(days=days))
    bets = list(s.scalars(q))

    def agg(items: list[m.UserBet]) -> dict:
        staked = sum(b.stake for b in items)
        pl = sum(b.profit for b in items)
        wins = sum(1 for b in items if b.result in ("win", "half_win"))
        clvs = [b.clv for b in items if b.clv is not None]
        return {"bets": len(items), "staked": round(staked, 2), "profit": round(pl, 2),
                "roi": round(pl / staked, 4) if staked else None,
                "hit_rate": round(wins / len(items), 3) if items else None,
                "avg_odds": round(sum(b.odds for b in items) / len(items), 2) if items else None,
                "avg_clv": round(sum(clvs) / len(clvs), 4) if clvs else None}

    groups: dict[str, dict[str, list]] = {k: defaultdict(list) for k in ("market", "competition", "bookmaker", "odds_band")}
    for b in bets:
        groups["market"][b.market].append(b)
        groups["competition"][b.match.competition.code].append(b)
        groups["bookmaker"][b.bookmaker].append(b)
        groups["odds_band"][_odds_band(b.odds)].append(b)
    return {"total": agg(bets), **{k: {kk: agg(vv) for kk, vv in g.items()} for k, g in groups.items()},
            "bankroll": bankroll_status(s, user)}
