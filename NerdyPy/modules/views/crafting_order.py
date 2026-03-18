# -*- coding: utf-8 -*-
"""Crafting order board views, modals, and DynamicItem buttons."""

import logging
import re
from datetime import UTC, datetime, timedelta
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
from utils.strings import get_string

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Virtual category sentinel values
# ---------------------------------------------------------------------------

_VCAT_PVP = "__pvp__"
_VCAT_RAID_PREP = "__raid_prep__"
_VCAT_ARMOR = "__armor__"
_VCAT_WEAPONS = "__weapons__"
_VCAT_PROFESSION = "__profession__"
_VCAT_OTHER = "__other_cat__"

_VCAT_LABEL_KEYS = {
    _VCAT_PVP: ("⚔️ ", "pvp_category"),
    _VCAT_RAID_PREP: ("🧪 ", "raid_prep_category"),
    _VCAT_ARMOR: ("🛡️ ", "armor_category"),
    _VCAT_WEAPONS: ("⚔️ ", "weapons_category"),
    _VCAT_PROFESSION: ("🔧 ", "profession_gear_category"),
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

# Maps gear-bucket vcats to the lowercase ItemClassName used in the recipe cache.
# Must match the Blizzard API item class names (lowercased) stored in CraftingRecipeCache.
_VCAT_TO_CLASS_NAME: dict[str, str] = {
    _VCAT_ARMOR: "armor",
    _VCAT_WEAPONS: "weapon",
    _VCAT_PROFESSION: "profession",
}


def _build_vcat_info(recipe_type: str, session, profession_ids) -> tuple[list[str], dict[str, int]]:
    """Check which virtual categories have items and build the item class ID map.

    Returns:
        available_vcats: ordered list of vcat sentinel keys that have ≥1 item
        item_class_ids: mapping of lower(ItemClassName) → ItemClassId for non-PvP orderable classes
    """
    available = []

    # Get all non-PvP orderable item classes to build the class ID map in one query.
    all_classes = CraftingRecipeCache.get_item_classes(
        recipe_type, session, profession_ids=profession_ids, orderable_only=True, exclude_pvp=True
    )
    item_class_ids = {name.lower(): cls_id for cls_id, name, _ in all_classes if name}

    if CraftingRecipeCache.get_pvp_item_classes(recipe_type, session, profession_ids):
        available.append(_VCAT_PVP)
    if CraftingRecipeCache.get_raid_prep_categories(recipe_type, session, profession_ids):
        available.append(_VCAT_RAID_PREP)
    for vcat in (_VCAT_ARMOR, _VCAT_WEAPONS, _VCAT_PROFESSION):
        if _VCAT_TO_CLASS_NAME[vcat] in item_class_ids:
            available.append(vcat)
    if CraftingRecipeCache.get_other_categories(recipe_type, session, profession_ids):
        available.append(_VCAT_OTHER)

    return available, item_class_ids


def _ls(interaction: Interaction, key: str, **kwargs) -> str:
    """Shorthand for localized string lookup."""
    return interaction.client.get_localized_string(interaction.guild_id, f"wow.craftingorder.{key}", **kwargs)


def _get_locale(locales: dict | None, lang: str) -> str | None:
    """Return the localized string for ``lang`` from a locale dict, or None for English / missing."""
    return (locales or {}).get(lang) if lang != "en" else None


def _build_localized_options(
    items: list[tuple[int | str, str | None, dict | None]], lang: str, emojis: bool = False
) -> list[discord.SelectOption]:
    """Build SelectOptions from (id, english_name, locales) tuples.

    Label is the localized name when available, falling back to the English name.
    Description shows the English name only when a different localized label is shown.
    Options are sorted by the displayed label so the dropdown order matches the locale.
    If emojis=True, a keyword-matched emoji prefix is prepended to each label.
    """
    options = []
    for item_id, name, locales in items:
        localized = _get_locale(locales, lang)
        label = localized or name or "Unknown"
        prefix = _emoji_for(name or "") if emojis else ""
        description = name[:100] if localized else None
        options.append(discord.SelectOption(label=(prefix + label)[:100], description=description, value=str(item_id)))
    options.sort(key=lambda o: o.label.casefold())
    return options[:25]


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
    embed.add_field(name=get_string(lang, "wow.craftingorder.order.profession"), value=role_display, inline=True)
    embed.add_field(name=get_string(lang, "wow.craftingorder.order.status"), value=status_text, inline=True)
    embed.add_field(
        name=get_string(lang, "wow.craftingorder.order.posted_by"), value=f"<@{order.CreatorId}>", inline=True
    )
    if order.Notes:
        embed.add_field(name=get_string(lang, "wow.craftingorder.order.notes"), value=order.Notes, inline=False)
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
        lang = mapped_prof_ids = mapping_role_ids = available_vcats = item_class_ids = None
        with self.bot.session_scope() as session:
            board_ctx = self._load_board_context(interaction.guild_id, session)
            if board_ctx is not None:
                lang, mapped_prof_ids, mapping_role_ids = board_ctx
                available_vcats, item_class_ids = _build_vcat_info(RECIPE_TYPE_CRAFTED, session, mapped_prof_ids)

        if board_ctx is None:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        roles = [r for rid in mapping_role_ids if (r := interaction.guild.get_role(rid))]
        if not roles:
            await interaction.response.send_message(_ls(interaction, "create.no_roles"), ephemeral=True)
            return

        if available_vcats:
            view = VirtualCategorySelectView(
                self.bot, roles, interaction.guild_id, lang, available_vcats, mapped_prof_ids, item_class_ids
            )
            await interaction.response.send_message(
                get_string(lang, "wow.craftingorder.virtual_category_select"), view=view, ephemeral=True
            )
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

        view = HousingProfessionSelectView(self.bot, interaction.guild_id, lang, housing_professions)
        await interaction.response.send_message(
            _ls(interaction, "housing_profession_select"), view=view, ephemeral=True
        )


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
            placeholder=get_string(lang, "wow.craftingorder.profession_select"),
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
            placeholder=get_string(lang, "wow.craftingorder.item_type_select"),
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
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
            )
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
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_subtype_select"), view=view
        )


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
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.item_class_id = item_class_id
        self.mapped_prof_ids = mapped_prof_ids
        self.orderable_only = orderable_only
        self.exclude_pvp = exclude_pvp

        options = _build_localized_options(subclasses, lang, emojis=True)
        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.item_subtype_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        item_subclass_id = int(interaction.data["values"][0])
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
            category_names = (
                CraftingRecipeCache.get_category_names(
                    RECIPE_TYPE_CRAFTED,
                    self.item_class_id,
                    item_subclass_id,
                    session,
                    profession_ids=self.mapped_prof_ids,
                    orderable_only=self.orderable_only,
                    exclude_pvp=self.exclude_pvp,
                )
                if len(recipes) > 24
                else []
            )

        if len(category_names) > 1:
            view = CategorySelectView(
                self.bot,
                self.roles,
                self.guild_id,
                self.lang,
                self.item_class_id,
                item_subclass_id,
                category_names,
                self.mapped_prof_ids,
                self.orderable_only,
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.category_select"), view=view
            )
            return

        view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


