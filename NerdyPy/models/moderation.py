# -*- coding: utf-8 -*-
""" AutoDelete Messages """

from sqlalchemy import Integer, BigInteger, Column, Index, Boolean, Text

from utils import database as db


class AutoDelete(db.BASE):
    """database entity model for AutoDelete"""

    __tablename__ = "AutoDelete"
    __table_args__ = (
        Index("AutoDelete_GuildId", "GuildId"),
        Index("AutoDelete_GuildId_ChannelId", "GuildId", "ChannelId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    KeepMessages = Column(BigInteger, default=0)
    DeleteOlderThan = Column(BigInteger)
    DeletePinnedMessage = Column(Boolean, default=False)

    @classmethod
    def get_all(cls, session):
        """returns configurations for all guilds | session needed!"""
        return session.query(AutoDelete).all()

    @classmethod
    def get_by_guild(cls, guild_id: int, session):
        """returns a configuration for a given guild | session needed!"""
        return session.query(AutoDelete).filter(AutoDelete.GuildId == guild_id).all()

    @classmethod
    def get_by_channel(cls, guild_id: int, channel_id: int, session):
        return (
            session.query(AutoDelete)
            .filter(AutoDelete.GuildId == guild_id)
            .filter(AutoDelete.ChannelId == channel_id)
            .first()
        )

    @classmethod
    def delete(cls, guild_id: int, channel_id: int, session):
        """deletes a channel with given guild"""
        session.delete(AutoDelete.get_by_channel(guild_id, channel_id, session))


class AutoKicker(db.BASE):
    """database entity model for General"""

    __tablename__ = "AutoKicker"
    __table_args__ = (Index("AutoKicker_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    KickAfter = Column(BigInteger, default=0)
    Enabled = Column(Boolean, default=False)
    ReminderMessage = Column(Text)

    @classmethod
    def get_all(cls, session):
        """get all"""
        return session.query(AutoKicker).all()

    @classmethod
    def get_by_guild(cls, guild_id: int, session):
        """get all"""
        return session.query(AutoKicker).filter(AutoKicker.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id: int, session):
        """deletes an entry with given name for given guild"""
        session.delete(AutoKicker.get(guild_id, session))
