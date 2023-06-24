# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_command, bot_has_permissions

from utils.errors import NerpyException


@bot_has_permissions(send_messages=True)
class Reminder(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.reminders = []
        self.config = self.bot.config["reminder"]

    def cog_unload(self):
        self.task.cancel()

    def add(self, author, channel, time, message):
        self.reminders.append({"author": author, "channel": channel, "time": time, "message": message})

    @tasks.loop(seconds=5)
    async def _loop(self):
        removals = []
        for rem in self.reminders:
            if rem["time"] <= datetime.now():
                mention = rem["author"].mention
                message = rem["message"]
                await rem["author"].send(f"{mention}, reminding you of: {message}")
                removals.append(rem)

        for r in removals:
            self.reminders.remove(r)

    @_loop.before_loop
    async def _before_loop(self):
        self.bot.loop.create_task(self._loop)
        self.bot.log.info("Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @hybrid_command()
    async def remindme(self, ctx, mins: int, *, text: str):
        """
        sets a reminder

        bot will answer in a DM
        """
        self.bot.reminder.add(ctx.author, ctx.message.channel, datetime.now() + timedelta(minutes=mins), text)
        await ctx.send(f"{ctx.author.mention}, i will remind you in {mins} minutes")


async def setup(bot):
    if "reminder" in bot.config:
        await bot.add_cog(Reminder(bot))
    else:
        raise NerpyException("Config not found.")
