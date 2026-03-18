# Roles Module

Two role management features in one module: delegated role assignment (`/rolemanage`) and reaction-based role
assignment (`/reactionrole`).

---

## Rolemanage

Allows specific roles to assign other roles without needing `manage_roles` permission. Admins configure which source
roles can assign which target roles.

### Concept

```text
Admin creates mapping:  @Moderator  →  @Verified
                        (source)       (target)

Any member with @Moderator can now:
  /rolemanage assign @user @Verified    (adds role)
  /rolemanage remove @user @Verified    (removes role)
```

### Commands

#### `/rolemanage allow <source_role> <target_role>`

Authorize a source role to assign a target role. Requires `manage_roles`.

| Parameter     | Type   | Description                              |
| ------------- | ------ | ---------------------------------------- |
| `source_role` | `Role` | Role whose members gain assignment power |
| `target_role` | `Role` | Role that can be assigned                |

**Safety checks:** Target role must not be a managed/integration role and must be below the bot's top role.

#### `/rolemanage deny <source_role> <target_role>`

Revoke a delegation mapping. Requires `manage_roles`.

#### `/rolemanage list`

Show all source-to-target role mappings for this server. Requires `manage_roles`.

#### `/rolemanage assign <member> <role>`

Assign a role to a member.

| Parameter | Type     | Description    |
| --------- | -------- | -------------- |
| `member`  | `Member` | Target user    |
| `role`    | `Role`   | Role to assign |

**Authorization:** The invoking user must hold at least one source role mapped to the target role.

#### `/rolemanage remove <member> <role>`

Remove a role from a member. Same authorization as `assign`.

### How Authorization Works

When a user runs `/rolemanage assign @user @SomeRole`:

1. Fetch all `RoleMapping` entries where `TargetRoleId == @SomeRole` for this guild
2. Get the user's current role IDs
3. Check if **any** of the user's roles appear as a `SourceRoleId` in the mappings
4. If yes — proceed. If no — reject with an error.

All role changes are logged with a reason string in the Discord audit log.

### Database Model — `RoleMapping`

| Column       | Type         | Purpose                           |
| ------------ | ------------ | --------------------------------- |
| Id           | Integer (PK) | Auto-increment                    |
| GuildId      | BigInteger   | Discord guild ID                  |
| SourceRoleId | BigInteger   | Role that grants assignment power |
| TargetRoleId | BigInteger   | Role that can be assigned         |

**Unique constraint:** `(GuildId, SourceRoleId, TargetRoleId)` — prevents duplicate mappings.

---

## Reaction Roles

Assign Discord roles based on emoji reactions on designated messages. Reacting adds the role; removing the reaction
removes the role.

### Event Listeners

#### `on_raw_reaction_add`

1. Skip if the reactor is a bot
2. Look up the message ID in `ReactionRoleMessage`
3. Find a `ReactionRoleEntry` matching the emoji
4. Add the mapped role to the user

#### `on_raw_reaction_remove`

Same process, but removes the role instead.

Uses **raw** reaction events so reaction roles work reliably on old messages that the bot hasn't seen since restart.

### Commands

All commands require **`manage_roles`** permission.

#### `/reactionrole add <channel> <message_id> <emoji> <role>`

Create an emoji-to-role mapping on a message.

| Parameter    | Type          | Description                    |
| ------------ | ------------- | ------------------------------ |
| `channel`    | `TextChannel` | Channel containing the message |
| `message_id` | `str`         | Discord message ID             |
| `emoji`      | `str`         | Emoji to react with            |
| `role`       | `Role`        | Role to assign                 |

Fetches the message to verify it exists, creates the DB entries, and adds the bot's reaction as a prompt for users.
Rejects roles above the bot's highest role.

#### `/reactionrole remove <message_id> <emoji>`

Remove an emoji-role mapping and clear the bot's reaction from the message.

#### `/reactionrole list`

List all reaction role mappings for this server, grouped by channel and message.

#### `/reactionrole clear <message_id>`

Remove **all** reaction role mappings from a message and clear all reactions.

### Database Models

#### `ReactionRoleMessage`

| Column    | Type         | Purpose                        |
| --------- | ------------ | ------------------------------ |
| Id        | Integer (PK) | Auto-increment                 |
| GuildId   | BigInteger   | Discord guild ID               |
| ChannelId | BigInteger   | Channel containing the message |
| MessageId | BigInteger   | Discord message ID (unique)    |

Has a `entries` relationship to `ReactionRoleEntry` with cascade delete.

#### `ReactionRoleEntry`

| Column                | Type         | Purpose                                 |
| --------------------- | ------------ | --------------------------------------- |
| Id                    | Integer (PK) | Auto-increment                          |
| ReactionRoleMessageId | Integer (FK) | Parent message                          |
| Emoji                 | Unicode(100) | Emoji string (Unicode or custom format) |
| RoleId                | BigInteger   | Discord role ID to assign               |
