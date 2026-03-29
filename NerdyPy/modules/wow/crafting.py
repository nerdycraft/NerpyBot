# -*- coding: utf-8 -*-
"""WoW crafting order cog: board management, cleanup loop, language refresh."""

import asyncio

import discord
from discord import Interaction, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import Cog

from typing import Literal

from sqlalchemy import or_, update as sa_update
from sqlalchemy.exc import SQLAlchemyError

from models.wow import (
    CURRENT_BOARD_VERSION,
    CraftingBoardConfig,
    CraftingOrder,
    CraftingRoleMapping,
)
from modules.wow.api import CRAFTING_PROFESSIONS
from utils.helpers import notify_error, register_before_loop
from utils.permissions import validate_channel_permissions
from utils.strings import get_string


class WowCraftingMixin:
    """Crafting order board commands and background cleanup.

    Mixed into the WorldofWarcraft GroupCog via __init__.py.
    """

    craftingorder = app_commands.Group(name="craftingorder", description="manage crafting order board", guild_only=True)

    def _init_crafting(self, bot):
        register_before_loop(bot, self._crafting_cleanup_loop, "Crafting Cleanup")
        self._crafting_cleanup_loop.start()

    # ── Board migration ──────────────────────────────────────────────────

    async def _run_board_migrations(self):
        """Wait for bot ready then migrate any stale crafting boards."""
        await self.bot.wait_until_ready()
        await self._migrate_boards()

    async def _migrate_boards(self):
        """Upgrade crafting boards that are behind CURRENT_BOARD_VERSION."""
        with self.bot.session_scope() as session:
            stale = (
                session.query(CraftingBoardConfig)
                .filter(
                    or_(
                        CraftingBoardConfig.BoardVersion.is_(None),
                        CraftingBoardConfig.BoardVersion < CURRENT_BOARD_VERSION,
                    )
                )
                .all()
            )
            boards = [(c.Id, c.GuildId, c.ChannelId, c.BoardMessageId, c.BoardVersion) for c in stale]

        await asyncio.gather(
            *[
                self._migrate_single_board(config_id, guild_id, channel_id, message_id, version)
                for config_id, guild_id, channel_id, message_id, version in boards
            ]
        )

    async def _migrate_single_board(
        self, config_id: int, guild_id: int, channel_id: int, message_id: int | None, version: int | None
    ):
        """Migrate a single crafting board to CURRENT_BOARD_VERSION.

        On success or terminal LookupError (guild/channel/message permanently gone),
        bumps BoardVersion so the board isn't retried on every restart. Transient
        discord.HTTPException (429, 5xx) does NOT bump the version so the migration
        is retried on the next startup.
        """
        # Local import to break circular dependency: crafting -> views -> cog callbacks -> crafting
        from modules.wow.views.board import CraftingBoardView

        lang = self._lang(guild_id)

        guild = self.bot.get_guild(guild_id)
        try:
            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(guild_id)
                except (discord.NotFound, discord.Forbidden) as exc:
                    raise LookupError(f"guild {guild_id} inaccessible") from exc

            try:
                channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden) as exc:
                raise LookupError(f"channel {channel_id} inaccessible") from exc

            if not message_id:
                raise LookupError("no board message id")

            try:
                msg = await channel.fetch_message(message_id)
            except (discord.NotFound, discord.Forbidden) as exc:
                raise LookupError(f"board message {message_id} inaccessible") from exc
            if msg.author.id != self.bot.user.id:
                raise LookupError("board message not authored by bot")

            # v1 -> v2: add housing button
            embed = msg.embeds[0] if msg.embeds else discord.Embed(color=discord.Color.gold())
            new_view = CraftingBoardView(
                self.bot,
                label=get_string(lang, "wow.craftingorder.create_button"),
                housing_label=get_string(lang, "wow.craftingorder.housing_button"),
            )
            try:
                await msg.edit(embed=embed, view=new_view)
            except (discord.NotFound, discord.Forbidden) as exc:
                raise LookupError(f"board message {message_id} edit failed") from exc
            self.bot.log.info(
                "Board migration v%s->v%d: guild=%d config=%d", version, CURRENT_BOARD_VERSION, guild_id, config_id
            )

        except LookupError as exc:
            # Terminal failure (guild/channel/message gone permanently) - bump version so
            # we don't retry on every restart. Notify the channel if it's still reachable.
            self.bot.log.warning(
                "Board migration failed (terminal) for config=%d guild=%d: %s", config_id, guild_id, exc
            )
            try:
                if guild is None:
                    try:
                        guild = await self.bot.fetch_guild(guild_id)
                    except (discord.NotFound, discord.Forbidden) as fetch_exc:
                        self.bot.log.debug("Could not re-fetch guild %d for notification: %s", guild_id, fetch_exc)
                if guild:
                    channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
                    await channel.send(
                        get_string(
                            lang,
                            "wow.craftingorder.board_migration_failed",
                            channel=channel.mention,
                            guild=guild.name,
                        )
                    )
            except discord.HTTPException as notify_exc:
                self.bot.log.debug("Board migration: could not notify channel %d: %s", channel_id, notify_exc)

        except discord.HTTPException as exc:
            # Transient failure (429, 5xx) - log and skip version bump so migration retries next startup.
            self.bot.log.warning(
                "Board migration failed (transient) for config=%d guild=%d: %s - will retry", config_id, guild_id, exc
            )
            return

        # Bump version on success or terminal LookupError.
        with self.bot.session_scope() as session:
            config = session.get(CraftingBoardConfig, config_id)
            if config:
                config.BoardVersion = CURRENT_BOARD_VERSION

    # ── Crafting cleanup loop ────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def _crafting_cleanup_loop(self):
        """Delete anchored order messages whose MessageDeleteAt deadline has passed."""
        self.bot.log.debug("Start Crafting Cleanup Loop!")
        try:
            with self.bot.session_scope() as session:
                pending = CraftingOrder.get_pending_cleanup(session)
                # Snapshot the fields we need before closing the session
                to_process = [(o.Id, o.GuildId, o.ChannelId, o.OrderMessageId, o.ThreadId) for o in pending]

            cleared_ids = []
            for order_id, guild_id, channel_id, message_id, thread_id in to_process:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    guild = self.bot.get_guild(guild_id)
                    if guild is None:
                        self.bot.log.debug("Crafting cleanup: guild %d not in cache for order #%d", guild_id, order_id)
                        continue
                    try:
                        channel = await guild.fetch_channel(channel_id)
                    except (discord.NotFound, discord.Forbidden):
                        self.bot.log.debug("Crafting cleanup: channel %d not found for order #%d", channel_id, order_id)
                        cleared_ids.append(order_id)
                        continue
                    except discord.HTTPException as ex:
                        self.bot.log.warning(
                            "Crafting cleanup: error fetching channel %d for order #%d: %s", channel_id, order_id, ex
                        )
                        continue
                try:
                    msg = await channel.fetch_message(message_id)
                    if msg.thread:
                        try:
                            await msg.thread.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass  # thread already gone or inaccessible
                        except discord.HTTPException as ex:
                            self.bot.log.debug("Crafting cleanup: thread delete failed for order #%d: %s", order_id, ex)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass  # already gone or inaccessible
                except discord.HTTPException as ex:
                    self.bot.log.warning("Crafting cleanup: failed to delete message for order #%d: %s", order_id, ex)
                    continue

                cleared_ids.append(order_id)

            if cleared_ids:
                with self.bot.session_scope() as session:
                    session.execute(
                        sa_update(CraftingOrder).where(CraftingOrder.Id.in_(cleared_ids)).values(MessageDeleteAt=None)
                    )
        except Exception as ex:
            self.bot.log.error("Crafting cleanup loop error: %s", ex)
            await notify_error(self.bot, "Crafting cleanup background loop", ex)
        self.bot.log.debug("Stop Crafting Cleanup Loop!")

    # ── Crafting Order commands ──────────────────────────────────────────

    @craftingorder.command(name="create")
    @checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel where the board embed will be posted",
        description="Description shown on the board embed (opens a modal if omitted)",
        roles="Profession role mentions separated by spaces or commas",
        description_message="Message ID or link whose text becomes the description (message is deleted)",
    )
    @app_commands.rename(description_message="description-message")
    async def _craftingorder_create(
        self,
        interaction: Interaction,
        channel: TextChannel,
        roles: str,
        description: str | None = None,
        description_message: str | None = None,
    ):
        """create a crafting order board in a channel [manage_channels]"""
        lang = self._lang(interaction.guild_id)

        # Resolve description from message reference if provided
        if description_message:
            from utils.helpers import fetch_message_content

            content, error = await fetch_message_content(
                self.bot,
                description_message,
                channel,
                interaction,
                lang,
                key_prefix="wow.craftingorder.fetch_description",
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            description = content

        if not description:
            # No description provided - show a modal to collect it
            modal = _BoardDescriptionModal(self.bot, lang, mode="create", channel=channel, roles=roles)
            await interaction.response.send_modal(modal)
            return

        if description and not description_message:
            # Inline description provided - show modal pre-filled for review
            modal = _BoardDescriptionModal(
                self.bot, lang, mode="create", channel=channel, roles=roles, default_text=description
            )
            await interaction.response.send_modal(modal)
            return

        await interaction.response.defer(ephemeral=True)
        await self.finish_board_create(interaction, channel, roles, description, lang)

    @staticmethod
    def _parse_role_ids(roles_str: str, guild: discord.Guild) -> list[int]:
        """Parse role mentions/IDs from a space/comma-separated string."""
        role_ids = []
        for part in roles_str.replace(",", " ").split():
            part = part.strip("<@&>")
            if part.isdigit():
                role = guild.get_role(int(part))
                if role:
                    role_ids.append(role.id)
        return role_ids

    @staticmethod
    def _auto_match_roles(guild: discord.Guild, role_ids: list[int], session) -> tuple[list[int], list[int]]:
        """Auto-match Discord roles to Blizzard profession IDs.

        Returns (mapped_role_ids, unmapped_role_ids).
        Creates CraftingRoleMapping rows for each match.
        """
        mapped = []
        unmapped = []
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if not role:
                unmapped.append(role_id)
                continue

            matched = False
            for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
                if prof_name.lower() in role.name.lower():
                    session.add(CraftingRoleMapping(GuildId=guild.id, RoleId=role_id, ProfessionId=prof_id))
                    mapped.append(role_id)
                    matched = True
                    break

            if not matched:
                unmapped.append(role_id)

        return mapped, unmapped

    async def finish_board_create(
        self, interaction: Interaction, channel: TextChannel, roles: str, description: str, lang: str
    ):
        """Shared board creation logic used by both the command and the description modal."""
        role_ids = self._parse_role_ids(roles, interaction.guild)

        if not role_ids:
            await interaction.followup.send(get_string(lang, "wow.craftingorder.create.no_roles"), ephemeral=True)
            return

        validate_channel_permissions(channel, interaction.guild, "send_messages", "embed_links", "manage_threads")

        already_exists_msg = None
        with self.bot.session_scope() as session:
            existing = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            if existing:
                existing_channel = interaction.guild.get_channel(existing.ChannelId)
                ch_mention = existing_channel.mention if existing_channel else f"#{existing.ChannelId}"
                already_exists_msg = get_string(lang, "wow.craftingorder.create.already_exists", channel=ch_mention)

        if already_exists_msg is not None:
            await interaction.followup.send(already_exists_msg, ephemeral=True)
            return

        with self.bot.session_scope() as session:
            config = CraftingBoardConfig(
                GuildId=interaction.guild_id,
                ChannelId=channel.id,
                Description=description,
                BoardVersion=CURRENT_BOARD_VERSION,
            )
            session.add(config)
            session.flush()

            # Auto-match roles to Blizzard professions
            mapped, unmapped = self._auto_match_roles(interaction.guild, role_ids, session)

        # Build embed and view then send to Discord outside the session so the DB
        # connection is not held open during the HTTP call.
        from modules.wow.views.board import CraftingBoardView

        embed = discord.Embed(
            title=get_string(lang, "wow.craftingorder.board_title"),
            description=description,
            color=discord.Color.gold(),
        )
        embed.set_footer(text=get_string(lang, "wow.craftingorder.board_footer"))

        view = CraftingBoardView(
            self.bot,
            label=get_string(lang, "wow.craftingorder.create_button"),
            housing_label=get_string(lang, "wow.craftingorder.housing_button"),
        )
        try:
            msg = await channel.send(embed=embed, view=view)
        except discord.HTTPException as exc:
            # Board config was committed above; clean it up so the guild can retry.
            with self.bot.session_scope() as session:
                orphaned = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
                if orphaned is not None:
                    session.delete(orphaned)
                CraftingRoleMapping.delete_by_guild(interaction.guild_id, session)
            self.bot.log.error("Failed to post crafting board embed (guild=%d): %s", interaction.guild_id, exc)
            await interaction.followup.send(
                get_string(lang, "wow.craftingorder.create.send_failed", channel=channel.mention), ephemeral=True
            )
            return

        try:
            with self.bot.session_scope() as session:
                config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
                if config is not None:
                    config.BoardMessageId = msg.id
        except SQLAlchemyError as exc:
            self.bot.log.error("Failed to save board message ID (guild=%d): %s", interaction.guild_id, exc)
            try:
                await msg.delete()
            except discord.HTTPException as exc:
                self.bot.log.warning(
                    "Failed to delete orphaned board message (guild=%d): %s", interaction.guild_id, exc
                )
            with self.bot.session_scope() as session:
                orphaned = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
                if orphaned is not None:
                    session.delete(orphaned)
                CraftingRoleMapping.delete_by_guild(interaction.guild_id, session)
            await interaction.followup.send(
                get_string(lang, "wow.craftingorder.create.send_failed", channel=channel.mention), ephemeral=True
            )
            return

        await interaction.followup.send(
            get_string(lang, "wow.craftingorder.create.success", channel=channel.mention), ephemeral=True
        )

        if unmapped:
            await self._send_manual_mapping_view(interaction, unmapped, lang)

    @craftingorder.command(name="remove")
    @checks.has_permissions(manage_channels=True)
    async def _craftingorder_remove(self, interaction: Interaction):
        """remove the crafting order board [manage_channels]"""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)

        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            if config is None:
                not_found_msg = get_string(lang, "wow.craftingorder.remove.not_found")
            else:
                not_found_msg = None
                channel_id = config.ChannelId
                message_id = config.BoardMessageId

        if not_found_msg is not None:
            await interaction.followup.send(not_found_msg, ephemeral=True)
            return

        # Try to delete the board embed before committing DB changes
        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await interaction.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                channel = None
        if channel and message_id:
            try:
                msg = await channel.fetch_message(message_id)
                if msg.thread:
                    try:
                        await msg.thread.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass  # thread/message already gone — nothing to clean up
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass  # thread/message already gone — nothing to clean up

        # Now delete DB config
        with self.bot.session_scope() as session:
            CraftingBoardConfig.delete_by_guild(interaction.guild_id, session)
            CraftingRoleMapping.delete_by_guild(interaction.guild_id, session)

        await interaction.followup.send(get_string(lang, "wow.craftingorder.remove.success"), ephemeral=True)

    @craftingorder.command(name="edit")
    @checks.has_permissions(manage_channels=True)
    @app_commands.describe(roles="New role mentions (optional - re-runs auto-matching)")
    async def _craftingorder_edit(self, interaction: Interaction, roles: str | None = None):
        """edit the crafting order board [manage_channels]"""
        lang = self._lang(interaction.guild_id)

        current_description = None
        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            if config is not None:
                current_description = config.Description

        if current_description is None:
            await interaction.response.send_message(
                get_string(lang, "wow.craftingorder.edit.not_found"), ephemeral=True
            )
            return

        # If new roles provided, update the mapping before showing the modal
        unmapped: list[int] = []
        if roles:
            role_ids = self._parse_role_ids(roles, interaction.guild)
            if role_ids:
                with self.bot.session_scope() as session:
                    CraftingRoleMapping.delete_by_guild(interaction.guild_id, session)
                    _mapped, unmapped = self._auto_match_roles(interaction.guild, role_ids, session)

        # Show modal pre-filled with current description
        modal = _BoardDescriptionModal(self.bot, lang, mode="edit", default_text=current_description, unmapped=unmapped)
        await interaction.response.send_modal(modal)

    async def finish_board_edit(
        self, interaction: Interaction, new_description: str, lang: str, unmapped: list[int] | None = None
    ):
        """Update the board description and edit the embed in-place."""
        channel_id = None
        message_id = None
        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(interaction.guild_id, session)
            if config is not None:
                config.Description = new_description
                channel_id = config.ChannelId
                message_id = config.BoardMessageId

        if channel_id is None:
            await interaction.followup.send(get_string(lang, "wow.craftingorder.edit.not_found"), ephemeral=True)
            return

        # Edit the board embed in-place and refresh the view with the housing button.
        # Pre-set True when there is no message to update - description was saved, nothing to fail.
        embed_updated = not message_id
        if message_id:
            try:
                from modules.wow.views.board import CraftingBoardView

                channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
                msg = await channel.fetch_message(message_id)
                embed = msg.embeds[0] if msg.embeds else discord.Embed(color=discord.Color.gold())
                embed.description = new_description
                new_view = CraftingBoardView(
                    self.bot,
                    label=get_string(lang, "wow.craftingorder.create_button"),
                    housing_label=get_string(lang, "wow.craftingorder.housing_button"),
                )
                await msg.edit(embed=embed, view=new_view)
                embed_updated = True
            except discord.HTTPException as exc:
                self.bot.log.warning("Failed to edit board embed (channel=%s, msg=%s): %s", channel_id, message_id, exc)

        if embed_updated:
            await interaction.followup.send(get_string(lang, "wow.craftingorder.edit.success"), ephemeral=True)
        else:
            await interaction.followup.send(get_string(lang, "wow.craftingorder.edit.embed_failed"), ephemeral=True)

        if unmapped:
            await self._send_manual_mapping_view(interaction, unmapped, lang)

    @Cog.listener("on_guild_language_changed")
    async def _on_guild_language_changed(self, guild_id: int, new_lang: str) -> None:
        """Refresh persistent WoW embeds when a guild's language preference changes."""
        await self._refresh_crafting_board(guild_id, new_lang)
        await self._refresh_active_orders(guild_id, new_lang)

    async def _refresh_crafting_board(self, guild_id: int, new_lang: str) -> None:
        """Edit the crafting board embed and view in-place with the new language."""
        from modules.wow.views.board import CraftingBoardView

        with self.bot.session_scope() as session:
            config = CraftingBoardConfig.get_by_guild(guild_id, session)
            if config is None or not config.BoardMessageId or not config.ChannelId:
                return
            channel_id = config.ChannelId
            message_id = config.BoardMessageId
            description = config.Description

        try:
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(channel_id) if guild else None
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)
            msg = await channel.fetch_message(message_id)
            embed = discord.Embed(
                title=get_string(new_lang, "wow.craftingorder.board_title"),
                description=description,
                color=discord.Color.gold(),
            )
            embed.set_footer(text=get_string(new_lang, "wow.craftingorder.board_footer"))
            view = CraftingBoardView(
                self.bot,
                label=get_string(new_lang, "wow.craftingorder.create_button"),
                housing_label=get_string(new_lang, "wow.craftingorder.housing_button"),
            )
            await msg.edit(embed=embed, view=view)
            self.bot.log.info("wow: refreshed crafting board embed for guild %d (lang=%s)", guild_id, new_lang)
        except (discord.NotFound, discord.Forbidden):
            self.bot.log.warning("wow: crafting board message not accessible for guild %d - skipping refresh", guild_id)
        except discord.HTTPException as exc:
            self.bot.log.warning("wow: failed to refresh crafting board for guild %d: %s", guild_id, exc)

    async def _refresh_active_orders(self, guild_id: int, new_lang: str) -> None:
        """Edit each active crafting order card embed and view with the new language."""
        from modules.wow.views.board import build_order_embed, build_order_view

        with self.bot.session_scope() as session:
            orders = CraftingOrder.get_active_by_guild(guild_id, session)
            active_orders = [o for o in orders if o.OrderMessageId and o.ChannelId]
            for o in active_orders:
                session.expunge(o)

        guild = self.bot.get_guild(guild_id)
        for i, order in enumerate(active_orders):
            try:
                channel = guild.get_channel(order.ChannelId) if guild else None
                if channel is None:
                    channel = await self.bot.fetch_channel(order.ChannelId)
                    if channel is not None and guild is None:
                        guild = channel.guild
                msg = await channel.fetch_message(order.OrderMessageId)
                embed = build_order_embed(order, guild, new_lang)
                view = build_order_view(order.Id, order.Status, new_lang)
                await msg.edit(embed=embed, view=view)
                self.bot.log.info("wow: refreshed order #%d embed for guild %d (lang=%s)", order.Id, guild_id, new_lang)
            except (discord.NotFound, discord.Forbidden):
                self.bot.log.warning(
                    "wow: order #%d message not accessible for guild %d - skipping refresh", order.Id, guild_id
                )
            except discord.HTTPException as exc:
                self.bot.log.warning("wow: failed to refresh order #%d for guild %d: %s", order.Id, guild_id, exc)
            if i < len(active_orders) - 1:
                await asyncio.sleep(1)

    async def _send_manual_mapping_view(self, interaction: Interaction, unmapped: list[int], lang: str):
        """Send an ephemeral followup with Select dropdowns for manual profession mapping."""
        from modules.wow.views.board import ManualProfessionMappingView

        unmapped_roles = [
            (rid, (role.name if (role := interaction.guild.get_role(rid)) else str(rid))) for rid in unmapped
        ]
        content = get_string(lang, "wow.craftingorder.manual_map.description")
        view = ManualProfessionMappingView(self.bot, interaction.guild_id, unmapped_roles, lang)
        await interaction.followup.send(content, view=view, ephemeral=True)


class _BoardDescriptionModal(discord.ui.Modal):
    """Modal for collecting/editing board description.

    Supports two modes:
    - "create": calls finish_board_create after submission
    - "edit": updates existing board config and edits the embed in-place
    """

    description_input = discord.ui.TextInput(
        label="Board Description",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )

    def __init__(
        self,
        bot,
        lang: str,
        *,
        mode: Literal["create", "edit"] = "create",
        channel: TextChannel = None,
        roles: str = None,
        default_text: str = None,
        unmapped: list[int] | None = None,
    ):
        super().__init__(title=get_string(lang, "wow.craftingorder.create.modal_title"))
        self.bot = bot
        self.lang = lang
        self.mode = mode
        self.channel = channel
        self.roles = roles
        self.unmapped = unmapped or []
        self.description_input.placeholder = get_string(lang, "wow.craftingorder.create.modal_description")
        if default_text:
            self.description_input.default = default_text

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = self.bot.get_cog("WorldofWarcraft")

        if self.mode == "create":
            await cog.finish_board_create(
                interaction, self.channel, self.roles, self.description_input.value.strip(), self.lang
            )
        else:
            await cog.finish_board_edit(
                interaction, self.description_input.value.strip(), self.lang, unmapped=self.unmapped
            )
