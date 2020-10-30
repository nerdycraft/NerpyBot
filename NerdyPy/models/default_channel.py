""" uhm """
# -*- coding: utf-8 -*-

from utils import database as db
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Index, asc


class DefaultChannel(db.BASE):
    """database entity model for tags"""

    __tablename__ = "DefaultChannel"
    __table_args__ = (
        Index("DefaultChannel_GuildId", "GuildId")
    )

    GuildId = Column(BigInteger, primary_key=True)
    ChannelId = Column(BigInteger)
    CreateDate = Column(DateTime)
    ModifiedDate = Column(DateTime)
    Author = Column(String)

    @classmethod
    def get(cls, guild_id, session):
        """returns a channel with given guild | session needed!"""
        return (
            session.query(DefaultChannel)
            .filter(DefaultChannel.GuildId == guild_id)
            .first()
        )

    @classmethod
    def delete(cls, guild_id: int):
        """deletes a channel with given guild"""
        with db.session_scope() as session:
            session.delete(DefaultChannel.get(guild_id, session))
