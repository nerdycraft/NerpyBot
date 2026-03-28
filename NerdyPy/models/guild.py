# -*- coding: utf-8 -*-
"""Guild-domain database models: guild registry and per-guild language preference."""

from sqlalchemy import BigInteger, Column, String

from utils import database as db


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