class VirtualCategorySelectView(ui.View):
    """Crafted order flow entry: choose a virtual category (PvP, Raid Prep, Armor, …)."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        available_vcats: list[str],
        mapped_prof_ids: set[int] | None,
        item_class_ids: dict[str, int],
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.item_class_ids = item_class_ids

        options = []
        for vcat in available_vcats:
            emoji, key = _VCAT_LABEL_KEYS[vcat]
            label = emoji + get_string(lang, f"wow.craftingorder.{key}")
            en_name = get_string("en", f"wow.craftingorder.{key}") if lang != "en" else None
            options.append(discord.SelectOption(label=label[:100], description=en_name, value=vcat))

        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.virtual_category_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        value = interaction.data["values"][0]

        if value == _VCAT_PVP:
            view = PvPGroupSelectView(
                self.bot, self.roles, self.guild_id, self.lang, self.mapped_prof_ids, self.item_class_ids
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.pvp_group_select"), view=view
            )

        elif value == _VCAT_RAID_PREP:
            with self.bot.session_scope() as session:
                categories = CraftingRecipeCache.get_raid_prep_categories(
                    RECIPE_TYPE_CRAFTED, session, profession_ids=self.mapped_prof_ids
                )
            view = RaidPrepCategorySelectView(
                self.bot, self.roles, self.guild_id, self.lang, categories, self.mapped_prof_ids
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.raid_prep_select"), view=view
            )

        elif value in (_VCAT_ARMOR, _VCAT_WEAPONS, _VCAT_PROFESSION):
            class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[value])
            if class_id is None:
                await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
                return
            exclude_pvp = value in (_VCAT_ARMOR, _VCAT_WEAPONS)
            with self.bot.session_scope() as session:
                subclasses = CraftingRecipeCache.get_item_subclasses(
                    RECIPE_TYPE_CRAFTED,
                    class_id,
                    session,
                    profession_ids=self.mapped_prof_ids,
                    orderable_only=True,
                    exclude_pvp=exclude_pvp,
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
                exclude_pvp=exclude_pvp,
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.item_subtype_select"), view=view
            )

        elif value == _VCAT_OTHER:
            with self.bot.session_scope() as session:
                categories = CraftingRecipeCache.get_other_categories(
                    RECIPE_TYPE_CRAFTED, session, profession_ids=self.mapped_prof_ids
                )
            view = OtherCategorySelectView(
                self.bot, self.roles, self.guild_id, self.lang, categories, self.mapped_prof_ids
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.other_select"), view=view
            )


class PvPGroupSelectView(ui.View):
    """PvP flow step 1: choose Weapons (all at once) or Gear (by armor type)."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        mapped_prof_ids: set[int] | None = None,
        item_class_ids: dict[str, int] | None = None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids
        self.item_class_ids = item_class_ids or {}

        options = []
        for vcat, pvp_value in ((_VCAT_WEAPONS, _PVP_GROUP_WEAPONS), (_VCAT_ARMOR, _PVP_GROUP_GEAR)):
            emoji, key = _VCAT_LABEL_KEYS[vcat]
            full_key = f"wow.craftingorder.{key}"
            options.append(
                discord.SelectOption(
                    label=emoji + get_string(lang, full_key),
                    description=get_string("en", full_key) if lang != "en" else None,
                    value=pvp_value,
                )
            )
        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.pvp_group_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        value = interaction.data["values"][0]

        if value == _PVP_GROUP_WEAPONS:
            weapon_class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[_VCAT_WEAPONS])
            if weapon_class_id is None:
                await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
                return
            with self.bot.session_scope() as session:
                recipes = CraftingRecipeCache.get_pvp_items(
                    RECIPE_TYPE_CRAFTED, weapon_class_id, None, session, profession_ids=self.mapped_prof_ids
                )
            view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
            )

        elif value == _PVP_GROUP_GEAR:
            armor_class_id = self.item_class_ids.get(_VCAT_TO_CLASS_NAME[_VCAT_ARMOR])
            if armor_class_id is None:
                await interaction.response.edit_message(content=_ls(interaction, "not_found"), view=None)
                return
            with self.bot.session_scope() as session:
                subclasses = CraftingRecipeCache.get_pvp_item_subclasses(
                    RECIPE_TYPE_CRAFTED, armor_class_id, session, profession_ids=self.mapped_prof_ids
                )
            view = PvPArmorTypeSelectView(
                self.bot, self.roles, self.guild_id, self.lang, armor_class_id, subclasses, self.mapped_prof_ids
            )
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.pvp_armor_select"), view=view
            )


