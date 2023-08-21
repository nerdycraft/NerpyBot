# -*- coding: utf-8 -*-
""" General message database model """

from sqlalchemy import BigInteger, Column, Boolean, Integer, Index, select

from utils import database as db


class RoleChecker(db.BASE):
    """database entity model for General"""

    __tablename__ = "RoleChecker"
    __table_args__ = (
        Index("RoleChecker_GuildId", "GuildId"),
        Index("RoleChecker_Id_GuildId", "Id", "GuildId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    Enabled = Column(Boolean)

    @classmethod
    def is_rolecheck_enabled(cls, guild_id: int, session):
        """returns if rolechecker is enabled"""
        stmt = select(RoleChecker).where(RoleChecker.GuildId == guild_id).first()
        result = session.execute(stmt)
        for obj in result.scalars():
            return obj.Enabled

    @classmethod
    def get_channel_id(cls, guild_id: int, session):
        """get channel id"""
        stmt = select(RoleChecker).where(RoleChecker.GuildId == guild_id).first()
        result = session.execute(stmt)
        for obj in result.scalars():
            return obj.ChannelId

    @classmethod
    def delete(cls, general_id, guild_id: int, session):
        """deletes an entry with given name for given guild"""
        session.delete(RoleChecker.get(general_id, guild_id, session))
