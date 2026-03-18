# -*- coding: utf-8 -*-
"""
Main Class of the NerpyBot
"""

import time
from asyncio import CancelledError, create_task, run, sleep
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from random import choices as random_choices
from random import uniform as random_uniform
from traceback import format_exc, print_exc, print_tb
from typing import Annotated, Any, Generator, Optional
from warnings import filterwarnings

import typer
from importlib.metadata import version as pkg_version
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
from alembic.config import Config
import alembic.command as alembic_command
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from models.admin import BotGuild
from utils import logging
from utils.audio import Audio
from utils.cache import GuildConfigCache
from utils.config import parse_config
from utils.conversation import AnswerType, ConversationManager
from utils.database import BASE
from utils.error_throttle import ErrorCounter, ErrorThrottle
from utils.errors import NerpyException, NerpyInfraException, SilentCheckFailure
from utils.helpers import error_context, notify_error, parse_id, send_hidden_message
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for
from utils.strings import get_string, load_strings
from utils.valkey import valkey_listener_loop

SENTINEL_PATH = Path("/tmp/nerpybot_ready")

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


def run_migrations() -> None:
    """Apply all pending Alembic migrations before the bot connects.

    Searches upward from this file's directory for alembic.ini, so it works
    both in the repo (alembic.ini at root) and in Docker. Raises on failure —
    callers must not catch it.
    """
    log = logging.get_logger("nerpybot")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "alembic.ini"
        if candidate.exists():
            alembic_ini = candidate
            break
    else:
        raise FileNotFoundError("alembic.ini not found in any parent directory of bot.py")
    log.info("Running database migrations...")
    try:
        alembic_cfg = Config(str(alembic_ini))
        alembic_command.upgrade(alembic_cfg, "head")
    except Exception as e:
        log.error(f"Database migration failed: {e}")
        raise
    log.info("Database migrations complete.")


