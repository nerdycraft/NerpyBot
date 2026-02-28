import os
from logging.config import fileConfig
from pathlib import Path

import yaml

# noinspection PyUnresolvedReferences
from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _build_url_from_bot_config(bot_config: dict) -> str | None:
    """Build a SQLAlchemy URL from the bot's config.yaml database section.

    Mirrors the URL construction logic in bot.py.
    """
    database_config = bot_config.get("database")
    if not database_config:
        return None

    db_type = database_config["db_type"]
    db_name = database_config["db_name"]
    db_username = ""
    db_password = ""
    db_host = ""
    db_port = ""

    if "postgresql" in db_type:
        db_type = f"{db_type}+psycopg"

    if database_config.get("db_password"):
        db_password = f":{database_config['db_password']}"
    if database_config.get("db_username"):
        db_username = database_config["db_username"]
    if database_config.get("db_host"):
        db_host = f"@{database_config['db_host']}"
    if database_config.get("db_port"):
        db_port = f":{database_config['db_port']}"

    db_authentication = f"{db_username}{db_password}{db_host}{db_port}"
    return f"{db_type}://{db_authentication}/{db_name}"


def _build_url_from_nerpybot_env() -> str | None:
    """Build a SQLAlchemy URL from NERPYBOT_DB_* environment variables."""
    db_type = os.environ.get("NERPYBOT_DB_TYPE")
    if not db_type:
        return None

    db_name = os.environ.get("NERPYBOT_DB_NAME", "db.db")
    db_username = os.environ.get("NERPYBOT_DB_USERNAME", "")
    db_password = os.environ.get("NERPYBOT_DB_PASSWORD", "")
    db_host = os.environ.get("NERPYBOT_DB_HOST", "")
    db_port = os.environ.get("NERPYBOT_DB_PORT", "")

    if "postgresql" in db_type:
        db_type = f"{db_type}+psycopg"

    if db_password:
        db_password = f":{db_password}"
    if db_host:
        db_host = f"@{db_host}"
    if db_port:
        db_port = f":{db_port}"

    auth = f"{db_username}{db_password}{db_host}{db_port}"
    return f"{db_type}://{auth}/{db_name}"


def _resolve_database_url() -> str | None:
    """Resolve the database URL.

    Priority: DATABASE_URL env > NERPYBOT_DB_* env vars > bot config.yaml > alembic.ini default.
    """
    # 1. Explicit DATABASE_URL override
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # 2. NERPYBOT_DB_* env vars
    nerpybot_url = _build_url_from_nerpybot_env()
    if nerpybot_url:
        return nerpybot_url

    # 3. Bot config.yaml (works in local dev where config is present)
    config_path = Path(os.environ.get("BOT_CONFIG", "config.yaml"))
    if config_path.exists():
        with open(config_path) as f:
            bot_config = yaml.safe_load(f)
        if bot_config:
            return _build_url_from_bot_config(bot_config)

    # 4. Fall back to alembic.ini default
    return None


# Override sqlalchemy.url if we resolved one from env/config
resolved_url = _resolve_database_url()
if resolved_url:
    config.set_main_option("sqlalchemy.url", resolved_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
