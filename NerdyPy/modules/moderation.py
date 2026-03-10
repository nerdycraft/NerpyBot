# -*- coding: utf-8 -*-

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Optional

from discord import Color, Embed, HTTPException, Interaction, Member, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import GroupCog
from humanize import naturaldate, naturaldelta
from pytimeparse2 import parse

from models.moderation import AutoDelete, AutoKicker

from utils.cog import NerpyBotCog
from utils.helpers import fetch_message_content, notify_error, register_before_loop, send_paginated
from utils.permissions import validate_channel_permissions
from utils.strings import get_guild_language, get_string

# If no tzinfo is given then UTC is assumed.
LOOP_RUN_TIME = time(hour=12, minute=30, tzinfo=UTC)

# Bulk-delete endpoint only accepts messages younger than 14 days.
_BULK_MAX_AGE = timedelta(days=14)
# Discord allows 2–100 messages per bulk-delete request.
_BULK_BATCH_SIZE = 100
# Per-run cap for individually-deleted messages (> 14 days old).
# Keeps each loop tick under ~1 minute; any remainder is picked up next tick.
_MAX_INDIVIDUAL_PER_RUN = 50


class Moderation(NerpyBotCog, GroupCog, group_name="moderation"):
    """cog for bot management"""

    autodeleter = app_commands.Group(name="autodeleter", description="Manage autodeletion per channel")
    user_group = app_commands.Group(name="user", description="User moderation")

    def _lang(self, guild_id):
        """Look up the guild's language preference."""
        with self.bot.session_scope() as session:
            return get_guild_language(guild_id, session)

    def __init__(self, bot):
        super().__init__(bot)
        register_before_loop(bot, self._autokicker_loop, "AutoKicker")
        register_before_loop(bot, self._autodeleter_loop, "AutoDeleter")
        self._autokicker_loop.start()
        self._autodeleter_loop.start()

    def cog_unload(self):
        self._autokicker_loop.cancel()
        self._autodeleter_loop.cancel()

    @tasks.loop(time=LOOP_RUN_TIME)
    async def _autokicker_loop(self):
        self.bot.log.debug("Start Autokicker Loop!")
        try:
            with self.bot.session_scope() as session:
                self.bot.log.debug("Fetching configurations")
                configurations = AutoKicker.get_all(session)
                self.bot.log.debug(f"Fetched {len(configurations)} configurations")
                guild_langs = {c.GuildId: get_guild_language(c.GuildId, session) for c in configurations}

            for configuration in configurations:
                if configuration is None:
                    continue
                if configuration.Enabled and configuration.KickAfter > 0:
                    guild = self.bot.get_guild(configuration.GuildId)
                    if guild is None:
                        continue
                    self.bot.log.info(f"[{guild.name} ({guild.id})]: checking for members without role")
                    lang = guild_langs.get(configuration.GuildId, "en")
                    for member in guild.members:
                        if len(member.roles) == 1:
                            self.bot.log.debug(
                                f"[{guild.name} ({guild.id})]: member without role: {member} ({member.id})"
                            )
                            kick_reminder = datetime.now(UTC) - timedelta(seconds=(configuration.KickAfter / 2))
                            kick_reminder = kick_reminder.replace(tzinfo=UTC)
                            kick_after = datetime.now(UTC) - timedelta(seconds=configuration.KickAfter)
                            kick_after = kick_after.replace(tzinfo=UTC)

                            if member.joined_at < kick_after:
                                self.bot.log.debug(f"[{guild.name} ({guild.id})]: kicking {member} ({member.id})")
                                await member.kick()
                            elif member.joined_at < kick_reminder:
                                self.bot.log.debug(
                                    f"[{guild.name} ({guild.id})]: sending kick reminder to {member} ({member.id})"
                                )
                                if configuration.ReminderMessage is not None:
                                    await member.send(configuration.ReminderMessage)
                                else:
                                    await member.send(
                                        get_string(
                                            lang,
                                            "moderation.autokicker.default_reminder",
                                            guild=guild.name,
                                            deadline=naturaldate(kick_after),
                                        )
                                    )
        except Exception as ex:
            self.bot.log.error(f"Autokicker: {ex}")
            await notify_error(self.bot, "Autokicker background loop", ex)
        self.bot.log.debug("Finish Autokicker Loop!")

    @tasks.loop(minutes=5)
    async def _autodeleter_loop(self):
        """
        Iterate enabled AutoDelete configurations, resolve their guilds and channels, and run per-channel cleanup.

        Fetches all AutoDelete entries from the database, skips configurations that are disabled or whose guild/channel cannot be resolved, and invokes _cleanup_channel for each remaining configuration. If a Discord HTTP 429 (rate limit) is encountered while cleaning a channel, stops processing further channels for the current run. Per-channel exceptions are logged; an unexpected error during the overall loop is logged and reported via notify_error.
        """
        self.bot.log.debug("Start Autodeleter Loop!")
        try:
            with self.bot.session_scope() as session:
                configurations = AutoDelete.get_all(session)
            self.bot.log.debug(f"Fetched {len(configurations)} configurations")

            for configuration in configurations:
                if not configuration.Enabled:
                    continue
                guild = self.bot.get_guild(configuration.GuildId)
                if guild is None:
                    continue
                channel = guild.get_channel(configuration.ChannelId)
                if channel is None:
                    continue
                try:
                    await self._cleanup_channel(configuration, guild, channel)
                except HTTPException as ex:
                    if ex.status == 429:
                        self.bot.log.warning(
                            f"Autodeleter: rate limited on #{channel.name}, skipping remaining channels this run"
                        )
                        break
                    self.bot.log.error(f"Autodeleter: Discord error on #{channel.name}: {ex}")
                except Exception as ex:
                    self.bot.log.error(f"Autodeleter: error cleaning #{channel.name}: {ex}")
        except Exception as ex:
            self.bot.log.error(f"Autodeleter: {ex}")
            await notify_error(self.bot, "Autodeleter background loop", ex)
        self.bot.log.debug("Finish Autodeleter Loop!")

    async def _cleanup_channel(self, configuration, guild, channel):
        """
        Remove messages from a channel according to an AutoDelete configuration.

        Deletes messages while preserving the newest `KeepMessages` messages and respecting `DeletePinnedMessage` and `DeleteOlderThan` from the configuration. Messages newer than 14 days are deleted in bulk (batched up to 100 per API call); messages 14 days or older are deleted individually, capped at _MAX_INDIVIDUAL_PER_RUN per run. Threads attached to messages are deleted prior to deleting their parent messages. HTTP 429 (rate limit) errors are propagated to allow the caller to handle/back off; other inaccessible-or-already-deleted resources are ignored.
        """
        cutoff = None
        if configuration.DeleteOlderThan is not None:
            cutoff = datetime.now(UTC) - timedelta(seconds=configuration.DeleteOlderThan)

        message_limit = configuration.KeepMessages or 0

        # Fetch enough candidates to satisfy keep_messages plus a full work batch.
        # Any excess is left for the next tick, preventing huge history pulls.
        fetch_limit = message_limit + _BULK_BATCH_SIZE + _MAX_INDIVIDUAL_PER_RUN
        # Fetch newest-first so candidates[0] is always the most recent message before cutoff.
        # This ensures keep_messages correctly preserves the actual newest messages in the channel,
        # not just the newest within a truncated oldest-first window.
        candidates = [m async for m in channel.history(before=cutoff, oldest_first=False, limit=fetch_limit)]

        # Respect keep_messages: skip the first message_limit entries (the newest ones to preserve).
        to_delete = candidates[message_limit:] if message_limit > 0 else candidates

        # Skip pinned messages unless explicitly configured to delete them.
        if not configuration.DeletePinnedMessage:
            to_delete = [m for m in to_delete if not m.pinned]

        if not to_delete:
            return

        # Split into bulk-eligible (< 14 days) and individually-deleted (≥ 14 days).
        age_cutoff = datetime.now(UTC) - _BULK_MAX_AGE
        bulk = []
        individual = []
        for m in to_delete:
            # Message.created_at is always UTC-aware (snowflake-derived); no normalization needed.
            (bulk if m.created_at > age_cutoff else individual).append(m)

        # Delete threads attached to bulk messages first (threads need their own API call).
        for m in bulk:
            if m.thread:
                try:
                    await m.thread.delete()
                    await asyncio.sleep(0.5)
                except HTTPException as ex:
                    if ex.status == 429:
                        raise
                    # already gone or inaccessible; ignore other HTTP errors

        # Bulk-delete recent messages in batches of up to 100.
        for i in range(0, len(bulk), _BULK_BATCH_SIZE):
            batch = bulk[i : i + _BULK_BATCH_SIZE]
            self.bot.log.info(f"[{guild.name} ({guild.id})]: bulk deleting {len(batch)} messages from #{channel.name}")
            if len(batch) == 1:
                await batch[0].delete()
            else:
                await channel.delete_messages(batch)
            await asyncio.sleep(1.0)

        # Individually delete old messages, capped per run to avoid long-running ticks.
        capped = individual[:_MAX_INDIVIDUAL_PER_RUN]
        for message in capped:
            self.bot.log.info(
                f"[{guild.name} ({guild.id})]: deleting old message from #{channel.name} "
                f"by {message.author} ({message.author.id}), created at {message.created_at}"
            )
            if message.thread:
                try:
                    await message.thread.delete()
                except HTTPException as ex:
                    if ex.status == 429:
                        raise
                    # already gone or inaccessible; ignore other HTTP errors
            await message.delete()
            await asyncio.sleep(1.0)

        if len(individual) > _MAX_INDIVIDUAL_PER_RUN:
            self.bot.log.debug(
                f"Autodeleter: #{channel.name} has {len(individual) - _MAX_INDIVIDUAL_PER_RUN} more old messages;"
                " will continue next run"
            )

    @app_commands.command()
    @app_commands.rename(
        kick_reminder_message="reminder_message",
        reminder_message_source="reminder-message-source",
    )
    @app_commands.describe(
        enable="Whether to enable the autokicker",
        kick_after='Time after someone gets kicked, e.g. "1 day", "1 week", "5 minutes"',
        kick_reminder_message="Custom reminder message sent before kick (optional)",
        reminder_message_source="Message ID or link whose text becomes the reminder message (message is deleted)",
    )
    @checks.has_permissions(kick_members=True)
    async def autokicker(
        self,
        interaction: Interaction,
        enable: bool,
        kick_after: str,
        kick_reminder_message: Optional[str] = None,
        reminder_message_source: Optional[str] = None,
    ):
        """Activates the AutoKicker. [bot-moderator]"""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)

        # Fetch from a message reference if provided
        if reminder_message_source:
            content, error = await fetch_message_content(
                self.bot,
                reminder_message_source,
                None,
                interaction,
                lang,
                key_prefix="moderation.fetch_message",
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            kick_reminder_message = content

        with self.bot.session_scope() as session:
            configuration = AutoKicker.get_by_guild(interaction.guild.id, session)
            kick_time = parse(kick_after)
            if kick_time is None:
                await interaction.response.send_message(get_string(lang, "moderation.invalid_timespan"), ephemeral=True)
                return
            if configuration is not None:
                configuration.KickAfter = kick_time
                configuration.Enabled = enable
                configuration.ReminderMessage = kick_reminder_message
            else:
                autokicker = AutoKicker(
                    GuildId=interaction.guild.id,
                    KickAfter=kick_time,
                    Enabled=enable,
                    ReminderMessage=kick_reminder_message,
                )
                session.add(autokicker)

        await interaction.response.send_message(get_string(lang, "moderation.autokicker.configured"), ephemeral=True)

    @autodeleter.command(name="create")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_create(
        self,
        interaction: Interaction,
        channel: TextChannel,
        delete_older_than: Optional[str] = None,
        keep_messages: Optional[int] = None,
        delete_pinned_message: bool = False,
    ) -> None:
        """
        Creates AutoDeletion configuration on a per-channel basis.

        Parameters
        ----------
        interaction
        channel: discord.TextChannel
        delete_older_than: Optional[str]
            Time after messages get deleted, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        keep_messages: Optional[int]
            Messages to keep after deletion. Can be used in combination with "delete_older_than".
        delete_pinned_message: bool
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel_id, session)
            if configuration is not None:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.create.already_exists"),
                    ephemeral=True,
                )
                return

            if interaction.guild.get_channel(channel_id) is not None:
                validate_channel_permissions(
                    channel,
                    interaction.guild,
                    "view_channel",
                    "manage_messages",
                    "manage_threads",
                    "read_message_history",
                )
                if delete_older_than is None:
                    delete = delete_older_than
                else:
                    delete = parse(delete_older_than)
                    if delete is None:
                        await interaction.response.send_message(
                            get_string(lang, "moderation.invalid_timespan"),
                            ephemeral=True,
                        )
                        return

                deleter = AutoDelete(
                    GuildId=interaction.guild.id,
                    ChannelId=channel_id,
                    KeepMessages=keep_messages,
                    DeleteOlderThan=delete,
                    DeletePinnedMessage=delete_pinned_message,
                    Enabled=True,
                )
                session.add(deleter)

        await interaction.response.send_message(
            get_string(lang, "moderation.autodeleter.create.success", channel=channel_name), ephemeral=True
        )

    @autodeleter.command(name="delete")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_delete(self, interaction: Interaction, channel: TextChannel) -> None:
        """
        Delete AutoDelete configuration for a channel.

        Parameters
        ----------
        interaction
        channel
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel_id, session)
            if configuration is not None:
                AutoDelete.delete(interaction.guild.id, channel_id, session)
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.delete.success", channel=channel_name), ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.delete.not_found", channel=channel_name), ephemeral=True
                )

    @autodeleter.command(name="list")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_list(self, interaction: Interaction) -> None:
        """
        Lists AutoDelete configuration.

        Parameters
        ----------
        interaction
        """

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configurations = AutoDelete.get_by_guild(interaction.guild.id, session)
            if configurations:
                msg = ""
                for configuration in configurations:
                    channel = interaction.guild.get_channel(configuration.ChannelId)
                    channel_name = channel.mention if channel else f"Unknown ({configuration.ChannelId})"
                    status = "\u2705" if configuration.Enabled else "\u23f8\ufe0f"
                    age = naturaldelta(configuration.DeleteOlderThan) if configuration.DeleteOlderThan else "\u2014"
                    keep = configuration.KeepMessages if configuration.KeepMessages else "\u2014"
                    pinned_key = (
                        "moderation.autodeleter.list.pinned_yes"
                        if configuration.DeletePinnedMessage
                        else "moderation.autodeleter.list.pinned_no"
                    )
                    pinned = get_string(lang, pinned_key)
                    msg += f"{status} **{channel_name}**\n"
                    msg += f"> {get_string(lang, 'moderation.autodeleter.list.entry_details', age=age, keep=keep, pinned=pinned)}\n\n"
                await send_paginated(
                    interaction,
                    msg,
                    title=get_string(lang, "moderation.autodeleter.list.title"),
                    color=0xE74C3C,
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.list.empty"), ephemeral=True
                )

    @autodeleter.command(name="pause")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_pause(self, interaction: Interaction, channel: TextChannel):
        """pause auto-deletion for a channel without removing the config

        Parameters
        ----------
        interaction
        channel: discord.TextChannel
            The channel to pause auto-deletion for
        """
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel.id, session)
            if configuration is None:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.no_config", channel=channel.mention), ephemeral=True
                )
                return
            if not configuration.Enabled:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.pause.already_paused", channel=channel.mention),
                    ephemeral=True,
                )
                return
            configuration.Enabled = False
        await interaction.response.send_message(
            get_string(lang, "moderation.autodeleter.pause.success", channel=channel.mention), ephemeral=True
        )

    @autodeleter.command(name="resume")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_resume(self, interaction: Interaction, channel: TextChannel):
        """resume auto-deletion for a paused channel

        Parameters
        ----------
        interaction
        channel: discord.TextChannel
            The channel to resume auto-deletion for
        """
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel.id, session)
            if configuration is None:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.no_config", channel=channel.mention), ephemeral=True
                )
                return
            if configuration.Enabled:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.resume.already_active", channel=channel.mention),
                    ephemeral=True,
                )
                return
            configuration.Enabled = True
        await interaction.response.send_message(
            get_string(lang, "moderation.autodeleter.resume.success", channel=channel.mention), ephemeral=True
        )

    @autodeleter.command(name="edit")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_modify(
        self,
        interaction: Interaction,
        channel: TextChannel,
        delete_older_than: Optional[str] = None,
        keep_messages: Optional[int] = None,
        delete_pinned_message: bool = False,
    ):
        """
        Modifies a AutoDeletion configuration for a channel.

        Parameters
        ----------
        interaction
        channel: discord.TextChannel
        delete_older_than: Optional[str]
            Time after messages get deleted, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        keep_messages: Optional[int]
            Messages to keep after deletion. Can be used in combination with "delete_older_than".
        delete_pinned_message: bool
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild.id, session)
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel_id, session)
            if configuration is not None:
                if delete_older_than is None:
                    configuration.DeleteOlderThan = delete_older_than
                else:
                    delete_in_seconds = parse(delete_older_than)
                    configuration.DeleteOlderThan = delete_in_seconds
                configuration.KeepMessages = keep_messages if keep_messages is not None else 0
                configuration.DeletePinnedMessage = delete_pinned_message

                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.edit.success", channel=channel_name), ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    get_string(lang, "moderation.autodeleter.edit.not_found", channel=channel_name),
                    ephemeral=True,
                )

    @user_group.command(name="info")
    @checks.has_permissions(moderate_members=True)
    async def _get_user_info(self, interaction: Interaction, member: Optional[Member] = None):
        """displays information about given user [bot-moderator]"""
        lang = self._lang(interaction.guild.id)
        member = member or interaction.user
        created = member.created_at.strftime("%d. %B %Y - %H:%M")
        joined = member.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = Embed(title=member.display_name, color=Color(0xE74C3C))
        emb.description = get_string(lang, "moderation.user.info.original_name", name=member.name)
        emb.set_thumbnail(url=member.avatar.url)
        emb.add_field(name=get_string(lang, "moderation.user.info.created"), value=created)
        emb.add_field(name=get_string(lang, "moderation.user.info.joined"), value=joined)
        emb.add_field(
            name=get_string(lang, "moderation.user.info.top_role"), value=member.top_role.name.replace("@", "")
        )
        rn = []
        for r in member.roles:
            rn.append(r.name.replace("@", ""))

        emb.add_field(name=get_string(lang, "moderation.user.info.roles"), value=", ".join(rn), inline=False)

        await interaction.response.send_message(embed=emb, ephemeral=True)

    @user_group.command(name="list")
    @checks.has_permissions(moderate_members=True)
    async def _list_user_info_from_guild(
        self, interaction: Interaction, show_only_users_without_roles: Optional[bool] = None
    ):
        """displays a list of users on your server [bot-moderator]

        Parameters
        ----------
        interaction
        show_only_users_without_roles: Optional[bool]
            If True shows only Users without a Role. (The role everyone is not considered a given role)
        """
        lang = self._lang(interaction.guild.id)
        msg = ""
        if show_only_users_without_roles:
            for member in interaction.guild.members:
                if len(member.roles) == 1:
                    joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                    msg += f"> {get_string(lang, 'moderation.user.list.entry_no_roles', name=member.display_name, joined=joined)}\n"
        else:
            for member in interaction.guild.members:
                created = member.created_at.strftime("%d. %b %Y - %H:%M")
                joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                msg += f"> {get_string(lang, 'moderation.user.list.entry_full', name=member.display_name, created=created, joined=joined)}\n"

        if msg == "":
            msg = get_string(lang, "moderation.user.list.empty")

        await send_paginated(
            interaction, msg, title=get_string(lang, "moderation.user.list.title"), color=0xE74C3C, ephemeral=True
        )

    @app_commands.command()
    async def membercount(self, interaction: Interaction):
        """displays the current membercount of the server [bot-moderator]"""
        lang = self._lang(interaction.guild.id)
        emb = Embed(
            description=get_string(lang, "moderation.membercount", count=interaction.guild.member_count),
            color=Color(0xE74C3C),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Moderation(bot))
