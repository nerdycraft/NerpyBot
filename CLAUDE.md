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

# Run the bot
uv run python NerdyPy/bot.py                    # Start with default config
uv run python NerdyPy/bot.py -d                 # Debug logging (no sqlalchemy noise)
uv run python NerdyPy/bot.py --verbosity 1      # DEBUG (bot only)
uv run python NerdyPy/bot.py --verbosity 2      # DEBUG + discord.py verbose
uv run python NerdyPy/bot.py --verbosity 3      # DEBUG + discord.py + sqlalchemy
uv run python NerdyPy/bot.py -c path             # Custom config file
uv run python NerdyPy/bot.py -V                  # Show version and exit

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

# Frontend — run before committing any web/ changes
npm run build --prefix web/frontend  # vue-tsc type-check + vite build

# Database migrations (alembic is now part of the bot dependency group)
uv run alembic upgrade head                              # Apply migrations manually
uv run alembic revision --autogenerate -m "description"  # Create a new migration
# NOTE: New tables do NOT need migrations — SQLAlchemy auto-creates missing tables at startup.
# Only create migrations when altering existing tables (add/remove columns, change constraints).
# When adding columns to existing tables, use server_default (not just ORM default) so existing rows get a value.

# Worktrees: always pass path explicitly — never cd && uv run
uv run --directory .worktrees/<branch> python -m pytest

# Docker builds
docker buildx build --target bot --build-arg VERSION=0.6.0 -t nerpybot .

# Validate GitHub Actions workflows
actionlint .github/workflows/*.yml

# Run CI locally with act (requires Docker)
act pull_request -W .github/workflows/test.yml --container-architecture linux/amd64

# Format markdown and YAML files
prettier --write "docs/**/*.md" "**/*.yaml" "**/*.yml" "*.md"

