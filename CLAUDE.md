# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NerpyBot is a Discord bot built with discord.py using the Cog extension system. It provides gaming integrations (WoW, League of Legends), entertainment, moderation, and utility features.

## Development Commands

```bash
# Install dependencies
uv sync                              # All bot dependencies (default)
uv sync --group test                 # Include test dependencies
uv sync --only-group migrations      # Migration tools only

# Run the bot
python NerdyPy/NerdyPy.py            # Start with default config
python NerdyPy/NerdyPy.py -l DEBUG   # Debug mode
python NerdyPy/NerdyPy.py -c path    # Custom config file
python NerdyPy/NerdyPy.py -r         # Auto-restart on failure

# Code quality
ruff check                           # Lint
ruff check --fix                     # Lint with auto-fix
ruff format                          # Format code
ruff format --check                  # Check formatting only

# Testing
pytest                               # Run tests
pytest --cov                         # With coverage

# Database migrations
uv sync --group migrations
uv run alembic upgrade head                              # Apply migrations
uv run alembic revision --autogenerate -m "description"  # Create migration

# Docker builds (two targets)
docker buildx build --target bot -t nerpybot .
docker buildx build --target migrations -t nerpybot-migrations .
```

## Architecture

### Entry Point
`NerdyPy/NerdyPy.py` - Contains `NerpyBot` class extending discord.py's `Bot`. Handles module loading, database initialization, and event routing.

### Module System
Modules live in `NerdyPy/modules/` as discord.py Cogs. They're loaded dynamically based on `config.yaml`:

- **admin** - Server management, prefix config, command sync
- **fun** - Entertainment commands
- **league** - Riot API integration
- **moderation** - Server moderation tools
- **music** - Voice channel audio playback
- **raidplaner** - Guild raid scheduling (largest module)
- **random** - Random generators
- **reminder** - Timed user reminders
- **search** - Multi-source search (Imgur, Genius, OMDB, IGDB, YouTube)
- **tagging** - Audio tag management
- **utility** - Weather, info commands
- **wow** - Blizzard API integration

### Database Layer
- `NerdyPy/models/` - SQLAlchemy ORM models
- `NerdyPy/utils/database.py` - Session management with context managers
- `database-migrations/` - Alembic migrations
- Supports SQLite (default), MySQL/MariaDB, PostgreSQL

### Utilities
`NerdyPy/utils/` contains:
- `audio.py` - Voice channel audio management
- `checks.py` - Permission decorators
- `conversation.py` - Interactive dialog state management
- `errors.py` - `NerpyException` for bot-specific errors
- `format.py` - Text formatting helpers
- `helpers.py` - General utilities

## Configuration

Copy `NerdyPy/config.yaml.template` to `NerdyPy/config.yaml` and fill in:
- Discord bot token and client ID
- Operator user IDs (bot admins)
- Database connection settings
- API keys for external services (Riot, Blizzard, YouTube, etc.)

## Code Style

- **Line length**: 120 characters
- **Formatter**: Ruff
- **Line endings**: LF
- CI enforces `ruff check` and `ruff format --check` on PRs
