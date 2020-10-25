import asyncio
from datetime import datetime, timedelta

from models.timed_message import TimedMessage
from utils.database import session_scope


class Timed:
    """description of class"""

    def __init__(self, bot):
        self.bot = bot
        self.doLoop = True
        self.bot.loop.create_task(self._loop())

    @classmethod
    def add(cls, author, guild, channel, time, repeat, message):
        with session_scope() as session:
            msg = TimedMessage(
                GuildId=guild.id,
                ChannelId=channel.id,
                Author=str(author),
                CreateDate=datetime.utcnow(),
                LastSend=datetime.utcnow(),
                Minutes=time,
                Message=message,
                Repeat=repeat,
                Count=0,
            )

            session.add(msg)
            session.flush()

    @classmethod
    def delete(cls, id, guildid):
        TimedMessage.delete(id, guildid)

    @classmethod
    def show(cls, guildid):
        to_send = ""
        with session_scope() as session:
            msgs = TimedMessage.get_all_from_guild(guildid, session)
            for msg in msgs:
                to_send += f'{str(msg)}\n\n'

        return to_send

    async def _loop(self):
        self.loopRunning = True
        while self.doLoop:
            await asyncio.sleep(30)

            with session_scope() as session:
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

    async def rip_loop(self):
        self.doLoop = False
        while self.loopRunning:
            await asyncio.sleep(1)
