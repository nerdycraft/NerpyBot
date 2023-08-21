# -*- coding: utf-8 -*-
""" AutoDelete Messages """

from sqlalchemy import BigInteger, Column, Index

from utils import database as db


class AutoDelete(db.BASE):
    """database entity model for AutoDelete"""

    __tablename__ = "AutoDelete"
    __table_args__ = (Index("AutoDelete_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    ChannelId = Column(BigInteger, primary_key=True)
    DeleteAfter = Column(BigInteger)

    @classmethod
    def get(cls, guild_id: int, session):
        """returns a channel with given guild | session needed!"""
        return session.query(AutoDelete).filter(AutoDelete.GuildId == guild_id).all()

    @classmethod
    def get_by_channel(cls, guild_id: int, channel_id: int, session):
        return session.query(AutoDelete).filter(AutoDelete.GuildId == guild_id and AutoDelete.ChannelId ==
                                                channel_id).first()

    @classmethod
    def delete(cls, guild_id: int, channel_id: int, session):
        """deletes a channel with given guild"""
        session.delete(AutoDelete.get_by_channel(guild_id, channel_id, session))
