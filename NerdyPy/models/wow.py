# -*- coding: utf-8 -*-
"""wow dbmodel"""

import functools
import inspect
import logging
from datetime import UTC, datetime

from cachetools import TTLCache
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Unicode,
    UnicodeText,
    and_,
    asc,
    func,
    or_,
)
from utils import database as db

_log = logging.getLogger(__name__)

# ── CraftingRecipeCache query cache ───────────────────────────────────────────
# Recipe data changes only on operator-triggered sync (daily/weekly at most).
# TTL of 1 hour prevents stale data without ever needing a bot restart.

_recipe_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)


def _cache_recipe_query(method):
    """Wrap a CraftingRecipeCache classmethod with TTL result caching.

    Builds a key from the method name + all arguments except ``cls`` and ``session``.
    ``set`` arguments are converted to ``frozenset`` for hashability.

    Warning: methods that return ``list[CraftingRecipeCache]`` yield session-detached
    ORM instances. Callers must not access lazy-loaded relationships on those objects —
    only eagerly-loaded columns are safe. Methods returning scalars or plain tuples are
    unaffected.
    """
    sig = inspect.signature(method)

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        key = (
            method.__name__,
            *(
                frozenset(val) if isinstance(val, set) else val
                for name, val in bound.arguments.items()
                if name not in ("cls", "session")
            ),
        )
        if key in _recipe_cache:
            return _recipe_cache[key]
        try:
            result = method(*args, **kwargs)
        except Exception:
            _log.exception("_cache_recipe_query: %s raised an error", method.__name__)
            raise
        session = bound.arguments.get("session")
        if session is not None and isinstance(result, list):
            try:
                for item in result:
                    if isinstance(item, db.BASE):
                        session.expunge(item)
            except SQLAlchemyError:
                _log.exception("_cache_recipe_query: %s — expunge failed", method.__name__)
                raise
        _recipe_cache[key] = result
        return result

    return wrapper


def invalidate_recipe_cache() -> None:
    """Clear all cached CraftingRecipeCache query results.

    Call this after a recipe sync completes to ensure fresh data on next access.
    """
    _recipe_cache.clear()


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


CURRENT_BOARD_VERSION = 2  # v2: adds housing button


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
    BoardVersion = Column(Integer, default=CURRENT_BOARD_VERSION, server_default=str(CURRENT_BOARD_VERSION))
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
    ItemNameLocalized = Column(Unicode(200), nullable=True)
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

# Sentinel for find_best_match: fetch one more than this many rows to detect ambiguity
# without issuing a separate COUNT query.
_BEST_MATCH_PROBE_LIMIT = 101

# Blizzard API binding type values (preview_item.binding.type).
BIND_ON_ACQUIRE = "ON_ACQUIRE"  # BoP — bind on pickup
BIND_TO_ACCOUNT = "TO_ACCOUNT"  # BoA/Warband — bind to account
BIND_ON_EQUIP = "ON_EQUIP"  # BoE — bind on equip

# Profession IDs used for orderable-item filtering.
_PROF_COOKING = 185
_PROF_ALCHEMY = 171
_GEAR_PROFESSIONS = frozenset({164, 165, 197, 202, 333, 755, 773})
_COOKING_CATEGORY_KEYWORDS = ("feast", "cooking for")
_ALCHEMY_CATEGORY_KEYWORDS = ("cauldron",)

