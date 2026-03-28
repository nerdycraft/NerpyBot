# -*- coding: utf-8 -*-
"""Application guild configuration models."""

from sqlalchemy import BigInteger, Column, Index, Unicode
from utils import database as db


class ApplicationGuildConfig(db.BASE):
    """Per-guild configuration for the application module."""

    __tablename__ = "ApplicationGuildConfig"

    GuildId = Column(BigInteger, primary_key=True)

    @classmethod
    def get(cls, guild_id, session):
        """Returns the config for the given guild."""
        return session.query(cls).filter(cls.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id, session):
        """Deletes the config for the given guild."""
        entry = cls.get(guild_id, session)
        if entry is not None:
            session.delete(entry)


class ApplicationGuildRole(db.BASE):
    """Per-guild role assignments for application management and review.

    RoleType is either "manager" (can manage forms, override decisions)
    or "reviewer" (can vote on submissions).
    """

    __tablename__ = "ApplicationGuildRole"
    __table_args__ = (Index("ApplicationGuildRole_GuildId_Type", "GuildId", "RoleType"),)

    GuildId = Column(BigInteger, primary_key=True)
    RoleId = Column(BigInteger, primary_key=True)
    RoleType = Column(Unicode(10), primary_key=True)  # "manager" | "reviewer"

    @classmethod
    def get_role_ids(cls, guild_id: int, role_type: str, session) -> list[int]:
        """Return all role IDs of the given type for this guild."""
        rows = session.query(cls).filter(cls.GuildId == guild_id, cls.RoleType == role_type).all()
        return [r.RoleId for r in rows]

    @classmethod
    def add(cls, guild_id: int, role_id: int, role_type: str, session) -> None:
        """Add a role mapping; silently no-ops if the role is already present."""
        existing = (
            session.query(cls).filter(cls.GuildId == guild_id, cls.RoleId == role_id, cls.RoleType == role_type).first()
        )
        if existing is None:
            session.add(cls(GuildId=guild_id, RoleId=role_id, RoleType=role_type))

    @classmethod
    def remove(cls, guild_id: int, role_id: int, role_type: str, session) -> bool:
        """Remove a role mapping of the given type; returns True if it existed, False if not found."""
        row = (
            session.query(cls).filter(cls.GuildId == guild_id, cls.RoleId == role_id, cls.RoleType == role_type).first()
        )
        if row is not None:
            session.delete(row)
            return True
        return False

    @classmethod
    def clear(cls, guild_id: int, role_type: str, session) -> None:
        """Remove all role mappings of the given type for this guild."""
        session.query(cls).filter(cls.GuildId == guild_id, cls.RoleType == role_type).delete()
