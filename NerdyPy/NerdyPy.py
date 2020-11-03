"""
Main Class of the NerpyBot
"""

import sys
import json
import asyncio
import logging
import discord
import argparse
import traceback
import configparser
from pathlib import Path
from datetime import datetime
from models.default_channel import DefaultChannel
from utils.audio import Audio
from discord.ext import commands
from utils.reminder import Reminder
from utils.database import create_all, session_scope
from utils.errors import NerpyException
from utils.timed import Timed


class NerpyBot(commands.Bot):
    """Discord Bot"""

    def __init__(self, config: configparser, debug: bool):
        super().__init__(command_prefix="!", description="NerdyBot - Always one step ahead!")

        self.config = config
        self.debug = debug
        self.client_id = config["bot"]["client_id"]
        self.token = config["bot"]["token"]
        self.ops = config["bot"]["ops"]
        self.moderator_role = self.config["bot"]["moderator_role_name"]
        self.modules = json.loads(self.config["bot"]["modules"])
        self.prefixes = ["!"]
        self.restart = True
        self.log = self._get_logger()
        self.uptime = datetime.utcnow()

        self.audio = Audio(self)
        self.reminder = Reminder(self)
        self.timed = Timed(self)
        self.last_cmd_cache = {}

        create_all()
        self._import_modules()

    async def on_ready(self):
        """calls when successfully logged in"""
        self.log.info("Ready!")

    async def on_command_completion(self, ctx):
        """ deleting msg on cmd completion """
        if self.restart is True and not isinstance(ctx.channel, discord.DMChannel):
            if ctx.guild.id not in self.last_cmd_cache:
                self.last_cmd_cache[ctx.guild.id] = []
            elif len(self.last_cmd_cache[ctx.guild.id]) >= 10:
                self.last_cmd_cache[ctx.guild.id].popleft()

            self.last_cmd_cache[ctx.guild.id].append(ctx.message)

            await ctx.message.delete()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            if isinstance(error, commands.CommandInvokeError) and not isinstance(error.original, NerpyException):
                print(f"In {ctx.command.qualified_name}:", file=sys.stderr)
                traceback.print_tb(error.original.__traceback__)
                print(
                    f"{error.original.__class__.__name__}: {error.original}",
                    file=sys.stderr,
                )
                await ctx.author.send("Unhandled error occurred. Please report to bot author!")
            else:
                await ctx.author.send(error)
        else:
            print(f"In {ctx.command.qualified_name}:", file=sys.stderr)
            traceback.print_tb(error.original.__traceback__)
            print(
                f"{error.original.__class__.__name__}: {error.original}",
                file=sys.stderr,
            )
            await ctx.author.send("Unhandled error occurred. Please report to bot author!")
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()

    async def send(self, guild_id, cur_chan, msg, emb=None, file=None, files=None, delete_after=None):
        with session_scope() as session:
            def_chan = DefaultChannel.get(guild_id, session)
            if def_chan is not None:
                chan = self.get_channel(def_chan.ChannelId)
                if chan is not None:
                    await chan.send(msg, embed=emb, file=file, files=files, delete_after=delete_after)
                    return

        await cur_chan.send(msg, embed=emb, file=file, files=files, delete_after=delete_after)

    async def sendc(self, ctx, msg, emb=None, file=None, files=None, delete_after=None):
        await self.send(ctx.guild.id, ctx.channel, msg, emb, file, files, delete_after)

    async def run(self):
        """
        generator connects the discord bot to the server
        """
        self.log.info("Logging into Discord...")
        if self.token:
            self.activity = discord.Game(name="!help for help")
            await self.login(self.token)
        else:
            self.log.error("No credentials available to login.")
            raise RuntimeError()
        await self.connect()

    async def shutdown(self):
        """
        shutting down discord nicely
        """
        self.log.info("shutting down server!")
        self.restart = False
        await self.audio.rip_loop()
        await self.reminder.rip_loop()
        await self.timed.rip_loop()
        await self.logout()

    def _import_modules(self):
        for module in self.modules:
            try:
                self.load_extension(f"modules.{module}")
            except (ImportError, commands.ExtensionFailed, discord.ClientException) as e:
                # TODO: Add better Exception handling
                self.log.error(f"failed to load extension {module}. {e}")
                if self.debug:
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


def parse_arguments():
    """
    parser for starting arguments

    currently only supports auto restart
    """
    parser = argparse.ArgumentParser(description="-> NerpyBot <-")
    parser.add_argument(
        "--auto-restart",
        "-r",
        help="Autorestarts NerdyPy in case of issues",
        action="store_true",
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Specify config file for NerdyPy",
        nargs=1,
    )
    parser.add_argument(
        "--debug",
        help="Debug",
        action="store_true",
    )
    return parser.parse_args()


def parse_config(config_file=None):
    config = configparser.ConfigParser(interpolation=None)

    if config_file is None:
        config_file = Path("./config.ini")

    if config_file.exists():
        config.read(config_file)

    return config


if __name__ == "__main__":
    # fmt: off
    INTRO = (
        "==========================\n"
        "       - Nerpy Bot -      \n"
        "==========================\n"
    )
    # fmt: on
    print(INTRO)

    RUNNING = True
    LOOP = asyncio.get_event_loop()
    ARGS = parse_arguments()
    CONFIG = parse_config(ARGS.config)
    DEBUG = ARGS.debug

    if "bot" in CONFIG:
        BOT = NerpyBot(CONFIG, DEBUG)

        while RUNNING:
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
                    RUNNING = False
    else:
        raise NerpyException("Bot config not found.")