class NerpyBot(Bot):
    """Discord Bot"""

    def __init__(self, config: dict, intents: Intents, debug: bool):
        """
        Initialize the NerpyBot instance, configure subsystems, and prepare database access.

        This sets up bot identity and operator lists from the provided config, initializes audio,
        conversation and error-throttling subsystems, tracks uptime, prepares module state, and
        creates a SQLAlchemy engine and session factory (with connection pre-ping enabled). If no
        "database" section is present in config, a warning is logged and a local SQLite fallback is used.

        Parameters:
            config (dict): Parsed configuration containing at minimum:
                - bot.client_id: bot application ID (string or int-like)
                - bot.token: bot token string
                - bot.ops: iterable of operator IDs (strings or int-like)
                - bot.modules: module list/configuration
                - database (optional): database connection pieces; if absent, sqlite:///db.db is used.
            intents (Intents): Discord gateway intents for the bot.
            debug (bool): Debug flag to enable debug behavior in subsystems.

        """
        self.bot_name = (config["bot"].get("name") or "").strip() or "NerpyBot"
        bot_description = (
            config["bot"].get("description") or ""
        ).strip() or f"{self.bot_name} - Always one step ahead!"
        super().__init__(
            command_prefix="",
            description=bot_description,
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
        self.error_counter = ErrorCounter()
        self.disabled_modules: set[str] = set()
        self.guild_cache = GuildConfigCache()

        # database variables
        db_connection_string = self.build_connection_string(config)
        if "database" not in config:
            self.log.warning("No Database specified! Fallback to local SQLite Database!")

        self.ENGINE = create_engine(db_connection_string, pool_pre_ping=True)
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

        if "postgresql" in db_type:
            db_type = f"{db_type}+psycopg"

        return URL.create(
            drivername=db_type,
            username=database_config.get("db_username") or None,
            password=database_config.get("db_password") or None,
            host=database_config.get("db_host") or None,
            port=int(database_config["db_port"]) if database_config.get("db_port") else None,
            database=db_name,
        ).render_as_string(hide_password=False)

    def create_all(self) -> None:
        """creates all tables previously defined"""
        BASE.metadata.create_all(self.ENGINE)

    def get_guild_language(self, guild_id: int | None) -> str:
        """Return the configured language for a guild, defaulting to 'en'.

        Uses the in-memory cache; loads from DB on first access per guild.
        """
        if guild_id is None:
            return "en"
        return self.guild_cache.get_guild_language(guild_id, self.SESSION)

    def get_localized_string(self, guild_id: int | None, key: str, **kwargs) -> str:
        """Resolve the guild language from cache, then look up and format a string."""
        lang = self.get_guild_language(guild_id)
        return get_string(lang, key, **kwargs)

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
        auto_load = ["server_admin", "operator"]
        if audio_module_loaded:
            auto_load.append("voicecontrol")

        for module in auto_load:
            if module not in self.modules:
                try:
                    await self.load_extension(f"modules.{module}")
                except (ImportError, ExtensionFailed, ClientException) as e:
                    self.log.error(f"failed to auto-load {module} extension. {e}")
                    self.log.debug(print_exc())

        # load localization strings before registering persistent views (views call get_string in __init__)
        load_strings()

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
                msg = self.get_localized_string(interaction.guild_id, "bot.module_disabled", module=module_name)
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
        """
        Handle post-login initialization and readiness tasks.

        Starts the activity status loop and the Valkey listener (if configured), synchronizes guild membership state to the database, checks each guild for required permissions and notifies subscribed guild admins of any missing permissions, and writes the readiness sentinel file to signal that the bot is healthy and ready.
        """
        from models.admin import PermissionSubscriber

        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")

        if not hasattr(self, "_activity_task") or self._activity_task.done():
            self._activity_task = create_task(self._activity_loop())

        # Start Valkey listener for web dashboard commands (if configured)
        valkey_url = self.config.get("web", {}).get("valkey_url")
        if valkey_url and (not hasattr(self, "_valkey_task") or self._valkey_task.done()):
            self._valkey_task = create_task(valkey_listener_loop(self, valkey_url))

        # Sync guild membership table for web dashboard presence detection
        try:
            with self.session_scope() as session:
                BotGuild.sync([g.id for g in self.guilds], session)
        except Exception as e:
            self.log.warning(f"Failed to sync BotGuild table: {e}")

        for cache_name, warm in (
            ("reaction-role", self.guild_cache.warm_reaction_roles),
            ("leave-message", self.guild_cache.warm_leave_messages),
        ):
            try:
                warm(self.SESSION)
            except Exception as e:
                self.log.warning(f"Failed to warm {cache_name} cache: {e}")
        self.log.debug("Guild config cache warm-up finished.")

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

        SENTINEL_PATH.touch()
        self.log.info("Readiness sentinel written — healthcheck will pass.")

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
            await send_hidden_message(interaction, msg)
        elif isinstance(error, app_commands.CommandInvokeError):
            if isinstance(error.original, NerpyException):
                err_msg = "".join(error.original.args[0])
                self.log.error(f"{err_ctx}: {err_msg}")
                await send_hidden_message(interaction, err_msg)
                if isinstance(error.original, NerpyInfraException):
                    self.error_counter.record()
                    await notify_error(self, err_ctx, error.original)
            else:
                self.log.error(f"{err_ctx}: {error.original.__class__.__name__}: {error.original}")
                print_tb(error.original.__traceback__)
                try:
                    msg = self.get_localized_string(interaction.guild_id, "common.error_generic")
                except Exception:
                    msg = get_string("en", "common.error_generic")
                await send_hidden_message(interaction, msg)
                self.error_counter.record()
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
                self.error_counter.record()
                await notify_error(self, error_context(ctx), error.original)
        elif isinstance(error, CommandError):
            self.log.error(f"{error_context(ctx)}: {error}")
            self.error_counter.record()
            await ctx.send("An error occurred.")

    async def on_guild_join(self, guild) -> None:
        """Add the newly joined guild to the BotGuild table."""
        try:
            with self.session_scope() as session:
                BotGuild.add(guild.id, session)
        except Exception as e:
            self.log.warning(f"Failed to add guild {guild.id} to BotGuild table: {e}")

    async def on_guild_remove(self, guild) -> None:
        """Remove the departed guild from the BotGuild table."""
        try:
            with self.session_scope() as session:
                BotGuild.remove(guild.id, session)
        except Exception as e:
            self.log.warning(f"Failed to remove guild {guild.id} from BotGuild table: {e}")
        self.guild_cache.evict_guild(guild.id)

    async def on_guild_language_changed(self, guild_id: int, language: str) -> None:
        """Update the language cache when a guild changes its language setting."""
        self.guild_cache.set_guild_language(guild_id, language)

    async def on_modrole_changed(self, guild_id: int, role_id: int | None) -> None:
        """Update the modrole cache when a guild's bot-moderator role is set or cleared."""
        self.guild_cache.set_modrole(guild_id, role_id)

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


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"NerpyBot v{pkg_version('NerpyBot')}")
        raise typer.Exit()


app = typer.Typer(add_completion=False)


