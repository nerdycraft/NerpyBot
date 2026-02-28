# -*- coding: utf-8 -*-
"""
Main Class of the NerpyBot
"""

import os
from asyncio import CancelledError, create_task, run, sleep
from contextlib import contextmanager
from warnings import filterwarnings
from datetime import UTC, datetime
from pathlib import Path
from random import choices as random_choices, uniform as random_uniform
from traceback import format_exc, print_exc, print_tb
from typing import Annotated, Any, Generator, Optional

import typer

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
from discord.ext import commands
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
from utils.error_throttle import ErrorThrottle
from utils.errors import NerpyException, NerpyInfraException, SilentCheckFailure
from utils.helpers import error_context, notify_error, parse_id
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for
from utils.strings import get_localized_string, get_string, load_strings


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
    "🌀 Spinning up something fun!",
    "👾 404: Chill not found",
    "🎲 Rolling the dice…",
    "🫡 At your service!",
]

# "Use / for commands" entries get 3× higher chance than flavor entries
ACTIVITY_WEIGHTS = [3 if "/" in a else 1 for a in ACTIVITIES]


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
        self.error_throttle = ErrorThrottle()
        self.disabled_modules: set[str] = set()

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

        if "postgresql" in db_type:
            db_type = f"{db_type}+psycopg"

        if "db_password" in database_config and database_config["db_password"]:
            db_password = f":{database_config['db_password']}"
        if "db_username" in database_config and database_config["db_username"]:
            db_username = database_config["db_username"]
        if "db_host" in database_config and database_config["db_host"]:
            db_host = f"@{database_config['db_host']}"
        if "db_port" in database_config and database_config["db_port"]:
            db_port = f":{database_config['db_port']}"

        db_authentication = f"{db_username}{db_password}{db_host}{db_port}"
        return f"{db_type}://{db_authentication}/{db_name}"

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
            raise NerpyInfraException("A database error occurred.") from exc
        finally:
            session.close()

    async def setup_hook(self) -> None:
        """
        Discord Bot setup_hook
        Loads Modules and creates Databases
        """
        self.tree.on_error = self._on_app_command_error
        self.tree.interaction_check = self._global_interaction_check

        # load modules
        audio_module_loaded = False
        for module in self.modules:
            try:
                await self.load_extension(f"modules.{module}")
                if module in ("tagging", "music") and not audio_module_loaded:
                    await self.audio.setup_loops()
                    audio_module_loaded = True
            except (ImportError, ExtensionFailed, ClientException) as e:
                self.log.error(f"failed to load extension {module}. {e}")
                self.log.debug(print_exc())

        # noinspection GrazieInspection
        # auto-load essential extensions not explicitly listed in config
        auto_load = ["admin"]
        if audio_module_loaded:
            auto_load.append("voicecontrol")

        for module in auto_load:
            if module not in self.modules:
                try:
                    await self.load_extension(f"modules.{module}")
                except (ImportError, ExtensionFailed, ClientException) as e:
                    self.log.error(f"failed to auto-load {module} extension. {e}")
                    self.log.debug(print_exc())

        # Register persistent views so buttons on old messages keep working
        if "application" in self.modules:
            try:
                from modules.views.application import ApplicationApplyView, ApplicationReviewView

                self.add_view(ApplicationReviewView(bot=self))
                self.add_view(ApplicationApplyView(bot=self))
            except Exception as e:
                self.log.error(f"failed to register application persistent views. {e}")
                self.log.debug(print_exc())

        # Register crafting order persistent views and dynamic items
        if "wow" in self.modules:
            try:
                from modules.views.crafting_order import (
                    AcceptOrderButton,
                    AskQuestionButton,
                    CancelOrderButton,
                    CompleteOrderButton,
                    CraftingBoardView,
                    DropOrderButton,
                )

                self.add_view(CraftingBoardView(bot=self))
                self.add_dynamic_items(
                    AcceptOrderButton, DropOrderButton, CompleteOrderButton, CancelOrderButton, AskQuestionButton
                )
            except Exception as e:
                self.log.error(f"failed to register crafting order persistent views. {e}")
                self.log.debug(print_exc())

        # load localization strings
        load_strings()

        # create database/tables and such stuff
        self.create_all()

    async def _global_interaction_check(self, interaction: Interaction) -> bool:
        """Block slash commands from disabled modules."""
        command = interaction.command
        if command is None:
            return True

        cog = getattr(command, "binding", None)
        if cog is None:
            return True

        module_name = type(cog).__module__.rsplit(".", 1)[-1]
        if module_name in self.disabled_modules:
            try:
                with self.session_scope() as session:
                    msg = get_localized_string(interaction.guild_id, "bot.module_disabled", session, module=module_name)
            except Exception:
                msg = get_string("en", "bot.module_disabled", module=module_name)
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
            raise SilentCheckFailure(msg)

        return True

    async def _activity_loop(self) -> None:
        try:
            while not self.is_closed():
                activity = random_choices(ACTIVITIES, weights=ACTIVITY_WEIGHTS)[0]
                await self.change_presence(activity=Game(name=activity))
                await sleep(random_uniform(120, 420))
        except CancelledError:
            # Task was cancelled during shutdown; exit silently as this is expected.
            return
        except Exception as e:
            self.log.error(f"Activity loop crashed: {e}")

    async def on_ready(self) -> None:
        """calls when successfully logged in"""
        from models.admin import PermissionSubscriber

        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")

        if not hasattr(self, "_activity_task") or self._activity_task.done():
            self._activity_task = create_task(self._activity_loop())

        required = required_permissions_for(self.modules)
        for guild in self.guilds:
            missing = check_guild_permissions(guild, required)
            if missing:
                self.log.warning(f"[{guild.name} ({guild.id})] missing permissions: {', '.join(missing)}")
                emb = build_permissions_embed(guild, missing, self.client_id, required)
                # noinspection PyArgumentList
                with self.session_scope() as session:
                    subscribers = PermissionSubscriber.get_by_guild(guild.id, session)
                for sub in subscribers:
                    try:
                        user = await self.fetch_user(sub.UserId)
                        await user.send(embed=emb)
                    except Exception as ex:
                        self.log.debug(f"Could not DM permission alert to {sub.UserId}: {ex}")

    # noinspection PyUnusedLocal
    async def on_app_command_completion(self, interaction: Interaction, command: app_commands.Command) -> None:
        """Log successful slash command invocations."""
        self.log.debug(error_context(interaction))

    async def on_command_completion(self, ctx: Context) -> None:
        """Log successful prefix command invocations."""
        self.log.debug(error_context(ctx))

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
                if isinstance(error.original, NerpyInfraException):
                    await notify_error(self, err_ctx, error.original)
            else:
                self.log.error(f"{err_ctx}: {error.original.__class__.__name__}: {error.original}")
                print_tb(error.original.__traceback__)
                try:
                    with self.session_scope() as session:
                        msg = get_localized_string(interaction.guild_id, "common.error_generic", session)
                except Exception:
                    msg = get_string("en", "common.error_generic")
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await interaction.followup.send(msg, ephemeral=True)
                except Exception:
                    pass  # interaction may have expired; still notify operator
                await notify_error(self, err_ctx, error.original)
        else:
            self.log.error(f"{err_ctx}: {error}")

    async def on_command_error(self, ctx: Context, error) -> None:
        """Handle errors from prefix commands (sync, debug)."""
        if isinstance(error, CommandNotFound):
            return  # Silently ignore — DM prefix fallback only
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, NerpyException):
            self.log.error(f"{error_context(ctx)}: {error.original.args[0]}")
            await ctx.send(str(error.original.args[0]))
            if isinstance(error.original, NerpyInfraException):
                await notify_error(self, error_context(ctx), error.original)
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


