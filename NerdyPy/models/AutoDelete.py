# -*- coding: utf-8 -*-
""" AutoDelete Messages """

from sqlalchemy import Integer, BigInteger, Column, Index, Boolean

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
    def get(cls, guild_id: int, session):
        """returns a channel with given guild | session needed!"""
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
