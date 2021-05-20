import asyncio
from datetime import datetime, timedelta

from models.timed_message import TimedMessage
from utils.errors import NerpyException
from utils.format import pagify, box
from discord.ext.commands import Cog, group


class Timed(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.reminders = []
        self.doLoop = True
        self.task = self.bot.loop.create_task(self._loop())
        self.config = self.bot.config["timed_message"]

    async def _loop(self):
        self.loopRunning = True
        while self.doLoop:
            await asyncio.sleep(30)

            with self.bot.session_scope() as session:
                for guild in self.bot.guilds:
                    msgs = TimedMessage.get_all_from_guild(guild.id, session)
                    for msg in msgs:
                        if msg.LastSend + timedelta(minutes=msg.Minutes) < datetime.utcnow():
                            chan = guild.get_channel(msg.ChannelId)
                            if chan is None:
                                session.delete(msg)
                            else:
                                await chan.send(msg.Message)
                                if msg.Repeat < 1:
                                    session.delete(msg)
                                else:
                                    msg.LastSend = datetime.utcnow()
                                    msg.Count += 1

                session.flush()

        self.loopRunning = False

    def cog_unload(self):
        self.task.cancel()

    @group(invoke_without_command=False)
    async def timed(self, ctx):
        """
        timed messages
        """

    @timed.command()
    async def create(self, ctx, minutes: int, repeat: bool, *, message: str):
        """
        creates a message which gets send after a certain time
        """
        with self.bot.session_scope() as session:
            msg = TimedMessage(
                GuildId=ctx.guild.id,
                ChannelId=ctx.channel.id,
                Author=str(ctx.author),
                CreateDate=datetime.utcnow(),
                LastSend=datetime.utcnow(),
                Minutes=minutes,
                Message=message,
                Repeat=repeat,
                Count=0,
            )

            session.add(msg)
            session.flush()

    @timed.command()
    async def list(self, ctx):
        """
        list all current timed messages
        """
        to_send = ""
        with self.bot.session_scope() as session:
            msgs = TimedMessage.get_all_from_guild(ctx.guild.id, session)
            for msg in msgs:
                to_send += f"{str(msg)}\n\n"
        for page in pagify(to_send, delims=["\n#"], page_length=1990):
            await self.bot.sendc(ctx, box(page, "md"))

    @timed.command()
    async def delete(self, ctx, timed_id: int):
        """
        deletes a timed message
        """
        with self.bot.session_scope() as session:
            TimedMessage.delete(timed_id, ctx.guild.id, session)


def setup(bot):
    if "reminder" in bot.config:
        bot.add_cog(Timed(bot))
    else:
        raise NerpyException("Config not found.")
