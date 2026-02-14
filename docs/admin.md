# Admin Module

Server administration and bot configuration. All commands require **Administrator** permission (enforced via `@checks.has_permissions(administrator=True)` on the cog class).

## Commands

### `/prefix get`

Retrieves the current custom command prefix for the server.

- **Default prefix:** `!` (if none configured)

### `/prefix set <new_pref>`

Sets a custom command prefix for the server.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_pref` | `str` | New prefix (no spaces allowed) |

Creates a new DB entry if none exists, otherwise updates the existing one.

### `/prefix delete`

Removes the custom prefix, reverting to the default `!`.

### `/modrole get`

Shows the configured bot-moderator role for this server. Alerts if the role has been deleted from Discord.

### `/modrole set <role>`

Sets the bot-moderator role. Members with this role gain elevated bot permissions (e.g., stopping playback, leaving voice).

| Parameter | Type | Description |
|-----------|------|-------------|
| `role` | `Role` | Discord role to designate as bot-moderator |

### `/modrole delete`

Removes the bot-moderator role configuration.

### `sync [guilds] [spec]`

Syncs slash commands with Discord. Prefix-only (not a slash command itself).

| Parameter | Type | Description |
|-----------|------|-------------|
| `guilds` | `Greedy[Object]` | Optional guild IDs to sync to |
| `spec` | `Literal["local", "copy", "clear"]` | Sync mode |

**Sync modes:**
- *(no spec, no guilds)* — Global sync
- `local` — Sync current guild's commands
- `copy` — Copy global commands to specified guild(s)
- `clear` — Clear commands from specified guild(s)

### `debug`

Toggles debug logging at runtime. **Operator-only** (user ID must be in `config.bot.ops`).

## Database Models

### `GuildPrefix`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| Prefix | String(30) | Custom prefix |
| CreateDate | DateTime | When set |
| ModifiedDate | DateTime | Last change |
| Author | String(30) | Who set it |

### `BotModeratorRole`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| RoleId | BigInteger | Discord role ID |

## How Bot-Moderator Checks Work

The bot-moderator system (`utils/checks.py:_is_bot_moderator`) grants elevated access to users who meet **any** of these conditions:

1. Have `mute_members` permission
2. Have `manage_channels` permission
3. Have `administrator` permission
4. Are listed in `config.bot.ops` (bot operators)
5. Have the role configured via `/modrole set`

This check is used by other modules (moderation, music, tagging) to gate privileged commands like stopping playback or making the bot leave voice.
