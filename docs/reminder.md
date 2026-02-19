# Reminder Module

Timed message reminders that send to a Discord channel on a schedule. Supports one-shot, repeating interval, and calendar-based (daily/weekly/monthly) reminders with timezone awareness.

## Background Task

### Reminder Loop

**Schedule:** Hybrid smart loop with dynamic interval between **5** and **60 seconds**.

**Process:**

1. Query all reminders `WHERE NextFire <= NOW() AND Enabled = True`
2. For each due reminder:
   - **Guild or channel deleted** — delete the reminder from DB
   - **One-shot** (`ScheduleType = once`) — send message, then delete
   - **Repeating** (interval/daily/weekly/monthly) — send message, recompute `NextFire` via `compute_next_fire()`, increment `Count`
3. After processing, query the earliest `NextFire` among all enabled reminders
4. Adjust the loop sleep interval: `max(5s, min(seconds_until_next_fire, 60s))`

This means the loop sleeps up to 60 seconds when no reminders are due soon, but tightens to as low as 5 seconds when a reminder is imminent.

## Commands

### `/reminder create <in> <message> [channel] [repeat]`

Create an interval-based reminder.

| Parameter | Type                     | Description                                                    |
| --------- | ------------------------ | -------------------------------------------------------------- |
| `in`      | `str`                    | When to fire, e.g. `2h30m`, `1d`, `90s`, `1w` (minimum 60s)    |
| `message` | `str`                    | Message text to send                                           |
| `channel` | `TextChannel` (optional) | Target channel (defaults to current channel)                   |
| `repeat`  | `bool` (optional)        | Repeat at the same interval after each fire (default: `False`) |

A bare integer (no unit suffix) is treated as minutes for backward compatibility.

When `repeat` is `False`, the reminder fires once and is deleted. When `True`, it fires at the given interval indefinitely (stored as `ScheduleType = interval` with `IntervalSeconds`).

### `/reminder schedule <type> <time> <message> [channel] [day_of_week] [day_of_month] [timezone]`

Create a calendar-based reminder (daily, weekly, or monthly).

| Parameter       | Type                     | Description                                                              |
| --------------- | ------------------------ | ------------------------------------------------------------------------ |
| `schedule_type` | Choice                   | `Daily`, `Weekly`, or `Monthly`                                          |
| `time_of_day`   | `str`                    | Time in HH:MM 24-hour format (e.g. `09:00`)                              |
| `message`       | `str`                    | Message text to send                                                     |
| `channel`       | `TextChannel` (optional) | Target channel (defaults to current channel)                             |
| `day_of_week`   | Choice (optional)        | Monday through Sunday (required for weekly)                              |
| `day_of_month`  | `int` (optional)         | Day of month, 1-28 (required for monthly)                                |
| `timezone`      | `str` (optional)         | IANA timezone, e.g. `Europe/Berlin` (default: UTC, autocomplete enabled) |

The `timezone` parameter supports autocomplete — start typing a timezone name and matching IANA zones will be suggested (up to 25 results).

### `/reminder list`

List all reminders for this server. Each entry shows:

- Status icon (enabled/paused)
- Reminder ID, target channel, and schedule description
- Message text (quoted)
- Author, next fire time (relative + absolute, displayed in the reminder's configured timezone), and hit count

Schedule descriptions vary by type:

- **one-time** — `one-time`
- **interval** — `every 2 hours` (humanized delta)
- **daily** — `daily at 09:00 Europe/Berlin`
- **weekly** — `weekly Monday at 09:00 Europe/Berlin`
- **monthly** — `monthly day 15 at 09:00 Europe/Berlin`

Output is paginated if it exceeds Discord's embed limits.

### `/reminder edit <reminder> [message] [channel] [delay] [time_of_day] [day_of_week] [day_of_month] [timezone]`

Edit an existing reminder. All parameters except `reminder` are optional — only supplied values are changed.

| Parameter      | Type                     | Description                                                 | Applies to                   |
| -------------- | ------------------------ | ----------------------------------------------------------- | ---------------------------- |
| `reminder`     | `int`                    | Reminder ID (autocompleted with status and message preview) | all                          |
| `message`      | `str` (optional)         | New message text                                            | all                          |
| `channel`      | `TextChannel` (optional) | New target channel                                          | all                          |
| `delay`        | `str` (optional)         | New interval, e.g. `2h30m` (minimum 60s)                    | `interval` only              |
| `time_of_day`  | `str` (optional)         | New time in HH:MM 24-hour format                            | `daily`, `weekly`, `monthly` |
| `day_of_week`  | Choice (optional)        | New day of week                                             | `weekly` only                |
| `day_of_month` | `int` (optional)         | New day of month, 1-28                                      | `monthly` only               |
| `timezone`     | `str` (optional)         | New IANA timezone (autocomplete enabled)                    | `daily`, `weekly`, `monthly` |

Parameters that don't apply to the reminder's schedule type are rejected with an error message. If any timing-related parameter is changed, `NextFire` is recalculated via `compute_next_fire()`.

### `/reminder delete <reminder_id>`

Delete a reminder by its ID.

| Parameter     | Type  | Description                                                 |
| ------------- | ----- | ----------------------------------------------------------- |
| `reminder_id` | `int` | Reminder ID (autocompleted with status and message preview) |

### `/reminder pause <reminder_id>`

Pause a reminder without deleting it. The background loop skips paused reminders.

| Parameter     | Type  | Description                                                 |
| ------------- | ----- | ----------------------------------------------------------- |
| `reminder_id` | `int` | Reminder ID (autocompleted with status and message preview) |

### `/reminder resume <reminder_id>`

Resume a paused reminder. If `NextFire` is in the past, it is recalculated to the next valid occurrence. For one-shot reminders whose time has passed, the reminder is deleted instead.

| Parameter     | Type  | Description                                                 |
| ------------- | ----- | ----------------------------------------------------------- |
| `reminder_id` | `int` | Reminder ID (autocompleted with status and message preview) |

## Database Model

### `ReminderMessage`

| Column             | Type         | Purpose                                          |
| ------------------ | ------------ | ------------------------------------------------ |
| Id                 | Integer (PK) | Auto-increment                                   |
| GuildId            | BigInteger   | Discord guild ID                                 |
| ChannelId          | BigInteger   | Target channel                                   |
| ChannelName        | String(30)   | Channel name (for display)                       |
| CreateDate         | DateTime     | When created                                     |
| Author             | Unicode(30)  | Who created it                                   |
| Message            | UnicodeText  | Message content                                  |
| Enabled            | Boolean      | Active toggle (default `True`)                   |
| Count              | Integer      | Number of times sent (default `0`)               |
| NextFire           | DateTime     | Absolute UTC timestamp of next scheduled fire    |
| ScheduleType       | String(10)   | `once`, `interval`, `daily`, `weekly`, `monthly` |
| IntervalSeconds    | Integer      | Seconds between fires (for `interval` type)      |
| ScheduleTime       | Time         | Time of day for calendar types                   |
| ScheduleDayOfWeek  | Integer      | 0 = Monday .. 6 = Sunday (for `weekly`)          |
| ScheduleDayOfMonth | Integer      | 1-28 (for `monthly`)                             |
| Timezone           | String(50)   | IANA timezone string, `None` = UTC               |

**Indexes:**

- `ReminderMessage_GuildId` — guild lookups
- `ReminderMessage_Id_GuildId` — unique composite for guild-scoped ID lookups
- `ReminderMessage_NextFire_Enabled` — efficient due-reminder queries

**Removed columns** (from the old schema): `Minutes`, `LastSend`, `Repeat`.

## How Timing Works

All scheduling is based on the `NextFire` column — an absolute UTC timestamp of when the reminder should fire next. The background loop simply queries `WHERE NextFire <= NOW() AND Enabled = True`.

### Recomputation per schedule type

After each fire, `NextFire` is recalculated by `compute_next_fire()`:

- **once** — returns `None`, causing the reminder to be deleted after firing.
- **interval** — `now + IntervalSeconds`. Straightforward fixed-delay repeat.
- **daily** — finds the next occurrence of `ScheduleTime` in the configured timezone. If today's time has passed, advances to tomorrow.
- **weekly** — finds the next occurrence of `ScheduleTime` on `ScheduleDayOfWeek` in the configured timezone. Advances by full weeks if the current week's slot has passed.
- **monthly** — finds the next occurrence of `ScheduleTime` on `ScheduleDayOfMonth` in the configured timezone. Clamps the day to the month's actual last day (e.g., day 28 in February). Advances to the next month if this month's slot has passed.

All calendar computations are performed in the reminder's configured timezone (or UTC if none), then converted back to UTC for storage. This ensures correct behavior across DST transitions.
