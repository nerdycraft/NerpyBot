# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NerpyBot is a Discord bot built with discord.py using the Cog extension system. It provides gaming integrations (WoW, League of Legends), entertainment, moderation, and utility features.

## Development Commands

**Always use `uv run` to execute Python, pytest, ruff, and other tools** — this project is uv-managed and all dependencies live in uv's virtual environment.

```bash
# Install dependencies
uv sync                              # All bot dependencies (default)
uv sync --group test                 # Include test dependencies
uv sync --only-group migrations      # Migration tools only

# Run the bot
uv run python NerdyPy/NerdyPy.py            # Start with default config
uv run python NerdyPy/NerdyPy.py -d         # Debug logging (no sqlalchemy noise)
uv run python NerdyPy/NerdyPy.py -l DEBUG   # Debug mode (includes sqlalchemy)
uv run python NerdyPy/NerdyPy.py -c path    # Custom config file
uv run python NerdyPy/NerdyPy.py -r         # Auto-restart on failure

# Code quality
uv run ruff check                    # Lint
uv run ruff check --fix              # Lint with auto-fix
uv run ruff format                   # Format code
uv run ruff format --check           # Check formatting only

# Testing
uv run pytest                        # Run tests
uv run pytest --cov                  # With coverage

# Database migrations
uv sync --group migrations
uv run alembic upgrade head                              # Apply migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
# NOTE: New tables do NOT need migrations — SQLAlchemy auto-creates missing tables at startup.
# Only create migrations when altering existing tables (add/remove columns, change constraints).

# Docker builds (two targets)
docker buildx build --target bot -t nerpybot .
docker buildx build --target migrations -t nerpybot-migrations .
```

## Architecture

### Documentation
`docs/` contains per-module markdown files documenting commands, database models, background tasks, and data flows. When adding a new module or changing an existing one, update or create the corresponding `docs/<module>.md` file.

### Entry Point
`NerdyPy/NerdyPy.py` - Contains `NerpyBot` class extending discord.py's `Bot`. Handles module loading, database initialization, and event routing.

### Module System
Modules live in `NerdyPy/modules/` as discord.py Cogs. They're loaded dynamically based on `config.yaml`:

- **admin** - Server management, prefix config, command sync
- **fun** - Entertainment commands
- **league** - Riot API integration
- **leavemsg** - Custom leave messages when members depart
- **moderation** - Server moderation tools
- **music** - Voice channel audio playback
- **raidplaner** - Guild raid scheduling (largest module)
- **random** - Random generators
- **reactionrole** - Reaction-based role assignment
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
- `checks.py` - Permission check functions for voice/moderator commands
- `conversation.py` - Interactive dialog state management
- `errors.py` - `NerpyException` for bot-specific errors
- `format.py` - Text formatting helpers
- `helpers.py` - General utilities (incl. `send_hidden_message` for ephemeral/DM responses)
- `download.py` - Audio downloading and ffmpeg conversion (yt-dlp)
- `logging.py` - Dual-handler log setup (stdout for INFO/DEBUG, stderr for WARNING+)

### Gotchas

- **SQLite strips timezone info from DateTime columns** — Values read back are naive. Normalize with `.replace(tzinfo=UTC)` before comparing against aware datetimes.
- **`blizzapi` does NOT auto-retry on 429** — It returns `{"code": 429}` as a dict. Check every response and handle rate limits manually.
- **`app_commands.checks` only gates slash commands** — Cog-level `@checks.has_permissions()` from `discord.app_commands` does NOT apply to prefix commands. A global `guild_only` check in `setup_hook` protects prefix commands from DM invocation.
- **`ephemeral=True` is silently ignored on prefix commands** — Always use `send_hidden_message()` from `utils/helpers.py` which falls back to DMs for prefix contexts.
- **Check functions must be side-effect-free during help** — `DefaultHelpCommand` calls `can_run()` on every command. Check functions in `checks.py` guard against this with `ctx.invoked_with == "help"`.

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
