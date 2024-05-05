# -- coding: utf-8 --
""" Twitch Modul """
from datetime import datetime, UTC, timedelta
from typing import Optional, Union

from discord import TextChannel
from discord.app_commands import guild_only
from discord.ext import tasks
from discord.ext.commands import bot_has_permissions, Context, hybrid_group, GroupCog
from twitchAPI.helper import first
from twitchAPI.object.api import TwitchUser
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent
from twitchAPI.twitch import Twitch as TwitchAPI
from twitchAPI.eventsub.webhook import EventSubWebhook, EventSubSubscriptionTimeout

from models.twitch import TwitchNotifications
from utils import format as fmt
from utils.errors import NerpyException
from utils.helpers import send_hidden_message, empty_subcommand


@bot_has_permissions(send_messages=True)
@guild_only()
class Twitch(GroupCog, group_name="twitch"):
    """Twitch Module"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["twitch"]
        self.streamers = {}
        self.stream_webhooks = {}
        self.api = None
        self.eventsub = None
        self._twitch_loop.start()

    def cog_unload(self):
        self._twitch_loop.cancel()
        self.eventsub.stop()

    async def cog_load(self):
        await self._get_twitch_api()
        await self._get_eventsub()

        await self.eventsub.unsubscribe_all()
        self.eventsub.start()

    @tasks.loop(seconds=30)
    async def _twitch_loop(self):
        self.bot.log.debug("Start Twitch Loop!")
        try:
            _configs = None
            with self.bot.session_scope() as session:
                for guild in self.bot.guilds:
                    _configs = TwitchNotifications.get_all_by_guild(guild.id, session)

                    if _configs:
                        for _config in _configs:
                            if _config.Streamer not in self.stream_webhooks:
                                await self._stream_webhook(self.eventsub, _config.Streamer)
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
        self.bot.log.debug("Stop Twitch Loop!")

    async def _get_twitch_user(self, _streamer: str) -> Union[TwitchUser | None]:
        """
        Get Twitch User by Streamer Name

        Users are cached for one hour after the first request.
        """
        if _streamer in self.streamers:
            if self.streamers[_streamer]["valid_until"] > datetime.now(UTC):
                return self.streamers[_streamer]["data"]

        _user = await first(self.api.get_users(logins=_streamer))
        self.streamers[_streamer] = {"data": _user, "valid_until": datetime.now(UTC) + timedelta(minutes=60)}
        return _user

    async def _get_twitch_api(self):
        self.bot.log.debug("Twitch: Getting API...")
        self.api = await TwitchAPI(
            self.config.get("client_id"),
            self.config.get("client_secret"),
        )

    async def _get_eventsub(self):
        self.bot.log.debug("Twitch: Getting EventSub...")
        try:
            self.eventsub = EventSubWebhook(self.config.get("webhook_url"), self.config.get("webhook_port"), self.api)
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")

    async def _on_stream_online(self, data: StreamOnlineEvent):
        broadcaster = data.event.broadcaster_user_name
        with self.bot.session_scope() as session:
            _configs = TwitchNotifications.get_all_by_streamer(self.bot.guild.id, broadcaster, session)
            for _config in _configs:
                _channel = self.bot.guild.get_channel(_config.ChannelId)
                if _channel:
                    if _config.Message:
                        await _channel.send(_config.Message)
                        return
                    await _channel.send(f"{broadcaster} is now live at https://twitch.tv/{broadcaster}")

    async def _stream_webhook(self, _eventsub, _streamer: str):
        _user = await self._get_twitch_user(_streamer)
        try:
            await _eventsub.listen_stream_online(_user.id, self._on_stream_online)
        except EventSubSubscriptionTimeout as ex:
            self.bot.log.error(f"Timeout waiting for Subscription: {ex}")
        else:
            self.stream_webhooks[_streamer] = _user.id

    @hybrid_group(aliases=["twitch_notifications"])
    @guild_only()
    async def notifications(self, ctx: Context) -> None:
        """Manages Twitch notifications on a per-channel/per-streamer basis."""
        await empty_subcommand(ctx)

    @notifications.command(name="list")
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
        ctx: Context
            The Context of the command.
        channel: TextChannel
            The channel to configure the Notifications for.
            If not set the current channel will be used.
        streamer: Optional[str]
            The Twitch ID of the Broadcaster to be notified about.
        """
        twitch = None
        with self.bot.session_scope() as session:
            if channel and not streamer:
                twitch = TwitchNotifications.get_all_by_channel(ctx.guild.id, channel.id, session)
            if streamer and not channel:
                twitch = TwitchNotifications.get_all_by_streamer(ctx.guild.id, streamer, session)
            if channel and streamer:
                twitch = TwitchNotifications.get_by_channel_and_streamer(ctx.guild.id, channel.id, streamer, session)
            if not channel and not streamer:
                twitch = TwitchNotifications.get_all_by_guild(ctx.guild.id, session)
            if twitch and len(twitch) > 0:
                msg = ["==== Twitch Configuration ===="]
                for config in twitch:
                    channel_name = ctx.guild.get_channel(config.ChannelId).name
                    user = await self._get_twitch_user(config.Streamer)
                    msg.append(
                        f"Id: {config.Id}, "
                        f"Channel: {channel_name}, "
                        f"Streamer: {user.display_name}, "
                        f"Message: {config.Message}"
                    )
                await send_hidden_message(ctx, fmt.box("\n".join(msg)))
                return
            await send_hidden_message(ctx, "No configuration found.")

    @notifications.command(name="create")
    async def _twitch_notifications_create(
        self,
        ctx: Context,
        streamer: str,
        channel: Optional[TextChannel],
        message: Optional[str],
    ) -> None:
        """
        Creates Twitch notifications.

        Parameters
        ----------
        ctx: Context
            The Context of the command.
        streamer: Optional[str]
            The Twitch ID of the Broadcaster to be notified about.
        channel: TextChannel
            The channel to configure the Notifications for.
            If not set the current channel will be used.
        message: Optional[str]
            Message to send as a notification to the channel.
        """
        if channel is None:
            channel = ctx.channel
        with self.bot.session_scope() as session:
            twitch = TwitchNotifications.get_by_channel_and_streamer(ctx.guild.id, channel.id, streamer, session)
            if twitch:
                await send_hidden_message(ctx, "Configuration already exists.")
                return
            user = await self._get_twitch_user(streamer)
            if not user:
                await send_hidden_message(ctx, f"Streamer {streamer} not found.")
                return
            twitch = TwitchNotifications(
                GuildId=ctx.guild.id,
                ChannelId=channel.id,
                Streamer=streamer,
                Message=message,
            )
            session.add(twitch)
        await send_hidden_message(ctx, "Configuration created.")

    @notifications.command(name="delete")
    async def _twitch_notifications_delete(
        self,
        ctx: Context,
        config_id: int,
    ) -> None:
        """
        Creates Twitch notifications.

        Parameters
        ----------
        ctx: Context
            The Context of the command.
        config_id: int
            The ID of the configuration to delete.
        """
        with self.bot.session_scope() as session:
            twitch = TwitchNotifications.get_by_id(ctx.guild.id, config_id, session)
            if not twitch:
                await send_hidden_message(ctx, f"Configuration with id {config_id} does not exist.")
                return
            session.delete(twitch)
        await send_hidden_message(ctx, "Configuration deleted.")

    @_twitch_loop.before_loop
    async def _twitch_before_loop(self):
        self.bot.log.info("Twitch: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    if "twitch" in bot.config:
        await bot.add_cog(Twitch(bot))
    else:
        raise NerpyException("Config not found.")
