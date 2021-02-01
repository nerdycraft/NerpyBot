import asyncio
from datetime import datetime, timedelta
from utils.errors import NerpyException
from discord.ext.commands import Cog, command, bot_has_permissions


class Reminder(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.reminders = []
        self.doLoop = True
        self.task = self.bot.loop.create_task(self._loop())
        self.config = self.bot.config["reminder"]

    def add(self, author, channel, time, message):
        self.reminders.append({"author": author, "channel": channel, "time": time, "message": message})

    async def _loop(self):
        self.loopRunning = True
        while self.doLoop:
            await asyncio.sleep(1)

            removals = []
            for rem in self.reminders:
                if rem["time"] <= datetime.now():
                    mention = rem["author"].mention
                    message = rem["message"]
                    await rem["channel"].send(f"{mention}, reminding you of: {message}")
                    removals.append(rem)

            for r in removals:
                self.reminders.remove(r)
        self.loopRunning = False

    def cog_unload(self):
        self.task.cancel()

    @command()
    @bot_has_permissions(send_messages=True)
    async def remindme(self, ctx, mins: int, *, text: str):
        """
        sets a reminder

        bot will answer in the channel you asked for it
        """
        self.bot.reminder.add(ctx.author, ctx.message.channel, datetime.now() + timedelta(minutes=mins), text)

        await self.bot.sendc(ctx, f"{ctx.author.mention}, i will remind you in {mins} minutes")


def setup(bot):
    if "reminder" in bot.config:
        bot.add_cog(Reminder(bot))
    else:
        raise NerpyException("Config not found.")
