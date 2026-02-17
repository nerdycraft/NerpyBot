# Reaction Role Module

Assign Discord roles based on emoji reactions on designated messages. When a user reacts, they get the role; when they remove the reaction, the role is removed.

## Event Listeners

### `on_raw_reaction_add`

Triggered when any user adds a reaction to any message.

**Process:**

1. Skip if the reactor is a bot
2. Look up the message ID in `ReactionRoleMessage`
3. Find a `ReactionRoleEntry` matching the emoji
4. Add the mapped role to the user
5. If the role or member can't be found, log a warning

### `on_raw_reaction_remove`

Triggered when any user removes a reaction.

**Process:** Same as above, but removes the role instead of adding it.

## Commands

All commands require **`manage_roles`** permission.

### `/reactionrole add <channel> <message_id> <emoji> <role>`

Create an emoji-to-role mapping on a message.

| Parameter    | Type          | Description                    |
| ------------ | ------------- | ------------------------------ |
| `channel`    | `TextChannel` | Channel containing the message |
| `message_id` | `str`         | Discord message ID             |
| `emoji`      | `str`         | Emoji to react with            |
| `role`       | `Role`        | Role to assign                 |

**Process:**

1. Fetch the message to verify it exists
2. Create `ReactionRoleMessage` entry if first mapping on this message
3. Create `ReactionRoleEntry` for the emoji-role pair
4. Bot adds the reaction to the message (as a prompt for users)

**Safety:** Rejects roles that are above the bot's highest role (can't assign them).

### `/reactionrole remove <message_id> <emoji>`

Remove an emoji-role mapping.

| Parameter    | Type  | Description        |
| ------------ | ----- | ------------------ |
| `message_id` | `str` | Discord message ID |
| `emoji`      | `str` | Emoji to unmap     |

Also attempts to clear the bot's reaction from the message.

### `/reactionrole list`

List all reaction role mappings for this server, grouped by channel and message.

### `/reactionrole clear <message_id>`

Remove **all** reaction role mappings from a message and clear all reactions.

| Parameter    | Type  | Description        |
| ------------ | ----- | ------------------ |
| `message_id` | `str` | Discord message ID |

## Database Models

### `ReactionRoleMessage`

| Column    | Type         | Purpose                        |
| --------- | ------------ | ------------------------------ |
| Id        | Integer (PK) | Auto-increment                 |
| GuildId   | BigInteger   | Discord guild ID               |
| ChannelId | BigInteger   | Channel containing the message |
| MessageId | BigInteger   | Discord message ID (unique)    |

Has a `entries` relationship to `ReactionRoleEntry` with cascade delete.

### `ReactionRoleEntry`

| Column                | Type         | Purpose                                 |
| --------------------- | ------------ | --------------------------------------- |
| Id                    | Integer (PK) | Auto-increment                          |
| ReactionRoleMessageId | Integer (FK) | Parent message                          |
| Emoji                 | Unicode(100) | Emoji string (Unicode or custom format) |
| RoleId                | BigInteger   | Discord role ID to assign               |

## How Detection Works

The listeners use **raw** reaction events (`on_raw_reaction_add/remove`), which fire even for uncached messages. This means reaction roles work reliably on old messages that the bot hasn't seen since restart. The emoji string from the event payload is matched against stored `ReactionRoleEntry.Emoji` values.
