# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_command, bot_has_permissions


@bot_has_permissions(send_messages=True)
class Reminder(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.reminders = []
        self._reminder.start()

    def cog_unload(self):
        self._reminder.cancel()

    @tasks.loop(seconds=5)
    async def _reminder(self):
        removals = []
        for rem in self.reminders:
            if rem["time"] <= datetime.now():
                mention = rem["author"].mention
                message = rem["message"]
                await rem["author"].send(f"Hello {mention}, you asked me to remind you of: {message}")
                removals.append(rem)

        for r in removals:
            self.reminders.remove(r)

    def add(self, author, channel, time, message):
        self.reminders.append({"author": author, "channel": channel, "time": time, "message": message})

    @hybrid_command()
    async def remindme(self, ctx, mins: int, *, text: str):
        """
        sets a reminder

        bot will answer in a DM
        """
        self.add(ctx.author, ctx.message.channel, datetime.now() + timedelta(minutes=mins), text)
        await ctx.send(f"Got it, {ctx.author.mention}. I will remind you in {mins} minute(s).", ephemeral=True)

    @_reminder.before_loop
    async def _before_loop(self):
        self.bot.log.info("Reminder: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Reminder(bot))
