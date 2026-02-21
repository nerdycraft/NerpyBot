# Admin Module

Server administration and bot configuration. All commands require **Administrator** permission (enforced via
`@checks.has_permissions(administrator=True)` on the cog class).

## Commands

### `/modrole get`

Shows the configured bot-moderator role for this server. Alerts if the role has been deleted from Discord.

### `/modrole set <role>`

Sets the bot-moderator role. Members with this role gain elevated bot permissions (e.g., stopping playback, leaving
voice).

| Parameter | Type   | Description                                |
|-----------|--------|--------------------------------------------|
| `role`    | `Role` | Discord role to designate as bot-moderator |

### `/modrole delete`

Removes the bot-moderator role configuration.

### `!help`

Lists all available operator commands with descriptions. Auto-discovers commands tagged `[operator]`. **Prefix-only,
DM-only, operator-only** (user ID must be in `config.bot.ops`).

### `!sync`

Syncs slash commands with Discord. **Prefix-only, DM-only, operator-only.**

| Parameter | Type                                | Description                   |
|-----------|-------------------------------------|-------------------------------|
| `guilds`  | `Greedy[Object]`                    | Optional guild IDs to sync to |
| `spec`    | `Literal["local", "copy", "clear"]` | Sync mode                     |

**Sync modes:**

- _(no spec, no guilds)_ — Global sync
- `local` — Sync current guild's commands
- `copy` — Copy global commands to specified guild(s)
- `clear` — Clear commands from specified guild(s)

### `/botpermissions check`

Checks whether the bot has all required permissions in the current server. Reports missing permissions and provides a
re-invite link with the correct permission set. Available to administrators.

### `/botpermissions subscribe`

Subscribe to automatic DM notifications about missing permissions. When the bot restarts and detects missing permissions
in this server, subscribed administrators receive a DM with the same report as `/botpermissions check`.

### `/botpermissions unsubscribe`

Stop receiving automatic permission notifications for this server.

### `/ping`

Responds with "Pong." — a simple latency check. **Hybrid command:** available as both a slash command (`/ping`) and a
prefix command (`!ping`). Available to all users in guilds and DMs.

### `!uptime`

Shows bot version and uptime. **Prefix-only, DM-only, operator-only** (user ID must be in `config.bot.ops`).

**Format:** `Version: X.Y.Z | Uptime: D Days, H Hours and M Minutes`

### `!debug`

Toggles debug logging at runtime. **Prefix-only, DM-only, operator-only** (user ID must be in `config.bot.ops`).

### `!errors`

Manage error notification throttling and suppression. **Prefix-only, DM-only, operator-only** (user ID must be in
`config.bot.ops`).

**Subcommands:**

| Subcommand       | Description                                                  |
|------------------|--------------------------------------------------------------|
| _(none)_         | Defaults to `status`                                         |
| `status`         | Show current throttle state with per-bucket error details    |
| `suppress <dur>` | Suppress all error DMs for duration (e.g. `30m`, `2h`, `1d`) |
| `resume`         | Cancel suppression and resume notifications                  |

**Throttling:** Errors are automatically deduplicated by exception type + context. After the first DM for a given error,
identical errors are suppressed for 15 minutes before sending another notification. This is always active — no
configuration needed.

**Suppression:** Operators can manually suppress all error DMs for a specified duration. Useful during deployments or
known maintenance windows.

### `!disable <module>`

Disable a module at runtime. All its slash commands will respond with an ephemeral "disabled for maintenance" message
until re-enabled. **Prefix-only, DM-only, operator-only** (user ID must be in `config.bot.ops`).

| Parameter | Type  | Description                                 |
|-----------|-------|---------------------------------------------|
| `module`  | `str` | Module name (e.g. `wow`, `league`, `music`) |

**Protected modules:** `admin` and `voicecontrol` cannot be disabled.

**State is in-memory only** — all modules are re-enabled on bot restart.

### `!enable [module]`

Re-enable a previously disabled module, or **all disabled modules** if no argument is given. **Prefix-only, DM-only,
operator-only** (user ID must be in `config.bot.ops`).

### `!disabled`

List all currently disabled modules. **Prefix-only, DM-only, operator-only** (user ID must be in `config.bot.ops`).

## Database Models

### `BotModeratorRole`

| Column  | Type            | Purpose          |
|---------|-----------------|------------------|
| GuildId | BigInteger (PK) | Discord guild ID |
| RoleId  | BigInteger      | Discord role ID  |

## How Bot-Moderator Checks Work

The bot-moderator system (`utils/checks.py:is_bot_moderator`) grants elevated access to users who meet **any** of these
conditions:

1. Have `mute_members` permission
2. Have `manage_channels` permission
3. Have `administrator` permission
4. Are listed in `config.bot.ops` (bot operators)
5. Have the role configured via `/modrole set`

This check is used by other modules (moderation, music, tagging) to gate privileged commands like stopping playback or
making the bot leave voice.
