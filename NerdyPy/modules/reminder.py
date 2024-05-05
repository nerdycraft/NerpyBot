# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, UTC
from typing import Optional

from discord import TextChannel
from discord.ext import tasks
from discord.ext.commands import GroupCog, hybrid_command, Context

from models.reminder import ReminderMessage
from utils.format import pagify, box
from utils.helpers import send_hidden_message


class Reminder(GroupCog, group_name="reminder"):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self._reminder_loop.start()

    def cog_unload(self):
        self._reminder_loop.cancel()

    @tasks.loop(seconds=30)
    async def _reminder_loop(self):
        self.bot.log.debug("Start Reminder Loop!")
        try:
            with self.bot.session_scope() as session:
                for guild in self.bot.guilds:
                    for msg in ReminderMessage.get_all_by_guild(guild.id, session):
                        if msg.LastSend.astimezone(UTC) + timedelta(minutes=msg.Minutes) < datetime.now(UTC):
                            chan = guild.get_channel(msg.ChannelId)
                            if chan is None:
                                session.delete(msg)
                            else:
                                await chan.send(msg.Message)
                                if msg.Repeat < 1:
                                    session.delete(msg)
                                else:
                                    msg.LastSend = datetime.now()
                                    msg.Count += 1
        except Exception as ex:
            self.bot.log.error(f"Error ocurred: {ex}")
        self.bot.log.debug("Stop Reminder Loop!")

    @hybrid_command(name="create")
    async def _reminder_create(
        self, ctx: Context, channel: Optional[TextChannel], minutes: int, repeat: bool, message: str
    ):
        """
        creates a message which gets send after a certain time
        """
        channel_id = ctx.channel.id
        channel_name = ctx.channel.name

        if channel:
            channel_id = channel.id
            channel_name = channel.name

        with self.bot.session_scope() as session:
            msg = ReminderMessage(
                GuildId=ctx.guild.id,
                ChannelId=channel_id,
                ChannelName=channel_name,
                Author=str(ctx.author),
                CreateDate=datetime.now(UTC),
                LastSend=datetime.now(UTC),
                Minutes=minutes,
                Message=message,
                Repeat=repeat,
                Count=0,
            )
            session.add(msg)
        await send_hidden_message(ctx, "Message created.")

    @hybrid_command(name="list")
    async def _reminder_list(self, ctx: Context):
        """
        list all current reminder messages
        """
        to_send = ""
        with self.bot.session_scope() as session:
            msgs = ReminderMessage.get_all_by_guild(ctx.guild.id, session)
            if len(msgs) > 0:
                for msg in msgs:
                    to_send += f"{str(msg)}\n\n"
                for page in pagify(to_send, delims=["\n#"], page_length=1990):
                    await send_hidden_message(ctx, box(page, "md"))
            else:
                await send_hidden_message(ctx, "No messages in queue.")

    @hybrid_command(name="delete")
    async def _reminder_delete(self, ctx: Context, reminder_id: int):
        """
        deletes a reminder message
        """
        with self.bot.session_scope() as session:
            ReminderMessage.delete(reminder_id, ctx.guild.id, session)
        await send_hidden_message(ctx, "Message deleted.")

    @_reminder_loop.before_loop
    async def _reminder_before_loop(self):
        self.bot.log.info("Reminder: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Reminder(bot))
