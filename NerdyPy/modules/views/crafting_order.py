# -*- coding: utf-8 -*-
"""Crafting order board views, modals, and DynamicItem buttons."""

import functools
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import discord
from discord import Interaction, ui
from sqlalchemy import update as sa_update

from models.wow import (
    RECIPE_TYPE_CRAFTED,
    RECIPE_TYPE_HOUSING,
    CraftingBoardConfig,
    CraftingOrder,
    CraftingRecipeCache,
    CraftingRoleMapping,
)
from utils.blizzard import CRAFTING_PROFESSIONS
from utils.errors import NerpyInfraException
from utils.strings import get_string

log = logging.getLogger(__name__)

# Discord select menu hard limit — options beyond this index are silently dropped.
_DISCORD_SELECT_LIMIT = 24


@dataclass
class CraftingRecipeContext:
    """Groups recipe-metadata fields passed from the cache-driven flow into CraftingOrderModal."""

    item_name: str
    item_name_english: str | None = None
    icon_url: str | None = None
    wowhead_url: str | None = None


@dataclass
class NavContext:
    """Bundles the stable navigation parameters shared by all _navigate_* helpers."""

    bot: Any
    roles: list[discord.Role]
    guild_id: int
    lang: str
    mapped_prof_ids: set[int] | None


# ---------------------------------------------------------------------------
# Virtual category sentinel values
# ---------------------------------------------------------------------------

_VCAT_PVP = "__pvp__"
_VCAT_RAID_PREP = "__raid_prep__"
_VCAT_ARMOR = "__armor__"
_VCAT_WEAPONS = "__weapons__"
_VCAT_PROFESSIONS = "__professions__"
_VCAT_OTHER = "__other_cat__"

_VCAT_LABEL_KEYS = {
    _VCAT_PVP: ("⚔️ ", "pvp_category"),
    _VCAT_RAID_PREP: ("🧪 ", "raid_prep_category"),
    _VCAT_ARMOR: ("🛡️ ", "armor_category"),
    _VCAT_WEAPONS: ("⚔️ ", "weapons_category"),
    _VCAT_PROFESSIONS: ("🔧 ", "professions_category"),
    _VCAT_OTHER: ("📦 ", "other_category"),
}

_EMOJI_MAP: dict[str, str] = {
    # Armor subtypes
    "plate": "🛡️",
    "mail": "🔗",
    "leather": "🧥",
    "cloth": "🧵",
    "shield": "🛡️",
    "cosmetic": "🎭",
    "miscellaneous": "📦",
    # Weapon subtypes
    "dagger": "🗡️",
    "sword": "⚔️",
    "axe": "🪓",
    "mace": "🔨",
    "staff": "🪄",
    "stave": "🪄",
    "wand": "✨",
    "bow": "🏹",
    "gun": "🔫",
    "fist": "👊",
    "polearm": "🔱",
    "glaive": "🗡️",
    "off-hand": "📖",
    # Consumables / Raid Prep
    "flask": "🧪",
    "phial": "🧪",
    "potion": "🧫",
    "cauldron": "🫕",
    "feast": "🍖",
    "food": "🍲",
    "rune": "🔮",
    "tea": "🍵",
    # Profession gear
    "profession": "🔧",
    "tool": "🔧",
    # Other
    "bag": "🎒",
    "gem": "💎",
    "enchant": "✨",
    "embellishment": "🪡",
    "transmut": "⚗️",
    "treatise": "📚",
    "alloy": "⛏️",
    # Gems / Jewelcrafting
    "diamond": "💎",
    "amethyst": "💎",
    "garnet": "💎",
    "lapis": "💎",
    "peridot": "💎",
    "jewel": "💎",
    "ring": "💍",
    "locket": "📿",
    # Engineering
    "cogwheel": "⚙️",
    "bot": "🤖",
    "parts": "⚙️",
    "bits": "⚙️",
    # Alchemy
    "alchemist": "⚗️",
    # Enchanting / Inscription / Misc craft
    "illusion": "🌀",
    "shatter": "💥",
    "contract": "📜",
    "myster": "🔮",
    "rod": "🪄",
    "spellthread": "🧵",
    "glamour": "🎭",
    # Tailoring
    "garment": "👗",
    "couture": "👗",
    "wardrobe": "👔",
    # Recycling / Salvage
    "recraft": "♻️",
    "salvage": "♻️",
    # Housing
    "decor": "🏠",
    # Progression tiers (Engineering)
    "starter": "🔰",
    "intermediate": "📗",
    "advanced": "📘",
    "master": "🏆",
    # Generic fallbacks — must stay at the END to avoid clobbering specific matches above
    "competitor": "⚔️",
    "reagent": "🧬",
    "consumable": "🧪",
    "trinket": "📿",
    "combat": "⚔️",
    "stonework": "🪨",
    "armor": "🛡️",
    "weapon": "⚔️",
    "fish": "🎣",
    "other": "📦",
}


def _emoji_for(name: str) -> str:
    """Return a matching emoji + space for a category/subclass name, or empty string."""
    name_lower = name.lower()
    for keyword, emoji in _EMOJI_MAP.items():
        if keyword in name_lower:
            return emoji + " "
    return ""


_PVP_GROUP_WEAPONS = "__pvp_weapons__"
_PVP_GROUP_GEAR = "__pvp_gear__"
_PROF_GROUP_GEAR = "__prof_gear__"
_PROF_GROUP_KNOWLEDGE = "__prof_knowledge__"

# Maps gear-bucket vcats to the lowercase ItemClassName used in the recipe cache.
# Must match the Blizzard API item class names (lowercased) stored in CraftingRecipeCache.
_VCAT_TO_CLASS_NAME: dict[str, str] = {
    _VCAT_ARMOR: "armor",
    _VCAT_WEAPONS: "weapon",
    _VCAT_PROFESSIONS: "profession",
}

# ---------------------------------------------------------------------------
# Locale key constants (full paths — typos become NameError at import time)
# ---------------------------------------------------------------------------
_KEY_BACK_BUTTON = "wow.craftingorder.back_button"
_KEY_BOARD_TITLE = "wow.craftingorder.board_title"
_KEY_ARMOR_CATEGORY = "wow.craftingorder.armor_category"
_KEY_WEAPONS_CATEGORY = "wow.craftingorder.weapons_category"
_KEY_PROFESSION_SELECT = "wow.craftingorder.profession_select"
_KEY_NO_PROFESSION_MAPPED = "wow.craftingorder.no_profession_mapped"
_KEY_CREATE_NO_ROLES = "wow.craftingorder.create.no_roles"
_KEY_ITEM_TYPE_SELECT = "wow.craftingorder.item_type_select"
_KEY_ITEM_SUBTYPE_SELECT = "wow.craftingorder.item_subtype_select"
_KEY_ITEM_SUBTYPE_SELECT_DESC = "wow.craftingorder.item_subtype_select_desc"
_KEY_VIRTUAL_CATEGORY_SELECT = "wow.craftingorder.virtual_category_select"
_KEY_VIRTUAL_CATEGORY_SELECT_DESC = "wow.craftingorder.virtual_category_select_desc"
_KEY_PVP_GROUP_SELECT = "wow.craftingorder.pvp_group_select"
_KEY_PVP_GROUP_SELECT_DESC = "wow.craftingorder.pvp_group_select_desc"
_KEY_PROF_GROUP_SELECT = "wow.craftingorder.prof_group_select"
_KEY_PROF_GROUP_SELECT_DESC = "wow.craftingorder.prof_group_select_desc"
_KEY_PROF_GEAR_OPTION = "wow.craftingorder.prof_gear_option"
_KEY_PROF_KNOWLEDGE_OPTION = "wow.craftingorder.prof_knowledge_option"
_KEY_RAID_PREP_SELECT = "wow.craftingorder.raid_prep_select"
_KEY_RAID_PREP_SELECT_DESC = "wow.craftingorder.raid_prep_select_desc"
_KEY_OTHER_SELECT = "wow.craftingorder.other_select"
_KEY_OTHER_SELECT_DESC = "wow.craftingorder.other_select_desc"
_KEY_ITEM_SELECT = "wow.craftingorder.item_select"
_KEY_ITEM_SELECT_DESC = "wow.craftingorder.item_select_desc"
_KEY_OTHER_BUTTON = "wow.craftingorder.other_button"
_KEY_CHOOSE_BUTTON = "wow.craftingorder.choose_button"
_KEY_HOUSING_PROFESSION_SELECT = "wow.craftingorder.housing_profession_select"
_KEY_HOUSING_PROFESSION_SELECT_DESC = "wow.craftingorder.housing_profession_select_desc"
_KEY_EXPANSION_SELECT = "wow.craftingorder.expansion_select"
_KEY_EXPANSION_SELECT_DESC = "wow.craftingorder.expansion_select_desc"
_KEY_MODAL_TITLE = "wow.craftingorder.modal_title"
_KEY_MODAL_ITEM_NAME = "wow.craftingorder.modal_item_name"
_KEY_MODAL_NOTES = "wow.craftingorder.modal_notes"
_KEY_ORDER_PROFESSION = "wow.craftingorder.order.profession"
_KEY_ORDER_STATUS = "wow.craftingorder.order.status"
_KEY_ORDER_POSTED_BY = "wow.craftingorder.order.posted_by"
_KEY_ORDER_NOTES = "wow.craftingorder.order.notes"
_KEY_ASK_MODAL_TITLE = "wow.craftingorder.ask.modal_title"
_KEY_ASK_MODAL_MESSAGE = "wow.craftingorder.ask.modal_message"
_KEY_MANUAL_MAP_SELECT_PLACEHOLDER = "wow.craftingorder.manual_map.select_placeholder"
_KEY_MANUAL_MAP_CONFIRM_BUTTON = "wow.craftingorder.manual_map.confirm_button"
_KEY_MANUAL_MAP_NO_SELECTIONS = "wow.craftingorder.manual_map.no_selections"
_KEY_MANUAL_MAP_NEXT_BATCH = "wow.craftingorder.manual_map.next_batch"
_KEY_MANUAL_MAP_DESCRIPTION = "wow.craftingorder.manual_map.description"
_KEY_MANUAL_MAP_SUCCESS = "wow.craftingorder.manual_map.success"
_KEY_MANUAL_MAP_PARTIAL = "wow.craftingorder.manual_map.partial"
_KEY_PAGE_INFO = "wow.craftingorder.page_info"


