"""
Main Class of the NerpyBot
"""

import json
import discord
import asyncio
import argparse
import traceback
import configparser
import utils.logging as logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from models.guild_prefix import GuildPrefix
from utils.audio import Audio
from utils.conversation import ConversationManager, AnswerType
from utils.database import BASE
from utils.errors import NerpyException


class NerpyBot(commands.Bot):
    """Discord Bot"""

    def __init__(self, config: configparser.ConfigParser, intents: discord.Intents, debug: bool):
        super().__init__(
            command_prefix=determine_prefix, description="NerdyBot - Always one step ahead!", intents=intents
        )

        self.config = config
        self.debug = debug
        self.client_id = config.get("bot", "client_id")
        self.token = config.get("bot", "token")
        self.ops = config.get("bot", "ops")
        self.moderator_role = config.get("bot", "moderator_role_name")
        self.modules = json.loads(config.get("bot", "modules"))
        self.restart = True
        self.log = logging.get_logger("nerpybot")
        self.uptime = datetime.utcnow()

        self.audio = Audio(self)
        self.last_cmd_cache = {}
        self.usr_cmd_err_spam = {}
        self.usr_cmd__err_spam_threshold = config.getint("bot", "error_spam_threshold")
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

        self.ENGINE = create_engine(db_connection_string)
        self.SESSION = sessionmaker(bind=self.ENGINE, expire_on_commit=False)

    def create_all(self):
        """creates all tables previously defined"""
        BASE.metadata.bind = self.ENGINE
        BASE.metadata.create_all()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
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

    async def commands_need_sync(self):
        global_app_commands = await self.tree.fetch_commands()
        for command in self.tree.walk_commands():
            if command.name not in global_app_commands:
                return True

        return False

    async def setup_hook(self):
        # load modules
        for module in self.modules:
            try:
                await self.load_extension(f"modules.{module}")
            except (ImportError, commands.ExtensionFailed, discord.ClientException) as e:
                self.log.error(f"failed to load extension {module}. {e}")
                self.log.debug(traceback.print_exc())

        # create database/tables and such stuff
        self.create_all()

        # sync commands
        if await self.commands_need_sync():
            self.log.info("Syncing commands...")
            await self.tree.sync()

    async def on_ready(self):
        """calls when successfully logged in"""
        self.log.info(f'Logged in as {self.user} (ID: {self.user.id})')

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
                    self.log.error(f"In {ctx.command.qualified_name}:")
                    traceback.print_tb(error.original.__traceback__)
                    self.log.error(f"{error.original.__class__.__name__}: {error.original}")
                    await ctx.author.send("Unhandled error occurred. Please report to bot author!")
                elif isinstance(error.original, NerpyException):
                    await ctx.author.send(error.original)
                else:
                    self.log.error(error)
            else:
                self.log.error(f"In {ctx.command.qualified_name}:")
                traceback.print_tb(error.original.__traceback__)
                self.log.error(f"{error.original.__class__.__name__}: {error.original}")
                await ctx.author.send("Unhandled error occurred. Please report to bot author!")

        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        user = await self.fetch_user(payload.user_id)
        if user is None or user.bot:
            return

        conv = self.convMan.get_user_conversation(user)
        if conv is not None and conv.is_conv_message(payload.message_id) and conv.is_answer_type(AnswerType.REACTION):
            await conv.on_react(payload.emoji)

    async def on_message(self, message):
        if message.author.bot:
            return

        invoke = True
        if isinstance(message.channel, discord.DMChannel):
            conv = self.convMan.get_user_conversation(message.author)
            if conv is not None and conv.is_answer_type(AnswerType.TEXT):
                await conv.on_message(message.content)
                invoke = False

        if invoke:
            await self.process_commands(message)

    async def start(self, token: str = None, reconnect: bool = True):
        """
        generator connects the discord bot to the server
        """
        self.log.info("Logging into Discord...")
        if self.token:
            self.activity = discord.Game(name="!help for help")
            await self.login(self.token)
        else:
            self.log.critical("No credentials available to login.")
            raise RuntimeError()
        await self.connect(reconnect=self.restart)

    async def shutdown(self):
        """
        shutting down discord nicely
        """
        self.log.info("shutting down server!")
        self.restart = False
        await self.close()


def get_intents():
    return discord.Intents.all()


def determine_prefix(bot, message):
    guild = message.guild
    # Only allow custom prefixes in guild
    if guild:
        with bot.session_scope() as session:
            pref = GuildPrefix.get(guild.id, session)
            if pref is not None:
                return pref.Prefix
    return ["!"]  # default prefix


def parse_arguments() -> argparse.Namespace:
    """
    parser for starting arguments

    currently only supports auto restart
    """
    parser = argparse.ArgumentParser(description="-> NerpyBot <-")
    parser.add_argument("-r", "--auto-restart", help="Autorestarts NerdyPy in case of issues", action="store_true")
    parser.add_argument("-c", "--config", help="Specify config file for NerdyPy", nargs=1)
    parser.add_argument("-v", "--verbose", action="count", required=False, dest="verbosity", default=0)
    parser.add_argument("-l", "--loglevel", action="store", required=False, dest="loglevel", default="WARNING")

    return parser.parse_args()


def parse_config(config_file=None) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)

    if config_file is None:
        config_file = Path("./config.ini")
    else:
        config_file = Path(config_file[0])

    if config_file.exists():
        config.read(config_file)

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

    RUNNING = True
    ARGS = parse_arguments()
    CONFIG = parse_config(ARGS.config)
    INTENTS = get_intents()
    if str(ARGS.loglevel).upper() == "DEBUG" or ARGS.verbosity > 0:
        DEBUG = True
    else:
        DEBUG = False

    if "bot" in CONFIG:
        for logger_name in ["nerpybot", "sqlalchemy.engine"]:
            logging.create_logger(ARGS.verbosity, ARGS.loglevel, logger_name)
        BOT = NerpyBot(CONFIG, INTENTS, DEBUG)

        try:
            asyncio.run(BOT.start())
        except discord.LoginFailure:
            BOT.log.error(traceback.format_exc())
            BOT.log.error("Failed to login")
        except KeyboardInterrupt:
            pass
    else:
        raise NerpyException("Bot config not found.")
