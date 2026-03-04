# Music Module

YouTube music playback in voice channels. Uses `yt-dlp` for video extraction and `ffmpeg` for audio conversion. Supports search queries, direct URLs, YouTube playlist URLs, and user-saved playlists. An interactive now-playing embed with playback controls is posted to the voice channel when a song starts.

## Commands

### `/play <url>`

Play a song, enqueue a YouTube playlist, or search YouTube by keyword. Joins the user's voice channel automatically.

| Parameter | Type  | Description                             |
| --------- | ----- | --------------------------------------- |
| `url`     | `str` | Song URL, playlist URL, or search query |

**Behavior by input:**

- **Direct URL** — Fetches video info via `yt-dlp` and enqueues the song.
- **YouTube playlist URL** — Extracts all entries and enqueues each one individually.
- **Text query (no `://`)** — Calls the YouTube Data API v3 to find the top result, then enqueues it.

**Requires:** User must be connected to a voice channel.

### `/playlist create <name>`

Create a new empty playlist owned by the calling user.

| Parameter | Type  | Description               |
| --------- | ----- | ------------------------- |
| `name`    | `str` | Name for the new playlist |

Fails with an error if a playlist with the same name already exists for the user in this guild.

### `/playlist list`

Show all playlists saved by the calling user in this guild.

### `/playlist show <name>`

Show the songs in one of your playlists, numbered in order with linked titles.

| Parameter | Type  | Description   |
| --------- | ----- | ------------- |
| `name`    | `str` | Playlist name |

### `/playlist add <name> <url>`

Add a song to an existing playlist. The song title is fetched from `yt-dlp` at the time of adding.

| Parameter | Type  | Description     |
| --------- | ----- | --------------- |
| `name`    | `str` | Playlist name   |
| `url`     | `str` | Song URL to add |

### `/playlist remove <name> <url>`

Remove a song from a playlist by its URL.

| Parameter | Type  | Description        |
| --------- | ----- | ------------------ |
| `name`    | `str` | Playlist name      |
| `url`     | `str` | Song URL to remove |

### `/playlist save <name> [count]`

Save the current queue (or the last N played songs) as a playlist. Creates the playlist if it does not exist; overwrites entries if it does.

| Parameter | Type             | Description                                                              |
| --------- | ---------------- | ------------------------------------------------------------------------ |
| `name`    | `str`            | Name for the playlist                                                    |
| `count`   | `int` (optional) | Number of recently played songs to save. Omit to save the current queue. |

When `count` is provided, songs are taken from the guild's playback history (most recent N entries). The history buffer holds up to 50 songs per guild.

## Now Playing Embed and View

When a song starts, the bot posts an embed to the voice channel with:

- **Title** — "Now Playing"
- **Description** — Song title as a hyperlink to the source URL
- **Progress bar** — `[====>------] 1:23 / 3:45` updated every 10 seconds by `_progress_updater`
- **Footer** — "Requested by \<username\>"
- **Thumbnail** — Video thumbnail image (when available)

The embed has four persistent buttons:

| Button | Action                                                                                |
| ------ | ------------------------------------------------------------------------------------- |
| ⏯     | Pause or resume playback                                                              |
| ⏭     | Skip the current track (triggers `Audio.stop()`; the queue manager picks up the next) |
| ⏹     | Stop playback and disconnect from the voice channel (`Audio.leave()`)                 |
| 📋     | Show the current queue as an ephemeral message (capped at 10 entries)                 |

All buttons require the user to be in the same voice channel as the bot. The embed is deleted when the bot disconnects.

## Configuration

```yaml
music:
  ytkey: your_youtube_api_key # Required for text-based search queries

audio:
  buffer_limit: 5 # Max songs pre-fetched ahead in the queue
```

The `ytkey` is only needed for search queries. Direct URL and playlist URL playback works without it.

## Background Tasks

### `Audio._queue_manager`

**Schedule:** 1-second loop.

Pops the next `QueuedSong` from the guild's queue buffer when the bot is not currently playing. Calls `Audio._play()` to start streaming, then pre-fetches the next `buffer_limit` songs via `_update_buffer()`.

### `Audio._timeout_manager`

**Schedule:** 10-second loop.

Disconnects from the voice channel if the bot has been idle (not playing) for more than 600 seconds. Resets the idle timer whenever a song is actively playing.

### `Music._progress_updater`

**Schedule:** 10-second loop.

Edits the now-playing embed for every active guild to advance the progress bar. Skips guilds where playback is paused. Removes the guild's embed reference if the message has been deleted (discord.NotFound).

## Database Models

### `Playlist`

Table: `MusicPlaylist`

| Column    | Type         | Purpose                         |
| --------- | ------------ | ------------------------------- |
| Id        | Integer (PK) | Auto-increment                  |
| GuildId   | BigInteger   | Discord guild ID                |
| UserId    | BigInteger   | Discord user ID (owner)         |
| Name      | Unicode(100) | Playlist name                   |
| CreatedAt | DateTime     | Creation timestamp (UTC, naive) |

**Unique constraint:** `(GuildId, UserId, Name)` — one playlist per name per user per guild.

**Index:** `(GuildId, UserId)` — efficient per-user lookups.

### `PlaylistEntry`

Table: `MusicPlaylistEntry`

| Column     | Type         | Purpose                                     |
| ---------- | ------------ | ------------------------------------------- |
| Id         | Integer (PK) | Auto-increment                              |
| PlaylistId | Integer (FK) | Parent `Playlist.Id` (CASCADE delete)       |
| Url        | UnicodeText  | Song URL                                    |
| Title      | Unicode(200) | Song title (captured at the time of adding) |
| Position   | Integer      | Order within the playlist (0-indexed)       |

**Index:** `PlaylistId` — fast entry lookups by playlist.

## Data Flow

```
/play <url>
  └─ _enqueue()                  Build QueuedSong with fetcher, metadata, requester
       └─ Audio.play()           Add to guild queue buffer (or play immediately if idle)
            └─ _queue_manager    1s loop detects idle + queued item
                 └─ Audio._play()  fetch_buffer() → join channel → VoiceClient.play()
                      └─ _on_song_start_hook
                           └─ Music._handle_song_start()
                                └─ NowPlayingView posted to voice channel
```

After posting the embed, `_progress_updater` edits it every 10 seconds to update the progress bar.
