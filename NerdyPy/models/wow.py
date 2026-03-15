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
    WowGuildNameDisplay = Column(Unicode(100), nullable=True)
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
                last_checked = entry.LastChecked
                if last_checked and last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=UTC)
                if last_checked and last_checked < stale_cutoff:
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
    ThreadCleanupDelayHours = Column(Integer, default=24, server_default="24")
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
    CreatorName = Column(UnicodeText, nullable=True)
    CrafterId = Column(BigInteger, nullable=True)
    CrafterName = Column(UnicodeText, nullable=True)
    ProfessionRoleId = Column(BigInteger)
    ItemName = Column(Unicode(200))
    IconUrl = Column(Unicode(500), nullable=True)
    WowheadUrl = Column(Unicode(500), nullable=True)
    Notes = Column(UnicodeText, nullable=True)
    Status = Column(String(20), default="open")
    MessageDeleteAt = Column(DateTime, nullable=True)
    CreateDate = Column(DateTime, default=lambda: datetime.now(UTC))

    @classmethod
    def get_by_id(cls, order_id, session):
        return session.query(cls).filter(cls.Id == order_id).first()

    @classmethod
    def get_active_by_guild(cls, guild_id, session):
        return session.query(cls).filter(cls.GuildId == guild_id, cls.Status.notin_(["completed", "cancelled"])).all()

    @classmethod
    def get_pending_cleanup(cls, session):
        """Return orders whose message should be deleted (MessageDeleteAt has passed)."""
        return (
            session.query(cls).filter(cls.MessageDeleteAt.isnot(None), cls.MessageDeleteAt <= datetime.now(UTC)).all()
        )


RECIPE_TYPE_CRAFTED = "crafted"
RECIPE_TYPE_HOUSING = "housing"


class CraftingRecipeCache(db.BASE):
    """Cache of WoW crafting recipes for the crafting order board UI.

    RecipeType values:
        RECIPE_TYPE_CRAFTED — recipes from profession skill tiers (gear, consumables, gems, enchants, etc.)
        RECIPE_TYPE_HOUSING — housing/decoration recipes from the Blizzard decor API
    """

    __tablename__ = "CraftingRecipeCache"
    __table_args__ = (
        Index("CraftingRecipeCache_ProfessionId", "ProfessionId"),
        Index("CraftingRecipeCache_RecipeType", "RecipeType"),
        Index("CraftingRecipeCache_Prof_Type", "ProfessionId", "RecipeType"),
        Index("CraftingRecipeCache_Type_Class", "RecipeType", "ItemClassId", "ItemSubClassId"),
    )

    RecipeId = Column(Integer, primary_key=True)
    ProfessionId = Column(Integer)
    ProfessionName = Column(Unicode(100))
    ItemId = Column(Integer, nullable=True)
    ItemName = Column(Unicode(200))
    IconUrl = Column(Unicode(500), nullable=True)
    RecipeType = Column(String(20))
    ItemClassName = Column(Unicode(100), nullable=True)
    ItemClassId = Column(Integer, nullable=True)
    ItemSubClassName = Column(Unicode(100), nullable=True)
    ItemSubClassId = Column(Integer, nullable=True)
    ExpansionName = Column(Unicode(100), nullable=True)
    CategoryName = Column(Unicode(200), nullable=True)
    LastSynced = Column(DateTime, default=lambda: datetime.now(UTC))

    @classmethod
    def get_by_profession(cls, prof_id, recipe_type, session):
        return (
            session.query(cls)
            .filter(cls.ProfessionId == prof_id, cls.RecipeType == recipe_type)
            .order_by(asc(cls.ItemName))
            .all()
        )

    @classmethod
    def get_by_profession_and_expansion(cls, prof_id, recipe_type, expansion, session):
        return (
            session.query(cls)
            .filter(cls.ProfessionId == prof_id, cls.RecipeType == recipe_type, cls.ExpansionName == expansion)
            .order_by(asc(cls.ItemName))
            .all()
        )

    @classmethod
    def get_by_type_and_subclass(cls, recipe_type, item_class_id, item_subclass_id, session):
        return (
            session.query(cls)
            .filter(
                cls.RecipeType == recipe_type,
                cls.ItemClassId == item_class_id,
                cls.ItemSubClassId == item_subclass_id,
            )
            .order_by(asc(cls.ItemName))
            .all()
        )

    @classmethod
    def get_expansions_for_profession(cls, prof_id, recipe_type, session):
        """Return distinct non-null expansion names for a profession, ordered alphabetically."""
        rows = (
            session.query(cls.ExpansionName)
            .filter(cls.ProfessionId == prof_id, cls.RecipeType == recipe_type, cls.ExpansionName.isnot(None))
            .distinct()
            .order_by(asc(cls.ExpansionName))
            .all()
        )
        return [r[0] for r in rows]

    @classmethod
    def get_item_classes(cls, recipe_type, session):
        """Return distinct (ItemClassId, ItemClassName) pairs for a recipe type."""
        rows = (
            session.query(cls.ItemClassId, cls.ItemClassName)
            .filter(cls.RecipeType == recipe_type, cls.ItemClassId.isnot(None))
            .distinct()
            .order_by(asc(cls.ItemClassName))
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    @classmethod
    def get_item_subclasses(cls, recipe_type, item_class_id, session):
        """Return distinct (ItemSubClassId, ItemSubClassName) pairs for a class."""
        rows = (
            session.query(cls.ItemSubClassId, cls.ItemSubClassName)
            .filter(cls.RecipeType == recipe_type, cls.ItemClassId == item_class_id, cls.ItemSubClassId.isnot(None))
            .distinct()
            .order_by(asc(cls.ItemSubClassName))
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    @classmethod
    def get_professions_with_recipes(cls, recipe_type, session):
        """Return distinct (ProfessionId, ProfessionName) pairs that have cached recipes of the given type."""
        rows = (
            session.query(cls.ProfessionId, cls.ProfessionName)
            .filter(cls.RecipeType == recipe_type)
            .distinct()
            .order_by(asc(cls.ProfessionName))
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    @classmethod
    def count_by_type(cls, session):
        """Return {recipe_type: count} mapping."""
        from sqlalchemy import func

        rows = session.query(cls.RecipeType, func.count(cls.RecipeId)).group_by(cls.RecipeType).all()
        return {r[0]: r[1] for r in rows}

    @classmethod
    def count_by_class(cls, session):
        """Return {ItemClassName: count} for 'crafted', plus 'housing' count."""
        from sqlalchemy import func

        crafted = (
            session.query(cls.ItemClassName, func.count(cls.RecipeId))
            .filter(cls.RecipeType == RECIPE_TYPE_CRAFTED, cls.ItemClassName.isnot(None))
            .group_by(cls.ItemClassName)
            .all()
        )
        housing_count = session.query(func.count(cls.RecipeId)).filter(cls.RecipeType == RECIPE_TYPE_HOUSING).scalar()
        result = {r[0]: r[1] for r in crafted}
        result["housing"] = housing_count or 0
        return result

    @property
    def wowhead_url(self) -> str | None:
        """Return the Wowhead URL for this recipe's crafted item or spell."""
        if self.ItemId:
            return f"https://www.wowhead.com/item={self.ItemId}"
        return f"https://www.wowhead.com/spell={self.RecipeId}"

    @classmethod
    def delete_all(cls, session):
        session.query(cls).delete()
