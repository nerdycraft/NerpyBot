# -*- coding: utf-8 -*-
"""Crafting order modal dialogs."""

import logging
from urllib.parse import quote

import discord
from discord import Interaction, ui
from sqlalchemy.exc import SQLAlchemyError

from utils.errors import NerpyInfraException

from models.wow import (
    CraftingBoardConfig,
    CraftingOrder,
    CraftingRecipeCache,
    ORDER_STATUS_OPEN,
)
from modules.wow.views.board import (
    CraftingRecipeContext,
    _ls,
    _LS_ASK_SENT,
    _LS_ASK_THREAD_FAILED,
    _LS_ASK_THREAD_NAME,
    _LS_MODAL_ITEM_NAME_EMPTY,
    _LS_NOT_FOUND,
    _LS_ORDER_CREATED,
    _KEY_ASK_MODAL_MESSAGE,
    _KEY_ASK_MODAL_TITLE,
    _KEY_MODAL_ITEM_NAME,
    _KEY_MODAL_NOTES,
    _KEY_MODAL_TITLE,
    build_order_embed,
    build_order_view,
)
from utils.helpers import send_hidden_message
from utils.strings import get_string

log = logging.getLogger(__name__)


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
            await interaction.followup.send(_ls(interaction, _LS_MODAL_ITEM_NAME_EMPTY), ephemeral=True)
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
                    Status=ORDER_STATUS_OPEN,
                )
                session.add(order)
                session.flush()
                order_id = order.Id
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, ORDER_STATUS_OPEN, lang)

        if config is None:
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        # Phase 2: send to Discord outside the session.
        try:
            channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden):
            channel = None
        except discord.HTTPException as exc:
            log.warning("Transient error fetching channel %d for order #%d: %s", channel_id, order_id, exc)
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    session.delete(order)
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return
        if channel is None:
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    session.delete(order)
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return
        try:
            role_mention = self.role.mention if self.role else f"<@&{self.role_id}>"
            msg = await channel.send(content=role_mention, embed=embed, view=view)
        except discord.HTTPException:
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    session.delete(order)
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        # Phase 3: store the message ID now that Discord has accepted the message.
        try:
            with self.bot.session_scope() as session:
                order = CraftingOrder.get_by_id(order_id, session)
                if order is not None:
                    order.OrderMessageId = msg.id
        except SQLAlchemyError as exc:
            log.error("Failed to save order message ID for order #%d: %s", order_id, exc)
            try:
                await msg.delete()
            except discord.HTTPException as exc:
                log.warning("Failed to delete orphaned order message (order_id=%d): %s", order_id, exc)
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        await interaction.followup.send(
            _ls(interaction, _LS_ORDER_CREATED, item=item_name_localized or item_name),
            ephemeral=True,
        )


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

        item_name = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is not None:
                item_name = order.ItemName
                creator_id = order.CreatorId
                thread_id = order.ThreadId
                channel_id = order.ChannelId
                message_id = order.OrderMessageId

        if item_name is None:
            await interaction.followup.send(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        try:
            channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden):
            channel = None
        if channel is None:
            await interaction.followup.send(_ls(interaction, _LS_ASK_THREAD_FAILED), ephemeral=True)
            return
        thread = None

        if thread_id:
            try:
                thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
            except (discord.NotFound, discord.Forbidden):
                thread = None

        is_new_thread = thread is None
        if thread is None:
            try:
                msg = await channel.fetch_message(message_id)
                thread_name = _ls(interaction, _LS_ASK_THREAD_NAME, item=item_name)[:100]
                thread = await msg.create_thread(name=thread_name)
            except discord.HTTPException:
                await send_hidden_message(interaction, _ls(interaction, _LS_ASK_THREAD_FAILED))
                return

        escaped_message = discord.utils.escape_mentions(self.message_input.value)
        escaped_name = discord.utils.escape_mentions(interaction.user.display_name)
        try:
            await thread.send(
                f"**{escaped_name}:** {escaped_message}\n\n<@{creator_id}>",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except discord.HTTPException:
            if is_new_thread:
                from modules.wow.views.dropdowns import _try_delete_thread

                await _try_delete_thread(thread, self.order_id, "unsent ask")
            await send_hidden_message(interaction, _ls(interaction, _LS_ASK_THREAD_FAILED))
            return

        thread_orphaned = False
        if is_new_thread:
            try:
                with interaction.client.session_scope() as session:
                    order = CraftingOrder.get_by_id(self.order_id, session)
                    if order is None:
                        thread_orphaned = True
                    else:
                        order.ThreadId = thread.id
            except NerpyInfraException:
                try:
                    await thread.delete()
                except discord.HTTPException:
                    log.warning("Failed to delete thread for order #%d after infra error", self.order_id)
                raise

        if thread_orphaned:
            from modules.wow.views.dropdowns import _try_delete_thread

            await _try_delete_thread(thread, self.order_id, "orphaned ask")
            await send_hidden_message(interaction, _ls(interaction, _LS_ASK_THREAD_FAILED))
            return

        await interaction.followup.send(_ls(interaction, _LS_ASK_SENT), ephemeral=True)