def _build_vcat_info(recipe_type: str, session, profession_ids) -> tuple[list[str], dict[str, int], dict[str, int]]:
    """Check which virtual categories have items and build the item class ID maps.

    Returns:
        available_vcats: ordered list of vcat sentinel keys that have ≥1 item
        item_class_ids: lower(ItemClassName) → ItemClassId for non-PvP orderable classes
        pvp_item_class_ids: lower(ItemClassName) → ItemClassId for PvP item classes
    """
    available = []

    # Non-PvP orderable classes (Armor, Weapon, Profession, …).
    all_classes = CraftingRecipeCache.get_item_classes(
        recipe_type, session, profession_ids=profession_ids, orderable_only=True, exclude_pvp=True
    )
    item_class_ids = {name.lower(): cls_id for cls_id, name, _ in all_classes if name}

    # PvP classes queried separately so the sub-picker is driven by accurate availability.
    pvp_classes = CraftingRecipeCache.get_pvp_item_classes(recipe_type, session, profession_ids)
    pvp_item_class_ids = {name.lower(): cls_id for cls_id, name, _ in pvp_classes if name}

    if pvp_item_class_ids:
        available.append(_VCAT_PVP)
    if CraftingRecipeCache.get_raid_prep_categories(recipe_type, session, profession_ids):
        available.append(_VCAT_RAID_PREP)
    for vcat in (_VCAT_ARMOR, _VCAT_WEAPONS):
        if _VCAT_TO_CLASS_NAME[vcat] in item_class_ids:
            available.append(vcat)
    has_prof_gear = _VCAT_TO_CLASS_NAME[_VCAT_PROFESSIONS] in item_class_ids
    has_prof_knowledge = CraftingRecipeCache.has_prof_knowledge_items(recipe_type, session, profession_ids)
    if has_prof_gear or has_prof_knowledge:
        available.append(_VCAT_PROFESSIONS)
        if has_prof_knowledge:
            item_class_ids[_PROF_GROUP_KNOWLEDGE] = 1  # sentinel: presence means knowledge items exist
    if CraftingRecipeCache.get_other_categories(recipe_type, session, profession_ids):
        available.append(_VCAT_OTHER)

    return available, item_class_ids, pvp_item_class_ids


async def _navigate_prof_gear(
    interaction: Interaction,
    ctx: NavContext,
    item_class_ids,
    breadcrumbs=None,
    back_factory=None,
):
    """Shared navigation helper: fetch profession gear subclasses and show ItemSubTypeSelectView."""
    class_id = item_class_ids.get(_VCAT_TO_CLASS_NAME[_VCAT_PROFESSIONS])
    if class_id is None:
        await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
        return
    with ctx.bot.session_scope() as session:
        subclasses = CraftingRecipeCache.get_item_subclasses(
            RECIPE_TYPE_CRAFTED,
            class_id,
            session,
            profession_ids=ctx.mapped_prof_ids,
            orderable_only=True,
            exclude_pvp=False,
        )
    view = ItemSubTypeSelectView(
        ctx.bot,
        ctx.roles,
        ctx.guild_id,
        ctx.lang,
        class_id,
        subclasses,
        ctx.mapped_prof_ids,
        orderable_only=True,
        exclude_pvp=False,
        breadcrumbs=breadcrumbs,
        back_factory=back_factory,
    )
    embed = view._make_embed()
    await interaction.response.edit_message(embed=embed, view=view, content=None)


async def _navigate_prof_knowledge(
    interaction: Interaction,
    ctx: NavContext,
    breadcrumbs=None,
    back_factory=None,
):
    """Shared navigation helper: fetch profession knowledge items and show ItemSelectView."""
    with ctx.bot.session_scope() as session:
        recipes = CraftingRecipeCache.get_prof_knowledge_items(
            RECIPE_TYPE_CRAFTED, session, profession_ids=ctx.mapped_prof_ids
        )
    view = ItemSelectView(
        ctx.bot, recipes, ctx.roles, ctx.guild_id, ctx.lang, breadcrumbs=breadcrumbs, back_factory=back_factory
    )
    embed = view._make_embed()
    await interaction.response.edit_message(embed=embed, view=view, content=None)


async def _navigate_pvp_weapons(
    interaction: Interaction,
    ctx: NavContext,
    weapon_class_id,
    breadcrumbs=None,
    back_factory=None,
):
    """Shared navigation helper: fetch PvP weapon recipes and show ItemSelectView.

    If there are more than 24 weapons, routes to a weapon-subtype picker first so no
    items are silently truncated by the Discord select menu limit.
    """
    with ctx.bot.session_scope() as session:
        recipes = CraftingRecipeCache.get_pvp_items(
            RECIPE_TYPE_CRAFTED, weapon_class_id, None, session, profession_ids=ctx.mapped_prof_ids
        )
        if len(recipes) > _DISCORD_SELECT_LIMIT:
            subclasses = CraftingRecipeCache.get_pvp_item_subclasses(
                RECIPE_TYPE_CRAFTED, weapon_class_id, session, profession_ids=ctx.mapped_prof_ids
            )
        else:
            subclasses = []

    if subclasses:
        view = PvPSubTypeSelectView(
            ctx.bot,
            ctx.roles,
            ctx.guild_id,
            ctx.lang,
            weapon_class_id,
            subclasses,
            ctx.mapped_prof_ids,
            placeholder_key="pvp_weapon_select",
            breadcrumbs=breadcrumbs,
            back_factory=back_factory,
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)
        return

    view = ItemSelectView(
        ctx.bot, recipes, ctx.roles, ctx.guild_id, ctx.lang, breadcrumbs=breadcrumbs, back_factory=back_factory
    )
    embed = view._make_embed()
    await interaction.response.edit_message(embed=embed, view=view, content=None)


async def _navigate_pvp_armor(
    interaction: Interaction,
    ctx: NavContext,
    armor_class_id,
    breadcrumbs=None,
    back_factory=None,
):
    """Shared navigation helper: fetch PvP armor subclasses and show PvPArmorTypeSelectView."""
    with ctx.bot.session_scope() as session:
        subclasses = CraftingRecipeCache.get_pvp_item_subclasses(
            RECIPE_TYPE_CRAFTED, armor_class_id, session, profession_ids=ctx.mapped_prof_ids
        )
    view = PvPArmorTypeSelectView(
        ctx.bot,
        ctx.roles,
        ctx.guild_id,
        ctx.lang,
        armor_class_id,
        subclasses,
        ctx.mapped_prof_ids,
        breadcrumbs=breadcrumbs,
        back_factory=back_factory,
    )
    embed = view._make_embed()
    await interaction.response.edit_message(embed=embed, view=view, content=None)


def _ls(interaction: Interaction, key: str, **kwargs) -> str:
    """Shorthand for localized string lookup."""
    return interaction.client.get_localized_string(interaction.guild_id, f"wow.craftingorder.{key}", **kwargs)


def _build_step_embed(
    title: str, description: str, breadcrumbs: list[str] | None, footer: str | None = None
) -> discord.Embed:
    """Build a step embed with optional breadcrumbs appended to description."""
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
    if breadcrumbs:
        embed.description = (embed.description or "") + f"\n\n-# {' > '.join(breadcrumbs)}"
    if footer:
        embed.set_footer(text=footer)
    return embed


def _add_back_button(view: ui.View, lang: str, callback, row: int = 4) -> None:
    """Add a secondary back button to *view* on the given row (default 4)."""
    btn = ui.Button(
        label=get_string(lang, _KEY_BACK_BUTTON),
        style=discord.ButtonStyle.secondary,
        emoji="◀",
        row=row,
    )
    btn.callback = callback
    view.add_item(btn)


def _nav_back(make_view):
    """Return a back-navigation callback that calls *make_view()* and edits the message."""

    async def _go_back(itx: Interaction) -> None:
        view = make_view()
        embed = view._make_embed()
        await itx.response.edit_message(embed=embed, view=view, content=None)

    return _go_back


def _get_locale(locales: dict | None, lang: str) -> str | None:
    """Return the localized string for ``lang`` from a locale dict, or None for English / missing."""
    return (locales or {}).get(lang) if lang != "en" else None


def _find_localized_label(entries: list[tuple[int | str, str, dict | None]], key: int | str, lang: str) -> str | None:
    """Find ``key`` in ``(key, name, locales)`` triples and return the localized label, or None."""
    for entry_key, name, locales in entries:
        if entry_key == key:
            return _get_locale(locales, lang) or name
    return None


def _resolve_subtype_label(subclasses: list[tuple[int, str, dict | None]], item_id: int, lang: str) -> str:
    """Return the localized label for ``item_id`` from a ``(id, name, locales)`` subclass list."""
    return _find_localized_label(subclasses, item_id, lang) or str(item_id)


def _resolve_category_label(categories: list[tuple[str, dict | None]], category_name: str, lang: str) -> str:
    """Return the localized label for ``category_name`` from a ``(name, locales)`` category list."""
    return _find_localized_label([(n, n, loc) for n, loc in categories], category_name, lang) or category_name


