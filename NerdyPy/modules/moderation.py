# -*- coding: utf-8 -*-
from datetime import timezone, time, datetime, timedelta
from typing import Optional, Union

import discord
import humanize
import pytimeparse
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_command, hybrid_group, command

import utils.format as fmt
from models.AutoDelete import AutoDelete
from models.RoleChecker import RoleChecker
from utils.errors import NerpyException

utc = timezone.utc
# If no tzinfo is given then UTC is assumed.
loop_run_time = time(hour=12, minute=30, tzinfo=utc)


class Moderation(Cog):
    """cog for bot management"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
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
    @checks.has_permissions(kick_members=True)
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
    @checks.has_permissions(manage_messages=True)
    async def autodeleter(self, ctx):
        """Manage autodeletion per channel [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await ctx.send(args[1])

    @autodeleter.command(name="create")
    @checks.has_permissions(manage_messages=True)
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
    @checks.has_permissions(manage_messages=True)
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
    @checks.has_permissions(manage_messages=True)
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

    @hybrid_group(aliases=["u"])
    @checks.has_permissions(moderate_members=True)
    async def user(self, ctx):
        """user moderation [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await ctx.send(args[1])

    @user.command(name="info")
    @checks.has_permissions(moderate_members=True)
    async def _get_user_info(self, ctx, member: Optional[discord.Member]):
        """displays information about given user [bot-moderator]"""

        member = member or ctx.author
        created = member.created_at.strftime("%d. %B %Y - %H:%M")
        joined = member.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = discord.Embed(title=member.display_name)
        emb.description = f"original name: {member.name}"
        emb.set_thumbnail(url=member.avatar.url)
        emb.add_field(name="created", value=created)
        emb.add_field(name="joined", value=joined)
        emb.add_field(name="top role", value=member.top_role.name.replace("@", ""))
        rn = []
        for r in member.roles:
            rn.append(r.name.replace("@", ""))

        emb.add_field(name="roles", value=", ".join(rn), inline=False)

        await ctx.send(embed=emb)

    @user.command(name="list")
    @checks.has_permissions(moderate_members=True)
    async def _list_user_info_from_guild(self, ctx, show_only_users_without_roles: Optional[bool]):
        """displays a list of users on your server [bot-moderator]"""
        msg = ""
        if show_only_users_without_roles:
            for member in ctx.guild.members:
                if len(member.roles) == 1:
                    joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                    msg += f"{member.display_name}: joined: {joined}\n"
        else:
            for member in ctx.guild.members:
                created = member.created_at.strftime("%d. %b %Y - %H:%M")
                joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                msg += f"{member.display_name}: [created: {created} | joined: {joined}]\n"

        if msg == "":
            msg = "None found."

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            await ctx.send(fmt.box(page))

    @hybrid_command()
    async def membercount(self, ctx):
        """displays the current membercount of the server [bot-moderator]"""
        await ctx.send(fmt.inline(f"There are currently {ctx.guild.member_count} members on this discord"))

    @hybrid_command(name="leave", aliases=["stop"])
    async def _bot_leave_channel(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)

    @command()
    async def history(self, ctx):
        """displays the last 10 received commands since last restart [bot-moderator]"""
        if ctx.guild.id in ctx.bot.last_cmd_cache:
            msg = ""
            for m in ctx.bot.last_cmd_cache[ctx.guild.id]:
                if m.content != "":
                    msg += f"{m.author} - {m.content}\n"

            if msg != "":
                await ctx.send(fmt.box(msg))
                return
        await ctx.send("No recent commands to display.")

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
    await bot.add_cog(Moderation(bot))
