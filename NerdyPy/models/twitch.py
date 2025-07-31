# -*- coding: utf-8 -*-
""" Twitch Modul """

from sqlalchemy import Integer, BigInteger, Column, Index, Text, String

from utils import database as db


class TwitchNotifications(db.BASE):
    """database entity model for TwitchNotifications"""

    __tablename__ = "TwitchNotifications"
    __table_args__ = (
        Index("TwitchNotifications_GuildId", "GuildId"),
        Index("TwitchNotifications_GuildId_ChannelId_Streamer", "GuildId", "ChannelId", "Streamer", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    Streamer = Column(String(30))
    Message = Column(Text)

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        """returns a configuration for a given guild | session needed!"""
        return session.query(TwitchNotifications).filter(TwitchNotifications.GuildId == guild_id).all()

    @classmethod
    def get_by_id(cls, guild_id: int, config_id: int, session):
        """returns a configuration for a given guild | session needed!"""
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.Id == config_id)
            .first()
        )

    @classmethod
    def get_all_by_streamer(cls, guild_id: int, streamer: str, session):
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.Streamer == streamer)
            .all()
        )

    @classmethod
    def get_all_by_channel(cls, guild_id: int, channel_id: int, session):
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.ChannelId == channel_id)
            .all()
        )

    @classmethod
    def get_by_channel_and_streamer(cls, guild_id: int, channel_id: int, streamer: str, session):
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.ChannelId == channel_id)
            .filter(TwitchNotifications.Streamer == streamer)
            .all()
        )
