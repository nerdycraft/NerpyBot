""" default channel dbmodel """
# -*- coding: utf-8 -*-

from utils import database as db
from sqlalchemy import BigInteger, Column, DateTime, String, Index


class GuildPrefix(db.BASE):
    """database entity model for tags"""

    __tablename__ = "GuildPrefix"
    __table_args__ = (Index("GuildPrefix_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    Prefix = Column(String)
    CreateDate = Column(DateTime)
    ModifiedDate = Column(DateTime)
    Author = Column(String)

    @classmethod
    def get(cls, guild_id, session):
        """returns a channel with given guild | session needed!"""
        return session.query(GuildPrefix).filter(GuildPrefix.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id: int, session):
        """deletes a channel with given guild"""
        session.delete(GuildPrefix.get(guild_id, session))