@app.command()
def main(
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Config file path")] = None,
    debug: Annotated[bool, typer.Option("--debug", "-d", help="Enable debug logging")] = False,
    loglevel: Annotated[str, typer.Option("--loglevel", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)")] = "INFO",
    verbosity: Annotated[
        int, typer.Option("--verbosity", "-v", help="Verbosity: 1=DEBUG, 2=+discord, 3=+sqlalchemy")
    ] = 0,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit")
    ] = False,
) -> None:
    """
    Start the NerpyBot CLI: load configuration, configure logging, run database migrations, instantiate the bot, and run its main lifecycle loop with automatic restart on unexpected crashes.

    Parameters:
        config (Path | None): Path to a YAML config file; if omitted, default config paths and environment variables are used.
        debug (bool): Enable verbose debug logging and developer-focused behavior.
        loglevel (str): Base log level (e.g., "DEBUG", "INFO", "WARNING", "ERROR"); environment config may override this when not explicitly provided.
        verbosity (int): Extra verbosity flags: 1 enables debug-style logging, 2 also enables Discord library logging, 3 also enables SQLAlchemy engine logging.
        version (bool): When set, prints the application version and exits (handled via a callback).

    Behavior:
        - Loads and merges configuration from the provided file and environment variables.
        - Determines effective logging configuration from CLI flags and config, and initializes selected loggers.
        - Runs database migrations before starting the bot.
        - Instantiates NerpyBot and enters its main run loop; on unexpected exceptions the process will remove the readiness sentinel file, wait briefly, and then retry.
        - Handles LoginFailure and KeyboardInterrupt by logging and exiting cleanly.

    Raises:
        NerpyInfraException: If no bot configuration is found in the resolved configuration.
    """
    print(BANNER)
    filterwarnings("ignore", category=DeprecationWarning, module=r"discord\.http")

    resolved_config = parse_config(config)
    intents = get_intents()

    # NERPYBOT_LOG_LEVEL env var is a fallback when --loglevel is not explicitly passed
    env_loglevel = resolved_config.get("bot", {}).get("log_level", "").upper()
    effective_loglevel = (env_loglevel if (env_loglevel and loglevel == "INFO") else loglevel).upper()

    is_debug = debug or effective_loglevel == "DEBUG" or verbosity > 0
    loggers = ["nerpybot"]
    if verbosity >= 2:
        loggers.append("discord")
    if verbosity >= 3:
        loggers.append("sqlalchemy.engine")

    if "bot" in resolved_config:
        # Configure alembic at INFO before run_migrations().
        # The guard in database-migrations/env.py checks logging.getLogger("alembic").handlers
        # to decide whether to skip fileConfig. Moving run_migrations() above this line
        # will silently revert embedded runs to alembic.ini formatting.
        logging.create_logger("INFO", "alembic")
        resolved_loglevel = "DEBUG" if (debug or verbosity > 0) else effective_loglevel
        for logger_name in loggers:
            logging.create_logger(resolved_loglevel, logger_name)
        SENTINEL_PATH.unlink(missing_ok=True)
        run_migrations()
        bot = NerpyBot(resolved_config, intents, is_debug)

        while True:
            try:
                run(bot.start())
                break  # clean exit
            except LoginFailure:
                bot.log.error(format_exc())
                bot.log.error("Failed to login — not restarting.")
                break
            except KeyboardInterrupt:
                bot.log.info("Received KeyboardInterrupt, shutting down.")
                break
            except Exception as e:
                bot.log.error(f"Crashed: {e}")
                bot.log.warning("Restarting in 5s...")
                SENTINEL_PATH.unlink(missing_ok=True)
                time.sleep(5)
    else:
        raise NerpyInfraException("Bot config not found.")


BANNER = """
'##::: ##:'########:'########::'########::'##:::'##::::'########:::'#######::'########:
 ###:: ##: ##.....:: ##.... ##: ##.... ##:. ##:'##::::: ##.... ##:'##.... ##:... ##..::
 ####: ##: ##::::::: ##:::: ##: ##:::: ##::. ####:::::: ##:::: ##: ##:::: ##:::: ##::::
 ## ## ##: ######::: ########:: ########::::. ##::::::: ########:: ##:::: ##:::: ##::::
 ##. ####: ##...:::: ##.. ##::: ##.....:::::: ##::::::: ##.... ##: ##:::: ##:::: ##::::
 ##:. ###: ##::::::: ##::. ##:: ##::::::::::: ##::::::: ##:::: ##: ##:::: ##:::: ##::::
 ##::. ##: ########: ##:::. ##: ##::::::::::: ##::::::: ########::. #######::::: ##::::
..::::..::........::..:::::..::..::::::::::::..::::::::........::::.......::::::..:::::
"""

if __name__ == "__main__":
    app()
