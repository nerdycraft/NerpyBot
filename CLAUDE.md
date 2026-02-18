# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NerpyBot is a Discord bot built with discord.py using the Cog extension system. It provides gaming integrations (WoW, League of Legends), entertainment, and moderation.

## Development Commands

**Always use `uv run` to execute Python, pytest, ruff, and other tools** — this project is uv-managed and all dependencies live in uv's virtual environment.

```bash
# Install dependencies
uv sync                              # All bot dependencies (default)
uv sync --group test                 # Include test dependencies
uv sync --only-group migrations      # Migration tools only

# Run the bot
uv run nerpybot                             # Start with default config
uv run nerpybot -d                          # Debug logging (no sqlalchemy noise)
uv run nerpybot -l DEBUG                    # Debug mode (includes sqlalchemy)
uv run nerpybot -c path                     # Custom config file
uv run nerpybot -r                          # Auto-restart on failure

# Code quality
uv run ruff check                    # Lint
uv run ruff check --fix              # Lint with auto-fix
uv run ruff format                   # Format code
uv run ruff format --check           # Check formatting only

# Testing
uv run pytest                        # Run tests
uv run pytest --cov                  # With coverage

# Database migrations (two separate configs: nerpybot and humanmusic)
uv sync --group migrations
uv run alembic-nerpybot upgrade head                              # Apply NerpyBot migrations
uv run alembic-nerpybot revision --autogenerate -m "description"  # Create NerpyBot migration
uv run alembic-humanmusic upgrade head                            # Apply HumanMusic migrations
uv run alembic-humanmusic revision --autogenerate -m "description" # Create HumanMusic migration
# NOTE: New tables do NOT need migrations — SQLAlchemy auto-creates missing tables at startup.
# Only create migrations when altering existing tables (add/remove columns, change constraints).
# When adding columns to existing tables, use server_default (not just ORM default) so existing rows get a value.
# NerpyBot migrations: for tables used by all modules (full deployment)
# HumanMusic migrations: only for tables shared by admin, voicecontrol, and music modules

# Docker builds (two targets)
docker buildx build --target bot -t nerpybot .
docker buildx build --target migrations -t nerpybot-migrations .

# Validate GitHub Actions workflows
actionlint .github/workflows/*.yml

# Run CI locally with act (requires Docker)
act pull_request -W .github/workflows/test.yml --container-architecture linux/amd64

# Format markdown and YAML files
prettier --write "docs/**/*.md" "**/*.yaml" "**/*.yml" "*.md"

# Docker smoke tests (run locally to verify images work)
docker run --rm nerpybot python -c "from NerdyPy import NerpyBot; print('OK')"
docker run --rm nerpybot-migrations alembic -c alembic-nerpybot.ini heads
docker run --rm -e ALEMBIC_CONFIG=alembic-humanmusic.ini nerpybot-migrations alembic -c alembic-humanmusic.ini heads
```

## Architecture

### Documentation

`docs/` contains per-module markdown files documenting commands, database models, background tasks, and data flows. When adding a new module or changing an existing one, update or create the corresponding `docs/<module>.md` file.

### Entry Point

`NerdyPy/NerdyPy.py` - Contains `NerpyBot` class and `main()` entry point. `cli.py` at project root provides `project.scripts` console entry points (`nerpybot`, `alembic-nerpybot`, `alembic-humanmusic`).

### Module System

Modules live in `NerdyPy/modules/` as discord.py Cogs. They're loaded dynamically based on `config.yaml`:

- **admin** - Server management, moderator role config, command sync (always auto-loaded)
- **league** - Riot API integration
- **leavemsg** - Custom leave messages when members depart
- **moderation** - Server moderation tools
- **music** - Voice channel audio playback
- **raidplaner** - Guild raid scheduling (largest module)
- **reactionrole** - Reaction-based role assignment
- **reminder** - Timed user reminders
- **rolemanage** - Delegated role management (lets specific roles assign other roles via mappings)
- **tagging** - Audio tag management
- **voicecontrol** - Voice stop/leave commands (auto-loaded when tagging or music is enabled)
- **wow** - Blizzard API integration

