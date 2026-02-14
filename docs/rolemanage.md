# Role Manage Module

Delegated role assignment — allows specific roles to assign other roles without needing `manage_roles` permission. Admins configure which source roles can assign which target roles.

## Concept

The role delegation model works like this:

```
Admin creates mapping:  @Moderator  →  @Verified
                        (source)       (target)

Any member with @Moderator can now:
  /rolemanage assign @user @Verified    (adds role)
  /rolemanage remove @user @Verified    (removes role)
```

This enables role hierarchies without giving broad `manage_roles` permission to moderators.

## Commands

### Configuration (requires `manage_roles`)

#### `/rolemanage allow <source_role> <target_role>`

Authorize a source role to assign a target role.

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_role` | `Role` | Role whose members gain assignment power |
| `target_role` | `Role` | Role that can be assigned |

**Safety checks:**
- Target role must not be a managed/integration role
- Target role must be below the bot's top role

#### `/rolemanage deny <source_role> <target_role>`

Revoke a delegation mapping.

#### `/rolemanage list`

Show all source-to-target role mappings for this server.

### Usage (requires delegation)

#### `/rolemanage assign <member> <role>`

Assign a role to a member.

| Parameter | Type | Description |
|-----------|------|-------------|
| `member` | `Member` | Target user |
| `role` | `Role` | Role to assign |

**Authorization:** The invoking user must have at least one role that is configured as a source for the requested target role.

#### `/rolemanage remove <member> <role>`

Remove a role from a member. Same authorization as `assign`.

## Database Model

### `RoleMapping`

| Column | Type | Purpose |
|--------|------|---------|
| Id | Integer (PK) | Auto-increment |
| GuildId | BigInteger | Discord guild ID |
| SourceRoleId | BigInteger | Role that grants assignment power |
| TargetRoleId | BigInteger | Role that can be assigned |

**Unique constraint:** `(GuildId, SourceRoleId, TargetRoleId)` — prevents duplicate mappings.

## How Authorization Works

When a user runs `/rolemanage assign @user @SomeRole`:

1. Fetch all `RoleMapping` entries where `TargetRoleId == @SomeRole` for this guild
2. Get the user's current role IDs
3. Check if **any** of the user's roles appear as a `SourceRoleId` in the mappings
4. If yes — proceed with the assignment. If no — reject with an error.

All role changes are logged with a reason string in the Discord audit log.