def _build_localized_options(
    items: list[tuple[int | str, str | None, dict | None]], lang: str, emojis: bool = False
) -> list[discord.SelectOption]:
    """Build SelectOptions from (id, english_name, locales) tuples.

    Label is the localized name when available, falling back to the English name.
    Description shows the English name only when a different localized label is shown.
    Options are sorted by the displayed label so the dropdown order matches the locale.
    If emojis=True, a keyword-matched emoji prefix is prepended to each label.
    """
    keyed: list[tuple[str, discord.SelectOption]] = []
    for item_id, name, locales in items:
        localized = _get_locale(locales, lang)
        label = localized or name or "Unknown"
        prefix = _emoji_for(name or "") if emojis else ""
        description = name[:100] if localized else None
        sort_key = (localized or name or "").casefold()
        keyed.append(
            (sort_key, discord.SelectOption(label=(prefix + label)[:100], description=description, value=str(item_id)))
        )
    keyed.sort(key=lambda x: x[0])
    return [o for _, o in keyed[:25]]


def _build_localized_category_options(
    categories: list[tuple[str, dict | None]], lang: str
) -> list[discord.SelectOption]:
    """Build SelectOptions from (category_name, locales) tuples.

    The value is always the English category name (used for DB lookups in callbacks).
    Emoji prefixes are always applied based on keyword matching.
    """
    return _build_localized_options([(name, name, locales) for name, locales in categories], lang, emojis=True)


def _display_item_name(order: CraftingOrder) -> str:
    """Return item name for user-facing messages.

    If a localized name is stored, returns 'Localized (English)' so the
    recipient can identify the item regardless of their own language.
    """
    if order.ItemNameLocalized:
        return f"{order.ItemNameLocalized} ({order.ItemName})"
    return order.ItemName


def build_order_embed(order: CraftingOrder, guild: discord.Guild, lang: str = "en") -> discord.Embed:
    """Build the embed for a crafting order."""
    role = guild.get_role(order.ProfessionRoleId)
    role_display = role.mention if role else f"Role #{order.ProfessionRoleId}"

    status_key = f"wow.craftingorder.order.status_{order.Status}"
    if order.Status == "in_progress" and order.CrafterId:
        status_text = get_string(lang, status_key, crafter=f"<@{order.CrafterId}>")
    else:
        status_text = get_string(lang, status_key)

    display_name = order.ItemNameLocalized or order.ItemName
    embed = discord.Embed(title=display_name, url=order.WowheadUrl, color=discord.Color.blue())
    if order.ItemNameLocalized:
        embed.description = f"-# {order.ItemName}"
    embed.add_field(name=get_string(lang, _KEY_ORDER_PROFESSION), value=role_display, inline=True)
    embed.add_field(name=get_string(lang, _KEY_ORDER_STATUS), value=status_text, inline=True)
    embed.add_field(name=get_string(lang, _KEY_ORDER_POSTED_BY), value=f"<@{order.CreatorId}>", inline=True)
    if order.Notes:
        embed.add_field(name=get_string(lang, _KEY_ORDER_NOTES), value=order.Notes, inline=False)
    if order.IconUrl:
        embed.set_thumbnail(url=order.IconUrl)

    return embed


def build_order_view(order_id: int, status: str, lang: str = "en") -> ui.View:
    """Construct a View with the appropriate buttons for an order's current status."""
    _s = lambda key: get_string(lang, f"wow.craftingorder.order.{key}")  # noqa: E731
    view = ui.View(timeout=None)
    if status == "open":
        view.add_item(
            ui.Button(
                label=_s("accept_button"), style=discord.ButtonStyle.success, custom_id=f"crafting:accept:{order_id}"
            )
        )
        view.add_item(
            ui.Button(
                label=_s("cancel_button"), style=discord.ButtonStyle.danger, custom_id=f"crafting:cancel:{order_id}"
            )
        )
        view.add_item(
            ui.Button(label=_s("ask_button"), style=discord.ButtonStyle.secondary, custom_id=f"crafting:ask:{order_id}")
        )
    elif status == "in_progress":
        view.add_item(
            ui.Button(
                label=_s("drop_button"), style=discord.ButtonStyle.secondary, custom_id=f"crafting:drop:{order_id}"
            )
        )
        view.add_item(
            ui.Button(
                label=_s("complete_button"),
                style=discord.ButtonStyle.success,
                custom_id=f"crafting:complete:{order_id}",
            )
        )
        view.add_item(
            ui.Button(
                label=_s("cancel_button"), style=discord.ButtonStyle.danger, custom_id=f"crafting:cancel:{order_id}"
            )
        )
        view.add_item(
            ui.Button(label=_s("ask_button"), style=discord.ButtonStyle.secondary, custom_id=f"crafting:ask:{order_id}")
        )
    return view


# ---------------------------------------------------------------------------
# Persistent Board View
# ---------------------------------------------------------------------------


class CraftingBoardView(ui.View):
    """Persistent view on the board embed with 'Create Order' and 'Request Housing' buttons.

    Button labels can be localized at board creation time. At bot restart
    (``setup_hook``), labels default to English — Discord shows the label stored
    in the original message, so it stays localized.
    """

    def __init__(self, bot, label: str | None = None, housing_label: str | None = None):
        super().__init__(timeout=None)
        self.bot = bot

        order_button = ui.Button(
            label=label or "Create Crafting Order",
            style=discord.ButtonStyle.primary,
            custom_id="crafting_create_order",
        )
        order_button.callback = self._on_create_order
        self.add_item(order_button)

        housing_button = ui.Button(
            label=housing_label or "Request Housing Item",
            style=discord.ButtonStyle.secondary,
            custom_id="crafting_create_housing",
        )
        housing_button.callback = self._on_create_housing
        self.add_item(housing_button)

    def _load_board_context(self, guild_id: int, session) -> tuple[str, set[int], list[int]] | None:
        """Load board lang + role maps from DB. Returns None if no board is configured for the guild."""
        if CraftingBoardConfig.get_by_guild(guild_id, session) is None:
            return None
        lang = self.bot.get_guild_language(guild_id)
        mapped_prof_ids: set[int] = set()
        mapping_role_ids: list[int] = []
        for m in CraftingRoleMapping.get_by_guild(guild_id, session):
            mapped_prof_ids.add(m.ProfessionId)
            mapping_role_ids.append(m.RoleId)
        return lang, mapped_prof_ids, mapping_role_ids

    async def _on_create_order(self, interaction: Interaction):
        lang = mapped_prof_ids = mapping_role_ids = available_vcats = item_class_ids = pvp_item_class_ids = None
        with self.bot.session_scope() as session:
            board_ctx = self._load_board_context(interaction.guild_id, session)
            if board_ctx is not None:
                lang, mapped_prof_ids, mapping_role_ids = board_ctx
                available_vcats, item_class_ids, pvp_item_class_ids = _build_vcat_info(
                    RECIPE_TYPE_CRAFTED, session, mapped_prof_ids
                )

        if board_ctx is None:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        roles = [r for rid in mapping_role_ids if (r := interaction.guild.get_role(rid))]
        if not roles:
            await interaction.response.send_message(_ls(interaction, "create.no_roles"), ephemeral=True)
            return

        if available_vcats:
            view = VirtualCategorySelectView(
                self.bot,
                roles,
                interaction.guild_id,
                lang,
                available_vcats,
                mapped_prof_ids,
                item_class_ids,
                pvp_item_class_ids,
                breadcrumbs=[get_string(lang, _KEY_BOARD_TITLE)],
            )
            embed = view._make_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            view = ProfessionSelectView(self.bot, roles, interaction.guild_id, lang)
            await interaction.response.send_message(_ls(interaction, "profession_select"), view=view, ephemeral=True)

    async def _on_create_housing(self, interaction: Interaction):
        lang = mapped_prof_ids = mapping_role_ids = housing_professions = None
        with self.bot.session_scope() as session:
            board_ctx = self._load_board_context(interaction.guild_id, session)
            if board_ctx is not None:
                lang, mapped_prof_ids, mapping_role_ids = board_ctx
                if mapped_prof_ids:
                    housing_professions = CraftingRecipeCache.get_professions_with_recipes(
                        RECIPE_TYPE_HOUSING, session, profession_ids=mapped_prof_ids
                    )
                else:
                    housing_professions = []

        if board_ctx is None:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        if not housing_professions:
            # Fall back to profession select (free-text flow)
            roles = [r for rid in mapping_role_ids if (r := interaction.guild.get_role(rid))]
            if not roles:
                await interaction.response.send_message(_ls(interaction, "create.no_roles"), ephemeral=True)
                return
            view = ProfessionSelectView(self.bot, roles, interaction.guild_id, lang)
            await interaction.response.send_message(_ls(interaction, "profession_select"), view=view, ephemeral=True)
            return

        view = HousingProfessionSelectView(
            self.bot,
            interaction.guild_id,
            lang,
            housing_professions,
            breadcrumbs=[get_string(lang, _KEY_BOARD_TITLE)],
        )
        embed = view._make_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# Ephemeral Selection Views
# ---------------------------------------------------------------------------


class ProfessionSelectView(ui.View):
    """Ephemeral profession selection (Step 1)."""

    def __init__(self, bot, roles: list[discord.Role], guild_id: int, lang: str = "en"):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        select = ui.Select(
            placeholder=get_string(lang, _KEY_PROFESSION_SELECT),
            options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in roles[:25]],
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        role_id = int(interaction.data["values"][0])
        role = interaction.guild.get_role(role_id)
        if role is None:
            try:
                role = await interaction.guild.fetch_role(role_id)
            except discord.HTTPException:
                role = None
        if role is None:
            await interaction.response.send_message(_ls(interaction, "no_profession_mapped"), ephemeral=True)
            return
        modal = CraftingOrderModal(self.bot, role_id, role, self.guild_id, self.lang)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Cache-driven flows: ItemTypeSelectView, ItemSubTypeSelectView, ItemSelectView,
# HousingProfessionSelectView, ExpansionSelectView
# ---------------------------------------------------------------------------