### Database Layer

- `NerdyPy/models/` - SQLAlchemy ORM models
- `NerdyPy/utils/database.py` - Session management with context managers
- `database-migrations/` - Alembic migrations (separate version dirs for `nerpybot/` and `humanmusic/`)
- Supports SQLite (default), MySQL/MariaDB, PostgreSQL

### Utilities

`NerdyPy/utils/` contains:

- `audio.py` - Voice channel audio management
- `checks.py` - Permission check functions for voice/moderator commands
- `conversation.py` - Interactive dialog state management
- `errors.py` - `NerpyException` for bot-specific errors
- `format.py` - Text formatting helpers
- `helpers.py` - General utilities (incl. `send_hidden_message` for ephemeral responses via Interaction)
- `download.py` - Audio downloading and ffmpeg conversion (yt-dlp)
- `logging.py` - Dual-handler log setup (stdout for INFO/DEBUG, stderr for WARNING+)
- `permissions.py` - Per-module bot permission requirements map and guild-level permission audit helpers

### Gotchas

- **NerdyPy uses script-relative imports** — Internal imports like `from models.admin import ...` assume `NerdyPy/` is on `sys.path`. Entry points or external callers must add it to `sys.path` before importing (see `cli.py:bot()`).
- **SQLite strips timezone info from DateTime columns** — Values read back are naive. Normalize with `.replace(tzinfo=UTC)` before comparing against aware datetimes.
- **`blizzapi` does NOT auto-retry on 429** — It returns `{"code": 429}` as a dict. Check every response and handle rate limits manually.
- **`send_hidden_message()` accepts Interaction** — It only handles `discord.Interaction` objects, using `response.send_message` or `followup.send` based on `is_done()`. Prefix commands use `ctx.send()` directly.
- **`sync` is prefix-only** — DM-only operator command (`!sync`). Supports global sync, guild-specific sync via `Greedy[Object]`, and `local`/`copy`/`clear` spec modes.
- **raidplaner remains prefix-only** — Uses interactive DM conversations that require message-based back-and-forth (`conversation.py` utilities).
- **Check functions accept Interaction, not Context** — All check functions in `checks.py` were converted to accept `discord.Interaction` for slash command compatibility. The `interaction_check` in admin.py uses these. The `cog_check` in admin.py has inline logic for prefix commands.
- **admin.py modrole and botpermissions are guild_only** — The `app_commands.Group` definitions have `guild_only=True` to prevent DM invocation, since they access `interaction.guild` unconditionally.
- **`@app_commands.guild_only()` on regular `Cog` does NOT propagate to commands** — discord.py's `Command.__init__` reads `guild_only` from the callback function, not the class. Only `GroupCog` propagates the class attribute via `Group.__init__`. For regular `Cog` classes, add `@app_commands.guild_only()` to each individual command and `guild_only=True` to each `Group()` definition.

## Configuration

Copy `NerdyPy/config.yaml.template` to `NerdyPy/config.yaml` and fill in:

- Discord bot token and client ID
- Operator user IDs (bot admins)
- Database connection settings
- API keys for external services (Riot, Blizzard, YouTube, etc.)

## Code Style

- **Line length**: 120 characters
- **Formatter**: Ruff
- **Markdown/YAML**: Prettier (run `prettier --write` on `.md`, `.yml`, `.yaml` files)
- **Line endings**: LF
- CI enforces `ruff check` and `ruff format --check` on PRs

## Git

- **Co-Authored-By**: `Co-Authored-By: Claude <noreply@anthropic.com>` (this is a GitHub repo)
- **`docs/plans/`** is gitignored — never stage or commit plan files
