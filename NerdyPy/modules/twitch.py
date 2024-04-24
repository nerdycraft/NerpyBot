# -- coding: utf-8 --
""" Twitch Modul """
from typing import Optional, Literal, Union

from discord import TextChannel
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import bot_has_permissions, hybrid_command, Context, hybrid_group, GroupCog
from twitchAPI.object.api import TwitchUser
from twitchAPI.twitch import Twitch as TwitchAPI

from utils import format as fmt
from models.twitch import TwitchNotifications
from utils.errors import NerpyException
from utils.helpers import send_hidden_message


@bot_has_permissions(send_messages=True)
class Twitch(GroupCog):
    """Twitch Module"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["twitch"]
        # self._twitch_loop.start()

    def cog_unload(self):
        self._twitch_loop.cancel()

    async def _get_streamer(self, streamer: Union[str|int]) -> TwitchUser:
        ids = None
        names = None
        api = await self._get_twitch_api()

        if isinstance(streamer, str):
            names = [streamer]
        if isinstance(streamer, int):
            ids = [streamer]
        async for user in api.get_users(user_ids=ids, logins=names):
            return user

    async def _get_twitch_api(self):
        return await TwitchAPI(
            self.config.get("client_id"),
            self.config.get("client_secret"),
        )

    @tasks.loop(seconds=30)
    async def _twitch_loop(self):
        self.bot.log.debug("Start Twitch Loop!")
        try:
            pass
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
        self.bot.log.debug("Stop Twitch Loop!")

    @hybrid_group(name="notifications", invoke_without_command=True, aliases=["twitch_notifications"])
    async def twitch_notifications(self, ctx: Context) -> None:
        """Manages Twitch notifications on a per-channel/per-streamer basis."""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await ctx.send(args[1])

    @twitch_notifications.command(name="list")
    async def _twitch_notifications_list(
        self,
        ctx: Context,
        channel: Optional[TextChannel],
        streamer: Optional[str],
    ) -> None:
        """
        List Twitch notifications.

        Parameters
        ----------
        ctx
        channel: TextChannel
            The channel to configure the Notifications for.
            If not set the current channel will be used.
        streamer: Optional[str]
            The Twitch ID of the Broadcaster to be notified about.
        """
        api = await self._get_twitch_api()
        twitch = None
        with self.bot.session_scope() as session:
            if channel and not streamer:
                twitch = TwitchNotifications.get_all_by_channel(ctx.guild.id, channel.id, session)
            if streamer and not channel:
                twitch = TwitchNotifications.get_all_by_streamer(ctx.guild.id, streamer, session)
            if channel and streamer:
                twitch = TwitchNotifications.get_by_channel_and_streamer(ctx.guild.id, channel.id, streamer, session)
            if twitch:
                channel_name = ctx.guild.get_channel(twitch.ChannelId).name
                user = await self._get_streamer(twitch.StreamerId)
                await send_hidden_message(
                    ctx,
                    fmt.box(
                        (
                            "==== Twitch Configuration ====\n" 
                            f"Channel: {channel_name}, "
                            f"Streamer: {user.display_name}, "
                            f"Message: {twitch.Message}"
                        )
                    ),
                )
                return
            if not channel and not streamer:
                msg = "==== Twitch Configuration ====\n"
                for twitch in TwitchNotifications.get_all_by_guild(ctx.guild.id, session):
                    channel_name = ctx.guild.get_channel(twitch.ChannelId).name
                    user = await self._get_streamer(twitch.StreamerId)
                    msg += (
                        f"Channel: {channel_name}, "
                        f"Streamer: {user.display_name}, "
                        f"Message: {twitch.Message}\n"
                    )
                    await send_hidden_message(ctx, fmt.box(msg))
                    return
            await send_hidden_message(ctx, "No configuration found.")

    @twitch_notifications.command(name="create")
    async def _twitch_notifications_create(
        self,
        ctx: Context,
        channel: Optional[TextChannel],
        streamer: Optional[str],
        message: Optional[str],
    ) -> None:
        """
        Creates Twitch notifications.

        Parameters
        ----------
        ctx
        channel: TextChannel
            The channel to configure the Notifications for.
            If not set the current channel will be used.
        streamer: Optional[str]
            The Twitch ID of the Broadcaster to be notified about.
        message: Optional[str]
            Message to send as a notification to the channel.
        """
        api = await self._get_twitch_api()
        if channel is None:
            channel = ctx.channel
        with self.bot.session_scope() as session:
            user = await self._get_streamer(streamer)
            twitch = TwitchNotifications.get_by_channel_and_streamer(ctx.guild.id, channel.id, user.id, session)
            if twitch:
                await send_hidden_message(ctx, "Configuration already exists.")
                return
            twitch = TwitchNotifications(
                GuildId=ctx.guild.id,
                ChannelId=channel.id,
                StreamerId=user.id,
                Message=message,
            )
            session.add(twitch)
        await send_hidden_message(ctx, "Configuration created.")

    @_twitch_loop.before_loop
    async def _before_loop(self):
        self.bot.log.info("Twitch: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    if "twitch" in bot.config:
        await bot.add_cog(Twitch(bot))
    else:
        raise NerpyException("Config not found.")