class ItemTypeSelectView(ui.View):
    """Equippable order flow step 1: select item class (Armor, Weapon, Consumable, …)."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        item_classes: list[tuple[int, str, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        orderable_only: bool = False,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.orderable_only = orderable_only

        options = _build_localized_options(item_classes, lang)
        select = ui.Select(
            placeholder=get_string(lang, _KEY_ITEM_TYPE_SELECT),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        item_class_id = int(interaction.data["values"][0])
        with self.bot.session_scope() as session:
            subclasses = CraftingRecipeCache.get_item_subclasses(
                RECIPE_TYPE_CRAFTED,
                item_class_id,
                session,
                profession_ids=self.mapped_prof_ids,
                orderable_only=self.orderable_only,
            )

        if not subclasses:
            # No subclasses — go straight to item select
            with self.bot.session_scope() as session:
                recipes = CraftingRecipeCache.get_by_type_and_subclass(
                    RECIPE_TYPE_CRAFTED,
                    item_class_id,
                    None,
                    session,
                    profession_ids=self.mapped_prof_ids,
                    orderable_only=self.orderable_only,
                )
            view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
            embed = view._make_embed()
            await interaction.response.edit_message(embed=embed, view=view, content=None)
            return

        view = ItemSubTypeSelectView(
            self.bot,
            self.roles,
            self.guild_id,
            self.lang,
            item_class_id,
            subclasses,
            self.mapped_prof_ids,
            self.orderable_only,
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


class ItemSubTypeSelectView(ui.View):
    """Equippable order flow step 2: select item subclass (Plate, Cloth, Sword, …)."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        item_class_id: int,
        subclasses: list[tuple[int, str, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        orderable_only: bool = False,
        exclude_pvp: bool = False,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.item_class_id = item_class_id
        self._subclasses = subclasses
        self.mapped_prof_ids = mapped_prof_ids
        self.orderable_only = orderable_only
        self.exclude_pvp = exclude_pvp
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        options = _build_localized_options(subclasses, lang, emojis=True)
        select = ui.Select(
            placeholder=get_string(lang, _KEY_ITEM_SUBTYPE_SELECT),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_ITEM_SUBTYPE_SELECT)
        desc = get_string(self.lang, _KEY_ITEM_SUBTYPE_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this ItemSubTypeSelectView."""
        return _nav_back(
            lambda: ItemSubTypeSelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self.item_class_id,
                self._subclasses,
                self.mapped_prof_ids,
                self.orderable_only,
                self.exclude_pvp,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_select(self, interaction: Interaction):
        item_subclass_id = int(interaction.data["values"][0])

        selected_label = _resolve_subtype_label(self._subclasses, item_subclass_id, self.lang)

        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_by_type_and_subclass(
                RECIPE_TYPE_CRAFTED,
                self.item_class_id,
                item_subclass_id,
                session,
                profession_ids=self.mapped_prof_ids,
                orderable_only=self.orderable_only,
                exclude_pvp=self.exclude_pvp,
            )

        view = ItemSelectView(
            self.bot,
            recipes,
            self.roles,
            self.guild_id,
            self.lang,
            breadcrumbs=self._breadcrumbs + [selected_label],
            back_factory=self._make_back_closure(),
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


class VirtualCategorySelectView(ui.View):
    """Crafted order flow entry: choose a virtual category (PvP, Raid Prep, Armor, …).

    Categories are shown as buttons instead of a dropdown.
    """

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        available_vcats: list[str],
        mapped_prof_ids: set[int] | None,
        item_class_ids: dict[str, int],
        pvp_item_class_ids: dict[str, int] | None = None,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.item_class_ids = item_class_ids
        self.pvp_item_class_ids = pvp_item_class_ids or {}
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory
        self._available_vcats = available_vcats

        for i, vcat in enumerate(available_vcats):
            emoji_str, key = _VCAT_LABEL_KEYS[vcat]
            label = get_string(lang, f"wow.craftingorder.{key}")
            btn = ui.Button(
                label=label,
                emoji=emoji_str.strip() or None,
                style=discord.ButtonStyle.primary,
                row=i // 3,
            )
            btn.callback = functools.partial(self._on_category, vcat=vcat)
            self.add_item(btn)

        if back_factory is not None:
            back_row = (len(available_vcats) - 1) // 3 + 1 if available_vcats else 1
            _add_back_button(self, lang, back_factory, row=back_row)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_VIRTUAL_CATEGORY_SELECT)
        desc = get_string(self.lang, _KEY_VIRTUAL_CATEGORY_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this VirtualCategorySelectView."""
        return _nav_back(
            lambda: VirtualCategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self._available_vcats,
                self.mapped_prof_ids,
                self.item_class_ids,
                self.pvp_item_class_ids,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_category(self, interaction: Interaction, vcat: str):
        new_breadcrumbs = self._breadcrumbs + [get_string(self.lang, f"wow.craftingorder.{_VCAT_LABEL_KEYS[vcat][1]}")]
        go_back = self._make_back_closure()

        if vcat == _VCAT_PVP:
            weapon_class_name = _VCAT_TO_CLASS_NAME[_VCAT_WEAPONS]
            armor_class_name = _VCAT_TO_CLASS_NAME[_VCAT_ARMOR]
            has_pvp_weapons = weapon_class_name in self.pvp_item_class_ids
            has_pvp_armor = armor_class_name in self.pvp_item_class_ids

            _ctx = NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids)
            if has_pvp_weapons and not has_pvp_armor:
                await _navigate_pvp_weapons(
                    interaction,
                    _ctx,
                    self.pvp_item_class_ids[weapon_class_name],
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )
            elif has_pvp_armor and not has_pvp_weapons:
                await _navigate_pvp_armor(
                    interaction,
                    _ctx,
                    self.pvp_item_class_ids[armor_class_name],
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )
            else:
                view = PvPGroupSelectView(
                    self.bot,
                    self.roles,
                    self.guild_id,
                    self.lang,
                    self.mapped_prof_ids,
                    self.pvp_item_class_ids,
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )
                embed = view._make_embed()
                await interaction.response.edit_message(embed=embed, view=view, content=None)

        elif vcat == _VCAT_RAID_PREP:
            with self.bot.session_scope() as session:
                categories = CraftingRecipeCache.get_raid_prep_categories(
                    RECIPE_TYPE_CRAFTED, session, profession_ids=self.mapped_prof_ids
                )
            view = RaidPrepCategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                categories,
                self.mapped_prof_ids,
                breadcrumbs=new_breadcrumbs,
                back_factory=go_back,
            )
            embed = view._make_embed()
            await interaction.response.edit_message(embed=embed, view=view, content=None)

        elif vcat in (_VCAT_ARMOR, _VCAT_WEAPONS):
            class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[vcat])
            if class_id is None:
                await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
                return

            with self.bot.session_scope() as session:
                subclasses = CraftingRecipeCache.get_item_subclasses(
                    RECIPE_TYPE_CRAFTED,
                    class_id,
                    session,
                    profession_ids=self.mapped_prof_ids,
                    orderable_only=True,
                    exclude_pvp=True,
                )
            view = ItemSubTypeSelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                class_id,
                subclasses,
                self.mapped_prof_ids,
                orderable_only=True,
                exclude_pvp=True,
                breadcrumbs=new_breadcrumbs,
                back_factory=go_back,
            )
            embed = view._make_embed()
            await interaction.response.edit_message(embed=embed, view=view, content=None)

        elif vcat == _VCAT_PROFESSIONS:
            has_gear = _VCAT_TO_CLASS_NAME[_VCAT_PROFESSIONS] in self.item_class_ids
            has_knowledge = _PROF_GROUP_KNOWLEDGE in self.item_class_ids

            if has_gear and has_knowledge:
                view = ProfessionGroupSelectView(
                    self.bot,
                    self.roles,
                    self.guild_id,
                    self.lang,
                    self.mapped_prof_ids,
                    self.item_class_ids,
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )
                embed = view._make_embed()
                await interaction.response.edit_message(embed=embed, view=view, content=None)
            elif has_gear:
                await _navigate_prof_gear(
                    interaction,
                    NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
                    self.item_class_ids,
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )
            elif has_knowledge:
                await _navigate_prof_knowledge(
                    interaction,
                    NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
                    breadcrumbs=new_breadcrumbs,
                    back_factory=go_back,
                )

        elif vcat == _VCAT_OTHER:
            with self.bot.session_scope() as session:
                categories = CraftingRecipeCache.get_other_categories(
                    RECIPE_TYPE_CRAFTED, session, profession_ids=self.mapped_prof_ids
                )
            view = OtherCategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                categories,
                self.mapped_prof_ids,
                breadcrumbs=new_breadcrumbs,
                back_factory=go_back,
            )
            embed = view._make_embed()
            await interaction.response.edit_message(embed=embed, view=view, content=None)


class PvPGroupSelectView(ui.View):
    """PvP flow step 1: choose Weapons or Gear — shown as buttons."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        mapped_prof_ids: set[int] | None = None,
        item_class_ids: dict[str, int] | None = None,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.item_class_ids = item_class_ids or {}
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        weapons_btn = ui.Button(
            label=get_string(lang, _KEY_WEAPONS_CATEGORY),
            emoji="⚔️",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        weapons_btn.callback = self._on_weapons
        self.add_item(weapons_btn)

        gear_btn = ui.Button(
            label=get_string(lang, _KEY_ARMOR_CATEGORY),
            emoji="🛡️",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        gear_btn.callback = self._on_gear
        self.add_item(gear_btn)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_PVP_GROUP_SELECT)
        desc = get_string(self.lang, _KEY_PVP_GROUP_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this PvPGroupSelectView."""
        return _nav_back(
            lambda: PvPGroupSelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self.mapped_prof_ids,
                self.item_class_ids,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_weapons(self, interaction: Interaction):
        weapon_class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[_VCAT_WEAPONS])
        if weapon_class_id is None:
            await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
            return
        new_breadcrumbs = self._breadcrumbs + [get_string(self.lang, _KEY_WEAPONS_CATEGORY)]
        await _navigate_pvp_weapons(
            interaction,
            NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
            weapon_class_id,
            breadcrumbs=new_breadcrumbs,
            back_factory=self._make_back_closure(),
        )

    async def _on_gear(self, interaction: Interaction):
        armor_class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[_VCAT_ARMOR])
        if armor_class_id is None:
            await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
            return
        new_breadcrumbs = self._breadcrumbs + [get_string(self.lang, _KEY_ARMOR_CATEGORY)]
        await _navigate_pvp_armor(
            interaction,
            NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
            armor_class_id,
            breadcrumbs=new_breadcrumbs,
            back_factory=self._make_back_closure(),
        )


