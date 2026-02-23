# -*- coding: utf-8 -*-
"""Crafting order board views, modals, and DynamicItem buttons."""

import json
import logging
import re

import discord
from discord import Interaction, ui

from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRecipeCache
from utils.strings import get_guild_language, get_localized_string, get_string

log = logging.getLogger(__name__)


def _ls(interaction: Interaction, key: str, **kwargs) -> str:
    """Shorthand for localized string lookup."""
    with interaction.client.session_scope() as session:
        return get_localized_string(interaction.guild_id, f"wow.craftingorder.{key}", session, **kwargs)


def build_order_embed(order: CraftingOrder, guild: discord.Guild, lang: str = "en") -> discord.Embed:
    """Build the embed for a crafting order."""
    role = guild.get_role(order.ProfessionRoleId)
    role_display = role.mention if role else f"Role #{order.ProfessionRoleId}"

    status_key = f"wow.craftingorder.order.status_{order.Status}"
    if order.Status == "in_progress" and order.CrafterId:
        status_text = get_string(lang, status_key, crafter=f"<@{order.CrafterId}>")
    else:
        status_text = get_string(lang, status_key)

    embed = discord.Embed(title=order.ItemName, color=discord.Color.blue())
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


def build_order_view(order_id: int, status: str) -> ui.View:
    """Construct a View with the appropriate buttons for an order's current status."""
    view = ui.View(timeout=None)
    if status == "open":
        view.add_item(
            ui.Button(label="Accept", style=discord.ButtonStyle.success, custom_id=f"crafting:accept:{order_id}")
        )
        view.add_item(
            ui.Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id=f"crafting:cancel:{order_id}")
        )
        view.add_item(
            ui.Button(label="Ask Question", style=discord.ButtonStyle.secondary, custom_id=f"crafting:ask:{order_id}")
        )
    elif status == "in_progress":
        view.add_item(
            ui.Button(label="Drop", style=discord.ButtonStyle.secondary, custom_id=f"crafting:drop:{order_id}")
        )
        view.add_item(
            ui.Button(label="Complete", style=discord.ButtonStyle.success, custom_id=f"crafting:complete:{order_id}")
        )
        view.add_item(
            ui.Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id=f"crafting:cancel:{order_id}")
        )
        view.add_item(
            ui.Button(label="Ask Question", style=discord.ButtonStyle.secondary, custom_id=f"crafting:ask:{order_id}")
        )
    return view


# ---------------------------------------------------------------------------
# Persistent Board View
# ---------------------------------------------------------------------------


