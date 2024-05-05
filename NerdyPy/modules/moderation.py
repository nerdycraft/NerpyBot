# -*- coding: utf-8 -*-
from datetime import timezone, time, datetime, timedelta, UTC
from typing import Optional, Union

from discord import TextChannel, Member, Embed
from discord.app_commands import checks, rename
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_command, hybrid_group, command, Context
from humanize import naturaldate
from pytimeparse2 import parse

from utils import format as fmt
from models.moderation import AutoDelete
from models.moderation import AutoKicker
from utils.errors import NerpyException
from utils.helpers import send_hidden_message, empty_subcommand

utc = timezone.utc
# If no tzinfo is given then UTC is assumed.
loop_run_time = time(hour=12, minute=30, tzinfo=utc)


class Moderation(Cog):
    """cog for bot management"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self._autokicker_loop.start()
        self._autodeleter_loop.start()

    def cog_unload(self):
        self._autokicker_loop.cancel()
        self._autodeleter_loop.cancel()

    @tasks.loop(time=loop_run_time)
    async def _autokicker_loop(self):
        self.bot.log.debug("Start Autokicker Loop!")
        try:
            with self.bot.session_scope() as session:
                configurations = AutoKicker.get_all(session)

            for configuration in configurations:
                if configuration is None:
                    continue
                if configuration.Enabled and configuration.KickAfter > 0:
                    guild = self.bot.get_guild(configuration.GuildId)
                    self.bot.log.info(f"Checking for member without role in {guild.name}.")
                    for member in guild.members:
                        if len(member.roles) == 1:
                            self.bot.log.debug(f"Found member without role: {member.display_name}")
                            kick_reminder = datetime.now(UTC) - timedelta(seconds=(configuration.KickAfter / 2))
                            kick_reminder = kick_reminder.replace(tzinfo=timezone.utc)
                            kick_after = datetime.now(UTC) - timedelta(seconds=configuration.KickAfter)
                            kick_after = kick_after.replace(tzinfo=timezone.utc)

                            if member.joined_at < kick_after:
                                self.bot.log.debug(f"Kick member {member.display_name}!")
                                await member.kick()
                            elif member.joined_at < kick_reminder:
                                self.bot.log.debug("Send reminder message to member")
                                if configuration.ReminderMessage is not None:
                                    await member.send(configuration.ReminderMessage)
                                else:
                                    await member.send(
                                        f"You have not selected a role on {guild.name}. "
                                        f"Please choose a role until {naturaldate(kick_after)}."
                                    )
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
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

            for configuration in configurations:
                guild = self.bot.get_guild(configuration.GuildId)
                if configuration.DeleteOlderThan is None:
                    list_before = None
                else:
                    list_before = datetime.now(UTC) - timedelta(seconds=configuration.DeleteOlderThan)
                    list_before = list_before.replace(tzinfo=timezone.utc)
                channel = guild.get_channel(configuration.ChannelId)
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
                        f"Delete message from channel {message.channel.name}, created at {message.created_at}."
                    )
                    await message.delete()
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
            if channel is not None:
                self.bot.log.debug(f"Channel: {channel}")
            if message is not None:
                self.bot.log.debug(f"Message: {message}")
                self.bot.log.debug(f"Channel from Message: {message.channel.name}")
        self.bot.log.debug("Finish Autodeleter Loop!")

    @hybrid_command()
    @rename(kick_reminder_message="reminder_message")
    @checks.has_permissions(kick_members=True)
    async def autokicker(
        self, ctx: Context, enable: bool, kick_after: Optional[str], kick_reminder_message: Optional[str]
    ):
        """Activates the AutoKicker. [bot-moderator]

        Parameters
        ----------
        ctx
        enable: bool
        kick_after: str
            Time after someone get's kicked, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        kick_reminder_message: Optional[str]
        """
        with self.bot.session_scope() as session:
            configuration = AutoKicker.get_by_guild(ctx.guild.id, session)
            if kick_after is not None:
                kick_time = parse(kick_after)
                if kick_time is None:
                    await send_hidden_message(
                        ctx, "Only timespans up until weeks are allowed. Do not use months or years."
                    )
                    return
            else:
                await send_hidden_message(ctx, "You need to specify when I should kick someone!")
                return
            if configuration is not None:
                configuration.KickAfter = kick_time
                configuration.Enabled = enable
                configuration.ReminderMessage = kick_reminder_message
            else:
                autokicker = AutoKicker(
                    GuildId=ctx.guild.id,
                    KickAfter=kick_time,
                    Enabled=enable,
                    ReminderMessage=kick_reminder_message,
                )
                session.add(autokicker)

        await send_hidden_message(ctx, "AutoKicker configured for this server.")

    @hybrid_group()
    @checks.has_permissions(manage_messages=True)
    async def autodeleter(self, ctx: Context) -> None:
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
    async def _autodeleter_create(
        self,
        ctx: Context,
        *,
        channel: TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ) -> None:
        """
        Creates AutoDeletion configuration on a per-channel basis.

        Parameters
        ----------
        ctx
        channel: discord.TextChannel
        delete_older_than: Optional[Union[str | None]]
            Time after messages get deleted, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        keep_messages: Optional[Union[int | None]]
            Messages to keep after deletion. Can be used in combination with "delete_older_than".
        delete_pinned_message: bool
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                await send_hidden_message(
                    ctx,
                    "This Channel is already configured for AutoDelete."
                    "Please edit or delete the existing configuration.",
                )
            else:
                if ctx.guild.get_channel(channel_id) is not None:
                    if delete_older_than is None:
                        delete = delete_older_than
                    else:
                        delete = parse(delete_older_than)
                        if delete is None:
                            await send_hidden_message(
                                ctx, "Only timespans up until weeks are allowed. Do not use months or years."
                            )
                            return

                    deleter = AutoDelete(
                        GuildId=ctx.guild.id,
                        ChannelId=channel_id,
                        KeepMessages=keep_messages,
                        DeleteOlderThan=delete,
                        DeletePinnedMessage=delete_pinned_message,
                    )
                    session.add(deleter)

        await send_hidden_message(ctx, f'AutoDeleter configured for channel "{channel_name}".')

    @autodeleter.command(name="delete")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_delete(self, ctx: Context, *, channel: TextChannel) -> None:
        """
        Delete AutoDelete configuration for a channel.

        Parameters
        ----------
        ctx
        channel
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                AutoDelete.delete(ctx.guild.id, channel_id, session)
                await send_hidden_message(ctx, f'Deleted configuration for channel "{channel_name}".')
            else:
                await send_hidden_message(ctx, f'No configuration for channel "{channel_name}" found!')

    @autodeleter.command(name="list")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_list(self, ctx: Context) -> None:
        """
        Lists AutoDelete configuration.

        Parameters
        ----------
        ctx
        """

        with self.bot.session_scope() as session:
            configurations = AutoDelete.get_by_guild(ctx.guild.id, session)
            if configurations is not None:
                msg = "==== AutoDeleter Configuration ====\n"
                for configuration in configurations:
                    channel_name = ctx.guild.get_channel(configuration.ChannelId).name
                    msg += (
                        f"Channel: {channel_name}, "
                        f"DeleteOlderThan: {configuration.DeleteOlderThan}, "
                        f"DeletePinnedMessages: {configuration.DeletePinnedMessage}, "
                        f"KeepMessages: {configuration.KeepMessages}\n"
                    )
                await send_hidden_message(ctx, fmt.box(msg))
            else:
                await send_hidden_message(ctx, "No configuration found!")

    @autodeleter.command(name="edit")
    @checks.has_permissions(manage_messages=True)
    async def _autodeleter_modify(
        self,
        ctx: Context,
        *,
        channel: TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ):
        """
        Modifies a AutoDeletion configuration for a channel.

        Parameters
        ----------
        ctx
        channel: discord.TextChannel
        delete_older_than: Optional[Union[str | None]]
            Time after messages get deleted, like "1 day", "1 week" or "5 minutes".
            Supports also abbreviations like "min" and "h".
        keep_messages: Optional[Union[int | None]]
            Messages to keep after deletion. Can be used in combination with "delete_older_than".
        delete_pinned_message: bool
        """
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                if delete_older_than is None:
                    configuration.DeleteOlderThan = delete_older_than
                else:
                    delete_in_seconds = parse(delete_older_than)
                    configuration.DeleteOlderThan = delete_in_seconds
                configuration.KeepMessages = keep_messages if keep_messages is not None else 0
                configuration.DeletePinnedMessage = delete_pinned_message

                await send_hidden_message(ctx, f'Updated configuration for channel "{channel_name}".')
            else:
                await send_hidden_message(
                    ctx, f'Configuration for channel "{channel_name}" does not exist. Please create one first.'
                )

    @hybrid_group(aliases=["u"])
    @checks.has_permissions(moderate_members=True)
    async def user(self, ctx: Context):
        """user moderation [bot-moderator]"""
        await empty_subcommand(ctx)

    @user.command(name="info")
    @checks.has_permissions(moderate_members=True)
    async def _get_user_info(self, ctx: Context, member: Optional[Member]):
        """displays information about given user [bot-moderator]"""

        member = member or ctx.author
        created = member.created_at.strftime("%d. %B %Y - %H:%M")
        joined = member.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = Embed(title=member.display_name)
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
    async def _list_user_info_from_guild(self, ctx: Context, show_only_users_without_roles: Optional[bool]):
        """displays a list of users on your server [bot-moderator]

        Parameters
        ----------
        ctx
        show_only_users_without_roles: Optional[bool]
            If True shows only Users without a Role. (The role everyone is not considered a given role)
        """
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
    async def membercount(self, ctx: Context):
        """displays the current membercount of the server [bot-moderator]"""
        await ctx.send(fmt.inline(f"There are currently {ctx.guild.member_count} members on this discord"))

    @hybrid_command(name="leave", aliases=["stop"])
    async def _bot_leave_channel(self, ctx: Context):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)

    @command()
    async def history(self, ctx: Context):
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

    @_autokicker_loop.before_loop
    async def _autokicker_before_loop(self):
        self.bot.log.info("AutoKicker: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @_autodeleter_loop.before_loop
    async def _autodeleter_before_loop(self):
        self.bot.log.info("AutoDeleter: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Moderation(bot))
