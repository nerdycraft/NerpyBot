# -*- coding: utf-8 -*-
"""default channel dbmodel"""

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Unicode
from utils import database as db


class GuildPrefix(db.BASE):
    """Database entity model for Guild Prefix"""

    __tablename__ = "GuildPrefix"
    __table_args__ = (Index("GuildPrefix_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    Prefix = Column(String(30))
    CreateDate = Column(DateTime)
    ModifiedDate = Column(DateTime)
    Author = Column(Unicode(30))

    @classmethod
    def get(cls, guild_id, session):
        """Returns the GuildPrefix entry for the given guild_id"""
        return session.query(GuildPrefix).filter(GuildPrefix.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id: int, session):
        """Deletes the GuildPrefix entry for the given guild_id."""
        session.delete(GuildPrefix.get(guild_id, session))
