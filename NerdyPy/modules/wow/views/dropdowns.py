# -*- coding: utf-8 -*-
"""DynamicItem buttons for crafting order interactions and thread utilities."""

import logging
import re
from datetime import UTC, datetime, timedelta

import discord
from discord import Interaction, ui
from sqlalchemy import update as sa_update

from models.wow import (
    CraftingBoardConfig,
    CraftingOrder,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_OPEN,
)
from modules.wow.views.board import (
    _display_item_name,
    _ls,
    _LS_ACCEPT_NO_ROLE,
    _LS_ACCEPT_NOT_OPEN,
    _LS_ASK_THREAD_NAME,
    _LS_CANCEL_DM_CANCEL,
    _LS_CANCEL_DONE,
    _LS_CANCEL_NOT_ALLOWED,
    _LS_COMPLETE_DM_COMPLETE,
    _LS_COMPLETE_DONE,
    _LS_COMPLETE_NOT_CRAFTER,
    _LS_COMPLETE_NOT_IN_PROGRESS,
    _LS_DROP_NOT_CRAFTER,
    _LS_DROP_NOT_IN_PROGRESS,
    _LS_NOT_FOUND,
    build_order_embed,
    build_order_view,
)

log = logging.getLogger(__name__)


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
        error_msg = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                error_msg = _ls(interaction, _LS_NOT_FOUND)
            elif order.Status != ORDER_STATUS_OPEN:
                error_msg = _ls(interaction, _LS_ACCEPT_NOT_OPEN)
            else:
                role = interaction.guild.get_role(order.ProfessionRoleId)
                if role is None or role not in interaction.user.roles:
                    role_label = role.name if role else f"<deleted role {order.ProfessionRoleId}>"
                    error_msg = _ls(interaction, _LS_ACCEPT_NO_ROLE, role=role_label)
        if error_msg is not None:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return False
        return True

    async def callback(self, interaction: Interaction):
        not_open = False
        embed = None
        view = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is not None:
                session.expunge(order)
        if order is None:
            not_open = True
        else:
            # Atomic update: only proceeds if status is still 'open', preventing
            # two crafters from both accepting the same order in a race.
            with interaction.client.session_scope() as session:
                rowcount = session.execute(
                    sa_update(CraftingOrder)
                    .where(CraftingOrder.Id == self.order_id, CraftingOrder.Status == ORDER_STATUS_OPEN)
                    .values(
                        Status=ORDER_STATUS_IN_PROGRESS,
                        CrafterId=interaction.user.id,
                        CrafterName=interaction.user.display_name,
                    )
                ).rowcount
            if rowcount == 0:
                not_open = True
            else:
                order.Status = ORDER_STATUS_IN_PROGRESS
                order.CrafterId = interaction.user.id
                order.CrafterName = interaction.user.display_name
                lang = interaction.client.get_guild_language(interaction.guild_id)
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, ORDER_STATUS_IN_PROGRESS, lang)
        if not_open:
            await interaction.response.send_message(_ls(interaction, _LS_ACCEPT_NOT_OPEN), ephemeral=True)
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
        error_msg = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                error_msg = _ls(interaction, _LS_NOT_FOUND)
            elif order.Status != ORDER_STATUS_IN_PROGRESS:
                error_msg = _ls(interaction, _LS_DROP_NOT_IN_PROGRESS)
            else:
                is_crafter = order.CrafterId == interaction.user.id
                is_admin = interaction.user.guild_permissions.administrator
                if not is_crafter and not is_admin:
                    error_msg = _ls(interaction, _LS_DROP_NOT_CRAFTER)
        if error_msg is not None:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return False
        return True

    async def callback(self, interaction: Interaction):
        order_not_found = False
        embed = view = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is not None:
                session.expunge(order)
        if order is None:
            order_not_found = True
        else:
            conditions = [CraftingOrder.Id == self.order_id, CraftingOrder.Status == ORDER_STATUS_IN_PROGRESS]
            if not interaction.user.guild_permissions.administrator:
                conditions.append(CraftingOrder.CrafterId == interaction.user.id)
            with interaction.client.session_scope() as session:
                rowcount = session.execute(
                    sa_update(CraftingOrder)
                    .where(*conditions)
                    .values(Status=ORDER_STATUS_OPEN, CrafterId=None, CrafterName=None)
                ).rowcount
            if rowcount == 0:
                order_not_found = True
            else:
                order.Status = ORDER_STATUS_OPEN
                order.CrafterId = None
                order.CrafterName = None
                lang = interaction.client.get_guild_language(interaction.guild_id)
                embed = build_order_embed(order, interaction.guild, lang)
                view = build_order_view(order.Id, ORDER_STATUS_OPEN, lang)
        if order_not_found:
            await interaction.response.send_message(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
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
        error_msg = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                error_msg = _ls(interaction, _LS_NOT_FOUND)
            elif order.Status != ORDER_STATUS_IN_PROGRESS:
                error_msg = _ls(interaction, _LS_COMPLETE_NOT_IN_PROGRESS)
            else:
                is_crafter = order.CrafterId == interaction.user.id
                is_admin = interaction.user.guild_permissions.administrator
                if not is_crafter and not is_admin:
                    error_msg = _ls(interaction, _LS_COMPLETE_NOT_CRAFTER)
        if error_msg is not None:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return False
        return True

    async def callback(self, interaction: Interaction):
        row_found = False
        item_name = creator_id = crafter_id = thread_id = None
        with interaction.client.session_scope() as session:
            conditions = [CraftingOrder.Id == self.order_id, CraftingOrder.Status == ORDER_STATUS_IN_PROGRESS]
            if not interaction.user.guild_permissions.administrator:
                conditions.append(CraftingOrder.CrafterId == interaction.user.id)
            row = session.execute(
                sa_update(CraftingOrder)
                .where(*conditions)
                .values(Status=ORDER_STATUS_COMPLETED)
                .returning(
                    CraftingOrder.ItemName,
                    CraftingOrder.ItemNameLocalized,
                    CraftingOrder.CreatorId,
                    CraftingOrder.CrafterId,
                    CraftingOrder.ThreadId,
                )
            ).fetchone()
            row_found = row is not None
            if row_found:
                item_name = _display_item_name(row)
                creator_id = row.CreatorId
                crafter_id = row.CrafterId
                thread_id = row.ThreadId
        if not row_found:
            await interaction.response.send_message(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        crafter_mention = f"<@{crafter_id}>" if crafter_id else interaction.user.mention
        # DM the creator; fall back to thread if DM fails
        used_thread = False
        try:
            creator = await interaction.client.fetch_user(creator_id)
            await creator.send(_ls(interaction, _LS_COMPLETE_DM_COMPLETE, item=item_name, crafter=crafter_mention))
        except (discord.Forbidden, discord.NotFound):
            used_thread = await _thread_fallback(
                interaction,
                self.order_id,
                _ls(interaction, _LS_COMPLETE_DM_COMPLETE, item=item_name, crafter=crafter_mention),
                creator_id,
            )

        if used_thread:
            _schedule_thread_cleanup(interaction, self.order_id)

        await interaction.response.edit_message(content=_ls(interaction, _LS_COMPLETE_DONE), embed=None, view=None)
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
        error_msg = None
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(self.order_id, session)
            if order is None:
                error_msg = _ls(interaction, _LS_NOT_FOUND)
            elif order.Status in (ORDER_STATUS_COMPLETED, ORDER_STATUS_CANCELLED):
                error_msg = _ls(interaction, _LS_NOT_FOUND)
            else:
                is_creator = order.CreatorId == interaction.user.id
                is_admin = interaction.user.guild_permissions.administrator
                if not is_creator and not is_admin:
                    error_msg = _ls(interaction, _LS_CANCEL_NOT_ALLOWED)
        if error_msg is not None:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return False
        return True

    async def callback(self, interaction: Interaction):
        row_found = False
        item_name = creator_id = thread_id = None
        cancelled_by_creator = False
        with interaction.client.session_scope() as session:
            row = session.execute(
                sa_update(CraftingOrder)
                .where(
                    CraftingOrder.Id == self.order_id,
                    CraftingOrder.Status.not_in([ORDER_STATUS_COMPLETED, ORDER_STATUS_CANCELLED]),
                )
                .values(Status=ORDER_STATUS_CANCELLED)
                .returning(
                    CraftingOrder.ItemName,
                    CraftingOrder.ItemNameLocalized,
                    CraftingOrder.CreatorId,
                    CraftingOrder.ThreadId,
                )
            ).fetchone()
            row_found = row is not None
            if row_found:
                item_name = _display_item_name(row)
                creator_id = row.CreatorId
                cancelled_by_creator = interaction.user.id == creator_id
                thread_id = row.ThreadId
        if not row_found:
            await interaction.response.send_message(_ls(interaction, _LS_NOT_FOUND), ephemeral=True)
            return

        # DM only if cancelled by admin (not by creator); fall back to thread if DM fails
        used_thread = False
        if not cancelled_by_creator:
            try:
                creator = await interaction.client.fetch_user(creator_id)
                await creator.send(_ls(interaction, _LS_CANCEL_DM_CANCEL, item=item_name))
            except (discord.Forbidden, discord.NotFound):
                used_thread = await _thread_fallback(
                    interaction, self.order_id, _ls(interaction, _LS_CANCEL_DM_CANCEL, item=item_name), creator_id
                )

        if used_thread:
            _schedule_thread_cleanup(interaction, self.order_id)

        await interaction.response.edit_message(content=_ls(interaction, _LS_CANCEL_DONE), embed=None, view=None)
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
        from modules.wow.views.modals import AskQuestionModal

        lang = interaction.client.get_guild_language(interaction.guild_id)
        modal = AskQuestionModal(self.order_id, lang)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# DM Thread Fallback
# ---------------------------------------------------------------------------


async def _try_delete_thread(thread: discord.Thread, order_id: int, context: str) -> None:
    """Best-effort thread deletion; logs a warning on failure."""
    try:
        await thread.delete()
    except discord.HTTPException:
        log.warning("Failed to clean up %s thread for order #%d", context, order_id)


def _schedule_thread_cleanup(interaction: Interaction, order_id: int) -> None:
    """Write MessageDeleteAt for the order so the background task auto-deletes the thread.

    Called after a thread was successfully used as a DM fallback. The write is advisory -
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
    except Exception:
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

    try:
        channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden):
        channel = None
    if channel is None:
        log.warning("Board channel %d not found for order #%d", channel_id, order_id)
        return False
    if thread_id:
        try:
            thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
        except (discord.NotFound, discord.Forbidden):
            thread = None
    else:
        thread = None

    is_new_thread = thread is None
    if thread is None:
        try:
            msg = await channel.fetch_message(message_id)
            thread_name = _ls(interaction, _LS_ASK_THREAD_NAME, item=item_name)[:100]
            thread = await msg.create_thread(name=thread_name)
        except discord.HTTPException:
            log.warning("Failed to create DM fallback thread for order #%d", order_id)
            return False

    try:
        await thread.send(f"{message}\n<@{creator_id}>")
    except discord.HTTPException:
        if is_new_thread:
            await _try_delete_thread(thread, order_id, "unsent DM fallback")
        log.warning("Failed to send message to DM fallback thread for order #%d", order_id)
        return False

    thread_orphaned = False
    if is_new_thread:
        with interaction.client.session_scope() as session:
            order = CraftingOrder.get_by_id(order_id, session)
            if order is None:
                thread_orphaned = True
            else:
                order.ThreadId = thread.id

    if thread_orphaned:
        await _try_delete_thread(thread, order_id, "orphaned DM fallback")
        return False

    return True
