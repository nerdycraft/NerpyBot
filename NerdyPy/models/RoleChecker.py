# -*- coding: utf-8 -*-
""" General message database model """

from sqlalchemy import BigInteger, Column, Boolean, Integer, Index, select

from utils import database as db


class RoleChecker(db.BASE):
    """database entity model for General"""

    __tablename__ = "RoleChecker"
    __table_args__ = (Index("RoleChecker_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    KickAfter = Column(BigInteger, default=0)
    Enabled = Column(Boolean, default=False)
    ChannelId = Column(BigInteger)

    @classmethod
    def get(cls, guild_id: int, session):
        """get all"""
        return session.query(RoleChecker).filter(RoleChecker.GuildId == guild_id).all()

    @classmethod
    def delete(cls, guild_id: int, session):
        """deletes an entry with given name for given guild"""
        session.delete(RoleChecker.get(guild_id, session))
