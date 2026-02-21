# -*- coding: utf-8 -*-
"""Admin-domain database models: bot-moderator role and permission notification subscribers."""

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


class PermissionSubscriber(db.BASE):
    """Users who opted in to receive DM notifications about missing bot permissions on startup."""

    __tablename__ = "PermissionSubscriber"

    GuildId = Column(BigInteger, primary_key=True)
    UserId = Column(BigInteger, primary_key=True)

    @classmethod
    def get_by_guild(cls, guild_id: int, session) -> list["PermissionSubscriber"]:
        """Returns all subscribers for a given guild."""
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get(cls, guild_id: int, user_id: int, session) -> "PermissionSubscriber | None":
        """Returns a specific subscription, or None."""
        return session.query(cls).filter(cls.GuildId == guild_id, cls.UserId == user_id).first()

    @classmethod
    def delete(cls, guild_id: int, user_id: int, session) -> None:
        """Removes a subscription."""
        entry = cls.get(guild_id, user_id, session)
        if entry is not None:
            session.delete(entry)
