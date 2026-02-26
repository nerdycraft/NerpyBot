# -*- coding: utf-8 -*-
"""wow dbmodel"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Unicode,
    UnicodeText,
    asc,
)
from utils import database as db


class WoW(db.BASE):
    """Database entity model for World of Warcraft"""

    __tablename__ = "WoW"
    __table_args__ = (Index("WoW_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)


class WowGuildNewsConfig(db.BASE):
    """Tracks which Discord guilds monitor which WoW guilds for news."""

    __tablename__ = "WowGuildNewsConfig"
    __table_args__ = (
        Index("WowGuildNewsConfig_GuildId", "GuildId"),
        Index("WowGuildNewsConfig_Id_GuildId", "Id", "GuildId", unique=True),
        Index(
            "WowGuildNewsConfig_Guild_Realm_Region",
            "GuildId",
            "WowGuildName",
            "WowRealmSlug",
            "Region",
            unique=True,
        ),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    WowGuildName = Column(Unicode(100))
    WowRealmSlug = Column(String(100))
    Region = Column(String(10))
    Language = Column(String(5), default="en")
    MinLevel = Column(Integer, default=10)
    ActiveDays = Column(Integer, default=7)
    RosterOffset = Column(Integer, default=0)
    LastActivityTimestamp = Column(DateTime, nullable=True)
    Enabled = Column(Boolean, default=True)
    CreateDate = Column(DateTime, default=lambda: datetime.now(UTC))
    AccountGroupData = Column(Text, default="{}")

    @classmethod
    def get_by_id(cls, config_id, guild_id, session):
        return session.query(cls).filter(cls.Id == config_id).filter(cls.GuildId == guild_id).first()

    @classmethod
    def get_all_enabled(cls, session):
        return session.query(cls).filter(cls.Enabled.is_(True)).order_by(asc("Id")).all()

    @classmethod
    def get_all_by_guild(cls, guild_id, session):
        return session.query(cls).filter(cls.GuildId == guild_id).order_by(asc("Id")).all()

    @classmethod
    def get_existing(cls, guild_id, wow_guild_name, realm_slug, region, session):
        """Check if a config already exists for this guild+realm+region combination."""
        return (
            session.query(cls)
            .filter(
                cls.GuildId == guild_id,
                cls.WowGuildName == wow_guild_name,
                cls.WowRealmSlug == realm_slug,
                cls.Region == region,
            )
            .first()
        )

    @classmethod
    def delete(cls, config_id, guild_id, session):
        config = cls.get_by_id(config_id, guild_id, session)
        if config:
            session.query(WowCharacterMounts).filter(WowCharacterMounts.ConfigId == config.Id).delete()
            session.delete(config)

    def __str__(self):
        status = "active" if self.Enabled else "paused"
        return (
            f"==== {self.Id} ====\n"
            f"Guild: {self.WowGuildName} ({self.WowRealmSlug}-{self.Region.upper()})\n"
            f"Language: {self.Language}\n"
            f"Status: {status}\n"
            f"Active Days Filter: {self.ActiveDays}\n"
        )


class WowCharacterMounts(db.BASE):
    """Stored mount set per player (account-wide, keyed by highest-level char)."""

    __tablename__ = "WowCharacterMounts"
    __table_args__ = (
        Index("WowCharacterMounts_ConfigId", "ConfigId"),
        Index("WowCharacterMounts_Config_Char", "ConfigId", "CharacterName", "RealmSlug", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    ConfigId = Column(Integer, ForeignKey("WowGuildNewsConfig.Id"))
    CharacterName = Column(Unicode(50))
    RealmSlug = Column(String(100))
    KnownMountIds = Column(Text, default="[]")
    LastChecked = Column(DateTime, nullable=True)

    @classmethod
    def get_by_character(cls, config_id, char_name, realm_slug, session):
        return (
            session.query(cls)
            .filter(cls.ConfigId == config_id)
            .filter(cls.CharacterName == char_name)
            .filter(cls.RealmSlug == realm_slug)
            .first()
        )

    @classmethod
    def get_all_by_config(cls, config_id, session):
        return session.query(cls).filter(cls.ConfigId == config_id).all()

    @classmethod
    def delete_stale(cls, config_id, active_keys, stale_cutoff, session):
        """Delete entries for characters no longer in the roster whose LastChecked is older than stale_cutoff.

        active_keys: set of (CharacterName, RealmSlug) currently in the guild roster.
        Returns the number of deleted entries.
        """
        all_entries = cls.get_all_by_config(config_id, session)
        deleted = 0
        for entry in all_entries:
            if (entry.CharacterName, entry.RealmSlug) not in active_keys:
                if entry.LastChecked and entry.LastChecked < stale_cutoff:
                    session.delete(entry)
                    deleted += 1
        return deleted


class CraftingBoardConfig(db.BASE):
    """Guild-level crafting order board configuration."""

    __tablename__ = "CraftingBoardConfig"
    __table_args__ = (Index("CraftingBoardConfig_GuildId", "GuildId", unique=True),)

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    BoardMessageId = Column(BigInteger, nullable=True)
    Description = Column(UnicodeText)
    CreateDate = Column(DateTime, default=lambda: datetime.now(UTC))

    @classmethod
    def get_by_guild(cls, guild_id, session):
        return session.query(cls).filter(cls.GuildId == guild_id).first()

    @classmethod
    def delete_by_guild(cls, guild_id, session):
        config = cls.get_by_guild(guild_id, session)
        if config:
            session.delete(config)
        return config


class CraftingRoleMapping(db.BASE):
    """Maps Discord roles to Blizzard profession IDs, per guild."""

    __tablename__ = "CraftingRoleMapping"
    __table_args__ = (
        Index("CraftingRoleMapping_GuildId", "GuildId"),
        Index("CraftingRoleMapping_Guild_Role", "GuildId", "RoleId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    RoleId = Column(BigInteger)
    ProfessionId = Column(Integer)

    @classmethod
    def get_by_guild(cls, guild_id, session):
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get_profession_id(cls, guild_id, role_id, session):
        mapping = session.query(cls).filter(cls.GuildId == guild_id, cls.RoleId == role_id).first()
        return mapping.ProfessionId if mapping else None

    @classmethod
    def delete_by_guild(cls, guild_id, session):
        session.query(cls).filter(cls.GuildId == guild_id).delete()


class CraftingOrder(db.BASE):
    """Individual crafting order posted by a user."""

    __tablename__ = "CraftingOrder"
    __table_args__ = (
        Index("CraftingOrder_GuildId", "GuildId"),
        Index("CraftingOrder_Status", "Status"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    OrderMessageId = Column(BigInteger, nullable=True)
    ThreadId = Column(BigInteger, nullable=True)
    CreatorId = Column(BigInteger)
    CrafterId = Column(BigInteger, nullable=True)
    ProfessionRoleId = Column(BigInteger)
    ItemName = Column(Unicode(200))
    IconUrl = Column(Unicode(500), nullable=True)
    Notes = Column(UnicodeText, nullable=True)
    Status = Column(String(20), default="open")
    CreateDate = Column(DateTime, default=lambda: datetime.now(UTC))

    @classmethod
    def get_by_id(cls, order_id, session):
        return session.query(cls).filter(cls.Id == order_id).first()

    @classmethod
    def get_active_by_guild(cls, guild_id, session):
        return session.query(cls).filter(cls.GuildId == guild_id, cls.Status.notin_(["completed", "cancelled"])).all()
