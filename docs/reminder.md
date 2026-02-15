# Reminder Module

Timed message reminders that send to a Discord channel on a schedule. Supports both one-shot and repeating reminders.

## Background Task

### Reminder Loop

**Schedule:** Runs every **30 seconds**.

**Process:**
1. For each guild the bot is in:
2. Fetch all `ReminderMessage` entries for that guild
3. For each message, check if `LastSend + Minutes` has elapsed
4. If due:
   - **Channel deleted** — delete the reminder from DB
   - **Repeat disabled** (`Repeat < 1`) — send message, then delete
   - **Repeat enabled** — send message, update `LastSend` to now, increment `Count`

## Commands

### `/reminder create [channel] <minutes> <repeat> <message>`

Create a new timed reminder.

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `TextChannel` (optional) | Target channel (defaults to current channel) |
| `minutes` | `int` | Interval in minutes between sends |
| `repeat` | `bool` | Whether to repeat or fire once |
| `message` | `str` | Message text to send |

### `/reminder list`

List all active reminders for this server. Shows ID, author, channel, creation date, next send time (humanized), message text, and hit count.

Output is paginated if it exceeds Discord's 2000-character limit.

### `/reminder delete <reminder_id>`

Delete a reminder by its ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `reminder_id` | `int` | Reminder ID (shown in `/reminder list`) |

## Database Model

### `ReminderMessage`

| Column | Type | Purpose |
|--------|------|---------|
| Id | Integer (PK) | Auto-increment |
| GuildId | BigInteger | Discord guild ID |
| ChannelId | BigInteger | Target channel |
| ChannelName | String(30) | Channel name (for display) |
| CreateDate | DateTime | When created |
| Author | Unicode(30) | Who created it |
| Repeat | Integer | 1 = repeating, 0 = one-shot |
| Minutes | Integer | Interval in minutes |
| LastSend | DateTime | Last time the message was sent |
| Message | UnicodeText | Message content |
| Count | Integer | Number of times sent |

## How Timing Works

The loop checks every 30 seconds whether `LastSend + timedelta(minutes=Minutes) < now`. On creation, `LastSend` is set to the current time, so the first send occurs after `Minutes` minutes. For repeating reminders, `LastSend` is updated after each send, resetting the countdown.
