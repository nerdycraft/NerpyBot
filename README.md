# NerpyBot

The nerdiest Discord bot! Built with [discord.py](https://discordpy.readthedocs.io/) using the Cog extension system. Provides gaming integrations (WoW, League of Legends), entertainment, moderation, music playback, and utility features.

## Quickstart (Local Development)

```bash
# Install dependencies
uv sync

# Copy and edit configuration
cp NerdyPy/config.yaml.template NerdyPy/config.yaml
# Fill in your Discord bot token, client ID, and API keys

# Start the bot
python NerdyPy/NerdyPy.py

# Debug mode
python NerdyPy/NerdyPy.py -l DEBUG
```

## Docker Compose

The recommended way to run NerpyBot in production. The compose setup runs two bot instances (NerpyBot and HumanMusic) with automatic database migrations.

### Setup

```bash
# Create config files from examples
cp config/nerpybot.yaml.example config/nerpybot.yaml
cp config/humanmusic.yaml.example config/humanmusic.yaml

# Edit both files with your Discord tokens and API keys
```

### Run

```bash
# Start all services (pulls images from GHCR)
docker compose up -d

# View logs
docker compose logs -f nerpybot
docker compose logs -f humanmusic

# Stop
docker compose down
```

Migration containers run automatically before each bot starts, applying any pending database schema changes.

### Building Locally

To build from source instead of pulling pre-built images:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### Using an External Database

To use MariaDB/MySQL instead of SQLite, update your config file:

```yaml
database:
  db_type: mariadb
  db_name: nerpybot
  db_username: bot_user
  db_password: your_password
  db_host: db_host
  db_port: 3306
```

Supported databases: SQLite (default), MariaDB/MySQL, PostgreSQL. For other databases, specify the type with its driver (e.g., `postgresql+psycopg2`).

## Database Migrations

Migrations are managed with [Alembic](https://alembic.sqlalchemy.org/) and run automatically in Docker Compose. For manual usage:

```bash
# Install migration dependencies
uv sync --only-group migrations

# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "description"
```

The migration runner resolves the database URL in this order:

1. `DATABASE_URL` environment variable
2. Bot `config.yaml` (path overridable via `BOT_CONFIG` env var)
3. `alembic.ini` default (`sqlite:///NerdyPy/db.db`)

## Modules

| Module | Description |
|--------|-------------|
| admin | Server management, prefix configuration, command sync |
| fun | Entertainment commands |
| league | Riot Games API integration |
| leavemsg | Server leave message announcements |
| moderation | Server moderation tools |
| music | Voice channel audio playback |
| raidplaner | Guild raid scheduling |
| random | Random generators |
| reminder | Timed user reminders |
| search | Multi-source search (Imgur, Genius, OMDB, IGDB, YouTube) |
| tagging | Audio tag management |
| utility | Weather, info commands |
| wow | Blizzard API integration |

Enable modules by listing them in the `bot.modules` section of your config file.

## Configuration

Copy `NerdyPy/config.yaml.template` (local dev) or `config/*.yaml.example` (Docker) and fill in:

- **bot.client_id** / **bot.token** — from the [Discord Developer Portal](https://discord.com/developers/applications)
- **bot.ops** — Discord user IDs with bot admin privileges
- **bot.modules** — list of modules to load
- **database** — connection settings (see [External Database](#using-an-external-database))
- **search** / **league** / **wow** / **utility** — API keys for respective services

## Development

```bash
# Lint
ruff check

# Lint with auto-fix
ruff check --fix

# Format
ruff format

# Run tests
pytest

# Run tests with coverage
pytest --cov
```

## Docker Builds

The Dockerfile provides two targets:

```bash
# Bot image
docker buildx build --target bot -t nerpybot .

# Migrations image
docker buildx build --target migrations -t nerpybot-migrations .
```

## Bot Invite Links

- **NerpyBot** — [Invite](https://discord.com/api/oauth2/authorize?client_id=246941850223640576&permissions=582632143842386&scope=applications.commands+bot)
- **HumanMusic** — [Invite](https://discord.com/api/oauth2/authorize?client_id=883656077357510697&permissions=414467959360&scope=applications.commands+bot)

## License

[GPL-3.0-or-later](LICENSE)
