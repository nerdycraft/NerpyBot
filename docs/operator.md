# Operator Module

Bot operator commands for managing the bot at runtime. Auto-loaded on every startup. Slash commands require
**Administrator** permission; prefix commands are **DM-only, operator-only** (user ID must be in `config.bot.ops`).

## Commands

### `/botpermissions check`

Checks whether the bot has all required permissions in the current server. Reports missing permissions and provides a
re-invite link with the correct permission set.

### `/botpermissions subscribe`

Subscribe to automatic DM notifications about missing permissions. When the bot restarts and detects missing permissions
in this server, subscribed administrators receive a DM with the same report as `/botpermissions check`.

### `/botpermissions unsubscribe`

Stop receiving automatic permission notifications for this server.

### `/ping`

Responds with "Pong." — a simple latency check. **Hybrid command:** available as both a slash command (`/ping`) and a
prefix command (`!ping`). Available to all users in guilds and DMs.

### `!help`

Lists all available operator commands with descriptions. Auto-discovers commands tagged `[operator]`. **Prefix-only,
DM-only, operator-only.**

### `!sync`

Syncs slash commands with Discord. **Prefix-only, DM-only, operator-only.**

| Parameter | Type                                | Description                   |
| --------- | ----------------------------------- | ----------------------------- |
| `guilds`  | `Greedy[Object]`                    | Optional guild IDs to sync to |
| `spec`    | `Literal["local", "copy", "clear"]` | Sync mode                     |

**Sync modes:**

- _(no spec, no guilds)_ — Global sync
- `local` — Sync current guild's commands
- `copy` — Copy global commands to specified guild(s)
- `clear` — Clear commands from specified guild(s)

### `!uptime`

Shows bot version and uptime. **Prefix-only, DM-only, operator-only.**

**Format:** `Version: X.Y.Z | Uptime: D Days, H Hours and M Minutes`

### `!debug`

Toggles debug logging at runtime. **Prefix-only, DM-only, operator-only.**

### `!errors`

Manage error notification throttling and suppression. **Prefix-only, DM-only, operator-only.**

**Subcommands:**

| Subcommand       | Description                                                     |
| ---------------- | --------------------------------------------------------------- |
| _(none)_         | Defaults to `status`                                            |
| `status`         | Show current throttle state with per-bucket error details       |
| `suppress <dur>` | Suppress all error DMs for duration (e.g. `30m`, `2h30m`, `1d`) |
| `resume`         | Cancel suppression and resume notifications                     |

**Throttling:** Errors are automatically deduplicated by exception type + context. After the first DM for a given error,
identical errors are suppressed for 15 minutes before sending another notification. Always active — no configuration
needed.

**Suppression:** Operators can manually suppress all error DMs for a duration. Useful during deployments or known
maintenance windows. Accepts any format supported by `utils/duration.py` (`30m`, `2h30m`, `1d`, etc.).

### `!disable <module>`

Disable a module at runtime. All its slash commands will respond with an ephemeral "disabled for maintenance" message
until re-enabled. **Prefix-only, DM-only, operator-only.**

| Parameter | Type  | Description                                 |
| --------- | ----- | ------------------------------------------- |
| `module`  | `str` | Module name (e.g. `wow`, `league`, `music`) |

**Protected modules:** `server_admin` and `operator` cannot be disabled.

**State is in-memory only** — all modules are re-enabled on bot restart.

### `!enable [module]`

Re-enable a previously disabled module, or **all disabled modules** if no argument is given. **Prefix-only, DM-only,
operator-only.**

### `!disabled`

List all currently disabled modules. **Prefix-only, DM-only, operator-only.**

## Database Models

### `PermissionSubscriber`

| Column  | Type            | Purpose                                         |
| ------- | --------------- | ----------------------------------------------- |
| GuildId | BigInteger (PK) | Discord guild ID                                |
| UserId  | BigInteger (PK) | Discord user ID subscribed to permission alerts |
