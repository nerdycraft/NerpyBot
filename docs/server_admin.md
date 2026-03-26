# Server Admin Module

Server-level configuration for the bot. All commands require **Administrator** permission. Auto-loaded on every
startup.

## Commands

### `/modrole get`

Shows the configured bot-moderator role for this server. Alerts if the role has been deleted from Discord.

### `/modrole set <role>`

Sets the bot-moderator role. Members with this role gain elevated bot permissions (e.g., stopping playback, leaving
voice).

| Parameter | Type   | Description                                |
| --------- | ------ | ------------------------------------------ |
| `role`    | `Role` | Discord role to designate as bot-moderator |

### `/modrole delete`

Removes the bot-moderator role configuration.

### `/language set <language>`

Set the server's language preference for all bot responses.

| Parameter  | Type  | Description                                     |
| ---------- | ----- | ----------------------------------------------- |
| `language` | `str` | Language code (e.g. `en`, `de`) — autocompleted |

The confirmation message is sent in the newly-set language so you can immediately verify it.

### `/language get`

Show the current language preference. Falls back to English if none is configured.

## Database Models

### `BotModeratorRole`

| Column  | Type            | Purpose          |
| ------- | --------------- | ---------------- |
| GuildId | BigInteger (PK) | Discord guild ID |
| RoleId  | BigInteger      | Discord role ID  |

### `GuildLanguageConfig`

| Column   | Type            | Purpose                         |
| -------- | --------------- | ------------------------------- |
| GuildId  | BigInteger (PK) | Discord guild ID                |
| Language | Unicode(10)     | Language code (e.g. `en`, `de`) |

## How Bot-Moderator Checks Work

The bot-moderator system (`utils/checks.py:is_bot_moderator`) grants elevated access to users who meet **any** of these
conditions:

1. Have `mute_members` permission
2. Have `manage_channels` permission
3. Have `administrator` permission
4. Are listed in `config.bot.ops` (bot operators)
5. Have the role configured via `/modrole set`

This check is used by other modules (moderation, music) to gate privileged commands like stopping playback or
making the bot leave voice.
