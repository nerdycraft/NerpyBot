# -*- coding: utf-8 -*-
""" Twitch Messages """

from sqlalchemy import Integer, BigInteger, Column, Index, Text

from utils import database as db


class Twitch(db.BASE):
    """database entity model for Twitch"""

    __tablename__ = "Twitch"
    __table_args__ = (
        Index("Twitch_GuildId", "GuildId"),
        Index("Twitch_GuildId_ChannelId", "GuildId", "ChannelId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    StreamerId = Column(BigInteger)
    Message = Column(Text)

    @classmethod
    def get_all(cls, session):
        """returns configurations for all guilds | session needed!"""
        return session.query(Twitch).all()

    @classmethod
    def get_by_guild(cls, guild_id: int, session):
        """returns a configuration for a given guild | session needed!"""
        return session.query(Twitch).filter(Twitch.GuildId == guild_id).all()

    @classmethod
    def get_by_channel(cls, guild_id: int, channel_id: int, session):
        return session.query(Twitch).filter(Twitch.GuildId == guild_id).filter(Twitch.ChannelId == channel_id).first()

    @classmethod
    def delete(cls, guild_id: int, channel_id: int, session):
        """deletes a channel with given guild"""
        session.delete(Twitch.get_by_channel(guild_id, channel_id, session))
