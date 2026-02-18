# Leave Message Module

Sends a configurable farewell message when a member leaves the server. All configuration commands require **Administrator** permission.

## Event Listener

### `on_member_remove`

Triggered when a member leaves (or is kicked/banned from) the guild.

**Process:**

1. Skip if the departing member is a bot
2. Look up `LeaveMessage` config for this guild
3. If enabled and channel still exists, send the configured message
4. The `{member}` placeholder in the message is replaced with the member's display name

## Commands

### `/leavemsg enable <channel>`

Enable leave messages and set the notification channel.

| Parameter | Type          | Description                     |
| --------- | ------------- | ------------------------------- |
| `channel` | `TextChannel` | Where to send farewell messages |

Creates a config entry with the default message if none exists, or re-enables an existing one.

### `/leavemsg disable`

Disable leave messages without deleting the configuration. Can be re-enabled later.

### `/leavemsg message <message>`

Set a custom farewell message.

| Parameter | Type  | Description                                       |
| --------- | ----- | ------------------------------------------------- |
| `message` | `str` | Custom message template (must contain `{member}`) |

**Validation:** The message must include the `{member}` placeholder or the command is rejected.

**Default message:** `"{member} left the server :("`

### `/leavemsg status`

Show the current leave message configuration: enabled/disabled state, target channel, and message template.

## Database Model

### `LeaveMessage`

| Column    | Type            | Purpose                                      |
| --------- | --------------- | -------------------------------------------- |
| GuildId   | BigInteger (PK) | Discord guild ID                             |
| ChannelId | BigInteger      | Target channel for messages                  |
| Message   | UnicodeText     | Message template with `{member}` placeholder |
| Enabled   | Boolean         | Active/inactive toggle (default `False`)     |