class CraftingBoardView(ui.View):
    """Persistent view on the board embed with a single 'Create Order' button."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Create Crafting Order", style=discord.ButtonStyle.primary, custom_id="crafting_create_order")
    async def create_order(self, interaction: Interaction, button: ui.Button):
        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            if config is None:
                await interaction.response.send_message(_ls(interaction, "not_found"), ephemeral=True)
                return
            role_ids = json.loads(config.RoleIds)

        roles = []
        for rid in role_ids:
            role = interaction.guild.get_role(rid)
            if role:
                roles.append(role)
        if not roles:
            await interaction.response.send_message(_ls(interaction, "create.no_roles"), ephemeral=True)
            return

        view = ProfessionSelectView(self.bot, roles, interaction.guild_id)
        await interaction.response.send_message(_ls(interaction, "profession_select"), view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# Ephemeral Selection Views
# ---------------------------------------------------------------------------


class ProfessionSelectView(ui.View):
    """Ephemeral profession selection (Step 1)."""

    def __init__(self, bot, roles: list[discord.Role], guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        select = ui.Select(
            placeholder="Select a profession...",
            options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in roles[:25]],
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        role_id = int(interaction.data["values"][0])
        role = interaction.guild.get_role(role_id)

        with self.bot.session_scope() as session:
            recipes = CraftingRecipeCache.get_by_profession(self.guild_id, role_id, session)
            recipe_options = [(r.ItemName, r.IconUrl) for r in recipes[:25]] if recipes else []

        if recipe_options:
            view = ItemSelectView(self.bot, role_id, role, recipe_options, self.guild_id)
            await interaction.response.edit_message(content=_ls(interaction, "item_select"), view=view)
        else:
            modal = CraftingOrderModal(self.bot, role_id, role, "", None, self.guild_id)
            await interaction.response.send_modal(modal)


class ItemSelectView(ui.View):
    """Ephemeral item selection (Step 2)."""

    def __init__(
        self,
        bot,
        role_id: int,
        role: discord.Role,
        recipe_options: list[tuple[str, str | None]],
        guild_id: int,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.role_id = role_id
        self.role = role
        self.guild_id = guild_id
        self._recipes = {name: icon for name, icon in recipe_options}

        options = [discord.SelectOption(label=name) for name, _ in recipe_options]
        options.append(discord.SelectOption(label="Other (specify below)", value="__other__"))
        select = ui.Select(placeholder="Select an item...", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction):
        value = interaction.data["values"][0]
        if value == "__other__":
            item_name = ""
            icon_url = None
        else:
            item_name = value
            icon_url = self._recipes.get(value)

        modal = CraftingOrderModal(self.bot, self.role_id, self.role, item_name, icon_url, self.guild_id)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Order Creation Modal
# ---------------------------------------------------------------------------


class CraftingOrderModal(ui.Modal):
    """Order creation modal (Step 3)."""

    item_name_input = ui.TextInput(label="Item Name", max_length=200)
    notes_input = ui.TextInput(
        label="Additional Notes (optional)", style=discord.TextStyle.paragraph, required=False, max_length=1000
    )

    def __init__(self, bot, role_id: int, role: discord.Role, item_name: str, icon_url: str | None, guild_id: int):
        super().__init__(title="Create Crafting Order")
        self.bot = bot
        self.role_id = role_id
        self.role = role
        self.icon_url = icon_url
        self.guild_id = guild_id
        if item_name:
            self.item_name_input.default = item_name

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        item_name = self.item_name_input.value.strip()
        notes = self.notes_input.value.strip() or None

        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(self.guild_id, session)
            if config is None:
                await interaction.followup.send(_ls(interaction, "not_found"), ephemeral=True)
                return

            lang = get_guild_language(self.guild_id, session)

            order = CraftingOrder(
                GuildId=self.guild_id,
                ChannelId=config.ChannelId,
                CreatorId=interaction.user.id,
                ProfessionRoleId=self.role_id,
                ItemName=item_name,
                IconUrl=self.icon_url,
                Notes=notes,
                Status="open",
            )
            session.add(order)
            session.flush()

            embed = build_order_embed(order, interaction.guild, lang)
            view = build_order_view(order.Id, "open")

            channel = interaction.guild.get_channel(config.ChannelId)
            msg = await channel.send(content=self.role.mention, embed=embed, view=view)
            order.OrderMessageId = msg.id

        await interaction.followup.send(
            _ls(interaction, "create.success", item=item_name),
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
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            order.Status = "in_progress"
            order.CrafterId = interaction.user.id
            lang = get_guild_language(interaction.guild_id, session)
            embed = build_order_embed(order, interaction.guild, lang)
            view = build_order_view(order.Id, "in_progress")
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
            lang = get_guild_language(interaction.guild_id, session)
            embed = build_order_embed(order, interaction.guild, lang)
            view = build_order_view(order.Id, "open")
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
            item_name = order.ItemName
            creator_id = order.CreatorId

        # DM the creator
        try:
            creator = await interaction.client.fetch_user(creator_id)
            await creator.send(_ls(interaction, "complete.dm_complete", item=item_name))
        except (discord.Forbidden, discord.NotFound):
            await _thread_fallback(
                interaction, self.order_id, _ls(interaction, "complete.dm_complete", item=item_name), creator_id
            )

        await interaction.response.edit_message(content=_ls(interaction, "complete.done"), embed=None, view=None)
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
            if order.Status == "completed":
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
            order.Status = "completed"
            item_name = order.ItemName
            creator_id = order.CreatorId
            cancelled_by_creator = interaction.user.id == creator_id

        # DM only if cancelled by admin (not by creator)
        if not cancelled_by_creator:
            try:
                creator = await interaction.client.fetch_user(creator_id)
                await creator.send(_ls(interaction, "cancel.dm_cancel", item=item_name))
            except (discord.Forbidden, discord.NotFound):
                await _thread_fallback(
                    interaction, self.order_id, _ls(interaction, "cancel.dm_cancel", item=item_name), creator_id
                )

        await interaction.response.edit_message(content=_ls(interaction, "cancel.done"), embed=None, view=None)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            log.debug("Failed to delete order message for order %s after cancellation", self.order_id, exc_info=True)


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
        modal = AskQuestionModal(self.order_id)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Ask Question Modal
# ---------------------------------------------------------------------------


class AskQuestionModal(ui.Modal):
    message_input = ui.TextInput(label="Your question", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, order_id: int):
        super().__init__(title="Ask a Question")
        self.order_id = order_id

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


async def _thread_fallback(interaction: Interaction, order_id: int, message: str, creator_id: int):
    """Create or reuse a thread and post a message as DM fallback."""
    with interaction.client.session_scope() as session:
        order = CraftingOrder.get_by_id(order_id, session)
        if order is None:
            return
        thread_id = order.ThreadId
        channel_id = order.ChannelId
        message_id = order.OrderMessageId
        item_name = order.ItemName

    channel = interaction.guild.get_channel(channel_id)
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
            return

    await thread.send(f"{message}\n<@{creator_id}>")
