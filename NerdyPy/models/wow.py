# -*- coding: utf-8 -*-
"""default channel dbmodel"""

from sqlalchemy import BigInteger, Column, DateTime, String, Index

from utils import database as db


class WoW(db.BASE):
    """Database entity model for World of Warcraft"""

    __tablename__ = "WoW"
    __table_args__ = (Index("WoW_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    Language = Column(String(30))
    CreateDate = Column(DateTime)
    ModifiedDate = Column(DateTime)
    Author = Column(String(30))

    @classmethod
    def get(cls, guild_id, session):
        """Returns the WoW entry for the given guild_id"""
        return session.query(WoW).filter(WoW.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id: int, session):
        """Deletes the WoW entry for the given guild_id"""
        session.delete(WoW.get(guild_id, session))
