# -*- coding: utf-8 -*-
"""
Main Class of the NerpyBot
"""

from argparse import ArgumentParser, Namespace
from asyncio import run
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exc, print_exc, print_tb
from typing import Any, Generator, List

import yaml
from discord import (
    ClientException,
    DMChannel,
    Game,
    Intents,
    LoginFailure,
    Message,
    RawReactionActionEvent,
    app_commands,
)
from discord.ext import commands
from discord.ext.commands import (
    Bot,
    CheckFailure,
    CommandError,
    CommandNotFound,
    Context,
    ExtensionFailed,
)
from models.admin import GuildPrefix
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from utils import logging
from utils.audio import Audio
from utils.conversation import AnswerType, ConversationManager
from utils.database import BASE
from utils.errors import NerpyException
from utils.helpers import send_hidden_message


class NerpyBot(Bot):
    """Discord Bot"""

    def __init__(self, config: dict, intents: Intents, debug: bool):
        # noinspection PyTypeChecker
        super().__init__(
            command_prefix=determine_prefix, description="NerdyBot - Always one step ahead!", intents=intents
        )

        self.config = config
        self.debug = debug
        self.client_id = config["bot"]["client_id"]
        self.token = config["bot"]["token"]
        self.ops = config["bot"]["ops"]
        self.modules = config["bot"]["modules"]
        self.restart = True
        self.log = logging.get_logger("nerpybot")
        self.uptime = datetime.now(UTC)

        self.audio = Audio(self)
        self.last_cmd_cache = {}
        self.usr_cmd_err_spam = {}
        self.usr_cmd__err_spam_threshold = config["bot"]["error_spam_threshold"]
        self.convMan = ConversationManager(self)

        # database variables
        if "database" not in config:
            self.log.warning("No Database specified! Fallback to local SQLite Database!")
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
                db_type = f"{db_type}+pymysql"
            if "db_password" in database_config and database_config["db_password"]:
                db_password = f":{database_config['db_password']}"
            if "db_username" in database_config and database_config["db_username"]:
                db_username = database_config["db_username"]
            if "db_host" in database_config and database_config["db_host"]:
                db_host = f"@{database_config['db_host']}"
            if "db_port" in database_config and database_config["db_port"]:
                db_port = f":{database_config['db_port']}"

            db_authentication = f"{db_username}{db_password}{db_host}{db_port}"
            db_connection_string = f"{db_type}://{db_authentication}/{db_name}"

        self.ENGINE = create_engine(db_connection_string)
        self.SESSION = sessionmaker(bind=self.ENGINE, expire_on_commit=False)

    def create_all(self) -> None:
        """creates all tables previously defined"""
        BASE.metadata.create_all(self.ENGINE)

    @contextmanager
    def session_scope(self) -> Generator[Session, Any, None]:
        """Provide a transactional scope around a series of operations.

        :rtype: object
        """
        session = self.SESSION()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            self.log.error(exc)
            raise NerpyException("There was an error with the database. Please report to Bot Author!")
        finally:
            session.close()

    async def setup_hook(self) -> None:
        """
        Discord Bot setup_hook
        Loads Modules and creates Databases
        """
        # load modules
        for module in self.modules:
            try:
                await self.load_extension(f"modules.{module}")
                if module == "tagging" or module == "music":
                    # set-up audio loops
                    await self.audio.setup_loops()
            except (ImportError, ExtensionFailed, ClientException) as e:
                self.log.error(f"failed to load extension {module}. {e}")
                self.log.debug(print_exc())

        # create database/tables and such stuff
        self.create_all()

    async def on_ready(self) -> None:
        """calls when successfully logged in"""
        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_command_completion(self, ctx: Context) -> None:
        """
        Deleting msg on cmd completion (this is only true if no slash command was used)

        Also adds legacy commands to the command cache, which can then be queried by the 'history' command
        """
        if self.restart is True and not isinstance(ctx.channel, DMChannel):
            if ctx.guild.id not in self.last_cmd_cache:
                self.last_cmd_cache[ctx.guild.id] = []
            elif len(self.last_cmd_cache[ctx.guild.id]) >= 10:
                self.last_cmd_cache[ctx.guild.id].pop(0)

            self.last_cmd_cache[ctx.guild.id].append(ctx.message)

            await ctx.message.delete()

    async def on_command_error(self, ctx: Context, error) -> None:
        """
        Sends an error message to the command invoker

        :param ctx:
        :param error:
        """
        send_err = True
        if isinstance(error, CommandNotFound):
            if ctx.author not in self.usr_cmd_err_spam:
                self.usr_cmd_err_spam[ctx.author] = 0

            if self.usr_cmd_err_spam[ctx.author] < self.usr_cmd__err_spam_threshold:
                send_err = False
                self.usr_cmd_err_spam[ctx.author] += 1
            else:
                self.usr_cmd_err_spam[ctx.author] = 0

        if send_err:
            if isinstance(error, CommandError):
                if isinstance(error, commands.CommandInvokeError) and not isinstance(error.original, NerpyException):
                    self.log.error(f"In {ctx.command.qualified_name}:")
                    print_tb(error.original.__traceback__)
                    self.log.error(f"{error.original.__class__.__name__}: {error.original}")
                    await ctx.author.send("Unhandled error occurred. Please report to bot author!")
                if isinstance(error.original, app_commands.CommandInvokeError) and isinstance(
                    error.original.original, NerpyException
                ):
                    await send_hidden_message(ctx, error.original.original.args[0])
                if not isinstance(error, CheckFailure) and isinstance(error.original, NerpyException):
                    if ctx.interaction is None:
                        await ctx.author.send("".join(error.original.args[0]))
                    else:
                        await send_hidden_message(ctx, "".join(error.original.args[0]))
                self.log.error(error)
            else:
                self.log.error(f"In {ctx.command.qualified_name}:")
                print_tb(error.original.__traceback__)
                self.log.error(f"{error.original.__class__.__name__}: {error.original}")
                if ctx.interaction is None:
                    await ctx.author.send("Unhandled error occurred. Please report to bot author!")
                else:
                    await send_hidden_message(ctx, "Unhandled error occurred. Please report to bot author!")

        if not isinstance(ctx.channel, DMChannel) and ctx.interaction is None:
            await ctx.message.delete()

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        """
        Handles reactions to messages

        :param payload:
        :return:
        """
        user = await self.fetch_user(payload.user_id)
        if user is None or user.bot:
            return

        conv = self.convMan.get_user_conversation(user)
        if conv is not None and conv.is_conv_message(payload.message_id) and conv.is_answer_type(AnswerType.REACTION):
            await conv.on_react(payload.emoji)

    async def on_message(self, message: Message) -> None:
        """
        Handles chats in DMs to the bot

        :param message:
        :return:
        """
        if message.author.bot:
            return

        invoke = True
        if isinstance(message.channel, DMChannel):
            conv = self.convMan.get_user_conversation(message.author)
            if conv is not None and conv.is_answer_type(AnswerType.TEXT):
                await conv.on_message(message.content)
                invoke = False

        if invoke:
            await self.process_commands(message)

    async def start(self, token: str = None, reconnect: bool = True) -> None:
        """
        generator connects the discord bot to the server

        :param token: str
        :param reconnect: bool
        """
        self.log.info("Logging into Discord...")
        if self.token:
            self.activity = Game(name="!help for help")
            await self.login(self.token)
        else:
            self.log.critical("No credentials available to login.")
            raise RuntimeError()
        await self.connect(reconnect=self.restart)

    async def shutdown(self) -> None:
        """
        shutting down discord nicely
        """
        self.log.info("shutting down server!")
        self.restart = False
        await self.close()


