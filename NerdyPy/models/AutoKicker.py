# -*- coding: utf-8 -*-
""" General message database model """

from sqlalchemy import BigInteger, Column, Boolean, Index, Text

from utils import database as db


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
