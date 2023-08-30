# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import tasks
from discord.ext.commands import GroupCog, hybrid_command

from models.TimedMessage import TimedMessage
from utils.format import pagify, box


class Timed(GroupCog, group_name="timed-message"):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.reminders = []
        self._timed_loop.start()

    def cog_unload(self):
        self._timed_loop.cancel()

    @tasks.loop(seconds=30)
    async def _timed_loop(self):
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

    @hybrid_command()
    async def create(self, ctx, channel: Optional[discord.TextChannel], minutes: int, repeat: bool, message: str):
        """
        creates a message which gets send after a certain time
        """
        with self.bot.session_scope() as session:
            if channel:
                channel_id = channel.id
            else:
                channel_id = ctx.channel.id

            msg = TimedMessage(
                GuildId=ctx.guild.id,
                ChannelId=channel_id,
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

        await ctx.send("Message created.", ephemeral=True)

    @hybrid_command()
    async def list(self, ctx):
        """
        list all current timed messages
        """
        to_send = ""
        with self.bot.session_scope() as session:
            msgs = TimedMessage.get_all_from_guild(ctx.guild.id, session)
            if len(msgs) > 0:
                for msg in msgs:
                    to_send += f"{str(msg)}\n\n"
                for page in pagify(to_send, delims=["\n#"], page_length=1990):
                    await ctx.send(box(page, "md"))
            else:
                await ctx.send("No messages in queue.")

    @hybrid_command()
    async def delete(self, ctx, timed_id: int):
        """
        deletes a timed message
        """
        with self.bot.session_scope() as session:
            TimedMessage.delete(timed_id, ctx.guild.id, session)

        await ctx.send("Message deleted.", ephemeral=True)

    @_timed_loop.before_loop
    async def _before_loop(self):
        self.bot.log.info("Timed: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Timed(bot))
