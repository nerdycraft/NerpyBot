# -*- coding: utf-8 -*-

from datetime import UTC, datetime, time, timedelta
from typing import Optional

from discord import Color, Embed, Interaction, Member, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import GroupCog
from humanize import naturaldate, naturaldelta
from pytimeparse2 import parse

from models.moderation import AutoDelete, AutoKicker

from utils.cog import NerpyBotCog
from utils.helpers import notify_error, register_before_loop, send_paginated
from utils.permissions import validate_channel_permissions

# If no tzinfo is given then UTC is assumed.
LOOP_RUN_TIME = time(hour=12, minute=30, tzinfo=UTC)


class Moderation(NerpyBotCog, GroupCog, group_name="moderation"):
    """cog for bot management"""

    autodeleter = app_commands.Group(name="autodeleter", description="Manage autodeletion per channel")
    user_group = app_commands.Group(name="user", description="User moderation")

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

            for configuration in configurations:
                if configuration is None:
                    continue
                if configuration.Enabled and configuration.KickAfter > 0:
                    guild = self.bot.get_guild(configuration.GuildId)
                    if guild is None:
                        continue
                    self.bot.log.info(f"[{guild.name} ({guild.id})]: checking for members without role")
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
                                        f"You have not selected a role on {guild.name}. "
                                        f"Please choose a role until {naturaldate(kick_after)}."
                                    )
        except Exception as ex:
            self.bot.log.error(f"Autokicker: {ex}")
            await notify_error(self.bot, "Autokicker background loop", ex)
        self.bot.log.debug("Finish Autokicker Loop!")

    @tasks.loop(minutes=5)
    async def _autodeleter_loop(self):
        self.bot.log.debug("Start Autodeleter Loop!")
        message = None
        channel = None
        try:
            with self.bot.session_scope() as session:
                self.bot.log.debug("Fetching configurations")
                configurations = AutoDelete.get_all(session)
                self.bot.log.debug(f"Fetched {len(configurations)} configurations")

            for configuration in configurations:
                if not configuration.Enabled:
                    continue
                guild = self.bot.get_guild(configuration.GuildId)
                if configuration.DeleteOlderThan is None:
                    list_before = None
                else:
                    list_before = datetime.now(UTC) - timedelta(seconds=configuration.DeleteOlderThan)
                    list_before = list_before.replace(tzinfo=UTC)
                channel = guild.get_channel(configuration.ChannelId)

                messages = []
                if channel is not None:
                    messages = [message async for message in channel.history(before=list_before, oldest_first=True)]

                message_limit = 0
                if configuration.KeepMessages is not None:
                    message_limit = configuration.KeepMessages

                while len(messages) > message_limit:
                    self.bot.log.debug(f"Messages in List: {len(messages)}")
                    message = messages.pop(0)
                    self.bot.log.debug(f"Check message: {message}")
                    if not configuration.DeletePinnedMessage and message.pinned:
                        self.bot.log.debug("Skip pinned message")
                        continue
                    self.bot.log.info(
                        f"[{guild.name} ({guild.id})]: deleting message from #{message.channel.name} "
                        f"by {message.author} ({message.author.id}), created at {message.created_at}"
                    )
                    await message.delete()
        except Exception as ex:
            self.bot.log.error(f"Autodeleter: {ex}")
            if channel is not None:
                self.bot.log.debug(f"Channel: {channel}")
            if message is not None:
                self.bot.log.debug(f"Message: {message}")
                self.bot.log.debug(f"Channel from Message: {message.channel.name}")
            await notify_error(self.bot, "Autodeleter background loop", ex)
        self.bot.log.debug("Finish Autodeleter Loop!")

    @app_commands.command()
    @app_commands.rename(kick_reminder_message="reminder_message")
    @checks.has_permissions(kick_members=True)
    async def autokicker(
        self, interaction: Interaction, enable: bool, kick_after: str, kick_reminder_message: Optional[str] = None
    ):
        """Activates the AutoKicker. [bot-moderator]

        Parameters
        ----------
        interaction
        enable: bool
        kick_after: str
            Time after someone gets kicked, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        kick_reminder_message: Optional[str]
        """
        with self.bot.session_scope() as session:
            configuration = AutoKicker.get_by_guild(interaction.guild.id, session)
            kick_time = parse(kick_after)
            if kick_time is None:
                await interaction.response.send_message(
                    "Only timespans up until weeks are allowed. Do not use months or years.", ephemeral=True
                )
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

        await interaction.response.send_message("AutoKicker configured for this server.", ephemeral=True)

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
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel_id, session)
            if configuration is not None:
                await interaction.response.send_message(
                    "This Channel is already configured for AutoDelete."
                    "Please edit or delete the existing configuration.",
                    ephemeral=True,
                )
                return

            if interaction.guild.get_channel(channel_id) is not None:
                validate_channel_permissions(
                    channel, interaction.guild, "view_channel", "manage_messages", "read_message_history"
                )
                if delete_older_than is None:
                    delete = delete_older_than
                else:
                    delete = parse(delete_older_than)
                    if delete is None:
                        await interaction.response.send_message(
                            "Only timespans up until weeks are allowed. Do not use months or years.",
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

        await interaction.response.send_message(f'AutoDeleter configured for channel "{channel_name}".', ephemeral=True)

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
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel_id, session)
            if configuration is not None:
                AutoDelete.delete(interaction.guild.id, channel_id, session)
                await interaction.response.send_message(
                    f'Deleted configuration for channel "{channel_name}".', ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f'No configuration for channel "{channel_name}" found!', ephemeral=True
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
            configurations = AutoDelete.get_by_guild(interaction.guild.id, session)
            if configurations is not None:
                msg = ""
                for configuration in configurations:
                    channel = interaction.guild.get_channel(configuration.ChannelId)
                    channel_name = channel.mention if channel else f"Unknown ({configuration.ChannelId})"
                    status = "\u2705" if configuration.Enabled else "\u23f8\ufe0f"
                    age = naturaldelta(configuration.DeleteOlderThan) if configuration.DeleteOlderThan else "\u2014"
                    keep = configuration.KeepMessages if configuration.KeepMessages else "\u2014"
                    pinned = "Yes" if configuration.DeletePinnedMessage else "No"
                    msg += f"{status} **{channel_name}**\n"
                    msg += f"> Age limit: {age} \u00b7 Keep: {keep} \u00b7 Delete pinned: {pinned}\n\n"
                await send_paginated(
                    interaction, msg, title="\U0001f5d1\ufe0f AutoDeleter", color=0xE74C3C, ephemeral=True
                )
            else:
                await interaction.response.send_message("No configuration found!", ephemeral=True)

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
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel.id, session)
            if configuration is None:
                await interaction.response.send_message(f"No auto-delete config for {channel.mention}.", ephemeral=True)
                return
            if not configuration.Enabled:
                await interaction.response.send_message(
                    f"Auto-deletion is already paused for {channel.mention}.", ephemeral=True
                )
                return
            configuration.Enabled = False
        await interaction.response.send_message(f"Paused auto-deletion for {channel.mention}.", ephemeral=True)

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
            configuration = AutoDelete.get_by_channel(interaction.guild.id, channel.id, session)
            if configuration is None:
                await interaction.response.send_message(f"No auto-delete config for {channel.mention}.", ephemeral=True)
                return
            if configuration.Enabled:
                await interaction.response.send_message(
                    f"Auto-deletion is already active for {channel.mention}.", ephemeral=True
                )
                return
            configuration.Enabled = True
        await interaction.response.send_message(f"Resumed auto-deletion for {channel.mention}.", ephemeral=True)

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
                    f'Updated configuration for channel "{channel_name}".', ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f'Configuration for channel "{channel_name}" does not exist. Please create one first.',
                    ephemeral=True,
                )

    @user_group.command(name="info")
    @checks.has_permissions(moderate_members=True)
    async def _get_user_info(self, interaction: Interaction, member: Optional[Member] = None):
        """displays information about given user [bot-moderator]"""

        member = member or interaction.user
        created = member.created_at.strftime("%d. %B %Y - %H:%M")
        joined = member.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = Embed(title=member.display_name, color=Color(0xE74C3C))
        emb.description = f"Original name: {member.name}"
        emb.set_thumbnail(url=member.avatar.url)
        emb.add_field(name="Created", value=created)
        emb.add_field(name="Joined", value=joined)
        emb.add_field(name="Top Role", value=member.top_role.name.replace("@", ""))
        rn = []
        for r in member.roles:
            rn.append(r.name.replace("@", ""))

        emb.add_field(name="Roles", value=", ".join(rn), inline=False)

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
        msg = ""
        if show_only_users_without_roles:
            for member in interaction.guild.members:
                if len(member.roles) == 1:
                    joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                    msg += f"> **{member.display_name}** \u2014 joined: {joined}\n"
        else:
            for member in interaction.guild.members:
                created = member.created_at.strftime("%d. %b %Y - %H:%M")
                joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                msg += f"> **{member.display_name}** \u2014 created: {created} \u00b7 joined: {joined}\n"

        if msg == "":
            msg = "None found."

        await send_paginated(interaction, msg, title="\U0001f465 Members", color=0xE74C3C, ephemeral=True)

    @app_commands.command()
    async def membercount(self, interaction: Interaction):
        """displays the current membercount of the server [bot-moderator]"""
        emb = Embed(
            description=f"There are currently **{interaction.guild.member_count}** members on this server.",
            color=Color(0xE74C3C),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Moderation(bot))
