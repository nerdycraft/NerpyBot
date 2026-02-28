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
uv run python NerdyPy/bot.py                    # Start with default config
uv run python NerdyPy/bot.py -d                 # Debug logging (no sqlalchemy noise)
uv run python NerdyPy/bot.py --verbosity 3      # Max verbosity (includes sqlalchemy)
uv run python NerdyPy/bot.py -c path             # Custom config file
uv run python NerdyPy/bot.py -r                  # Auto-restart on failure

# Git hooks (run once after cloning)
uv sync --group test                 # Installs pre-commit
uv run pre-commit install            # Wires up .pre-commit-config.yaml into .git/hooks

# Code quality (also run automatically on commit via pre-commit)
uv run ruff check                    # Lint
uv run ruff check --fix              # Lint with auto-fix
uv run ruff format                   # Format code
uv run ruff format --check           # Check formatting only

# Testing
uv run python -m pytest              # Run tests
uv run python -m pytest --cov        # With coverage

# Database migrations
uv sync --group migrations
uv run alembic upgrade head                              # Apply migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
# NOTE: New tables do NOT need migrations — SQLAlchemy auto-creates missing tables at startup.
# Only create migrations when altering existing tables (add/remove columns, change constraints).
# When adding columns to existing tables, use server_default (not just ORM default) so existing rows get a value.

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
docker run --rm nerpybot python -c "from bot import NerpyBot; print('OK')"
docker run --rm nerpybot-migrations alembic heads  # uses alembic.ini (default)
```

## Architecture

### Documentation

`docs/` contains per-module markdown files documenting commands, database models, background tasks, and data flows. When adding a new module or changing an existing one, update or create the corresponding `docs/<module>.md` file.

### Entry Point

`NerdyPy/bot.py` - Contains `NerpyBot` class and `main()` entry point.

### Module System

Modules live in `NerdyPy/modules/` as discord.py Cogs. They're loaded dynamically based on `config.yaml`:

- **admin** - Server management, moderator role config, language preference, command sync (always auto-loaded)
- **application** - Custom application/form system with DM conversations and button-based review
- **league** - Riot API integration
- **leavemsg** - Custom leave messages when members depart
- **moderation** - Server moderation tools
- **music** - Voice channel audio playback
- **reactionrole** - Reaction-based role assignment
- **reminder** - Timed user reminders
- **rolemanage** - Delegated role management (lets specific roles assign other roles via mappings)
- **tagging** - Audio tag management
- **voicecontrol** - Voice stop/leave commands (auto-loaded when tagging or music is enabled)
- **wow** - Blizzard API integration (armory lookup, guild news tracking, crafting order board)

### Database Layer

- `NerdyPy/models/` - SQLAlchemy ORM models
- `NerdyPy/utils/database.py` - Session management with context managers
- `database-migrations/` - Alembic migrations
- Supports SQLite (default) and PostgreSQL

### Utilities

`NerdyPy/utils/` contains:

- `audio.py` - Voice channel audio management
- `checks.py` - Permission check functions for voice/moderator commands
- `conversation.py` - Interactive dialog state management
- `errors.py` - Exception hierarchy: `NerpyException` (base) → `NerpyUserException` → `{NerpyNotFoundError, NerpyValidationError, NerpyPermissionError}`; `NerpyInfraException` (infrastructure failures — triggers operator DM notification)
- `format.py` - Text formatting helpers
- `helpers.py` - General utilities (incl. `send_hidden_message` for ephemeral responses via Interaction)
- `download.py` - Audio downloading and ffmpeg conversion (yt-dlp)
- `logging.py` - Dual-handler log setup (stdout for INFO/DEBUG, stderr for WARNING+)
- `permissions.py` - Per-module bot permission requirements map and guild-level permission audit helpers
- `duration.py` - `parse_duration()` for human-friendly duration strings (`2h30m`, `1d12h`, `1w`); wraps `pytimeparse2`
- `schedule.py` - `compute_next_fire()` for DST-aware next-fire-time computation (interval/daily/weekly/monthly)
- `strings.py` - Localized string lookup: `load_strings()` at startup, `get_string(lang, key, **kwargs)` for templates, `get_guild_language(guild_id, session)` for DB lookup, `get_localized_string(guild_id, key, session, **kwargs)` convenience wrapper

### Gotchas

- **NerdyPy uses script-relative imports** — Internal imports like `from models.admin import ...` assume `NerdyPy/` is on `sys.path`.
- **SQLite strips timezone info from DateTime columns** — Values read back are naive. Normalize with `.replace(tzinfo=UTC)` before comparing against aware datetimes.
- **`blizzapi` does NOT auto-retry on 429** — It returns `{"code": 429}` as a dict. Check every response and handle rate limits manually.
- **`send_hidden_message()` accepts Interaction** — It only handles `discord.Interaction` objects, using `response.send_message` or `followup.send` based on `is_done()`. Prefix commands use `ctx.send()` directly.
- **`sync` is prefix-only** — DM-only operator command (`!sync`). Supports global sync, guild-specific sync via `Greedy[Object]`, and `local`/`copy`/`clear` spec modes.
- **Check functions accept Interaction, not Context** — All check functions in `checks.py` were converted to accept `discord.Interaction` for slash command compatibility. The `interaction_check` in admin.py uses these. The `cog_check` in admin.py has inline logic for prefix commands.
- **admin.py modrole and botpermissions are guild_only** — The `app_commands.Group` definitions have `guild_only=True` to prevent DM invocation, since they access `interaction.guild` unconditionally.
- **`@app_commands.guild_only()` on regular `Cog` does NOT propagate to commands** — discord.py's `Command.__init__` reads `guild_only` from the callback function, not the class. Only `GroupCog` propagates the class attribute via `Group.__init__`. The remaining regular `Cog` classes (`admin`, `voicecontrol`) need `@app_commands.guild_only()` on each individual command and `guild_only=True` on each `Group()` definition. Never pass `guild_only=True` to `app_commands.Command(name=..., callback=...)` directly — it raises `TypeError: Command.__init__() got an unexpected keyword argument 'guild_only'`.
- **`docs/plans/` is gitignored** — Design docs and implementation plans live there but are NOT committed.
- **Testing `@app_commands.command()` methods** — Call `.callback(cog, interaction, ...)` to bypass discord.py decorator machinery. See `tests/modules/test_reminder.py` for the pattern.
- **Tests using new locale keys need `load_strings()` reload** — The localization cache is populated once per process. Test classes exercising newly added YAML keys must include `@pytest.fixture(autouse=True) def _load_locale_strings(self): load_strings()` to refresh the cache. See `TestTemplateView` in `test_application.py`.
- **`@app_commands.rename` for cleaner Discord param names** — Use `@app_commands.rename(python_name="discord_name")` whenever the Discord-facing name should differ from the Python identifier: required when the name is a keyword (e.g. `in`), and useful for readability (e.g. `form_name` → `form`). `describe`, `autocomplete`, and all internal references keep using the Python name.
- **Alembic migrations must be dialect-aware** — SQLite uses `datetime()`, PostgreSQL uses `make_interval()`. Use `op.get_bind().dialect.name` to branch. Always use `batch_alter_table` for SQLite column operations. Note: `op.alter_column()` **without** a `batch_alter_table` context crashes on SQLite — and type-only encoding migrations (e.g. `Text` → `UnicodeText`) can skip SQLite entirely since it stores all text as Unicode internally.
- **All Alembic migrations must guard column/index existence, not just table existence** — `create_all()` on a fresh install already builds the latest schema; a subsequent `alembic upgrade head` must be a no-op. Before `add_column`, check `{c["name"] for c in inspect(conn).get_columns(table)}`; before `create_index`, check `{i["name"] for i in inspect(conn).get_indexes(table)}`. The return-early guard must cover both the "table absent" and "schema already current" cases.
- **`interaction.response.is_done()` returns `False` after a failed `send_message()`** — If `send_message()` raises (e.g. 10062 Unknown interaction), `is_done()` is still `False`. In `_on_app_command_error`, wrap the user-facing response in `try/except` _before_ `notify_error`, or `notify_error` will never be reached.
- **`pyproject.toml` requires `packages = []`** — Without `[tool.setuptools] packages = []`, setuptools auto-discovers `config/` and `NerdyPy/` as a flat-layout conflict, breaking all `uv` commands.
- **`cog_load` runs before `create_all()`** — `setup_hook` calls `load_extension()` (triggering `cog_load`) before `create_all()`. If a cog accesses new tables in `cog_load`, call `self.bot.create_all()` at the top of `cog_load` to ensure tables exist on existing databases.
- **SQLite enforces unique constraints row-by-row, not deferred** — Swapping two values under a unique column in a single flush raises `IntegrityError`. Use a two-phase update: write temporary/offset values and flush, then write final values and flush.
- **Module-specific permission helpers stay with the module** — Only move a permission check to `utils/checks.py` if it is purely based on Discord roles/permissions. If it queries a module-specific table (e.g. `ApplicationGuildConfig`), keep it in the module's own file.
- **Cannot `send_modal()` after `defer()`** — Once `interaction.response.defer()` is called, `send_modal()` will raise. Design around this: if a button defers (e.g. to show a spinner), any follow-up that needs a modal must be a separate button/action.
- **Exception narrowing conventions** — Use `SQLAlchemyError` (from `sqlalchemy.exc`) for ops inside `session_scope()`, `discord.HTTPException` for Discord API calls (fetch, edit, send to channels), and `(discord.Forbidden, discord.NotFound)` for user DM attempts.
- **Pre-filling `discord.ui.Modal` fields** — Set `self.<field>.default = value` as an instance attribute in `__init__()` after `super().__init__()`. The class-level `TextInput` definition only sets the layout; instance-level assignment provides the pre-filled value.
- **Localization strings vs user-defined templates** — `get_string()` only processes bot-authored strings from `NerdyPy/locales/lang_*.yaml`. User-defined content (leave messages, custom tags) must never pass through `get_string()` — format them at the call site instead.
- **Adding a new language** — Create `NerdyPy/locales/lang_<code>.yaml`, restart the bot. No code changes needed. English keys are canonical — any missing key in other languages falls back to English automatically.
- **Guild language is global** — `GuildLanguageConfig` is the single source of truth for a guild's language preference. Modules calling external APIs (Blizzard, Riot) should honor this setting when the API supports it, falling back to English otherwise.
- **Full env var config** — All config keys can be set via `NERPYBOT_*` environment variables (see `docker-compose.yml` for the full list). Env vars take priority over `config.yaml` when both are present. Lists (`modules`, `ops`, `error_recipients`) use comma-separated values.

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