def _csv(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _to_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes")


def _set_nested(d: dict, keys: list[str], value) -> None:
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def parse_env_config() -> dict:
    """Read NERPYBOT_* environment variables and return a config dict."""
    env: dict = {}
    mappings = [
        ("NERPYBOT_TOKEN", ["bot", "token"], str),
        ("NERPYBOT_CLIENT_ID", ["bot", "client_id"], str),
        ("NERPYBOT_OPS", ["bot", "ops"], _csv),
        ("NERPYBOT_MODULES", ["bot", "modules"], _csv),
        ("NERPYBOT_DB_TYPE", ["database", "db_type"], str),
        ("NERPYBOT_DB_NAME", ["database", "db_name"], str),
        ("NERPYBOT_DB_USERNAME", ["database", "db_username"], str),
        ("NERPYBOT_DB_PASSWORD", ["database", "db_password"], str),
        ("NERPYBOT_DB_HOST", ["database", "db_host"], str),
        ("NERPYBOT_DB_PORT", ["database", "db_port"], str),
        ("NERPYBOT_AUDIO_BUFFER_LIMIT", ["audio", "buffer_limit"], int),
        ("NERPYBOT_YOUTUBE_KEY", ["music", "ytkey"], str),
        ("NERPYBOT_RIOT_KEY", ["league", "riot"], str),
        ("NERPYBOT_WOW_CLIENT_ID", ["wow", "wow_id"], str),
        ("NERPYBOT_WOW_CLIENT_SECRET", ["wow", "wow_secret"], str),
        ("NERPYBOT_WOW_POLL_INTERVAL_MINUTES", ["wow", "guild_news", "poll_interval_minutes"], int),
        ("NERPYBOT_WOW_MOUNT_BATCH_SIZE", ["wow", "guild_news", "mount_batch_size"], int),
        ("NERPYBOT_WOW_TRACK_MOUNTS", ["wow", "guild_news", "track_mounts"], _to_bool),
        ("NERPYBOT_WOW_ACTIVE_DAYS", ["wow", "guild_news", "active_days"], int),
        ("NERPYBOT_ERROR_RECIPIENTS", ["notifications", "error_recipients"], _csv),
    ]
    for var_name, keys, converter in mappings:
        value = os.environ.get(var_name)
        if value:
            _set_nested(env, keys, converter(value))
    return env


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base; override wins on conflicts."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def parse_config(config_path: Optional[Path] = None) -> dict:
    config = {}
    path = config_path or Path("./config.yaml")
    if path.exists():
        with open(path) as stream:
            try:
                config = yaml.safe_load(stream) or {}
            except yaml.YAMLError as exc:
                print(f"Error in configuration file: {exc}")
    return deep_merge(config, parse_env_config())


app = typer.Typer(add_completion=False)


@app.command()
def main(
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Config file path")] = None,
    debug: Annotated[bool, typer.Option("--debug", "-d", help="Enable debug logging")] = False,
    auto_restart: Annotated[bool, typer.Option("--auto-restart", "-r", help="Auto-restart on failure")] = False,
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)")] = "INFO",
    verbosity: Annotated[
        int, typer.Option("--verbosity", "-v", help="Verbosity: 1=DEBUG, 2=+discord, 3=+sqlalchemy")
    ] = 0,
) -> None:
    """NerpyBot — the nerdiest Discord bot."""
    filterwarnings("ignore", category=DeprecationWarning, module=r"discord\.http")

    resolved_config = parse_config(config)
    intents = get_intents()

    is_debug = debug or str(loglevel).upper() == "DEBUG" or verbosity > 0
    loggers = ["nerpybot"]
    if verbosity >= 2:
        loggers.append("discord")
    if verbosity >= 3 or str(loglevel).upper() == "DEBUG":
        loggers.append("sqlalchemy.engine")

    if "bot" in resolved_config:
        resolved_loglevel = "DEBUG" if (debug or verbosity > 0) else loglevel
        for logger_name in loggers:
            logging.create_logger(resolved_loglevel, logger_name)
        bot = NerpyBot(resolved_config, intents, is_debug)

        try:
            run(bot.start())
        except LoginFailure:
            bot.log.error(format_exc())
            bot.log.error("Failed to login")
        except KeyboardInterrupt:
            bot.log.info("Received KeyboardInterrupt, shutting down.")
    else:
        raise NerpyInfraException("Bot config not found.")


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
    app()
