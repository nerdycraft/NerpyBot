# -*- coding: utf-8 -*-
"""Bot moderator role database model"""

from sqlalchemy import BigInteger, Column
from utils import database as db


class BotModeratorRole(db.BASE):
    """Database entity model for a per-guild bot-moderator role."""

    __tablename__ = "BotModeratorRole"

    GuildId = Column(BigInteger, primary_key=True)
    RoleId = Column(BigInteger, nullable=False)

    @classmethod
    def get(cls, guild_id, session):
        """Returns the BotModeratorRole entry for the given guild_id."""
        return session.query(cls).filter(cls.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id: int, session):
        """Deletes the BotModeratorRole entry for the given guild_id."""
        entry = cls.get(guild_id, session)
        if entry is not None:
            session.delete(entry)
