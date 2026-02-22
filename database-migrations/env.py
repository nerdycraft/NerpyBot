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

    is_mysql = any(s in db_type for s in ("mysql", "mariadb"))
    is_postgres = "postgresql" in db_type

    if is_mysql:
        db_type = f"{db_type}+pymysql"
    elif is_postgres:
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


def _resolve_database_url() -> str | None:
    """Resolve the database URL with priority: DATABASE_URL env > bot config.yaml > alembic.ini default."""
    # 1. Explicit env var override
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # 2. Bot config.yaml (works in Docker where config is mounted)
    config_path = Path(os.environ.get("BOT_CONFIG", "config.yaml"))
    if config_path.exists():
        with open(config_path) as f:
            bot_config = yaml.safe_load(f)
        if bot_config:
            return _build_url_from_bot_config(bot_config)

    # 3. Fall back to alembic.ini default
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