# Docker smoke tests (run locally to verify images work)
docker run --rm nerpybot python -c "from bot import NerpyBot; print('OK')"
```

## Architecture

### Documentation

`docs/` contains per-module markdown files documenting commands, database models, background tasks, and data flows. When adding a new module or changing an existing one, update or create the corresponding `docs/<module>.md` file.

For release procedures (tagging, release branches, hotfixes), see `docs/release-process.md`.

### Entry Point

`NerdyPy/bot.py` - Contains `NerpyBot` class and `main()` entry point.

### Module System

Modules live in `NerdyPy/modules/` as discord.py Cogs. They're loaded dynamically based on `config.yaml`:

- **server_admin** - Modrole config and language preference (always auto-loaded)
- **operator** - Bot operator commands: botpermissions, ping, sync, debug, uptime, errors, disable/enable (always auto-loaded)
- **application** - Custom application/form system with DM conversations and button-based review
- **league** - Riot API integration
- **moderation** - Server moderation tools including leave messages (`/moderation leavemsg`)
- **music** - Voice channel audio playback
- **reminder** - Timed user reminders
- **roles** - Delegated role management (`/rolemanage`) and reaction-based role assignment (`/reactionrole`)
- **tagging** - Audio tag management
- **voicecontrol** - Voice stop/leave commands (auto-loaded when tagging or music is enabled)
- **wow** - Blizzard API integration (armory lookup, guild news tracking, crafting order board)

### Database Layer

- `NerdyPy/models/` - SQLAlchemy ORM models
- `NerdyPy/utils/database.py` - Session management with context managers
- `database-migrations/` - Alembic migrations
- Supports SQLite (default) and PostgreSQL

### Web Component

`web/` contains a FastAPI application (`web/app.py`) with JWT auth (`web/auth/`), API routes (`web/routes/`), schemas (`web/schemas.py`), and a Vue frontend (`web/frontend/`). Configuration is separate from the bot — see `webapp.env`.

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
- **`send_hidden_message()` accepts Interaction and swallows send errors** — Uses `response.send_message`/`followup.send` based on `is_done()`, wrapped in try/except so send failures never interrupt post-send logic (error recording, operator DMs). Prefix commands use `ctx.send()` directly.
- **`sync` is prefix-only** — DM-only operator command (`!sync`). Supports global sync, guild-specific sync via `Greedy[Object]`, and `local`/`copy`/`clear` spec modes.
- **Check functions accept Interaction, not Context** — All check functions in `checks.py` were converted to accept `discord.Interaction` for slash command compatibility. The `interaction_check` in admin.py uses these. The `cog_check` in admin.py has inline logic for prefix commands.
- **admin.py modrole and botpermissions are guild_only** — The `app_commands.Group` definitions have `guild_only=True` to prevent DM invocation, since they access `interaction.guild` unconditionally.
- **`@app_commands.guild_only()` on regular `Cog` does NOT propagate to commands** — discord.py's `Command.__init__` reads `guild_only` from the callback function, not the class. Only `GroupCog` propagates the class attribute via `Group.__init__`. The remaining regular `Cog` classes (`admin`, `voicecontrol`) need `@app_commands.guild_only()` on each individual command and `guild_only=True` on each `Group()` definition. Never pass `guild_only=True` to `app_commands.Command(name=..., callback=...)` directly — it raises `TypeError: Command.__init__() got an unexpected keyword argument 'guild_only'`.
- **`docs/plans/` is gitignored** — Design docs and implementation plans live there but are NOT committed.
- **Testing `@app_commands.command()` methods** — Call `.callback(cog, interaction, ...)` to bypass discord.py decorator machinery. See `tests/modules/test_reminder.py` for the pattern.
- **Testing `app_commands.Group` subcommands** — Access via `Group._children["subcommand_name"].callback(cog, interaction, ...)`. Example: `Music.playlist._children["create"].callback(cog, interaction, name="x")`.
- **`discord.ui.View(timeout=None)` for persistent buttons** — Default timeout is ~3 minutes; buttons on long-lived embeds (e.g. now-playing) silently stop working after timeout. Pass `timeout=None` in `super().__init__()`.
- **`session_scope()` + `await` ordering** — Place `await interaction.followup.send(...)` calls _outside_ the `with self.bot.session_scope()` block to avoid holding the DB connection open during HTTP calls. A bare `return` inside the `with` is safe — `__exit__` still commits/closes.
- **`VoiceChannel.send()` for embeds that outlast an interaction** — Interaction tokens expire after 15 minutes; posting an embed directly to `song.channel` (a `VoiceChannel`) via `channel.send(embed=emb, view=view)` lets the embed persist indefinitely, updated in-place by background tasks.
- **Tests using new locale keys need `load_strings()` reload** — The localization cache is populated once per process. Test classes exercising newly added YAML keys must include `@pytest.fixture(autouse=True) def _load_locale_strings(self): load_strings()` to refresh the cache. See `TestTemplateView` in `test_application.py`.
- **`@app_commands.rename` for cleaner Discord param names** — Use `@app_commands.rename(python_name="discord_name")` whenever the Discord-facing name should differ from the Python identifier: required when the name is a keyword (e.g. `in`), and useful for readability (e.g. `form_name` → `form`). `describe`, `autocomplete`, and all internal references keep using the Python name.
- **Alembic migrations must be dialect-aware** — SQLite uses `datetime()`, PostgreSQL uses `make_interval()`. Use `op.get_bind().dialect.name` to branch. Always use `batch_alter_table` for SQLite column operations. Note: `op.alter_column()` **without** a `batch_alter_table` context crashes on SQLite — and type-only encoding migrations (e.g. `Text` → `UnicodeText`) can skip SQLite entirely since it stores all text as Unicode internally.
- **All Alembic migrations must guard column/index existence, not just table existence** — `create_all()` on a fresh install already builds the latest schema; a subsequent `alembic upgrade head` must be a no-op. Before `add_column`, check `{c["name"] for c in inspect(conn).get_columns(table)}`; before `create_index`, check `{i["name"] for i in inspect(conn).get_indexes(table)}`. The return-early guard must cover both the "table absent" and "schema already current" cases.
- **`interaction.response.is_done()` returns `False` after a failed `send_message()`** — If `send_message()` raises (e.g. 10062 Unknown interaction), `is_done()` is still `False`. Always use `send_hidden_message()` in error handlers — it wraps the dispatch in try/except so `notify_error`/`error_counter.record()` always run even when the interaction has expired.
- **Version is derived from git tags** — `hatch-vcs` reads the version from git tags (e.g. `v0.6.0` → `0.6.0`). No static version in `pyproject.toml`. In Docker, `SETUPTOOLS_SCM_PRETEND_VERSION` build arg supplies the version since there's no `.git` dir. `hatch.build.targets.wheel.packages = []` prevents hatchling from trying to include `config/` or `NerdyPy/` as installable packages.
- **`uv sync --only-group` skips the project package** — Only `--group` (without `only-`) installs the project metadata alongside dependencies. The bot Docker image needs `--group bot` so `importlib.metadata.version("NerpyBot")` works at runtime.
- **`cog_load` runs before `create_all()`** — `setup_hook` calls `load_extension()` (triggering `cog_load`) before `create_all()`. If a cog accesses new tables in `cog_load`, call `self.bot.create_all()` at the top of `cog_load` to ensure tables exist on existing databases.
- **SQLite enforces unique constraints row-by-row, not deferred** — Swapping two values under a unique column in a single flush raises `IntegrityError`. Use a two-phase update: write temporary/offset values and flush, then write final values and flush.
- **Module-specific permission helpers stay with the module** — Only move a permission check to `utils/checks.py` if it is purely based on Discord roles/permissions. If it queries a module-specific table (e.g. `ApplicationGuildConfig`), keep it in the module's own file.
- **Cannot `send_modal()` after `defer()`** — Once `interaction.response.defer()` is called, `send_modal()` will raise. Design around this: if a button defers (e.g. to show a spinner), any follow-up that needs a modal must be a separate button/action.
- **Exception narrowing conventions** — Use `SQLAlchemyError` (from `sqlalchemy.exc`) for ops inside `session_scope()`, `discord.HTTPException` for Discord API calls (fetch, edit, send to channels), and `(discord.Forbidden, discord.NotFound)` for user DM attempts. In background task loops that edit persistent messages (e.g. now-playing embeds), catch `(discord.NotFound, discord.Forbidden)` — both mean "this message/channel is no longer accessible" and require the same recovery path (drop the reference, optionally re-create).
- **`self_mute=True` in `channel.connect()` does NOT silence the bot** — It is a cosmetic gateway hint that shows a muted-mic icon in the Discord client for other users. The bot's UDP RTP audio packets are transmitted regardless. Do not "fix" this.
- **`asyncio.to_thread(fn, *args)` for blocking calls** — Preferred over `get_event_loop().run_in_executor(None, fn, args)`. The project targets Python 3.13 where `get_event_loop()` from a running coroutine emits `DeprecationWarning`. Use `asyncio.to_thread()` for any blocking I/O (yt-dlp, file ops) inside coroutines.
- **Pre-filling `discord.ui.Modal` fields** — Set `self.<field>.default = value` as an instance attribute in `__init__()` after `super().__init__()`. The class-level `TextInput` definition only sets the layout; instance-level assignment provides the pre-filled value.
- **Localization strings vs user-defined templates** — `get_string()` only processes bot-authored strings from `NerdyPy/locales/lang_*.yaml`. User-defined content (leave messages, custom tags) must never pass through `get_string()` — format them at the call site instead.
- **Adding a new language** — Create `NerdyPy/locales/lang_<code>.yaml`, restart the bot. No code changes needed. English keys are canonical — any missing key in other languages falls back to English automatically.
- **Guild language is global** — `GuildLanguageConfig` is the single source of truth for a guild's language preference. Modules calling external APIs (Blizzard, Riot) should honor this setting when the API supports it, falling back to English otherwise.
- **Full env var config** — All config keys can be set via `NERPYBOT_*` environment variables (see `docker-compose.yml` for the full list). Env vars take priority over `config.yaml` when both are present. Lists (`modules`, `ops`, `error_recipients`) use comma-separated values.
- **`Guild.get_channel()` is cache-only** — Returns `None` on cache miss (e.g. after reconnect). Fall back to `await guild.fetch_channel(channel_id)` and catch `(discord.NotFound, discord.Forbidden)` before treating a channel as missing or deleting related DB rows. Canonical pattern: `NerdyPy/utils/helpers.py`; inline shorthand: `NerdyPy/modules/views/crafting_order.py`.
- **`psutil.Process().cpu_percent(interval=None)` returns 0.0 on first call** — psutil needs an initial sample to compute a CPU diff. Prime with a discard call at module init: `_proc = psutil.Process(); _proc.cpu_percent(interval=None)` before the first real use. See `NerdyPy/utils/valkey.py`.
- **`ruff` only lints Python** — Never pass `.yaml`/`.yml` files to `ruff check`; it produces hundreds of parse errors. YAML is checked by `npx prettier --check` (see dev commands above).
- **SQLAlchemy 2.x bulk insert** — Use `session.execute(insert(Model), list_of_dicts)` for batch inserts instead of a `session.add()` loop; emits a single `INSERT ... VALUES` instead of N round-trips. Always guard with `if list_of_dicts:` before calling.
- **`server_default` auto-quotes plain strings** — A plain Python string is quoted by SQLAlchemy automatically: `server_default="active"` → `DEFAULT 'active'` (valid). Use `text()` for raw SQL emission: `server_default=text("'active'")` → `DEFAULT 'active'`, `server_default=text("2")` → `DEFAULT 2`. For integer columns: `Column(Integer, default=MY_CONST, server_default=text(str(MY_CONST)))` or `server_default=str(MY_CONST)` both work. Do NOT pass inner-quoted strings directly — `server_default="'active'"` emits `DEFAULT '''active'''`.

#### Web Component (FastAPI / Vue)

- **`session.commit()` before `background_tasks.add_task()`** — FastAPI background tasks run after the response is sent but before yield-dependency cleanup, so `session.commit()` in `_get_db_session` fires too late. Always call `session.commit()` explicitly before scheduling any background task that re-reads data written by the same request.
- **`selectinload` for multiple one-to-many collections** — Two `joinedload` on different one-to-many relationships on the same parent produce a Cartesian product (rows × rows). Use `selectinload` for the second (and any further) collection — it fires a separate `IN` query instead.
- **No `return` inside `finally`** — Biome flags this as `noUnsafeFinally`; it suppresses any exception that escapes the `catch` block. Move stale-sequence guards and cleanup logic to _after_ the `try/catch` block instead.
- **`route.query` TypeScript types** — Vue Router types query values as `LocationQueryValue | LocationQueryValue[]` where `LocationQueryValue = string | null`. Any helper that normalizes a query param must accept `(string | null)[]`, not `string[]`.
- **Support mode GET endpoints need the `X-Support-Mode` header** — Add `response: Response = None` to the function signature and call `_set_support_mode_header(user, response)` at the top. Also guard any lazy ORM mutations (e.g. name backfill loops) with `if not user.get("support_mode")` — SQLAlchemy auto-commits ORM changes at request end, so mutations inside GET handlers persist even for support-mode reads.
- **Tests for `require_guild_access` must first grant premium** — The guild router has `dependencies=[Depends(require_premium)]` at router level. A test user without premium hits `require_premium` (not `require_guild_access`) and gets 403 for the wrong reason. Call `PremiumUser.grant(user_id, operator_id, session)` before asserting access behavior.
- **Vue Router `beforeEach` never sees the source of a declarative redirect** — `{ path: "/", redirect: "/guilds" }` is resolved before guards fire; `to.path` will be `"/guilds"`, never `"/"`. Guard conditions using the pre-redirect path silently never match.
- **Static `index.html` `<title>` is baked at build time** — The Vue SPA updates `document.title` at runtime via `watch()` on the branding store, but the `<title>` tag in `dist/index.html` reflects whatever was configured when `npm run build` ran. Pre-built Docker containers always show the build-time title on first load.
- **`GET /api/branding` is intentionally unauthenticated** — Any endpoint that provides pre-login UI data (bot name, description) must not have a JWT dependency. Users hit this endpoint before they have a token.
- **Pinia one-shot load dedup: reset `_loadPromise = null` in outer `.catch()`** — If the reset is inside the async IIFE's `catch`, a concurrent caller can bypass the guard mid-flight. Attach `.catch(() => { _loadPromise = null; })` to the IIFE result before returning, so the guard stays valid for the full request lifetime.

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

- **`docs/plans/`** and **`docs/superpowers/`** are gitignored — never stage or commit plan/spec files
- **`gh pr create` in worktrees** — Always pass `--repo owner/repo --head <branch> --base main` explicitly; `gh` reads from the shell CWD (main worktree) and detects the wrong head branch otherwise.
- **`no-command-chaining.sh` Claude Code hook blocks `&&`** — A `PreToolUse:Bash` hook in the user's Claude Code config rejects commands containing `&&`. This is NOT a git pre-commit hook. Use separate Bash tool calls for each command.
- **`gh api -F` for comment bodies** — Use `-F body="..."` (capital F), not `-f body="..."`, when the body may contain backticks or special characters; `-f` causes parse errors in fish shell.
- **Resolving PR review threads** — Use `gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "PRRT_kwDO..."}) { thread { isResolved } } }'`. The `threadId` is the GraphQL node ID from `reviewThreads.nodes[].id` (NOT the REST comment `id`). Fetch node IDs via GraphQL: `pullRequest(number: N) { reviewThreads(first: 50) { nodes { id isResolved isOutdated comments(first:1) { nodes { databaseId body } } } } }`.
