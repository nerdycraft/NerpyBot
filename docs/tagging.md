# Tagging Module

User-created sound, text, and URL tags. Sound tags play audio in voice channels; text/URL tags display content. Tags are per-guild and can have multiple entries (randomly selected on use).

## Commands

### `/tag <name>`

Play or display a tag. This is the default subcommand (`fallback="get"`).

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tag name |

**Behavior by type:**
- **Sound** — Downloads and plays audio in the user's voice channel (requires voice connection)
- **Text** — Sends the text content as a message
- **URL** — Sends the URL as a message

If a tag has multiple entries, one is selected at random. Each use increments the tag's `Count`.

### `/tag create <name> <tag_type> <content>`

Create a new tag.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tag name (max 30 chars, unique per guild) |
| `tag_type` | `TagTypeConverter` | `sound`, `text`, or `url` |
| `content` | `str` | URL for sound/url tags, text for text tags |

**Sound processing pipeline:**
1. Download audio from URL via HTTP
2. Run through `ffmpeg` with `loudnorm` filter (normalizes volume)
3. Convert to MP3 (48kHz, 2-channel)
4. Store the processed bytes in `TagEntry.ByteContent`

### `/tag add <name> <content>`

Add an additional entry to an existing tag.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Existing tag name |
| `content` | `str` | New content entry |

Allows a tag to have multiple variants — each invocation plays/shows a random one.

### `/tag volume <name> <vol>`

Adjust playback volume for a sound tag.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tag name |
| `vol` | `int` | Volume 0-200 (100 = normal) |

Applied as an ffmpeg filter at playback: `-filter:a volume={vol/100}`.

### `/tag delete <name>`

Delete a tag and all its entries.

**Permission:** `mute_members` (acts as moderator check for tags)

### `/tag list`

List all tags in this server, grouped alphabetically by first letter. Shows tag type and entry count.

### `/tag info <name>`

Show detailed metadata for a tag: author, type, creation date, hit count, number of entries.

### `/tag raw <name>`

Show all raw content entries for a tag.

### `/tag skip`

Skip the currently playing sound tag.

### `/tag queue list`

List queued sound tags.

### `/tag queue drop`

Clear the sound tag queue.

**Permission:** `mute_members`

## Tag Types

| Type | Value | Storage | Playback |
|------|-------|---------|----------|
| `sound` | 0 | `ByteContent` (binary audio) | Voice channel via ffmpeg |
| `text` | 1 | `TextContent` (string) | Channel message |
| `url` | 2 | `TextContent` (URL string) | Channel message |

## How Sound Playback Works

1. `Tag.get_random_entry()` selects a random `TagEntry` from the tag's entries
2. The `ByteContent` is passed to `convert()` which creates an `FFmpegOpusAudio` stream
3. Volume is applied as an ffmpeg filter: `volume={tag.Volume / 100}`
4. Audio is queued via `Audio.play()` — the `_queue_manager` handles playback order
5. If another sound is playing, the new one waits in the queue

## Database Models

### `Tag`

| Column | Type | Purpose |
|--------|------|---------|
| Id | Integer (PK) | Auto-increment |
| GuildId | BigInteger | Discord guild ID |
| Name | String(30) | Tag name |
| Type | Integer | TagType enum value (0=sound, 1=text, 2=url) |
| Author | String(30) | Creator's name |
| CreateDate | DateTime | When created |
| Count | Integer | Times used |
| Volume | Integer | Playback volume 0-200 |

**Unique constraint:** `(Name, GuildId)` — one tag per name per guild.

### `TagEntry`

| Column | Type | Purpose |
|--------|------|---------|
| Id | Integer (PK) | Auto-increment |
| TagId | Integer (FK) | Parent tag |
| TextContent | String(255) | Text/URL content |
| ByteContent | LargeBinary(16MB) | Processed audio bytes (sound tags) |

## Audio Normalization

All sound tags go through a two-pass ffmpeg processing on upload:

1. **`loudnorm` filter** — EBU R128 loudness normalization ensures consistent volume across tags
2. **MP3 encoding** — 48kHz, stereo, standardized format

This means a whisper-quiet clip and a deafening one will play at roughly the same volume.
