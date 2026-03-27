# -*- coding: utf-8 -*-
"""Twitch EventSub notification DB models."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from utils import database as db

# EventSub event types
STREAM_ONLINE = "stream.online"
STREAM_OFFLINE = "stream.offline"

# EventSub subscription statuses
SUB_STATUS_PENDING = "pending"
SUB_STATUS_ENABLED = "enabled"
SUB_STATUS_REVOKED = "revoked"
SUB_STATUS_FAILED = "failed"


class TwitchNotifications(db.BASE):
    """Per-guild streamer notification config."""

    __tablename__ = "TwitchNotifications"
    __table_args__ = (
        UniqueConstraint("GuildId", "ChannelId", "Streamer", name="uq_twitch_guild_channel_streamer"),
        Index("TwitchNotifications_GuildId", "GuildId"),
        Index("TwitchNotifications_Streamer", "Streamer"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=False)
    ChannelId = Column(BigInteger, nullable=False)
    Streamer = Column(String(25), nullable=False)
    StreamerDisplayName = Column(String(25), nullable=False)
    Message = Column(Text, nullable=True)
    NotifyOffline = Column(Boolean, default=False, server_default="0", nullable=False)

    @classmethod
    def get_by_id(cls, notification_id: int, guild_id: int, session):
        return session.query(cls).filter(cls.Id == notification_id, cls.GuildId == guild_id).first()

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get_all_by_streamer(cls, streamer: str, session):
        return session.query(cls).filter(cls.Streamer == streamer).all()

    @classmethod
    def get_by_channel_and_streamer(cls, guild_id: int, channel_id: int, streamer: str, session):
        return (
            session.query(cls)
            .filter(cls.GuildId == guild_id, cls.ChannelId == channel_id, cls.Streamer == streamer)
            .first()
        )

    @classmethod
    def get_all_distinct_streamers(cls, session) -> list[str]:
        rows = session.query(cls.Streamer).distinct().all()
        return [r[0] for r in rows]


class TwitchEventSubSubscription(db.BASE):
    """Tracks active Twitch-side EventSub subscriptions (shared across guilds)."""

    __tablename__ = "TwitchEventSubSubscription"
    __table_args__ = (UniqueConstraint("StreamerLogin", "EventType", name="uq_twitch_eventsub_streamer_type"),)

    Id = Column(Integer, primary_key=True)
    TwitchSubscriptionId = Column(String(64), unique=True, nullable=False)
    StreamerLogin = Column(String(25), nullable=False)
    StreamerUserId = Column(String(20), nullable=False)
    EventType = Column(String(30), nullable=False)
    Status = Column(String(20), nullable=False, default=SUB_STATUS_PENDING, server_default=SUB_STATUS_PENDING)
    CreatedAt = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @classmethod
    def get_by_streamer_and_type(cls, streamer_login: str, event_type: str, session):
        return session.query(cls).filter(cls.StreamerLogin == streamer_login, cls.EventType == event_type).first()

    @classmethod
    def get_by_twitch_id(cls, twitch_subscription_id: str, session):
        return session.query(cls).filter(cls.TwitchSubscriptionId == twitch_subscription_id).first()

    @classmethod
    def get_all_enabled(cls, session):
        return session.query(cls).filter(cls.Status == SUB_STATUS_ENABLED).all()

    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()