class ProfessionGroupSelectView(ui.View):
    """Professions flow step 1: choose Gear or Knowledge — shown as buttons."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        mapped_prof_ids: set[int] | None = None,
        item_class_ids: dict[str, int] | None = None,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.item_class_ids = item_class_ids or {}
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        if _VCAT_TO_CLASS_NAME[_VCAT_PROFESSIONS] in self.item_class_ids:
            gear_btn = ui.Button(
                label=get_string(lang, _KEY_PROF_GEAR_OPTION),
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                row=0,
            )
            gear_btn.callback = self._on_gear
            self.add_item(gear_btn)

        if _PROF_GROUP_KNOWLEDGE in self.item_class_ids:
            knowledge_btn = ui.Button(
                label=get_string(lang, _KEY_PROF_KNOWLEDGE_OPTION),
                emoji="📚",
                style=discord.ButtonStyle.primary,
                row=0,
            )
            knowledge_btn.callback = self._on_knowledge
            self.add_item(knowledge_btn)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_PROF_GROUP_SELECT)
        desc = get_string(self.lang, _KEY_PROF_GROUP_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this ProfessionGroupSelectView."""
        return _nav_back(
            lambda: ProfessionGroupSelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self.mapped_prof_ids,
                self.item_class_ids,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_gear(self, interaction: Interaction):
        new_breadcrumbs = self._breadcrumbs + [get_string(self.lang, _KEY_PROF_GEAR_OPTION)]
        await _navigate_prof_gear(
            interaction,
            NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
            self.item_class_ids,
            breadcrumbs=new_breadcrumbs,
            back_factory=self._make_back_closure(),
        )

    async def _on_knowledge(self, interaction: Interaction):
        new_breadcrumbs = self._breadcrumbs + [get_string(self.lang, _KEY_PROF_KNOWLEDGE_OPTION)]
        await _navigate_prof_knowledge(
            interaction,
            NavContext(self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids),
            breadcrumbs=new_breadcrumbs,
            back_factory=self._make_back_closure(),
        )


class PvPSubTypeSelectView(ui.View):
    """PvP flow: choose an item subtype (armor type or weapon type), then items."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        item_class_id: int,
        subclasses: list[tuple[int, str | None, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        placeholder_key: str = "pvp_armor_select",
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.item_class_id = item_class_id
        self._subclasses = subclasses
        self.mapped_prof_ids = mapped_prof_ids
        self._placeholder_key = placeholder_key
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        options = _build_localized_options(subclasses, lang, emojis=True)
        select = ui.Select(
            placeholder=get_string(lang, f"wow.craftingorder.{placeholder_key}"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, f"wow.craftingorder.{self._placeholder_key}")
        desc = get_string(self.lang, f"wow.craftingorder.{self._placeholder_key}_desc")
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this PvPSubTypeSelectView."""
        return _nav_back(
            lambda: PvPSubTypeSelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self.item_class_id,
                self._subclasses,
                self.mapped_prof_ids,
                placeholder_key=self._placeholder_key,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_select(self, interaction: Interaction):
        item_subclass_id = int(interaction.data["values"][0])

        selected_label = _resolve_subtype_label(self._subclasses, item_subclass_id, self.lang)

        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_pvp_items(
                RECIPE_TYPE_CRAFTED, self.item_class_id, item_subclass_id, session, profession_ids=self.mapped_prof_ids
            )
        if len(recipes) > _DISCORD_SELECT_LIMIT:
            log.warning(
                "PvP subtype overflow: class_id=%d subclass_id=%d returned %d recipes (>24); paginating",
                self.item_class_id,
                item_subclass_id,
                len(recipes),
            )

        view = ItemSelectView(
            self.bot,
            recipes,
            self.roles,
            self.guild_id,
            self.lang,
            breadcrumbs=self._breadcrumbs + [selected_label],
            back_factory=self._make_back_closure(),
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


PvPArmorTypeSelectView = PvPSubTypeSelectView


class RaidPrepCategorySelectView(ui.View):
    """Raid prep flow: choose consumable/cauldron category, then items."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        categories: list[tuple[str, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self._categories = categories
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        select = ui.Select(
            placeholder=get_string(lang, _KEY_RAID_PREP_SELECT),
            options=_build_localized_category_options(categories, lang),
        )
        select.callback = self._on_select
        self.add_item(select)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_RAID_PREP_SELECT)
        desc = get_string(self.lang, _KEY_RAID_PREP_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this RaidPrepCategorySelectView."""
        return _nav_back(
            lambda: RaidPrepCategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self._categories,
                self.mapped_prof_ids,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_select(self, interaction: Interaction):
        category_name = interaction.data["values"][0]

        selected_label = _resolve_category_label(self._categories, category_name, self.lang)

        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_raid_prep_items(
                RECIPE_TYPE_CRAFTED, category_name, session, profession_ids=self.mapped_prof_ids
            )
        if len(recipes) > _DISCORD_SELECT_LIMIT:
            log.warning(
                "Raid prep category overflow: category=%r returned %d recipes (>24); paginating",
                category_name,
                len(recipes),
            )

        view = ItemSelectView(
            self.bot,
            recipes,
            self.roles,
            self.guild_id,
            self.lang,
            breadcrumbs=self._breadcrumbs + [selected_label],
            back_factory=self._make_back_closure(),
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


class OtherCategorySelectView(ui.View):
    """Other bucket flow: choose a category (bags, treatises, transmutations, …), then items."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        categories: list[tuple[str, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self._categories = categories
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        select = ui.Select(
            placeholder=get_string(lang, _KEY_OTHER_SELECT),
            options=_build_localized_category_options(categories, lang),
        )
        select.callback = self._on_select
        self.add_item(select)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_OTHER_SELECT)
        desc = get_string(self.lang, _KEY_OTHER_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this OtherCategorySelectView."""
        return _nav_back(
            lambda: OtherCategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self._categories,
                self.mapped_prof_ids,
                breadcrumbs=list(self._breadcrumbs),
                back_factory=self._back_factory,
            )
        )

    async def _on_select(self, interaction: Interaction):
        category_name = interaction.data["values"][0]

        selected_label = _resolve_category_label(self._categories, category_name, self.lang)

        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_other_items(
                RECIPE_TYPE_CRAFTED, category_name, session, profession_ids=self.mapped_prof_ids
            )
        if len(recipes) > _DISCORD_SELECT_LIMIT:
            log.warning(
                "Other category overflow: category=%r returned %d recipes (>24); paginating",
                category_name,
                len(recipes),
            )

        view = ItemSelectView(
            self.bot,
            recipes,
            self.roles,
            self.guild_id,
            self.lang,
            breadcrumbs=self._breadcrumbs + [selected_label],
            back_factory=self._make_back_closure(),
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


class ItemSelectView(ui.View):
    """Shared item selection step: shows up to 25 cached recipes with paginated Prev/Next buttons.

    - All 25 select slots are real items (no sentinel option consuming a slot).
    - Pagination uses ◀/▶ emoji-only buttons (row 1), shown only when total items > 25.
    - 'Other' (free-text fallback) and 'Back' are text buttons on row 1 (single-page) or row 2 (multi-page).
    - Selecting an item shows a preview embed with a 'Choose' button before opening the modal.
    """

    _PAGE_SIZE = 25

    def __init__(
        self,
        bot,
        recipes: list,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        page: int = 1,
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory
        self._page = page
        self._selected_recipe = None
        self._all_recipes = sorted(
            recipes,
            key=lambda r: (_get_locale(r.ItemNameLocales, lang) or r.ItemName or "").casefold(),
        )

        total_items = len(self._all_recipes)
        self._total_pages = max(1, (total_items + self._PAGE_SIZE - 1) // self._PAGE_SIZE)
        offset = (page - 1) * self._PAGE_SIZE
        self._page_items = self._all_recipes[offset : offset + self._PAGE_SIZE]

        items = [(r.RecipeId, r.ItemName, r.ItemNameLocales) for r in self._page_items]
        self._select_options = _build_localized_options(items, self.lang)

        self._build_items()

    def _build_items(self, include_choose: bool = False) -> None:
        """Populate the view with select, pagination, back, choose (optional), and other buttons."""
        self._recipes_by_id = {str(r.RecipeId): r for r in self._page_items}
        total_items = len(self._all_recipes)
        is_multipage = total_items > self._PAGE_SIZE
        action_row = 2 if is_multipage else 1

        select = ui.Select(
            placeholder=get_string(self.lang, _KEY_ITEM_SELECT),
            options=self._select_options,
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)

        if is_multipage:
            prev_btn = ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, row=1, disabled=(self._page == 1))
            prev_btn.callback = self._on_prev
            self.add_item(prev_btn)

            next_btn = ui.Button(
                emoji="▶",
                style=discord.ButtonStyle.secondary,
                row=1,
                disabled=(self._page >= self._total_pages),
            )
            next_btn.callback = self._on_next
            self.add_item(next_btn)

        if self._back_factory is not None:
            _add_back_button(self, self.lang, self._back_factory, row=action_row)

        other_btn = ui.Button(
            label=get_string(self.lang, _KEY_OTHER_BUTTON),
            style=discord.ButtonStyle.secondary,
            emoji="✍️",
            row=action_row,
        )
        other_btn.callback = self._on_other
        self.add_item(other_btn)

        if include_choose:
            choose_btn = ui.Button(
                label=get_string(self.lang, _KEY_CHOOSE_BUTTON),
                style=discord.ButtonStyle.success,
                emoji="✅",
                row=action_row,
            )
            choose_btn.callback = self._on_choose
            self.add_item(choose_btn)

    def _make_embed(self, recipe=None) -> discord.Embed:
        total_items = len(self._all_recipes)
        is_multipage = total_items > self._PAGE_SIZE

        if recipe is not None:
            localized_name = _get_locale(recipe.ItemNameLocales, self.lang)
            title = localized_name or recipe.ItemName
            desc_parts = []
            if recipe.ItemClassName:
                desc_parts.append(recipe.ItemClassName)
            if recipe.ItemSubClassName:
                desc_parts.append(recipe.ItemSubClassName)
            if recipe.ProfessionName:
                desc_parts.append(recipe.ProfessionName)
            description = " · ".join(desc_parts) if desc_parts else title
            embed = _build_step_embed(title, description, self._breadcrumbs)
            embed.url = recipe.wowhead_url
            if recipe.IconUrl:
                embed.set_thumbnail(url=recipe.IconUrl)
        else:
            title = get_string(self.lang, _KEY_ITEM_SELECT)
            desc = get_string(self.lang, _KEY_ITEM_SELECT_DESC)
            embed = _build_step_embed(title, desc, self._breadcrumbs)

        if is_multipage:
            footer = get_string(
                self.lang,
                _KEY_PAGE_INFO,
                page=self._page,
                total=self._total_pages,
                items=total_items,
            )
            embed.set_footer(text=footer)
        return embed

    async def _on_select(self, interaction: Interaction):
        value = interaction.data["values"][0]
        recipe = self._recipes_by_id.get(value)
        if not recipe:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        self._selected_recipe = recipe
        self.clear_items()
        self._build_items(include_choose=True)
        embed = self._make_embed(recipe)
        await interaction.response.edit_message(embed=embed, view=self, content=None)

    async def _navigate_to_page(self, interaction: Interaction, page: int) -> None:
        view = ItemSelectView(
            self.bot,
            self._all_recipes,
            self.roles,
            self.guild_id,
            self.lang,
            page=page,
            breadcrumbs=list(self._breadcrumbs),
            back_factory=self._back_factory,
        )
        await interaction.response.edit_message(embed=view._make_embed(), view=view, content=None)

    async def _on_prev(self, interaction: Interaction):
        await self._navigate_to_page(interaction, self._page - 1)

    async def _on_next(self, interaction: Interaction):
        await self._navigate_to_page(interaction, self._page + 1)

    async def _on_other(self, interaction: Interaction):
        with self.bot.session_scope() as session:
            mappings = CraftingRoleMapping.get_by_guild(interaction.guild_id, session)
        roles_found = []
        for m in mappings:
            role = interaction.guild.get_role(m.RoleId)
            if role is None:
                try:
                    role = await interaction.guild.fetch_role(m.RoleId)
                except discord.HTTPException:
                    role = None
            if role is not None:
                roles_found.append(role)
        if not roles_found:
            await interaction.response.edit_message(
                content=get_string(self.lang, _KEY_CREATE_NO_ROLES), view=None, embed=None
            )
            return
        view = ProfessionSelectView(self.bot, roles_found, interaction.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, _KEY_PROFESSION_SELECT), view=view, embed=None
        )

    async def _on_choose(self, interaction: Interaction):
        recipe = self._selected_recipe
        if not recipe:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        role_id = None
        with self.bot.session_scope() as session:
            mappings = CraftingRoleMapping.get_by_guild(interaction.guild_id, session)
            for m in mappings:
                if m.ProfessionId == recipe.ProfessionId:
                    role_id = m.RoleId
                    break

        if not role_id:
            await interaction.response.edit_message(
                content=get_string(self.lang, _KEY_NO_PROFESSION_MAPPED),
                view=None,
                embed=None,
            )
            return

        role = interaction.guild.get_role(role_id)
        if role is None:
            try:
                role = await interaction.guild.fetch_role(role_id)
            except discord.HTTPException:
                role = None
        if role is None:
            await interaction.response.edit_message(
                content=get_string(self.lang, _KEY_NO_PROFESSION_MAPPED),
                view=None,
                embed=None,
            )
            return

        localized_name = _get_locale(recipe.ItemNameLocales, self.lang)
        modal = CraftingOrderModal(
            self.bot,
            role_id,
            role,
            interaction.guild_id,
            self.lang,
            recipe=CraftingRecipeContext(
                item_name=localized_name or recipe.ItemName,
                item_name_english=recipe.ItemName if localized_name else None,
                icon_url=recipe.IconUrl,
                wowhead_url=recipe.wowhead_url,
            ),
        )
        await interaction.response.send_modal(modal)


class HousingProfessionSelectView(ui.View):
    """Housing order flow step 1: select profession."""

    def __init__(
        self,
        bot,
        guild_id: int,
        lang: str,
        housing_professions: list[tuple[int, str]],
        breadcrumbs: list[str] | None = None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        self._housing_professions = housing_professions
        self._breadcrumbs = breadcrumbs or []

        options = [discord.SelectOption(label=name, value=str(prof_id)) for prof_id, name in housing_professions[:25]]
        select = ui.Select(
            placeholder=get_string(lang, _KEY_HOUSING_PROFESSION_SELECT),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_HOUSING_PROFESSION_SELECT)
        desc = get_string(self.lang, _KEY_HOUSING_PROFESSION_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this HousingProfessionSelectView."""
        return _nav_back(
            lambda: HousingProfessionSelectView(
                self.bot,
                self.guild_id,
                self.lang,
                list(self._housing_professions),
                breadcrumbs=list(self._breadcrumbs),
            )
        )

    async def _on_select(self, interaction: Interaction):
        prof_id = int(interaction.data["values"][0])
        prof_name = next((name for pid, name in self._housing_professions if pid == prof_id), str(prof_id))
        child_crumbs = self._breadcrumbs + [prof_name]

        with self.bot.session_scope() as session:
            expansions = CraftingRecipeCache.get_expansions_for_profession(prof_id, RECIPE_TYPE_HOUSING, session)
            recipes = (
                CraftingRecipeCache.get_by_profession(prof_id, RECIPE_TYPE_HOUSING, session) if not expansions else None
            )

        go_back = self._make_back_closure()
        if not expansions:
            view = ItemSelectView(
                self.bot, recipes, [], self.guild_id, self.lang, breadcrumbs=child_crumbs, back_factory=go_back
            )
            embed = view._make_embed()
            await interaction.response.edit_message(embed=embed, view=view, content=None)
            return

        view = ExpansionSelectView(
            self.bot, prof_id, self.guild_id, self.lang, expansions, breadcrumbs=child_crumbs, back_factory=go_back
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


class ExpansionSelectView(ui.View):
    """Housing order flow step 2: select expansion."""

    def __init__(
        self,
        bot,
        prof_id: int,
        guild_id: int,
        lang: str,
        expansions: list[str],
        breadcrumbs: list[str] | None = None,
        back_factory=None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.prof_id = prof_id
        self.guild_id = guild_id
        self.lang = lang
        self._expansions = expansions
        self._breadcrumbs = breadcrumbs or []
        self._back_factory = back_factory

        options = [discord.SelectOption(label=exp, value=exp) for exp in expansions[:25]]
        select = ui.Select(
            placeholder=get_string(lang, _KEY_EXPANSION_SELECT),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

        if back_factory is not None:
            _add_back_button(self, lang, back_factory)

    def _make_embed(self) -> discord.Embed:
        title = get_string(self.lang, _KEY_EXPANSION_SELECT)
        desc = get_string(self.lang, _KEY_EXPANSION_SELECT_DESC)
        return _build_step_embed(title, desc, self._breadcrumbs)

    def _make_back_closure(self):
        """Return an async callback that navigates back to this ExpansionSelectView."""
        crumbs = list(self._breadcrumbs)
        return _nav_back(
            lambda: ExpansionSelectView(
                self.bot,
                self.prof_id,
                self.guild_id,
                self.lang,
                self._expansions,
                breadcrumbs=crumbs,
                back_factory=self._back_factory,
            )
        )

    async def _on_select(self, interaction: Interaction):
        expansion = interaction.data["values"][0]
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_by_profession_and_expansion(
                self.prof_id, RECIPE_TYPE_HOUSING, expansion, session
            )

        view = ItemSelectView(
            self.bot,
            recipes,
            [],
            self.guild_id,
            self.lang,
            breadcrumbs=self._breadcrumbs + [expansion],
            back_factory=self._make_back_closure(),
        )
        embed = view._make_embed()
        await interaction.response.edit_message(embed=embed, view=view, content=None)


# ---------------------------------------------------------------------------
# Order Creation Modal
# ---------------------------------------------------------------------------


class CraftingOrderModal(ui.Modal):
    """Order creation modal (Step 2).

    Accepts an optional ``recipe`` context from the cache-driven flow to pre-fill
    the item name field and attach icon/wowhead metadata to the created order.
    """

    def __init__(
        self,
        bot,
        role_id: int,
        role: discord.Role,
        guild_id: int,
        lang: str = "en",
        recipe: CraftingRecipeContext | None = None,
    ):
        super().__init__(title=get_string(lang, _KEY_MODAL_TITLE))
        self.bot = bot
        self.role_id = role_id
        self.role = role
        self.guild_id = guild_id
        self._recipe = recipe
        self.item_name_input = ui.TextInput(label=get_string(lang, _KEY_MODAL_ITEM_NAME), max_length=200)
        if recipe and recipe.item_name:
            self.item_name_input.default = recipe.item_name
        self.notes_input = ui.TextInput(
            label=get_string(lang, _KEY_MODAL_NOTES),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
        )
        self.add_item(self.item_name_input)
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        item_name_input = self.item_name_input.value.strip()
        if not item_name_input:
            await interaction.followup.send(_ls(interaction, "modal_item_name_empty"), ephemeral=True)
            return
        notes = self.notes_input.value.strip() or None

        # For cache-driven flow: keep English canonical in ItemName; store user-confirmed
        # (localized) name in ItemNameLocalized for display. For free-text flow: only ItemName.
        # If the user changed the pre-filled name, treat as free-text and drop cached metadata.
        recipe = self._recipe
        if recipe is not None and item_name_input != recipe.item_name:
            item_name = item_name_input
            item_name_localized = None
            recipe = None  # discard cache metadata — user overrode the name
        elif recipe is not None and recipe.item_name_english is not None:
            item_name = recipe.item_name_english
            item_name_localized = item_name_input
        else:
            item_name = item_name_input
            item_name_localized = None

        # Phase 1: persist the order and resolve all data needed for Discord.
        # Exit the session before any Discord HTTP calls to avoid holding a DB
        # connection open across network I/O.
        order_id = None
        channel_id = None
        embed = None
        view = None
        config = None
        icon_url = recipe.icon_url if recipe else None
        wowhead_url = recipe.wowhead_url if recipe else None

        with self.bot.session_scope() as session:
            # Resolve free-text item names against the recipe cache before
            # falling back to a Wowhead search URL.
            if not wowhead_url and item_name:
                cached = CraftingRecipeCache.find_best_match(item_name, session)
                if cached:
                    wowhead_url = cached.wowhead_url
                    if not icon_url:
                        icon_url = cached.IconUrl
                if not wowhead_url:
                    wowhead_url = f"https://www.wowhead.com/search?q={quote(item_name)}"

            config = CraftingBoardConfig.get_by_guild(self.guild_id, session)
            if config is not None:
                lang = self.bot.get_guild_language(self.guild_id)
                channel_id = config.ChannelId

                order = CraftingOrder(
                    GuildId=self.guild_id,
                    ChannelId=config.ChannelId,
                    CreatorId=interaction.user.id,
                    CreatorName=interaction.user.display_name,
                    ProfessionRoleId=self.role_id,
                    ItemName=item_name,
                    ItemNameLocalized=item_name_localized,
                    IconUrl=icon_url,
                    WowheadUrl=wowhead_url,
                    Notes=notes,
                    Status="open",
                )
                session.add(order)
                session.flush()
                order_id = order.Id
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, "open", lang)

        if config is None:
            await interaction.followup.send(_ls(interaction, "not_found"), ephemeral=True)
            return

        # Phase 2: send to Discord outside the session.
        try:
            channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
        except discord.HTTPException:
            channel = None
        if channel is None:
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    session.delete(order)
            await interaction.followup.send(_ls(interaction, "not_found"), ephemeral=True)
            return
        try:
            role_mention = self.role.mention if self.role else f"<@&{self.role_id}>"
            msg = await channel.send(content=role_mention, embed=embed, view=view)
        except discord.HTTPException:
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    session.delete(order)
            await interaction.followup.send(_ls(interaction, "not_found"), ephemeral=True)
            return

        # Phase 3: store the message ID now that Discord has accepted the message.
        with self.bot.session_scope() as session:
            order = CraftingOrder.get_by_id(order_id, session)
            if order is not None:
                order.OrderMessageId = msg.id

        await interaction.followup.send(
            _ls(interaction, "order_created", item=item_name_localized or item_name),
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# DynamicItem Buttons
# ---------------------------------------------------------------------------


class AcceptOrderButton(ui.DynamicItem[ui.Button], template=r"crafting:accept:(?P<order_id>\d+)"):
    def __init__(self, order_id: int):
        super().__init__(
            ui.Button(label="Accept", style=discord.ButtonStyle.success, custom_id=f"crafting:accept:{order_id}")
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: re.Match):
        return cls(order_id=int(match["order_id"]))

    async def interaction_check(self, interaction: Interaction) -> bool:
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return False
            if order.Status != "open":
                await interaction.response.send_message(_ls(interaction, "accept.not_open"), ephemeral=True)
                return False
            role = interaction.guild.get_role(order.ProfessionRoleId)
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    _ls(interaction, "accept.no_role", role=role.name), ephemeral=True
                )
                return False
        return True

    async def callback(self, interaction: Interaction):
        not_open = False
        embed = None
        view = None
        with interaction.client.session_scope() as session:
            # Atomic update: only proceeds if status is still 'open', preventing
            # two crafters from both accepting the same order in a race.
            rowcount = session.execute(
                sa_update(CraftingOrder)
                .where(CraftingOrder.Id == self.order_id, CraftingOrder.Status == "open")
                .values(
                    Status="in_progress",
                    CrafterId=interaction.user.id,
                    CrafterName=interaction.user.display_name,
                )
            ).rowcount
            if rowcount == 0:
                not_open = True
            else:
                order = CraftingOrder.get_by_id(self.order_id, session)
                lang = interaction.client.get_guild_language(interaction.guild_id)
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, "in_progress", lang)
        if not_open:
            await interaction.response.send_message(_ls(interaction, "accept.not_open"), ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)


class DropOrderButton(ui.DynamicItem[ui.Button], template=r"crafting:drop:(?P<order_id>\d+)"):
    def __init__(self, order_id: int):
        super().__init__(
            ui.Button(label="Drop", style=discord.ButtonStyle.secondary, custom_id=f"crafting:drop:{order_id}")
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: re.Match):
        return cls(order_id=int(match["order_id"]))

    async def interaction_check(self, interaction: Interaction) -> bool:
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return False
            if order.Status != "in_progress":
                await interaction.response.send_message(_ls(interaction, "drop.not_in_progress"), ephemeral=True)
                return False
            is_crafter = order.CrafterId == interaction.user.id
            is_admin = interaction.user.guild_permissions.administrator
            if not is_crafter and not is_admin:
                await interaction.response.send_message(_ls(interaction, "drop.not_crafter"), ephemeral=True)
                return False
        return True

    async def callback(self, interaction: Interaction):
        order_not_found = False
        embed = view = None
        with interaction.client.session_scope() as session:
            rowcount = session.execute(
                sa_update(CraftingOrder)
                .where(CraftingOrder.Id == self.order_id, CraftingOrder.Status == "in_progress")
                .values(Status="open", CrafterId=None, CrafterName=None)
            ).rowcount
            if rowcount == 0:
                order_not_found = True
            else:
                order = CraftingOrder.get_by_id(self.order_id, session)
                lang = interaction.client.get_guild_language(interaction.guild_id)
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, "open", lang)
        if order_not_found:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)


class CompleteOrderButton(ui.DynamicItem[ui.Button], template=r"crafting:complete:(?P<order_id>\d+)"):
    def __init__(self, order_id: int):
        super().__init__(
            ui.Button(label="Complete", style=discord.ButtonStyle.success, custom_id=f"crafting:complete:{order_id}")
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: re.Match):
        return cls(order_id=int(match["order_id"]))

    async def interaction_check(self, interaction: Interaction) -> bool:
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return False
            if order.Status != "in_progress":
                await interaction.response.send_message(_ls(interaction, "complete.not_in_progress"), ephemeral=True)
                return False
            is_crafter = order.CrafterId == interaction.user.id
            is_admin = interaction.user.guild_permissions.administrator
            if not is_crafter and not is_admin:
                await interaction.response.send_message(_ls(interaction, "complete.not_crafter"), ephemeral=True)
                return False
        return True

    async def callback(self, interaction: Interaction):
        order_not_found = False
        item_name = creator_id = crafter_id = thread_id = None
        with interaction.client.session_scope() as session:
            rowcount = session.execute(
                sa_update(CraftingOrder)
                .where(CraftingOrder.Id == self.order_id, CraftingOrder.Status == "in_progress")
                .values(Status="completed")
            ).rowcount
            if rowcount == 0:
                order_not_found = True
            else:
                order = CraftingOrder.get_by_id(self.order_id, session)
                item_name = _display_item_name(order)
                creator_id = order.CreatorId
                crafter_id = order.CrafterId
                thread_id = order.ThreadId
        if order_not_found:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        crafter_mention = f"<@{crafter_id}>" if crafter_id else interaction.user.mention
        # DM the creator; fall back to thread if DM fails
        used_thread = False
        try:
            creator = await interaction.client.fetch_user(creator_id)
            await creator.send(_ls(interaction, "complete.dm_complete", item=item_name, crafter=crafter_mention))
        except (discord.Forbidden, discord.NotFound):
            used_thread = await _thread_fallback(
                interaction,
                self.order_id,
                _ls(interaction, "complete.dm_complete", item=item_name, crafter=crafter_mention),
                creator_id,
            )

        if used_thread:
            _schedule_thread_cleanup(interaction, self.order_id)

        await interaction.response.edit_message(content=_ls(interaction, "complete.done"), embed=None, view=None)
        if not used_thread:
            # Delete the Ask thread before the parent message (deleting message first archives the thread)
            if thread_id:
                try:
                    thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                    await thread.delete()
                except discord.HTTPException:
                    log.debug("Failed to delete thread %s for order %s", thread_id, self.order_id)
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                log.debug("Failed to delete order message for order %s after completion", self.order_id, exc_info=True)


class CancelOrderButton(ui.DynamicItem[ui.Button], template=r"crafting:cancel:(?P<order_id>\d+)"):
    def __init__(self, order_id: int):
        super().__init__(
            ui.Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id=f"crafting:cancel:{order_id}")
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: re.Match):
        return cls(order_id=int(match["order_id"]))

    async def interaction_check(self, interaction: Interaction) -> bool:
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return False
            if order.Status in ("completed", "cancelled"):
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return False
            is_creator = order.CreatorId == interaction.user.id
            is_admin = interaction.user.guild_permissions.administrator
            if not is_creator and not is_admin:
                await interaction.response.send_message(_ls(interaction, "cancel.not_allowed"), ephemeral=True)
                return False
        return True

    async def callback(self, interaction: Interaction):
        order_not_found = False
        item_name = creator_id = thread_id = None
        cancelled_by_creator = False
        with interaction.client.session_scope() as session:
            rowcount = session.execute(
                sa_update(CraftingOrder)
                .where(
                    CraftingOrder.Id == self.order_id,
                    CraftingOrder.Status.not_in(["completed", "cancelled"]),
                )
                .values(Status="cancelled")
            ).rowcount
            if rowcount == 0:
                order_not_found = True
            else:
                order = CraftingOrder.get_by_id(self.order_id, session)
                item_name = _display_item_name(order)
                creator_id = order.CreatorId
                cancelled_by_creator = interaction.user.id == creator_id
                thread_id = order.ThreadId
        if order_not_found:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        # DM only if cancelled by admin (not by creator); fall back to thread if DM fails
        used_thread = False
        if not cancelled_by_creator:
            try:
                creator = await interaction.client.fetch_user(creator_id)
                await creator.send(_ls(interaction, "cancel.dm_cancel", item=item_name))
            except (discord.Forbidden, discord.NotFound):
                used_thread = await _thread_fallback(
                    interaction, self.order_id, _ls(interaction, "cancel.dm_cancel", item=item_name), creator_id
                )

        if used_thread:
            _schedule_thread_cleanup(interaction, self.order_id)

        await interaction.response.edit_message(content=_ls(interaction, "cancel.done"), embed=None, view=None)
        if not used_thread:
            # Delete the Ask thread before the parent message (deleting message first archives the thread)
            if thread_id:
                try:
                    thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                    await thread.delete()
                except discord.HTTPException:
                    log.debug("Failed to delete thread %s for order %s", thread_id, self.order_id)
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                log.debug(
                    "Failed to delete order message for order %s after cancellation", self.order_id, exc_info=True
                )


class AskQuestionButton(ui.DynamicItem[ui.Button], template=r"crafting:ask:(?P<order_id>\d+)"):
    def __init__(self, order_id: int):
        super().__init__(
            ui.Button(label="Ask Question", style=discord.ButtonStyle.secondary, custom_id=f"crafting:ask:{order_id}")
        )
        self.order_id = order_id

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: re.Match):
        return cls(order_id=int(match["order_id"]))

    async def callback(self, interaction: Interaction):
        lang = interaction.client.get_guild_language(interaction.guild_id)
        modal = AskQuestionModal(self.order_id, lang)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Ask Question Modal
# ---------------------------------------------------------------------------


class AskQuestionModal(ui.Modal):
    def __init__(self, order_id: int, lang: str = "en"):
        super().__init__(title=get_string(lang, _KEY_ASK_MODAL_TITLE))
        self.order_id = order_id
        self.message_input = ui.TextInput(
            label=get_string(lang, _KEY_ASK_MODAL_MESSAGE),
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                await interaction.followup.send(_ls(interaction, "not_found"), ephemeral=True)
                return

            item_name = order.ItemName
            creator_id = order.CreatorId
            thread_id = order.ThreadId
            channel_id = order.ChannelId
            message_id = order.OrderMessageId

        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            await interaction.followup.send(_ls(interaction, "ask.thread_failed"), ephemeral=True)
            return
        thread = None

        if thread_id:
            thread = channel.get_thread(thread_id)

        if thread is None:
            try:
                msg = await channel.fetch_message(message_id)
                thread = await msg.create_thread(name=_ls(interaction, "ask.thread_name", item=item_name))
                with interaction.client.session_scope() as session:
                    order = CraftingOrder.get_by_id(self.order_id, session)
                    order.ThreadId = thread.id
            except discord.HTTPException:
                await interaction.followup.send(_ls(interaction, "ask.thread_failed"), ephemeral=True)
                return

        await thread.send(f"**{interaction.user.display_name}:** {self.message_input.value}\n\n<@{creator_id}>")
        await interaction.followup.send(_ls(interaction, "ask.sent"), ephemeral=True)


# ---------------------------------------------------------------------------
# DM Thread Fallback
# ---------------------------------------------------------------------------


def _schedule_thread_cleanup(interaction: Interaction, order_id: int) -> None:
    """Write MessageDeleteAt for the order so the background task auto-deletes the thread.

    Called after a thread was successfully used as a DM fallback. The write is advisory —
    a failure here is logged but never propagates to the user.
    """
    try:
        with interaction.client.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            delay = config.ThreadCleanupDelayHours if config else 24
            session.execute(
                sa_update(CraftingOrder)
                .where(CraftingOrder.Id == order_id)
                .values(MessageDeleteAt=datetime.now(UTC) + timedelta(hours=delay))
            )
    except NerpyInfraException:
        log.error("Failed to schedule thread cleanup for order %s; thread may not be auto-deleted", order_id)


async def _thread_fallback(interaction: Interaction, order_id: int, message: str, creator_id: int) -> bool:
    """Create or reuse a thread and post a message as DM fallback.

    Returns True if the thread was successfully used (message should be kept as anchor).
    """
    with interaction.client.session_scope() as session:
        order = CraftingOrder.get_by_id(order_id, session)
        if order is None:
            return False
        thread_id = order.ThreadId
        channel_id = order.ChannelId
        message_id = order.OrderMessageId
        item_name = order.ItemName

    channel = interaction.guild.get_channel(channel_id)
    if channel is None:
        log.warning("Board channel %d not found for order #%d", channel_id, order_id)
        return False
    thread = channel.get_thread(thread_id) if thread_id else None

    if thread is None:
        try:
            msg = await channel.fetch_message(message_id)
            thread = await msg.create_thread(name=_ls(interaction, "ask.thread_name", item=item_name))
            with interaction.client.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                order.ThreadId = thread.id
        except discord.HTTPException:
            log.warning("Failed to create DM fallback thread for order #%d", order_id)
            return False

    await thread.send(f"{message}\n<@{creator_id}>")
    return True


# ---------------------------------------------------------------------------
# Manual Profession Mapping View (admin followup after auto-match failures)
# ---------------------------------------------------------------------------


class ManualProfessionMappingView(ui.View):
    """Ephemeral followup view shown to admins when auto-match fails for some roles.

    Presents one Select per unmapped role (up to MAX_ROLES per batch).
    If there are more roles than MAX_ROLES, confirming a batch automatically
    advances to the next one. Choices are persisted as CraftingRoleMapping rows.
    """

    MAX_ROLES = 4  # Discord allows 5 rows: 4 selects + 1 button

    def __init__(
        self,
        bot,
        guild_id: int,
        all_unmapped_roles: list[tuple[int, str]],
        lang: str = "en",
        offset: int = 0,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang
        self.all_unmapped_roles = all_unmapped_roles
        self.offset = offset
        self.selections: dict[int, int] = {}  # role_id -> profession_id

        prof_options = [
            discord.SelectOption(label=name, value=str(prof_id)) for name, prof_id in CRAFTING_PROFESSIONS.items()
        ]

        for role_id, role_name in all_unmapped_roles[offset : offset + self.MAX_ROLES]:
            placeholder = get_string(lang, _KEY_MANUAL_MAP_SELECT_PLACEHOLDER).format(role=role_name)
            select = ui.Select(
                placeholder=placeholder,
                options=prof_options,
                min_values=0,
                max_values=1,
            )
            select.callback = self._make_select_callback(role_id)
            self.add_item(select)

        confirm = ui.Button(
            label=get_string(lang, _KEY_MANUAL_MAP_CONFIRM_BUTTON),
            style=discord.ButtonStyle.success,
        )
        confirm.callback = self._on_confirm
        self.add_item(confirm)

    def _make_select_callback(self, role_id: int):
        async def _callback(interaction: Interaction):
            values = interaction.data.get("values", [])
            if values:
                self.selections[role_id] = int(values[0])
            else:
                self.selections.pop(role_id, None)
            await interaction.response.defer()

        return _callback

    async def _on_confirm(self, interaction: Interaction):
        next_offset = self.offset + self.MAX_ROLES
        is_last_batch = next_offset >= len(self.all_unmapped_roles)

        if not self.selections and is_last_batch:
            await interaction.response.send_message(
                get_string(self.lang, _KEY_MANUAL_MAP_NO_SELECTIONS), ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            for role_id, prof_id in self.selections.items():
                existing = (
                    session.query(CraftingRoleMapping)
                    .filter(CraftingRoleMapping.GuildId == self.guild_id, CraftingRoleMapping.RoleId == role_id)
                    .first()
                )
                if existing:
                    existing.ProfessionId = prof_id
                else:
                    session.add(CraftingRoleMapping(GuildId=self.guild_id, RoleId=role_id, ProfessionId=prof_id))

        self.stop()

        if not is_last_batch:
            next_view = ManualProfessionMappingView(
                self.bot, self.guild_id, self.all_unmapped_roles, self.lang, offset=next_offset
            )
            header = get_string(self.lang, _KEY_MANUAL_MAP_NEXT_BATCH, count=len(self.selections))
            description = get_string(self.lang, _KEY_MANUAL_MAP_DESCRIPTION)
            await interaction.response.edit_message(content=f"{header}\n\n{description}", view=next_view)
        else:
            num_selects = sum(1 for item in self.children if isinstance(item, ui.Select))
            skipped = num_selects - len(self.selections)
            if skipped > 0:
                reply = get_string(self.lang, _KEY_MANUAL_MAP_PARTIAL, count=len(self.selections), skipped=skipped)
            else:
                reply = get_string(self.lang, _KEY_MANUAL_MAP_SUCCESS)
            await interaction.response.edit_message(content=reply, view=None)
