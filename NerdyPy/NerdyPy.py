"""
Main Class of the NerpyBot
"""

import sys
import json
import asyncio
import logging
from contextlib import contextmanager

import discord
import argparse
import traceback
import configparser
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from models.default_channel import DefaultChannel
from models.guild_prefix import GuildPrefix
from utils.audio import Audio
from discord.ext import commands

from utils.database import BASE
from utils.errors import NerpyException


class NerpyBot(commands.Bot):
    """Discord Bot"""

    def __init__(self, config: configparser, debug: bool):
        super().__init__(command_prefix=determine_prefix, description="NerdyBot - Always one step ahead!")

        self.config = config
        self.debug = debug
        self.client_id = config["bot"]["client_id"]
        self.token = config["bot"]["token"]
        self.ops = config["bot"]["ops"]
        self.moderator_role = config["bot"]["moderator_role_name"]
        self.modules = json.loads(config["bot"]["modules"])
        self.restart = True
        self.log = self._get_logger()
        self.uptime = datetime.utcnow()

        self.audio = Audio(self)
        self.last_cmd_cache = {}
        self.usr_cmd_err_spam = {}
        self.usr_cmd__err_spam_threshold = int(config["bot"]["error_spam_threshold"])

        # database variables
        if "database" not in config:
            self.log.error("No Database specified! Fallback to local SQLite Database!")
            db_connection_string = "sqlite:///db.db"
        else:
            database_config = config["database"]
            db_type = database_config["db_type"]
            db_name = database_config["db_name"]
            db_username = ""
            db_password = ""
            db_host = ""
            db_port = ""

            if any(s in db_type for s in ("mysql", "mariadb")):
                db_type = f'{database_config["db_type"]}+pymysql'
            if "db_password" in database_config and database_config["db_password"]:
                db_password = f':{database_config["db_password"]}'
            if "db_username" in database_config and database_config["db_username"]:
                db_username = database_config["db_username"]
            if "db_host" in database_config and database_config["db_host"]:
                db_host = f'@{database_config["db_host"]}'
            if "db_port" in database_config and database_config["db_port"]:
                db_port = f':{database_config["db_port"]}'

            db_authentication = f"{db_username}{db_password}{db_host}{db_port}"
            db_connection_string = f"{db_type}://{db_authentication}/{db_name}"

        self.ENGINE = create_engine(db_connection_string, echo=self.debug, echo_pool="debug")
        self.SESSION = sessionmaker(bind=self.ENGINE)

        self.create_all()
        self._import_modules()

    def create_all(self):
        """creates all tables previously defined"""
        BASE.metadata.bind = self.ENGINE
        BASE.metadata.create_all()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.SESSION()
        error = None
        try:
            yield session
            session.commit()
        except SQLAlchemyError as ex:
            session.rollback()
            error = ex
        finally:
            session.close()

        if error is not None:
            raise NerpyException() from error

    async def on_ready(self):
        """calls when successfully logged in"""
        self.log.info("Ready!")

    async def on_command_completion(self, ctx):
        """deleting msg on cmd completion"""
        if self.restart is True and not isinstance(ctx.channel, discord.DMChannel):
            if ctx.guild.id not in self.last_cmd_cache:
                self.last_cmd_cache[ctx.guild.id] = []
            elif len(self.last_cmd_cache[ctx.guild.id]) >= 10:
                self.last_cmd_cache[ctx.guild.id].pop(0)

            self.last_cmd_cache[ctx.guild.id].append(ctx.message)

            await ctx.message.delete()

    async def on_command_error(self, ctx, error):
        send_err = True
        if isinstance(error, commands.CommandNotFound):
            if ctx.author not in self.usr_cmd_err_spam:
                self.usr_cmd_err_spam[ctx.author] = 0

            if self.usr_cmd_err_spam[ctx.author] < self.usr_cmd__err_spam_threshold:
                send_err = False
                self.usr_cmd_err_spam[ctx.author] += 1
            else:
                self.usr_cmd_err_spam[ctx.author] = 0

        if send_err:
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
        with self.session_scope() as session:
            def_chan = DefaultChannel.get(guild_id, session)
            if def_chan is not None:
                chan = self.get_channel(def_chan.ChannelId)
                if chan is not None:
                    await chan.send(msg, embed=emb, file=file, files=files, delete_after=delete_after)
                    return

        if not cur_chan.permissions_for(cur_chan.guild.me).send_messages:
            raise NerpyException("Missing permission to send message to channel.")

        await cur_chan.send(msg, embed=emb, file=file, files=files, delete_after=delete_after)

    async def sendc(self, ctx, msg, emb=None, file=None, files=None, delete_after=None):
        await self.send(ctx.guild.id, ctx.channel, msg, emb, file, files, delete_after)

    async def start(self):
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
        await self.connect(reconnect=self.restart)

    async def shutdown(self):
        """
        shutting down discord nicely
        """
        self.log.info("shutting down server!")
        self.restart = False
        await self.audio.rip_loop()
        await self.close()

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


def determine_prefix(bot, message):
    guild = message.guild
    # Only allow custom prefixes in guild
    if guild:
        with bot.session_scope() as session:
            pref = GuildPrefix.get(guild.id, session)
            if pref is not None:
                return pref.Prefix
    return ["!"]  # default prefix


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
    ARGS = parse_arguments()
    CONFIG = parse_config(ARGS.config)
    DEBUG = ARGS.debug

    if "bot" in CONFIG:
        BOT = NerpyBot(CONFIG, DEBUG)

        try:
            BOT.run()
        except discord.LoginFailure:
            BOT.log.error(traceback.format_exc())
            BOT.log.error("Failed to login")
    else:
        raise NerpyException("Bot config not found.")
