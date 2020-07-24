"""
Main Class of the NerpyBot
"""

import os
import sys
import asyncio
import logging
import discord
import traceback
import config
from datetime import datetime
from utils.audio import Audio
from discord.ext import commands
from utils.reminder import Reminder
from utils.database import create_all
from utils.errors import NerpyException


class NerpyBot(commands.Bot):
    """Discord Bot"""

    def __init__(self):
        super().__init__(command_prefix="!", description="hi")

        self.client_id = config.client_id
        self.prefixes = ["!"]
        self.restart = True
        self.log = self._get_logger()
        self.uptime = datetime.utcnow()

        self.audio = Audio(self)
        self.reminder = Reminder(self)

        create_all()
        self._import_modules()

    async def on_ready(self):
        """calls when successfully logged in"""
        self.log.info("Ready!")

    async def on_command_completion(self, ctx):
        """ deleting msg on cmd completion """
        if self.restart is True and not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            if isinstance(error, commands.CommandInvokeError) and not isinstance(
                error.original, NerpyException
            ):
                print(f"In {ctx.command.qualified_name}:", file=sys.stderr)
                traceback.print_tb(error.original.__traceback__)
                print(
                    f"{error.original.__class__.__name__}: {error.original}",
                    file=sys.stderr,
                )
                await ctx.author.send(
                    "Unhandled error occured. Please report to bot author!"
                )
            else:
                await ctx.author.send(error)
        else:
            print(f"In {ctx.command.qualified_name}:", file=sys.stderr)
            traceback.print_tb(error.original.__traceback__)
            print(
                f"{error.original.__class__.__name__}: {error.original}",
                file=sys.stderr,
            )
            await ctx.author.send(
                "Unhandled error occured. Please report to bot author!"
            )
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()

    @asyncio.coroutine
    def run(self):
        """
        generator connects the discord bot to the server
        """
        self.log.info("Logging into Discord...")
        if config.token:
            self.activity = discord.Game(name="!help for help")
            yield from self.login(config.token)
        else:
            self.log.error("No credentials available to login.")
            raise RuntimeError()
        yield from self.connect()

    async def shutdown(self):
        """
        shutting down discord nicely
        """
        self.log.info("shutting down server!")
        self.restart = False
        await self.audio.rip_loop()
        await self.reminder.rip_loop()
        await self.logout()

    def _import_modules(self):
        for file in os.listdir(path="./modules"):
            split = os.path.splitext(file)
            if split[1] == ".py" and split[0] != "__init__":
                try:
                    self.load_extension(f"modules.{split[0]}")
                except (ImportError, discord.ClientException):
                    # TODO: Add better Exception handling
                    self.log.error(f"failed to load extension {split[0]}.")
                    traceback.print_exc()

    # noinspection PyMethodMayBeStatic
    def _get_logger(self):
        logger = logging.getLogger("Nerpy")
        logger.setLevel(logging.INFO)

        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
            datefmt="[%d/%m/%Y %H:%M]",
        )

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(fmt)

        logger.addHandler(stdout_handler)

        return logger


if __name__ == "__main__":
    BOT = NerpyBot()

    LOOP = asyncio.get_event_loop()
    try:
        LOOP.run_until_complete(BOT.run())
    except discord.LoginFailure:
        BOT.log.error(traceback.format_exc())
        BOT.log.error("Failed to login")
    except KeyboardInterrupt:
        LOOP.run_until_complete(BOT.logout())
    except Exception as ex:
        BOT.log.exception("Fatal exception, attempting graceful logout", exc_info=ex)
        LOOP.run_until_complete(BOT.logout())
    finally:
        LOOP.close()
        if BOT.restart is False:
            exit(0)
        elif BOT.restart is True:
            exit(26)  # Restart
        else:
            exit(1)
