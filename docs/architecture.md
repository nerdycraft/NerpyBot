# Architecture Overview

NerpyBot is a Discord bot built with discord.py using the Cog extension system. This document covers the entry point, module loading, database layer, utility systems, and key patterns.

## Entry Point

**File:** `NerdyPy/NerdyPy.py` — `NerpyBot(Bot)`

### Startup Flow

1. Parse CLI arguments (`-d` debug, `-c` config path, `-r` auto-restart, `-l` loglevel)
2. Load `config.yaml` and initialize the bot
3. `setup_hook()`:
   - Load each module listed in `config.bot.modules` via `bot.load_extension(f"modules.{name}")`
   - Register global guild-only check (exceptions: `help`, `debug`, `sync`, `armory`)
   - Call `create_all()` to auto-create missing database tables
   - Start audio loops if `tagging` or `music` modules are loaded
4. `on_ready()` — log successful connection

### CLI Arguments

| Flag | Description |
|------|-------------|
| `-r, --auto-restart` | Restart bot on failure |
| `-c, --config` | Custom config file path |
| `-d, --debug` | Debug logging (excludes SQLAlchemy noise) |
| `-v, --verbose` | Verbosity level (stackable) |
| `-l, --loglevel` | Set log level directly (INFO, DEBUG, etc.) |

### Key Events

| Event | Behavior |
|-------|----------|
| `on_command_completion` | Deletes the invoking prefix message; caches last 10 commands per guild |
| `on_command_error` | Logs errors, sends user-friendly messages, throttles `CommandNotFound` spam |
| `on_raw_reaction_add` | Routes reactions to active conversations (raidplaner) |
| `on_message` | Routes DMs to active conversations, then processes commands |

### Prefix Resolution

`determine_prefix(bot, message)`:
- **In a guild:** Custom prefix from `GuildPrefix` table, or `!` as default
- **In DMs:** Both `!` and empty string (no prefix needed)

## Module System

Modules live in `NerdyPy/modules/` as discord.py Cogs. Each must implement:

```python
async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

Modules are loaded dynamically based on `config.bot.modules`. Available modules:

| Module | Type | Background Tasks | External APIs |
|--------|------|-----------------|---------------|
| admin | Cog | — | — |
| fun | Cog | — | — |
| league | GroupCog | — | Riot API |
| leavemsg | Cog | — | — |
| moderation | Cog | AutoKicker (daily), AutoDeleter (5min) | — |
| music | GroupCog + QueueMixin | — | YouTube API, yt-dlp |
| raidplaner | Cog | — | — |
| random | Cog | — | Various public APIs |
| reactionrole | Cog | — | — |
| reminder | GroupCog | Reminder loop (30s) | — |
| rolemanage | Cog | — | — |
| search | GroupCog | — | Imgur, Genius, OMDB, IGDB, YouTube |
| tagging | Cog + QueueMixin | — | — |
| utility | Cog | — | OpenWeatherMap |
| wow | GroupCog | Guild news loop (15min) | Blizzard API, Raider.io |

## Database Layer

### Connection

**File:** `NerdyPy/NerdyPy.py` (connection setup in `NerpyBot.__init__`)

Supports SQLite, MySQL/MariaDB, and PostgreSQL via SQLAlchemy connection strings:
- SQLite: `sqlite:///db.db` (default)
- MySQL: `mysql+pymysql://user:pass@host:port/dbname`
- PostgreSQL: `postgresql://user:pass@host:port/dbname`

### Session Management

```python
with self.bot.session_scope() as session:
    # read/write operations
    # auto-commits on exit, rolls back on SQLAlchemy errors
```

The `session_scope()` context manager (`NerdyPy.py:112`) creates a session, yields it, commits on success, rolls back on error, and always closes.

**Key property:** `expire_on_commit=False` — objects remain usable after the session closes. This allows snapshotting values for use outside the session scope.

### Table Auto-Creation

`create_all()` calls `BASE.metadata.create_all(engine)` — any model class inheriting from `db.BASE` gets its table created if missing. **No Alembic migration needed for new tables.** Alembic is only used when altering existing tables.

Alembic uses two separate configs (`alembic-nerpybot.ini` and `alembic-humanmusic.ini`) with independent version directories, since HumanMusic only loads a subset of modules and its database won't have all tables.

### Model Base

**File:** `NerdyPy/utils/database.py`

