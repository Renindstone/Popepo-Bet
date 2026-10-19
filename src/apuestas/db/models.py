"""Esquema de la base de datos.

Convenciones:
- Fechas/horas siempre en UTC (timestamptz).
- Cada entidad tiene un id interno; los ids de cada fuente viven en `EntityAlias`.
- Las estadísticas de conteo se guardan por fuente en `StatObservation` y el valor
  reconciliado en `TeamMatchStats` (con marca si las fuentes discrepan).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------- catálogo


class Competition(Base):
    __tablename__ = "competition"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(40))
    tier: Mapped[str] = mapped_column(String(8))  # full | light
    is_cup: Mapped[bool] = mapped_column(Boolean, default=False)


class Season(Base):
    __tablename__ = "season"
    __table_args__ = (UniqueConstraint("competition_id", "start_year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competition.id"))
    start_year: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(10))
    # Nivel de almacenamiento: hot (actual) | warm (2-3 anteriores) | cold (exportada a Parquet)
    storage_tier: Mapped[str] = mapped_column(String(8), default="hot")
    competition: Mapped[Competition] = relationship()


class Team(Base, TimestampMixin):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(40))


class Player(Base, TimestampMixin):
    __tablename__ = "player"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str | None] = mapped_column(String(4))  # GK | DF | MF | FW
    birth_date: Mapped[date | None] = mapped_column(Date)
    country: Mapped[str | None] = mapped_column(String(40))
    current_team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), index=True)
    market_value_eur: Mapped[float | None] = mapped_column(Float)
    season_rating: Mapped[float | None] = mapped_column(Float)  # rating FotMob de la temporada


class Referee(Base, TimestampMixin):
    __tablename__ = "referee"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    country: Mapped[str | None] = mapped_column(String(40))


class EntityAlias(Base):
    """Relaciona el id/nombre que usa cada fuente con nuestra entidad interna."""

    __tablename__ = "entity_alias"
    __table_args__ = (UniqueConstraint("entity_type", "source", "source_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(10))  # team | player | referee | match
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(16))  # fotmob | understat | fdco | espn | oddspapi
    source_key: Mapped[str] = mapped_column(String(160))  # id de la fuente o nombre normalizado
    source_name: Mapped[str | None] = mapped_column(String(160))


# --------------------------------------------------------------------------- partidos


class Match(Base, TimestampMixin):
    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint("competition_id", "kickoff_utc", "home_team_id", "away_team_id"),
        Index("ix_match_kickoff", "kickoff_utc"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competition.id"), index=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), index=True)
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    round: Mapped[str | None] = mapped_column(String(40))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="scheduled")  # scheduled|finished|postponed|cancelled
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    home_goals_ht: Mapped[int | None] = mapped_column(Integer)
    away_goals_ht: Mapped[int | None] = mapped_column(Integer)
    referee_id: Mapped[int | None] = mapped_column(ForeignKey("referee.id"), index=True)
    neutral_venue: Mapped[bool] = mapped_column(Boolean, default=False)
    fotmob_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    understat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    espn_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    details_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lineup_status: Mapped[str | None] = mapped_column(String(10))  # predicted | confirmed

    competition: Mapped[Competition] = relationship()
    season: Mapped[Season] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    referee: Mapped[Referee | None] = relationship()


class TeamMatchStats(Base):
    """Estadísticas reconciliadas de un equipo en un partido."""

    __tablename__ = "team_match_stats"
    __table_args__ = (UniqueConstraint("match_id", "team_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    is_home: Mapped[bool] = mapped_column(Boolean)
    goals: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)  # promedio de los modelos de xG disponibles
    xg_sources: Mapped[dict | None] = mapped_column(JSONType)  # {"fotmob": 1.2, "understat": 1.1}
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    corners: Mapped[int | None] = mapped_column(Integer)
    fouls: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    offsides: Mapped[int | None] = mapped_column(Integer)
    possession: Mapped[float | None] = mapped_column(Float)
    saves: Mapped[int | None] = mapped_column(Integer)
    big_chances: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONType)
    discrepancies: Mapped[dict | None] = mapped_column(JSONType)  # {"corners": {"fotmob": 8, "fdco": 7}}


class StatObservation(Base):
    """Valor crudo de una estadística según cada fuente (para validar entre fuentes)."""

    __tablename__ = "stat_observation"
    __table_args__ = (UniqueConstraint("match_id", "team_id", "stat", "source"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    stat: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    value: Mapped[float | None] = mapped_column(Float)


class Lineup(Base):
    __tablename__ = "lineup"
    __table_args__ = (UniqueConstraint("match_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    status: Mapped[str] = mapped_column(String(10))  # predicted | confirmed
    is_starter: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[str | None] = mapped_column(String(4))
    market_value_eur: Mapped[float | None] = mapped_column(Float)
    season_rating: Mapped[float | None] = mapped_column(Float)


class PlayerMatchStats(Base):
    __tablename__ = "player_match_stats"
    __table_args__ = (UniqueConstraint("match_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    is_starter: Mapped[bool | None] = mapped_column(Boolean)
    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    xa: Mapped[float | None] = mapped_column(Float)
    key_passes: Mapped[int | None] = mapped_column(Integer)
    fouls_committed: Mapped[int | None] = mapped_column(Integer)
    fouls_won: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    tackles: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict | None] = mapped_column(JSONType)


class Availability(Base, TimestampMixin):
    """Bajas: lesiones, sanciones o dudas. `active` = sigue vigente."""

    __tablename__ = "availability"
    __table_args__ = (Index("ix_availability_active", "team_id", "active"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    kind: Mapped[str] = mapped_column(String(12))  # injury | suspension | doubtful | other
    reason: Mapped[str | None] = mapped_column(String(160))
    expected_return: Mapped[str | None] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(16))  # fotmob | manual | derived
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    player: Mapped[Player] = relationship()


class Transfer(Base):
    __tablename__ = "transfer"
    __table_args__ = (UniqueConstraint("player_id", "to_team_id", "detected_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    from_team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"))
    to_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    detected_on: Mapped[date] = mapped_column(Date)
    market_value_eur: Mapped[float | None] = mapped_column(Float)


# --------------------------------------------------------------------------- cuotas


class OddsSnapshot(Base):
    """Una cuota de una casa para una selección. Solo se guarda una fila nueva cuando el precio cambia."""

    __tablename__ = "odds_snapshot"
    __table_args__ = (Index("ix_odds_lookup", "match_id", "bookmaker", "market", "selection", "line"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"))
    bookmaker: Mapped[str] = mapped_column(String(24))  # bet365 | betano | betfair_ex | pinnacle | avg | max
    market: Mapped[str] = mapped_column(String(24))  # 1x2 | ou_goals | ah | btts ...
    selection: Mapped[str] = mapped_column(String(24))  # home | draw | away | over | under | yes | no
    line: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(8), default="live")  # live | opening | closing
    source: Mapped[str] = mapped_column(String(16))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- modelo y picks


class TeamRating(Base):
    __tablename__ = "team_rating"
    __table_args__ = (UniqueConstraint("team_id", "model", "as_of"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    model: Mapped[str] = mapped_column(String(24))  # goals_dc | elo | shots | corners | cards ...
    as_of: Mapped[date] = mapped_column(Date)
    attack: Mapped[float | None] = mapped_column(Float)
    defence: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    params: Mapped[dict | None] = mapped_column(JSONType)


class Prediction(Base):
    __tablename__ = "prediction"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(14))  # pre_lineup | confirmed
    model_version: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload: Mapped[dict] = mapped_column(JSONType)


class Pick(Base):
    """Apuesta con valor detectada por el sistema (incluye la apuesta del día)."""

    __tablename__ = "pick"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pick_date: Mapped[date] = mapped_column(Date, index=True)  # fecha local (Lima)
    stage: Mapped[str] = mapped_column(String(14))
    market: Mapped[str] = mapped_column(String(24))
    selection: Mapped[str] = mapped_column(String(24))
    line: Mapped[float | None] = mapped_column(Float)
    bookmaker: Mapped[str] = mapped_column(String(24))
    odds: Mapped[float] = mapped_column(Float)
    model_prob: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    ev: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    stake_pct: Mapped[float] = mapped_column(Float)
    is_pick_of_day: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | withdrawn | settled
    result: Mapped[str | None] = mapped_column(String(10))  # win | loss | push | half_win | half_loss | void
    closing_odds: Mapped[float | None] = mapped_column(Float)
    clv: Mapped[float | None] = mapped_column(Float)
    reasons: Mapped[list | None] = mapped_column(JSONType)
    match: Mapped[Match] = relationship()


# --------------------------------------------------------------------------- usuarios y apuestas reales


class User(Base, TimestampMixin):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40))
    bankroll: Mapped[float] = mapped_column(Float, default=1000.0)
    currency: Mapped[str] = mapped_column(String(4), default="PEN")
    kelly_fraction: Mapped[float | None] = mapped_column(Float)
    max_stake_pct: Mapped[float | None] = mapped_column(Float)


class UserBet(Base, TimestampMixin):
    __tablename__ = "user_bet"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), index=True)
    pick_id: Mapped[int | None] = mapped_column(ForeignKey("pick.id"))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    bookmaker: Mapped[str] = mapped_column(String(24))
    market: Mapped[str] = mapped_column(String(24))
    selection: Mapped[str] = mapped_column(String(40))
    line: Mapped[float | None] = mapped_column(Float)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("player.id"))
    odds: Mapped[float] = mapped_column(Float)
    stake: Mapped[float] = mapped_column(Float)
    model_prob: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str | None] = mapped_column(String(10))
    profit: Mapped[float | None] = mapped_column(Float)
    closing_odds: Mapped[float | None] = mapped_column(Float)
    clv: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    match: Mapped[Match] = relationship()


# --------------------------------------------------------------------------- resúmenes y operación


class SeasonSummary(Base):
    """Resumen de temporada por equipo o jugador: sirve de punto de partida para la siguiente."""

    __tablename__ = "season_summary"
    __table_args__ = (UniqueConstraint("season_id", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(8))  # team | player | referee
    entity_id: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSONType)


class IngestionRun(Base):
    __tablename__ = "ingestion_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(24), index=True)
    task: Mapped[str] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="running")  # running | ok | error
    rows: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
