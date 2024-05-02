# -*- coding: utf-8 -*-
""" Twitch Modul """

from sqlalchemy import Integer, BigInteger, Column, Index, Text, String

from utils import database as db


class TwitchNotifications(db.BASE):
    """database entity model for TwitchNotifications"""

    __tablename__ = "TwitchNotifications"
    __table_args__ = (Index("TwitchNotifications_GuildId", "GuildId", unique=True),)

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    StreamerId = Column(String(30))
    Message = Column(Text)

    @classmethod
    def get_all(cls, session):
        """returns configurations for all guilds | session needed!"""
        return session.query(TwitchNotifications).all()

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        """returns a configuration for a given guild | session needed!"""
        return session.query(TwitchNotifications).filter(TwitchNotifications.GuildId == guild_id).all()

    @classmethod
    def get_all_by_streamer(cls, guild_id: int, streamer_id: str, session):
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.StreamerId == streamer_id)
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
    def get_by_channel_and_streamer(cls, guild_id: int, channel_id: int, streamer_id: str, session):
        return (
            session.query(TwitchNotifications)
            .filter(TwitchNotifications.GuildId == guild_id)
            .filter(TwitchNotifications.ChannelId == channel_id)
            .filter(TwitchNotifications.StreamerId == streamer_id)
            .all()
        )

    @classmethod
    def delete(cls, guild_id: int, channel_id: int, session):
        """deletes a channel with given guild"""
        session.delete(TwitchNotifications.get_by_channel(guild_id, channel_id, session))