```python
BASE = declarative_base()
```

All models inherit from `db.BASE`. Convention: PascalCase column names (`GuildId`, `ChannelId`), classmethods for queries.

## Utility Systems

### Audio (`utils/audio.py`)

Manages voice channel connections, playback, and queuing.

- **`Audio`** — Main class. Maintains per-guild buffers for channel, queue, and voice client.
- **`QueuedSong`** — Encapsulates a song with a lazy fetcher function.
- **`QueueMixin`** — Inherited by Music and Tagging cogs for shared queue operations.
- **`_queue_manager`** — 1-second loop that dequeues and starts playback.
- **`_timeout_manager`** — 10-second loop that disconnects after 600s of inactivity.

### Conversation (`utils/conversation.py`)

State machine framework for interactive DM flows (used by raidplaner).

- **`Conversation`** — Base class. Subclass must implement `create_state_handler()` returning a dict mapping states to async methods.
- **`AnswerType`** — Enum: `REACTION`, `TEXT`, `BOTH`
- Reactions map emoji strings to target states. Text input is validated by answer handlers.
- `ConversationManager` tracks active conversations per user.

### Download (`utils/download.py`)

Audio downloading and conversion.

- **`fetch_yt_infos(url)`** — Cached YouTube metadata extraction via yt-dlp
- **`download(url, tag=False)`** — Downloads audio, converts via ffmpeg
- **`convert(source, tag=False)`** — Applies `loudnorm` filter for tags, returns `FFmpegOpusAudio`
- **Cache:** `TTLCache(maxsize=100, ttl=600)` for video metadata

### Format (`utils/format.py`)

Discord markdown helpers: `bold()`, `italics()`, `box()`, `inline()`, `strikethrough()`, `underline()`, `pagify()`, `strip_tags()`.

`pagify()` is used extensively to split long output into 2000-character pages.

### Helpers (`utils/helpers.py`)

- **`send_hidden_message(ctx, msg)`** — Slash: ephemeral reply. Prefix: DM fallback.
- **`error_context(ctx)`** — Formatted log prefix: `[Guild (id)] User (id) -> /command`
- **`empty_subcommand(ctx)`** — Default handler when no subcommand is given.
- **`check_api_response(response)`** — Raises `NerpyException` on non-200 status.
- **`youtube(yt_key, return_type, query)`** — YouTube Data API v3 search.

### Checks (`utils/checks.py`)

Permission check functions for use with `@check()` decorator:

| Function | Gates |
|----------|-------|
| `is_connected_to_voice` | User in voice + bot can connect |
| `is_in_same_voice_channel_as_bot` | User in same channel (mod override) |
| `can_stop_playback` | Mod, or alone with bot in voice |
| `can_leave_voice` | Bot-moderator only |

All checks guard against side effects during help probes (`ctx.invoked_with == "help"`).

### Logging (`utils/logging.py`)

Dual-handler setup:
- **stdout:** INFO and DEBUG (below WARNING)
- **stderr:** WARNING and above

Format: `[DD/MM/YYYY HH:MM] - LEVEL - module line: message`

## Key Patterns

### Hybrid Commands

Most commands are `@hybrid_command` — they work as both prefix (`!command`) and slash (`/command`). The `GroupCog` pattern creates command groups (e.g., `/wow armory`, `/reminder create`).

### Ephemeral Messaging

`ephemeral=True` is silently ignored on prefix commands (no interaction context). Always use `send_hidden_message()` which falls back to DMs.

### Background Task Pattern

```python
@tasks.loop(seconds=30)
async def _my_loop(self):
    # task logic

@_my_loop.before_loop
async def _before_my_loop(self):
    await self.bot.wait_until_ready()

def cog_unload(self):
    self._my_loop.cancel()
```

### Error Handling

- `NerpyException` — bot-specific errors, message sent to user
- `CommandNotFound` — throttled per user via `error_spam_threshold`
- Other exceptions — logged with traceback, generic error sent to user

## Configuration

```yaml
bot:
  client_id: discord_app_id
  token: discord_bot_token
  ops: [operator_user_ids]
  error_spam_threshold: 5
  modules: [admin, fun, ...]

database:
  db_type: sqlite          # sqlite, mariadb, postgresql
  db_name: db.db

audio:
  buffer_limit: 5

# Per-module config sections (search, league, utility, wow)
```

See `config.yaml.template` for the full reference.
