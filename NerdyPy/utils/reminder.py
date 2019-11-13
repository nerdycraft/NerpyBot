import asyncio
from datetime import datetime


class Reminder:
    """description of class"""

    def __init__(self, bot):
        self.bot = bot
        self.reminders = []
        self.doloop = True
        self.bot.loop.create_task(self._loopingloui())

    def add(self, author, channel, time, message):
        self.reminders.append({'author': author,
                               'channel': channel,
                               'time': time,
                               'message': message
                               })

    async def _loopingloui(self):
        self.looprunning = True
        while self.doloop:
            await asyncio.sleep(1)

            removals = []
            for rem in self.reminders:
                if rem['time'] <= datetime.now():
                    mention = rem['author'].mention
                    message = rem['message']
                    await rem['channel'].send(f'{mention}, reminding you of: {message}')
                    removals.append(rem)

            for r in removals:
                self.reminders.remove(r)
        self.looprunning = False

    async def riploop(self):
        self.doloop = False
        while self.looprunning:
            await asyncio.sleep(1)
