# -- coding: utf-8 --
""" Twitch Modul """

from datetime import timedelta, datetime, UTC

from discord.ext import tasks
from discord.ext.commands import GroupCog, bot_has_permissions, hybrid_command
from twitchAPI.twitch import Twitch

from models.Twitch import Twitch
from utils.errors import NerpyException


@bot_has_permissions(send_messages=True)
class Twitch(GroupCog):
    """Twitch Module"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["twitch"]
        self.api = Twitch(self.config.get("client_id"), self.config.get("client_secret"))
        self._twitch_loop.start()

    def cog_unload(self):
        self._twitch_loop.cancel()

    @tasks.loop(seconds=30)
    async def _twitch_loop(self):
        self.bot.log.debug("Start Reminder Loop!")
        try:
            with self.bot.session_scope() as session:
                for guild in self.bot.guilds:
                    msgs = Twitch.get_all_by_guild(guild.id, session)
                    for msg in msgs:
                        if msg.LastSend + timedelta(minutes=msg.Minutes) < datetime.now(UTC):
                            chan = guild.get_channel(msg.ChannelId)
                            if chan is None:
                                session.delete(msg)
                            else:
                                await chan.send(msg.Message)
                                if msg.Repeat < 1:
                                    session.delete(msg)
                                else:
                                    msg.LastSend = datetime.now(UTC)
                                    msg.Count += 1
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
        self.bot.log.debug("Stop Reminder Loop!")

    @hybrid_command
    async def _configure_notifications(self):
        return

    @_twitch_loop.before_loop
    async def _before_loop(self):
        self.bot.log.info("Twitch: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    if "search" in bot.config:
        await bot.add_cog(Twitch(bot))
    else:
        raise NerpyException("Config not found.")