# Virtual category classification keywords.
_PVP_CATEGORY_KEYWORDS = ("competitor", "pvp")
_RAID_PREP_CATEGORY_KEYWORDS = ("flask", "phial", "potion", "feast", "rune", "tea")
_RAID_PREP_CAULDRON_KEYWORD = "cauldron"
# Item class names (lowercase) for the main gear buckets (used in Other exclusion filter).
_MAIN_ITEM_CLASS_NAMES = ("armor", "weapon", "profession")


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
    ItemNameLocales = Column(JSON, nullable=True)
    IconUrl = Column(Unicode(500), nullable=True)
    RecipeType = Column(String(20))
    ItemClassName = Column(Unicode(100), nullable=True)
    ItemClassNameLocales = Column(JSON, nullable=True)
    ItemClassId = Column(Integer, nullable=True)
    ItemSubClassName = Column(Unicode(100), nullable=True)
    ItemSubClassNameLocales = Column(JSON, nullable=True)
    ItemSubClassId = Column(Integer, nullable=True)
    ExpansionName = Column(Unicode(100), nullable=True)
    CategoryName = Column(Unicode(200), nullable=True)
    CategoryNameLocales = Column(JSON, nullable=True)
    BindType = Column(String(20), nullable=True)  # ON_ACQUIRE, TO_ACCOUNT, ON_EQUIP, or None
    ItemQuality = Column(String(20), nullable=True)  # EPIC, RARE, COMMON, etc.
    LastSynced = Column(DateTime, default=lambda: datetime.now(UTC))

    @classmethod
    def _apply_orderable_filter(cls, q, profession_ids: set[int] | None):
        """Narrow *q* to items that require a crafting order (BoP/BoA/BoE gear, feasts, cauldrons).

        Each profession group gets its own condition; a row passes if it matches any applicable rule.
        Returns the query unchanged when *profession_ids* is empty/None (no professions selected yet).
        """
        if not profession_ids:
            return q

        conditions = []

        gear_ids = _GEAR_PROFESSIONS & profession_ids
        if gear_ids:
            conditions.append(
                and_(
                    cls.ProfessionId.in_(gear_ids),
                    cls.BindType.in_((BIND_ON_ACQUIRE, BIND_TO_ACCOUNT, BIND_ON_EQUIP)),
                )
            )

        if _PROF_COOKING in profession_ids:
            cooking_cond = or_(*[func.lower(cls.CategoryName).contains(kw) for kw in _COOKING_CATEGORY_KEYWORDS])
            conditions.append(and_(cls.ProfessionId == _PROF_COOKING, cooking_cond))

        if _PROF_ALCHEMY in profession_ids:
            alchemy_cond = or_(*[func.lower(cls.CategoryName).contains(kw) for kw in _ALCHEMY_CATEGORY_KEYWORDS])
            conditions.append(and_(cls.ProfessionId == _PROF_ALCHEMY, alchemy_cond))

        if conditions:
            q = q.filter(or_(*conditions))
        return q

    @classmethod
    def _pvp_condition(cls):
        """Return an OR condition matching PvP items by category name or item name.

        Most PvP items have a "Competitor's" or "PvP" CategoryName, but some Blizzard
        items use a generic category (e.g. "Mail Equipment") while keeping "Competitor's"
        in the ItemName. Both columns are checked so no PvP items leak into gear buckets.
        """
        return or_(
            *[func.lower(cls.CategoryName).contains(kw) for kw in _PVP_CATEGORY_KEYWORDS],
            *[func.lower(cls.ItemName).contains(kw) for kw in _PVP_CATEGORY_KEYWORDS],
        )

    @classmethod
    def _raid_prep_condition(cls):
        """Return an OR condition matching consumables and cauldrons used for raid prep.

        Consumables (NULL BindType): flask, phial, potion, feast, rune, tea.
        Cauldrons: any BindType (bound or unbound).
        """
        consumable_cond = and_(
            cls.BindType.is_(None),
            or_(*[func.lower(cls.CategoryName).contains(kw) for kw in _RAID_PREP_CATEGORY_KEYWORDS]),
        )
        cauldron_cond = func.lower(cls.CategoryName).contains(_RAID_PREP_CAULDRON_KEYWORD)
        return or_(consumable_cond, cauldron_cond)

    @classmethod
    def _main_class_condition(cls):
        """Return an OR condition matching items that belong to the main gear class buckets.

        Matches rows whose ItemClassName (lowercase) is one of the main class names
        (armor, weapon, profession). Use ``~cls._main_class_condition()`` to exclude them.
        """
        return or_(*[func.lower(cls.ItemClassName) == name for name in _MAIN_ITEM_CLASS_NAMES])

    @classmethod
    def _prof_knowledge_condition(cls):
        """Return an OR condition matching profession knowledge items (treatises and skinning knives).

        Matches: any item with 'treatise' in CategoryName, or Miscellaneous items with 'profession'
        in CategoryName (e.g. Thalassian Skinning Knife in "Profession Equipment").
        """
        return or_(
            func.lower(cls.CategoryName).contains("treatise"),
            and_(
                func.lower(cls.ItemClassName) == "miscellaneous",
                func.lower(cls.CategoryName).contains("profession"),
            ),
        )

    @classmethod
    @_cache_recipe_query
    def get_prof_knowledge_items(
        cls, recipe_type, session, profession_ids: set[int] | None = None
    ) -> list["CraftingRecipeCache"]:
        """Return recipe rows for profession knowledge items (treatises and skinning knives)."""
        q = session.query(cls).filter(
            cls.RecipeType == recipe_type,
            cls._prof_knowledge_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return q.order_by(asc(cls.ItemName)).all()

    @classmethod
    @_cache_recipe_query
    def has_prof_knowledge_items(cls, recipe_type, session, profession_ids: set[int] | None = None) -> bool:
        """Return True if there are any profession knowledge items for the given filters."""
        q = session.query(cls.RecipeId).filter(
            cls.RecipeType == recipe_type,
            cls._prof_knowledge_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return q.limit(1).scalar() is not None

    @classmethod
    @_cache_recipe_query
    def get_by_profession(cls, prof_id, recipe_type, session):
        return (
            session.query(cls)
            .filter(cls.ProfessionId == prof_id, cls.RecipeType == recipe_type)
            .order_by(asc(cls.ItemName))
            .all()
        )

    @classmethod
    @_cache_recipe_query
    def get_by_profession_and_expansion(cls, prof_id, recipe_type, expansion, session):
        return (
            session.query(cls)
            .filter(cls.ProfessionId == prof_id, cls.RecipeType == recipe_type, cls.ExpansionName == expansion)
            .order_by(asc(cls.ItemName))
            .all()
        )

    @classmethod
    @_cache_recipe_query
    def get_by_type_and_subclass(
        cls,
        recipe_type,
        item_class_id,
        item_subclass_id,
        session,
        profession_ids: set[int] | None = None,
        orderable_only: bool = False,
        exclude_pvp: bool = False,
    ):
        q = session.query(cls).filter(
            cls.RecipeType == recipe_type,
            cls.ItemClassId == item_class_id,
            cls.ItemSubClassId == item_subclass_id,
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        if orderable_only:
            q = cls._apply_orderable_filter(q, profession_ids)
        if exclude_pvp:
            q = q.filter(~cls._pvp_condition())
        return q.order_by(asc(cls.ItemName)).all()

    @classmethod
    @_cache_recipe_query
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

    @staticmethod
    def _dedup_rows(q, order_col) -> list[tuple]:
        """Deduplicate (id, name, locales) rows by display name, preserving sort order.

        SQL DISTINCT cannot be used when a JSON column is projected — PostgreSQL has no
        equality operator for json.  Instead, collect all rows ordered by name and pick
        the first row per unique name using dict insertion order (Python 3.7+).

        Deduplication is intentionally by name (not id): the Blizzard item API historically
        returned short names ("Axe") for all hand-type variants sharing a subclass, causing
        duplicate dropdown entries.  The sync now fetches verbose_name from the item-subclass
        endpoint ("One-Handed Axes", "Two-Handed Axes"), but deduplication by name is kept as
        a safety net for stale rows that predate that fix.
        """
        seen: dict = {}
        for r in q.order_by(asc(order_col)).all():
            current = seen.get(r[1])
            if current is None or (current[2] is None and r[2] is not None):
                seen[r[1]] = (r[0], r[1], r[2])
        return list(seen.values())

    @staticmethod
    def _dedup_category_rows(rows) -> list[tuple[str, dict | None]]:
        """Deduplicate (CategoryName, CategoryNameLocales) rows by name, preserving insertion order.

        Prefers rows with populated locale JSON over null-locale duplicates.
        """
        seen: dict = {}
        for name, locales in rows:
            current = seen.get(name)
            if current is None or (current[1] is None and locales is not None):
                seen[name] = (name, locales)
        return list(seen.values())

    @classmethod
    @_cache_recipe_query
    def get_item_classes(
        cls,
        recipe_type,
        session,
        profession_ids: set[int] | None = None,
        orderable_only: bool = False,
        exclude_pvp: bool = False,
    ):
        """Return distinct (ItemClassId, ItemClassName, ItemClassNameLocales) tuples for a recipe type.

        If profession_ids is provided, only return classes that have recipes for those professions.
        If orderable_only is True, only return classes that contain orderable items.
        If exclude_pvp is True, exclude items whose CategoryName matches PvP keywords.
        """
        q = session.query(cls.ItemClassId, cls.ItemClassName, cls.ItemClassNameLocales).filter(
            cls.RecipeType == recipe_type, cls.ItemClassId.isnot(None)
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        if orderable_only:
            q = cls._apply_orderable_filter(q, profession_ids)
        if exclude_pvp:
            q = q.filter(~cls._pvp_condition())
        return cls._dedup_rows(q, cls.ItemClassName)

    @classmethod
    @_cache_recipe_query
    def get_item_subclasses(
        cls,
        recipe_type,
        item_class_id,
        session,
        profession_ids: set[int] | None = None,
        orderable_only: bool = False,
        exclude_pvp: bool = False,
    ):
        """Return distinct (ItemSubClassId, ItemSubClassName, ItemSubClassNameLocales) tuples for a class.

        If profession_ids is provided, only return subclasses that have recipes for those professions.
        If orderable_only is True, only return subclasses that contain orderable items.
        If exclude_pvp is True, exclude items whose CategoryName matches PvP keywords.
        """
        q = session.query(cls.ItemSubClassId, cls.ItemSubClassName, cls.ItemSubClassNameLocales).filter(
            cls.RecipeType == recipe_type, cls.ItemClassId == item_class_id, cls.ItemSubClassId.isnot(None)
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        if orderable_only:
            q = cls._apply_orderable_filter(q, profession_ids)
        if exclude_pvp:
            q = q.filter(~cls._pvp_condition())
        return cls._dedup_rows(q, cls.ItemSubClassName)

    @classmethod
    @_cache_recipe_query
    def get_pvp_item_classes(cls, recipe_type, session, profession_ids: set[int] | None = None):
        """Return distinct (ItemClassId, ItemClassName, locales) for PvP items (bound, PvP category)."""
        q = session.query(cls.ItemClassId, cls.ItemClassName, cls.ItemClassNameLocales).filter(
            cls.RecipeType == recipe_type,
            cls.ItemClassId.isnot(None),
            cls.BindType.isnot(None),
            cls._pvp_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return cls._dedup_rows(q, cls.ItemClassName)

    @classmethod
    @_cache_recipe_query
    def get_pvp_item_subclasses(cls, recipe_type, item_class_id, session, profession_ids: set[int] | None = None):
        """Return distinct (ItemSubClassId, ItemSubClassName, locales) for PvP items in a class."""
        q = session.query(cls.ItemSubClassId, cls.ItemSubClassName, cls.ItemSubClassNameLocales).filter(
            cls.RecipeType == recipe_type,
            cls.ItemClassId == item_class_id,
            cls.ItemSubClassId.isnot(None),
            cls.BindType.isnot(None),
            cls._pvp_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return cls._dedup_rows(q, cls.ItemSubClassName)

    @classmethod
    @_cache_recipe_query
    def get_pvp_items(
        cls, recipe_type, item_class_id, item_subclass_id, session, profession_ids: set[int] | None = None
    ):
        """Return recipe rows for PvP items in a class/subclass.

        item_subclass_id may be None to retrieve all subclasses within the class.
        """
        q = session.query(cls).filter(
            cls.RecipeType == recipe_type,
            cls.ItemClassId == item_class_id,
            cls.BindType.isnot(None),
            cls._pvp_condition(),
        )
        if item_subclass_id is not None:
            q = q.filter(cls.ItemSubClassId == item_subclass_id)
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return q.order_by(asc(cls.ItemName)).all()

    @classmethod
    @_cache_recipe_query
    def get_raid_prep_categories(
        cls, recipe_type, session, profession_ids: set[int] | None = None
    ) -> list[tuple[str, dict | None]]:
        """Return distinct (CategoryName, CategoryNameLocales) tuples matching raid prep consumables and cauldrons."""
        q = session.query(cls.CategoryName, cls.CategoryNameLocales).filter(
            cls.RecipeType == recipe_type,
            cls.CategoryName.isnot(None),
            cls._raid_prep_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        rows = q.order_by(asc(cls.CategoryName)).all()
        return cls._dedup_category_rows(rows)

    @classmethod
    @_cache_recipe_query
    def get_raid_prep_items(cls, recipe_type, category_name, session, profession_ids: set[int] | None = None):
        """Return recipe rows for a specific raid prep category."""
        q = session.query(cls).filter(
            cls.RecipeType == recipe_type,
            cls.CategoryName == category_name,
            cls._raid_prep_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return q.order_by(asc(cls.ItemName)).all()

    @classmethod
    @_cache_recipe_query
    def get_other_categories(
        cls, recipe_type, session, profession_ids: set[int] | None = None
    ) -> list[tuple[str, dict | None]]:
        """Return distinct (CategoryName, CategoryNameLocales) tuples for bound items outside the main gear buckets.

        Excludes Armor, Weapon, and Profession class items, PvP items, and raid prep items.
        """
        q = session.query(cls.CategoryName, cls.CategoryNameLocales).filter(
            cls.RecipeType == recipe_type,
            cls.CategoryName.isnot(None),
            cls.BindType.isnot(None),
            ~cls._main_class_condition(),
            ~cls._pvp_condition(),
            ~cls._raid_prep_condition(),
            ~cls._prof_knowledge_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        rows = q.order_by(asc(cls.CategoryName)).all()
        return cls._dedup_category_rows(rows)

    @classmethod
    @_cache_recipe_query
    def get_other_items(cls, recipe_type, category_name, session, profession_ids: set[int] | None = None):
        """Return recipe rows for a specific 'Other' category."""
        q = session.query(cls).filter(
            cls.RecipeType == recipe_type,
            cls.CategoryName == category_name,
            cls.BindType.isnot(None),
            ~cls._main_class_condition(),
            ~cls._pvp_condition(),
            ~cls._raid_prep_condition(),
            ~cls._prof_knowledge_condition(),
        )
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return q.order_by(asc(cls.ItemName)).all()

    @classmethod
    @_cache_recipe_query
    def get_professions_with_recipes(cls, recipe_type, session, profession_ids: set[int] | None = None):
        """Return distinct (ProfessionId, ProfessionName) pairs that have cached recipes of the given type."""
        q = session.query(cls.ProfessionId, cls.ProfessionName).filter(cls.RecipeType == recipe_type)
        if profession_ids:
            q = q.filter(cls.ProfessionId.in_(profession_ids))
        return [(r[0], r[1]) for r in q.distinct().order_by(asc(cls.ProfessionName)).all()]

    @classmethod
    def count_by_type(cls, session):
        """Return {recipe_type: count} mapping."""
        rows = session.query(cls.RecipeType, func.count(cls.RecipeId)).group_by(cls.RecipeType).all()
        return {r[0]: r[1] for r in rows}

    @classmethod
    def count_by_class(cls, session):
        """Return {ItemClassName: count} for 'crafted', plus 'housing' count."""
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

    @property
    def _dedup_key(self) -> str:
        return f"item:{self.ItemId}" if self.ItemId is not None else f"spell:{self.RecipeId}"

    @classmethod
    def find_best_match(cls, name: str, session):
        """Try to resolve a free-text item name against the cache.

        Strategy:
        1. Exact case-insensitive match on ItemName → return immediately.
        2. Substring match → return the first result only if all hits refer to the
           same item (deduplicated by _dedup_key). Multiple distinct items = ambiguous
           → return None.

        The caller should fall back to a Wowhead search URL when None is returned.
        """
        name_lower = name.lower()

        # Exact match — fetch one more than _BEST_MATCH_PROBE_LIMIT to detect ambiguity
        # without a separate COUNT query.
        exact_matches = (
            session.query(cls).filter(func.lower(cls.ItemName) == name_lower).limit(_BEST_MATCH_PROBE_LIMIT).all()
        )
        if exact_matches:
            if len(exact_matches) == _BEST_MATCH_PROBE_LIMIT:
                return None
            exact_keys = {r._dedup_key for r in exact_matches}
            return exact_matches[0] if len(exact_keys) == 1 else None

        # Substring match — if the result is truncated we cannot prove uniqueness, treat as ambiguous.
        matches = (
            session.query(cls)
            .filter(func.lower(cls.ItemName).contains(name_lower))
            .limit(_BEST_MATCH_PROBE_LIMIT)
            .all()
        )
        if not matches or len(matches) == _BEST_MATCH_PROBE_LIMIT:
            return None

        unique_ids = {r._dedup_key for r in matches}
        if len(unique_ids) == 1:
            return matches[0]

        return None

    @classmethod
    def count(cls, session) -> int:
        return session.query(cls).count()

    @classmethod
    def delete_all(cls, session):
        session.query(cls).delete()