def get_intents() -> Intents:
    return Intents.all()


def determine_prefix(bot, message) -> List[str]:
    """
    Gets the current prefix if any and set's it for the bot.
    Defaults to '!'

    :param bot: NerpyBot
    :param message: discord.message.Message
    :return: List[str]
    """
    guild = message.guild
    # Only allow custom prefixes in guild
    if guild:
        with bot.session_scope() as session:
            pref = GuildPrefix.get(guild.id, session)
            if pref is not None:
                return [pref.Prefix]
    return ["!"]  # default prefix


def parse_arguments() -> Namespace:
    """
    parser for starting arguments

    currently only supports auto restart
    """
    parser = ArgumentParser(description="-> NerpyBot <-")
    parser.add_argument("-r", "--auto-restart", help="Autorestarts NerdyPy in case of issues", action="store_true")
    parser.add_argument("-c", "--config", help="Specify config file for NerdyPy", nargs=1)
    parser.add_argument("-v", "--verbose", action="count", required=False, dest="verbosity", default=0)
    parser.add_argument("-l", "--loglevel", action="store", required=False, dest="loglevel", default="INFO")

    return parser.parse_args()


def parse_config(config_file=None) -> dict:
    config = {}

    if config_file is None:
        config_file = Path("./config.yaml")
    else:
        config_file = Path(config_file[0])

    if config_file.exists():
        with open(config_file, "r") as stream:
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(f"Error in configuration file: {exc}")

    return config


if __name__ == "__main__":
    print(
        """
'##::: ##:'########:'########::'########::'##:::'##::::'########:::'#######::'########:
 ###:: ##: ##.....:: ##.... ##: ##.... ##:. ##:'##::::: ##.... ##:'##.... ##:... ##..::
 ####: ##: ##::::::: ##:::: ##: ##:::: ##::. ####:::::: ##:::: ##: ##:::: ##:::: ##::::
 ## ## ##: ######::: ########:: ########::::. ##::::::: ########:: ##:::: ##:::: ##::::
 ##. ####: ##...:::: ##.. ##::: ##.....:::::: ##::::::: ##.... ##: ##:::: ##:::: ##::::
 ##:. ###: ##::::::: ##::. ##:: ##::::::::::: ##::::::: ##:::: ##: ##:::: ##:::: ##::::
 ##::. ##: ########: ##:::. ##: ##::::::::::: ##::::::: ########::. #######::::: ##::::
..::::..::........::..:::::..::..::::::::::::..::::::::........::::.......::::::..:::::
"""
    )

    ARGS = parse_arguments()
    CONFIG = parse_config(ARGS.config)
    INTENTS = get_intents()
    if str(ARGS.loglevel).upper() == "DEBUG" or ARGS.verbosity > 0:
        DEBUG = True
        loggers = ["nerpybot", "sqlalchemy.engine"]
    else:
        DEBUG = False
        loggers = ["nerpybot"]

    if "bot" in CONFIG:
        for logger_name in loggers:
            logging.create_logger(ARGS.verbosity, ARGS.loglevel, logger_name)
        BOT = NerpyBot(CONFIG, INTENTS, DEBUG)

        try:
            run(BOT.start())
        except LoginFailure:
            BOT.log.error(format_exc())
            BOT.log.error("Failed to login")
        except KeyboardInterrupt:
            pass
    else:
        raise NerpyException("Bot config not found.")
