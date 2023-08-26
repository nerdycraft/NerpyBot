# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, timezone, time
from typing import Optional, Union

import discord
import humanize
import pytimeparse
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_command, hybrid_group, group

from models.AutoDelete import AutoDelete
from models.GuildPrefix import GuildPrefix
from models.RoleChecker import RoleChecker

utc = timezone.utc
# If no tzinfo is given then UTC is assumed.
loop_run_time = time(hour=12, minute=30, tzinfo=utc)


@checks.has_permissions(administrator=True)
class Admin(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.settings = {}
        self._rolechecker.start()
        self._autodeleter.start()

    def cog_unload(self):
        self._rolechecker.cancel()
        self._autodeleter.cancel()

    @tasks.loop(time=loop_run_time)
    async def _rolechecker(self):
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                configuration = RoleChecker.get(guild.id, session)
                if configuration is None:
                    continue
                if configuration.Enabled and configuration.KickAfter > 0:
                    self.bot.log.info(f"Checking for member without role in {guild.name}.")
                    for member in guild.members:
                        if len(member.roles) == 1:
                            kick_reminder = datetime.utcnow() - timedelta(seconds=(configuration.KickAfter / 2))
                            kick_reminder = kick_reminder.replace(tzinfo=timezone.utc)
                            kick_after = datetime.utcnow() - timedelta(seconds=configuration.KickAfter)
                            kick_after = kick_after.replace(tzinfo=timezone.utc)

                            if member.joined_at < kick_after:
                                self.bot.log.debug(f"Kick member {member.display_name}!")
                                await member.kick()
                            elif member.joined_at < kick_reminder:
                                if configuration.ReminderMessage is not None:
                                    await member.send(configuration.ReminderMessage)
                                else:
                                    await member.send(
                                        f"You have not selected a role on {guild.name}. "
                                        f"Please choose a role until {humanize.naturaldate(kick_after)}."
                                    )

    @tasks.loop(minutes=5)
    async def _autodeleter(self):
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                configurations = AutoDelete.get(guild.id, session)

                for configuration in configurations:
                    if configuration.DeleteOlderThan is None:
                        list_before = None
                    else:
                        list_before = datetime.utcnow() - timedelta(seconds=configuration.DeleteOlderThan)
                        list_before = list_before.replace(tzinfo=timezone.utc)
                    channel = guild.get_channel(configuration.ChannelId)
                    messages = [message async for message in channel.history(before=list_before, oldest_first=True)]

                    while len(messages) > configuration.KeepMessages:
                        message = messages.pop(0)
                        if not configuration.DeletePinnedMessage and message.pinned:
                            continue
                        self.bot.log.info(f"Delete message {message.id}, created at {message.created_at}.")
                        await message.delete()

    @hybrid_command()
    async def rolechecker(self, ctx, enable: bool, kick_after: str, kick_reminder_message: Optional[str]):
        """Activates the Role Checker. [bot-moderator]"""
        with self.bot.session_scope() as session:
            configuration = RoleChecker.get(ctx.guild.id, session)
            if kick_after is not None:
                kick_time = pytimeparse.parse(kick_after)
                if kick_time is None:
                    await ctx.send("Only timespans up until weeks are allowed. Do not use months or years.")
                    return
            else:
                await ctx.send("You need to specify when I should kick someone!")
                return
            if configuration is not None:
                configuration.KickAfter = kick_time
                configuration.Enabled = enable
                configuration.ReminderMessage = kick_reminder_message
            else:
                rolechecker = RoleChecker(
                    GuildId=ctx.guild.id,
                    KickAfter=kick_time,
                    Enabled=enable,
                    ReminderMessage=kick_reminder_message,
                )
                session.add(rolechecker)

        await ctx.send("RoleChecker configured for this server.")

    @hybrid_group()
    async def autodeleter(self, ctx):
        """Manage autodeletion per channel [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autodeleter.command(name="create")
    async def create_autodeleter(
        self,
        ctx,
        *,
        channel: discord.TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                await ctx.send(
                    "This Channel is already configured for AutoDelete."
                    "Please edit or delete the existing configuration."
                )
            else:
                if ctx.guild.get_channel(channel_id) is not None:
                    if delete_older_than is None:
                        delete = delete_older_than
                    else:
                        delete = pytimeparse.parse(delete_older_than)
                        if delete is None:
                            await ctx.send("Only timespans up until weeks are allowed. Do not use months or years.")
                            return

                    deleter = AutoDelete(
                        GuildId=ctx.guild.id,
                        ChannelId=channel_id,
                        KeepMessages=keep_messages,
                        DeleteOlderThan=delete,
                        DeletePinnedMessage=delete_pinned_message,
                    )
                    session.add(deleter)

        await ctx.send(f'AutoDeleter configured for channel "{channel_name}".')

    @autodeleter.command(name="delete")
    async def delete_autodeleter(self, ctx, *, channel: discord.TextChannel):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                AutoDelete.delete(ctx.guild.id, channel_id, session)
                await ctx.send(f'Deleted configuration for channel "{channel_name}".')
            else:
                await ctx.send(f'No configuration for channel "{channel_name}" found!')

    @autodeleter.command(name="edit")
    async def modify_autodeleter(
        self,
        ctx,
        *,
        channel: discord.TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                if delete_older_than is None:
                    configuration.DeleteOlderThan = delete_older_than
                else:
                    delete_in_seconds = pytimeparse.parse(delete_older_than)
                    configuration.DeleteOlderThan = delete_in_seconds
                configuration.KeepMessages = keep_messages
                configuration.DeletePinnedMessage = delete_pinned_message

                await ctx.send(f'Updated configuration for channel "{channel_name}".')
            else:
                await ctx.send(f'Configuration for channel "{channel_name}" does not exist. Please create one first.')

    @group()
    async def prefix(self, ctx):
        """Manage the prefix for the bot [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command(name="get")
    async def _prefix_get(self, ctx):
        """Get the prefix currently used. [bot-moderator]"""
        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is not None:
                await ctx.send(f"The current prefix is set to: {pref.Prefix}")
            else:
                await ctx.send(
                    'There is no custom prefix set. I will respond to Slash Commands or the default prefix "!".'
                )

    @prefix.command(name="set")
    async def _prefix_set(self, ctx, *, new_pref):
        """Set the prefix to use. [bot-moderator]"""
        if " " in new_pref:
            await ctx.send("Spaces not allowed in prefixes")

        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is None:
                pref = GuildPrefix(GuildId=ctx.guild.id, CreateDate=datetime.utcnow(), Author=ctx.author.name)
                session.add(pref)

            pref.ModifiedDate = datetime.utcnow()
            pref.Prefix = new_pref

        await ctx.send(f"new prefix is now set to '{new_pref}'.")

    @prefix.command(name="delete", aliases=["remove", "rm", "del"])
    async def _prefix_del(self, ctx):
        """Delete the current prefix. [bot-moderator]"""
        with self.bot.session_scope() as session:
            GuildPrefix.delete(ctx.guild.id, session)
        await ctx.send("Prefix removed.")

    @hybrid_command(name="leave", aliases=["stop"])
    async def _bot_leave_channel(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)

    @_rolechecker.before_loop
    async def _role_checker_before_loop(self):
        self.bot.log.info("Rolechecker: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @_autodeleter.before_loop
    async def _autodeleter_before_loop(self):
        self.bot.log.info("AutoDeleter: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