class PvPArmorTypeSelectView(ui.View):
    """PvP flow step 2 (gear path): choose armor subtype, then items."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        armor_class_id: int,
        subclasses: list[tuple[int, str | None, dict | None]],
        mapped_prof_ids: set[int] | None = None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.armor_class_id = armor_class_id
        self.mapped_prof_ids = mapped_prof_ids

        options = _build_localized_options(subclasses, lang, emojis=True)
        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.pvp_armor_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        item_subclass_id = int(interaction.data["values"][0])
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_pvp_items(
                RECIPE_TYPE_CRAFTED, self.armor_class_id, item_subclass_id, session, profession_ids=self.mapped_prof_ids
            )
        view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


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
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids

        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.raid_prep_select"),
            options=_build_localized_category_options(categories, lang),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        category_name = interaction.data["values"][0]
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_raid_prep_items(
                RECIPE_TYPE_CRAFTED, category_name, session, profession_ids=self.mapped_prof_ids
            )
        view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


class CategorySelectView(ui.View):
    """Generic category drill-down for armor subclass overflow (>24 items)."""

    def __init__(
        self,
        bot,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
        item_class_id: int,
        item_subclass_id: int,
        category_names: list[tuple[str, dict | None]],
        mapped_prof_ids: set[int] | None = None,
        orderable_only: bool = False,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.item_class_id = item_class_id
        self.item_subclass_id = item_subclass_id
        self.mapped_prof_ids = mapped_prof_ids
        self.orderable_only = orderable_only

        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.category_select"),
            options=_build_localized_category_options(category_names, lang),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        category_name = interaction.data["values"][0]
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_by_type_subclass_and_category(
                RECIPE_TYPE_CRAFTED,
                self.item_class_id,
                self.item_subclass_id,
                category_name,
                session,
                profession_ids=self.mapped_prof_ids,
                orderable_only=self.orderable_only,
            )
        view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


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
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self.mapped_prof_ids = mapped_prof_ids

        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.other_select"),
            options=_build_localized_category_options(categories, lang),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        category_name = interaction.data["values"][0]
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_other_items(
                RECIPE_TYPE_CRAFTED, category_name, session, profession_ids=self.mapped_prof_ids
            )
        view = ItemSelectView(self.bot, recipes, self.roles, self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


class ItemSelectView(ui.View):
    """Shared item selection step: shows up to 24 cached recipes + 'Other' option."""

    _OTHER_VALUE = "__other__"

    def __init__(
        self,
        bot,
        recipes: list,
        roles: list[discord.Role],
        guild_id: int,
        lang: str,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.roles = roles
        self.guild_id = guild_id
        self.lang = lang
        self._recipes_by_id = {str(r.RecipeId): r for r in recipes}

        items = [(r.RecipeId, r.ItemName, r.ItemNameLocales) for r in recipes]
        options = _build_localized_options(items, lang)[:24]  # leave room for "Other"
        options.append(
            discord.SelectOption(
                label=get_string(lang, "wow.craftingorder.item_select_other"),
                value=self._OTHER_VALUE,
            )
        )

        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.item_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        value = interaction.data["values"][0]

        if value == self._OTHER_VALUE:
            # Fall back to profession select (free-text)
            lang = self.bot.get_guild_language(interaction.guild_id)
            with self.bot.session_scope() as session:
                mappings = CraftingRoleMapping.get_by_guild(interaction.guild_id, session)
            roles_found = [r for m in mappings if (r := interaction.guild.get_role(m.RoleId))]
            if not roles_found:
                await interaction.response.edit_message(
                    content=get_string(self.lang, "wow.craftingorder.create.no_roles"), view=None
                )
                return
            view = ProfessionSelectView(self.bot, roles_found, interaction.guild_id, lang)
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.profession_select"), view=view
            )
            return

        recipe = self._recipes_by_id.get(value)
        if not recipe:
            await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
            return

        # Resolve role from profession ID via CraftingRoleMapping
        role_id = None
        role = None
        with self.bot.session_scope() as session:
            mappings = CraftingRoleMapping.get_by_guild(interaction.guild_id, session)
            for m in mappings:
                if m.ProfessionId == recipe.ProfessionId:
                    role_id = m.RoleId
                    break

        if not role_id:
            # Safety net: upstream profession_ids filter should prevent this, but if a profession
            # in the cache has no role mapping, surface a clear error rather than silently falling back.
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.no_profession_mapped"),
                view=None,
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
                content=get_string(self.lang, "wow.craftingorder.no_profession_mapped"),
                view=None,
            )
            return

        localized_name = _get_locale(recipe.ItemNameLocales, self.lang)
        modal = CraftingOrderModal(
            self.bot,
            role_id,
            role,
            interaction.guild_id,
            self.lang,
            item_name=localized_name or recipe.ItemName,
            item_name_english=recipe.ItemName if localized_name else None,
            icon_url=recipe.IconUrl,
            wowhead_url=recipe.wowhead_url,
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
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.lang = lang

        options = [discord.SelectOption(label=name, value=str(prof_id)) for prof_id, name in housing_professions[:25]]
        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.housing_profession_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        prof_id = int(interaction.data["values"][0])
        with self.bot.session_scope() as session:
            expansions = CraftingRecipeCache.get_expansions_for_profession(prof_id, RECIPE_TYPE_HOUSING, session)

        if not expansions:
            # No expansion data — go straight to items
            with self.bot.session_scope() as session:
                recipes = CraftingRecipeCache.get_by_profession(prof_id, RECIPE_TYPE_HOUSING, session)
            view = ItemSelectView(self.bot, recipes, [], self.guild_id, self.lang)
            await interaction.response.edit_message(
                content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
            )
            return

        view = ExpansionSelectView(self.bot, prof_id, self.guild_id, self.lang, expansions)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.expansion_select"), view=view
        )


class ExpansionSelectView(ui.View):
    """Housing order flow step 2: select expansion."""

    def __init__(
        self,
        bot,
        prof_id: int,
        guild_id: int,
        lang: str,
        expansions: list[str],
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.prof_id = prof_id
        self.guild_id = guild_id
        self.lang = lang

        options = [discord.SelectOption(label=exp, value=exp) for exp in expansions[:25]]
        select = ui.Select(
            placeholder=get_string(lang, "wow.craftingorder.expansion_select"),
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        expansion = interaction.data["values"][0]
        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_by_profession_and_expansion(
                self.prof_id, RECIPE_TYPE_HOUSING, expansion, session
            )

        view = ItemSelectView(self.bot, recipes, [], self.guild_id, self.lang)
        await interaction.response.edit_message(
            content=get_string(self.lang, "wow.craftingorder.item_select"), view=view
        )


# ---------------------------------------------------------------------------
# Order Creation Modal
# ---------------------------------------------------------------------------


class CraftingOrderModal(ui.Modal):
    """Order creation modal (Step 2).

    Accepts optional pre-filled values from the cache-driven flows:
        item_name   — pre-fill the item name field
        icon_url    — store on the order for embed thumbnail
        wowhead_url — store on the order for Wowhead link
    """

    def __init__(
        self,
        bot,
        role_id: int,
        role: discord.Role,
        guild_id: int,
        lang: str = "en",
        item_name: str | None = None,
        item_name_english: str | None = None,
        icon_url: str | None = None,
        wowhead_url: str | None = None,
    ):
        super().__init__(title=get_string(lang, "wow.craftingorder.modal_title"))
        self.bot = bot
        self.role_id = role_id
        self.role = role
        self.guild_id = guild_id
        self._item_name_english = item_name_english
        self._item_name_prefill = item_name  # original pre-fill for edit-detection
        self._icon_url = icon_url
        self._wowhead_url = wowhead_url
        self.item_name_input = ui.TextInput(label=get_string(lang, "wow.craftingorder.modal_item_name"), max_length=200)
        if item_name:
            self.item_name_input.default = item_name
        self.notes_input = ui.TextInput(
            label=get_string(lang, "wow.craftingorder.modal_notes"),
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
        if self._item_name_english is not None and item_name_input != self._item_name_prefill:
            item_name = item_name_input
            item_name_localized = None
            self._icon_url = None
            self._wowhead_url = None
        elif self._item_name_english is not None:
            item_name = self._item_name_english
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
        with self.bot.session_scope() as session:
            # Resolve free-text item names against the recipe cache before
            # falling back to a Wowhead search URL.
            if not self._wowhead_url and item_name:
                cached = CraftingRecipeCache.find_best_match(item_name, session)
                if cached:
                    self._wowhead_url = cached.wowhead_url
                    if not self._icon_url:
                        self._icon_url = cached.IconUrl
                else:
                    self._wowhead_url = f"https://www.wowhead.com/search?q={quote(item_name)}"

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
                    IconUrl=self._icon_url,
                    WowheadUrl=self._wowhead_url,
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
        except (discord.NotFound, discord.Forbidden):
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
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            order.Status = "open"
            order.CrafterId = None
            order.CrafterName = None
            lang = interaction.client.get_guild_language(interaction.guild_id)
            embed = build_order_embed(order, interaction.guild, lang)
            view = build_order_view(order.Id, "open", lang)
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
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            order.Status = "completed"
            item_name = _display_item_name(order)
            creator_id = order.CreatorId
            crafter_id = order.CrafterId
            thread_id = order.ThreadId

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
            with interaction.client.session_scope() as session:
                config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
                delay = config.ThreadCleanupDelayHours if config else 24
                order = CraftingOrder.get_by_id(self.order_id, session)
                order.MessageDeleteAt = datetime.now(UTC) + timedelta(hours=delay)

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
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            order.Status = "cancelled"
            item_name = _display_item_name(order)
            creator_id = order.CreatorId
            cancelled_by_creator = interaction.user.id == creator_id
            thread_id = order.ThreadId

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
            with interaction.client.session_scope() as session:
                config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
                delay = config.ThreadCleanupDelayHours if config else 24
                order = CraftingOrder.get_by_id(self.order_id, session)
                order.MessageDeleteAt = datetime.now(UTC) + timedelta(hours=delay)

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
        super().__init__(title=get_string(lang, "wow.craftingorder.ask.modal_title"))
        self.order_id = order_id
        self.message_input = ui.TextInput(
            label=get_string(lang, "wow.craftingorder.ask.modal_message"),
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
            placeholder = get_string(lang, "wow.craftingorder.manual_map.select_placeholder", role=role_name)
            select = ui.Select(
                placeholder=placeholder,
                options=prof_options,
                min_values=0,
                max_values=1,
            )
            select.callback = self._make_select_callback(role_id)
            self.add_item(select)

        confirm = ui.Button(
            label=get_string(lang, "wow.craftingorder.manual_map.confirm_button"),
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
                get_string(self.lang, "wow.craftingorder.manual_map.no_selections"), ephemeral=True
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
            header = get_string(self.lang, "wow.craftingorder.manual_map.next_batch", count=len(self.selections))
            description = get_string(self.lang, "wow.craftingorder.manual_map.description")
            await interaction.response.edit_message(content=f"{header}\n\n{description}", view=next_view)
        else:
            num_selects = sum(1 for item in self.children if isinstance(item, ui.Select))
            skipped = num_selects - len(self.selections)
            if skipped > 0:
                reply = get_string(
                    self.lang, "wow.craftingorder.manual_map.partial", count=len(self.selections), skipped=skipped
                )
            else:
                reply = get_string(self.lang, "wow.craftingorder.manual_map.success")
            await interaction.response.edit_message(content=reply, view=None)
