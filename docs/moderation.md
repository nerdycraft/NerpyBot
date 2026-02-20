# Moderation Module

Server moderation tools including automatic member kicking, message cleanup, and user info. All commands are grouped under `/moderation`. Runs two background task loops.

## Background Tasks

### AutoKicker Loop

**Schedule:** Runs once daily at **12:30 UTC**.

**Process:**

1. For each guild with an enabled `AutoKicker` config:
2. Iterate all members
3. **Detection:** A member is "roleless" if they only have the `@everyone` role (`len(member.roles) == 1`)
4. Calculate kick deadline: `member.joined_at + KickAfter`
5. Calculate reminder point: `member.joined_at + KickAfter / 2`
6. **Actions:**
   - If past the kick deadline — **kick the member** with reason logged
   - If past the reminder point but before deadline — **send a DM reminder**
7. The reminder message is either custom (from config) or the default:
   > "You have not selected a role on {guild}. Please choose a role until {deadline}."

### AutoDeleter Loop

**Schedule:** Runs every **5 minutes**.

**Process:**

1. For each enabled `AutoDelete` config across all guilds (skips paused configs):
2. Fetch message history for the configured channel
3. Find messages older than `DeleteOlderThan` seconds
4. Sort oldest-first, keep the newest `KeepMessages` count
5. Delete everything else (respects `DeletePinnedMessage` flag)
6. Uses `channel.purge()` for bulk deletion

## Commands

### `/moderation autokicker <enable> <kick_after> [kick_reminder_message]`

Configure automatic kicking of members who don't pick a role.

| Parameter               | Type             | Description                                                        |
| ----------------------- | ---------------- | ------------------------------------------------------------------ |
| `enable`                | `bool`           | Enable or disable                                                  |
| `kick_after`            | `str`            | Duration string (e.g., `"7d"`, `"48h"`) — parsed by `pytimeparse2` |
| `kick_reminder_message` | `str` (optional) | Custom reminder DM. Use `{guild}` for server name                  |

**Permission:** `kick_members`

### `/moderation autodeleter create <channel> [delete_older_than] [keep_messages] [delete_pinned_message]`

Create an auto-delete policy for a channel.

| Parameter               | Type          | Default      | Description                           |
| ----------------------- | ------------- | ------------ | ------------------------------------- |
| `channel`               | `TextChannel` | _(required)_ | Target channel                        |
| `delete_older_than`     | `str`         | `None`       | Age threshold (e.g., `"24h"`, `"7d"`) |
| `keep_messages`         | `int`         | `None`       | Minimum messages to keep              |
| `delete_pinned_message` | `bool`        | `False`      | Whether to delete pinned messages     |

**Permission:** `manage_messages`

### `/moderation autodeleter delete <channel>`

Remove the auto-delete policy for a channel.

**Permission:** `manage_messages`

### `/moderation autodeleter list`

List all auto-delete configurations for this server.

**Permission:** `manage_messages`

### `/moderation autodeleter edit <channel> [delete_older_than] [keep_messages] [delete_pinned_message]`

Modify an existing auto-delete configuration.

**Permission:** `manage_messages`

### `/moderation autodeleter pause <channel>`

Pause auto-deletion for a channel without removing the configuration.

**Permission:** `manage_messages`

### `/moderation autodeleter resume <channel>`

Resume auto-deletion for a previously paused channel.

**Permission:** `manage_messages`

### `/moderation user info [member]`

Show detailed information about a member.

| Parameter | Type     | Default         | Description       |
| --------- | -------- | --------------- | ----------------- |
| `member`  | `Member` | command invoker | Member to inspect |

**Displays:** Account creation date, server join date, top role, all roles.

**Permission:** `moderate_members`

### `/moderation user list [show_only_users_without_roles]`

List all server members with join dates. Paginated output.

| Parameter                       | Type   | Default | Description                     |
| ------------------------------- | ------ | ------- | ------------------------------- |
| `show_only_users_without_roles` | `bool` | `False` | Filter to roleless members only |

**Permission:** `moderate_members`

### `/moderation membercount`

Shows the current server member count. No permission required.

## Database Models

### `AutoKicker`

| Column          | Type            | Purpose                         |
| --------------- | --------------- | ------------------------------- |
| GuildId         | BigInteger (PK) | Discord guild ID                |
| KickAfter       | BigInteger      | Seconds before kick (default 0) |
| Enabled         | Boolean         | Active toggle (default `False`) |
| ReminderMessage | UnicodeText     | Custom reminder DM template     |

### `AutoDelete`

| Column              | Type         | Purpose                                   |
| ------------------- | ------------ | ----------------------------------------- |
| Id                  | Integer (PK) | Auto-increment                            |
| GuildId             | BigInteger   | Discord guild ID                          |
| ChannelId           | BigInteger   | Target channel                            |
| KeepMessages        | BigInteger   | Minimum messages to retain (default 0)    |
| DeleteOlderThan     | BigInteger   | Age threshold in seconds                  |
| DeletePinnedMessage | Boolean      | Include pinned messages (default `False`) |
| Enabled             | Boolean      | Active toggle (default `True`)            |
