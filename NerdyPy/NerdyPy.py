# -*- coding: utf-8 -*-
"""
Main Class of the NerpyBot
"""

from argparse import ArgumentParser, Namespace
from asyncio import run
from contextlib import contextmanager
from datetime import UTC, datetime
from itertools import cycle
from pathlib import Path
from traceback import format_exc, print_exc, print_tb
from typing import Any, Generator

import yaml
from discord import (
    ClientException,
    DMChannel,
    Game,
    Intents,
    Interaction,
    LoginFailure,
    Message,
    RawReactionActionEvent,
    app_commands,
)
from discord.ext import commands, tasks
from discord.ext.commands import (
    Bot,
    CommandError,
    CommandNotFound,
    Context,
    ExtensionFailed,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from utils import logging
from utils.audio import Audio
from utils.conversation import AnswerType, ConversationManager
from utils.database import BASE
from utils.errors import NerpyException, SilentCheckFailure
from utils.helpers import error_context, notify_error, parse_id
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for


ACTIVITIES = [
    "💡 Use / for commands",
    "🤓 Now even more Nerdy!",
    "⚡ Use / for commands",
    "🔮 I told you it was true!",
    "🚀 Use / for commands",
    "🏃 One step ahead!",
    "✨ Use / for commands",
    "🤖 Beep boop, I'm helping!",
    "🎯 Use / for commands",
    "🧠 Trust the process.",
]


class NerpyBot(Bot):
    """Discord Bot"""

    def __init__(self, config: dict, intents: Intents, debug: bool):
        super().__init__(
            command_prefix="",
            description="NerdyBot - Always one step ahead!",
            intents=intents,
            help_command=None,
        )

        self.config = config
        self.debug = debug
        self.client_id = parse_id(config["bot"]["client_id"])
        self.token = config["bot"]["token"]
        self.ops = [parse_id(op) for op in config["bot"]["ops"]]
        self.modules = config["bot"]["modules"]
        self.restart = True
        self.log = logging.get_logger("nerpybot")
        self.uptime = datetime.now(UTC)

        self.audio = Audio(self)
        self.convMan = ConversationManager(self)
        self._activity_cycle = cycle(ACTIVITIES)

        # database variables
        db_connection_string = self.build_connection_string(config)
        if "database" not in config:
            self.log.warning("No Database specified! Fallback to local SQLite Database!")

        self.ENGINE = create_engine(db_connection_string)
        self.SESSION = sessionmaker(bind=self.ENGINE, expire_on_commit=False)

    @staticmethod
    def build_connection_string(config: dict) -> str:
        """Build a SQLAlchemy connection string from the bot config.

        Returns ``"sqlite:///db.db"`` when no database section is present.
        Appends ``?charset=utf8mb4`` for MySQL/MariaDB connections so PyMySQL
        negotiates UTF-8 instead of defaulting to latin1.
        """
        if "database" not in config:
            return "sqlite:///db.db"

        database_config = config["database"]
        db_type = database_config["db_type"]
        db_name = database_config["db_name"]
        db_username = ""
        db_password = ""
        db_host = ""
        db_port = ""

        is_mysql = any(s in db_type for s in ("mysql", "mariadb"))

        if is_mysql:
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
        connection_string = f"{db_type}://{db_authentication}/{db_name}"

        if is_mysql:
            connection_string += "?charset=utf8mb4"

        return connection_string

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
        self.tree.on_error = self._on_app_command_error

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

    @tasks.loop(minutes=5)
    async def _rotate_activity(self) -> None:
        await self.change_presence(activity=Game(name=next(self._activity_cycle)))

    async def on_ready(self) -> None:
        """calls when successfully logged in"""
        from models.permissions import PermissionSubscriber

        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")

        if not self._rotate_activity.is_running():
            self._rotate_activity.start()

        required = required_permissions_for(self.modules)
        for guild in self.guilds:
            missing = check_guild_permissions(guild, required)
            if missing:
                self.log.warning(f"[{guild.name} ({guild.id})] missing permissions: {', '.join(missing)}")
                emb = build_permissions_embed(guild, missing, self.client_id, required)
                with self.session_scope() as session:
                    subscribers = PermissionSubscriber.get_by_guild(guild.id, session)
                for sub in subscribers:
                    try:
                        user = await self.fetch_user(sub.UserId)
                        await user.send(embed=emb)
                    except Exception as ex:
                        self.log.debug(f"Could not DM permission alert to {sub.UserId}: {ex}")

    async def _on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError) -> None:
        """Handle errors from slash commands."""
        err_ctx = error_context(interaction)

        if isinstance(error, app_commands.CheckFailure):
            if isinstance(error, SilentCheckFailure):
                self.log.warning(f"{err_ctx}: {error}")
                return
            msg = str(error)
            self.log.warning(f"{err_ctx}: {msg}")
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        elif isinstance(error, app_commands.CommandInvokeError):
            if isinstance(error.original, NerpyException):
                err_msg = "".join(error.original.args[0])
                self.log.error(f"{err_ctx}: {err_msg}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(err_msg, ephemeral=True)
                else:
                    await interaction.followup.send(err_msg, ephemeral=True)
            else:
                self.log.error(f"{err_ctx}: {error.original.__class__.__name__}: {error.original}")
                print_tb(error.original.__traceback__)
                msg = "An error occurred. The bot operator has been notified."
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
                await notify_error(self, err_ctx, error.original)
        else:
            self.log.error(f"{err_ctx}: {error}")

    async def on_command_error(self, ctx: Context, error) -> None:
        """Handle errors from prefix commands (sync, debug, raidplaner)."""
        if isinstance(error, CommandNotFound):
            return  # Silently ignore — DM prefix fallback only
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, NerpyException):
            self.log.error(f"{error_context(ctx)}: {error.original.args[0]}")
            await ctx.send(str(error.original.args[0]))
        elif isinstance(error, CommandError):
            self.log.error(f"{error_context(ctx)}: {error}")
            await ctx.send("An error occurred.")

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
        Handles DM messages — prefix commands and conversation replies.
        Guild messages are ignored; guilds use slash commands exclusively.
        """
        if message.author.bot:
            return

        if not isinstance(message.channel, DMChannel):
            return

        conv = self.convMan.get_user_conversation(message.author)
        if conv is not None and conv.is_answer_type(AnswerType.TEXT):
            await conv.on_message(message.content)
        else:
            await self.process_commands(message)

    async def start(self, token: str = None, reconnect: bool = True) -> None:
        """
        generator connects the discord bot to the server

        :param token: str
        :param reconnect: bool
        """
        self.log.info("Logging into Discord...")
        if self.token:
            self.activity = Game(name=ACTIVITIES[0])
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


def parse_arguments() -> Namespace:
    """
    parser for starting arguments

    currently only supports auto restart
    """
    parser = ArgumentParser(description="-> NerpyBot <-")
    parser.add_argument("-r", "--auto-restart", help="Autorestarts NerdyPy in case of issues", action="store_true")
    parser.add_argument("-c", "--config", help="Specify config file for NerdyPy", nargs=1)
    parser.add_argument("-d", "--debug", help="Enable debug logging", action="store_true")
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


def main() -> None:
    """Entry point for the NerpyBot."""
    args = parse_arguments()
    config = parse_config(args.config)
    intents = get_intents()

    debug = args.debug or str(args.loglevel).upper() == "DEBUG" or args.verbosity > 0
    loggers = ["nerpybot"]
    if args.verbosity >= 3 or str(args.loglevel).upper() == "DEBUG":
        loggers.append("sqlalchemy.engine")

    if "bot" in config:
        loglevel = "DEBUG" if args.debug else args.loglevel
        for logger_name in loggers:
            logging.create_logger(args.verbosity, loglevel, logger_name)
        bot = NerpyBot(config, intents, debug)

        try:
            run(bot.start())
        except LoginFailure:
            bot.log.error(format_exc())
            bot.log.error("Failed to login")
        except KeyboardInterrupt:
            bot.log.info("Received KeyboardInterrupt, shutting down.")
    else:
        raise NerpyException("Bot config not found.")


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

    main()
