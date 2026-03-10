# -*- coding: utf-8 -*-
"""Admin-domain database models: bot-moderator role and permission notification subscribers."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, String
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


class BotGuild(db.BASE):
    """Guilds where the bot is currently a member, synced on startup and join/remove events."""

    __tablename__ = "BotGuild"

    GuildId = Column(BigInteger, primary_key=True)

    @classmethod
    def sync(cls, guild_ids: list[int], session) -> None:
        """Replace the full set of known guilds with the given list."""
        session.query(cls).delete()
        for gid in guild_ids:
            session.add(cls(GuildId=gid))

    @classmethod
    def add(cls, guild_id: int, session) -> None:
        """Insert a guild if not already present."""
        from sqlalchemy.exc import IntegrityError

        try:
            with session.begin_nested():
                session.add(cls(GuildId=guild_id))
                session.flush()
        except IntegrityError:
            pass  # Already exists

    @classmethod
    def remove(cls, guild_id: int, session) -> None:
        """Remove a guild entry if present."""
        session.query(cls).filter(cls.GuildId == guild_id).delete()

    @classmethod
    def get_ids(cls, session) -> set[str]:
        """Return all known bot guild IDs as a set of strings."""
        return {str(row.GuildId) for row in session.query(cls).all()}


class GuildLanguageConfig(db.BASE):
    """Per-guild language preference for localized bot responses."""

    __tablename__ = "GuildLanguageConfig"

    GuildId = Column(BigInteger, primary_key=True)
    Language = Column(String(5), nullable=False, default="en")

    @classmethod
    def get(cls, guild_id: int, session) -> "GuildLanguageConfig | None":
        """Returns the language config for the given guild, or None."""
        return session.query(cls).filter(cls.GuildId == guild_id).first()


class PremiumUser(db.BASE):
    """Dashboard users who have been granted premium access by an operator."""

    __tablename__ = "PremiumUser"

    UserId = Column(BigInteger, primary_key=True)
    GrantedAt = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    GrantedByUserId = Column(BigInteger, nullable=True)

    @classmethod
    def has(cls, user_id: int, session) -> bool:
        """Return True if the user has premium dashboard access."""
        return session.query(cls).filter(cls.UserId == user_id).first() is not None

    @classmethod
    def get_all(cls, session) -> list["PremiumUser"]:
        """Return all premium users ordered by grant date."""
        return session.query(cls).order_by(cls.GrantedAt).all()

    @classmethod
    def grant(cls, user_id: int, granted_by: int, session) -> "PremiumUser":
        """Grant premium to a user idempotently. Returns the existing entry if already present."""
        from sqlalchemy.exc import IntegrityError

        entry = cls(UserId=user_id, GrantedByUserId=granted_by)
        try:
            with session.begin_nested():
                session.add(entry)
                session.flush()
        except IntegrityError:
            return session.query(cls).filter(cls.UserId == user_id).first()
        return entry

    @classmethod
    def revoke(cls, user_id: int, session) -> bool:
        """Revoke premium from a user. Returns True if the entry existed."""
        entry = session.query(cls).filter(cls.UserId == user_id).first()
        if entry:
            session.delete(entry)
            return True
        return False
