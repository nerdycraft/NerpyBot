# Music Module

YouTube music playback in voice channels. Uses `yt-dlp` for video extraction and `ffmpeg` for audio conversion. Inherits queue management from `QueueMixin`.

## Commands

### `/play [song_url]`

Play audio from a URL or search YouTube.

| Parameter | Type | Description |
|-----------|------|-------------|
| `song_url` | `str` | URL or search query |

**Behavior depends on input:**
- **Direct URL** — Fetches video info, queues, and plays
- **YouTube playlist URL** — Redirects to `play playlist`
- **Text query** — Redirects to `play search`

**Requires:** User must be connected to a voice channel.

### `/play song <song_url>`

Play a single song by direct URL. Hidden subcommand (used internally).

| Parameter | Type | Description |
|-----------|------|-------------|
| `song_url` | `str` | Direct URL to audio/video |

### `/play playlist <playlist_url>`

Add all videos from a YouTube playlist to the queue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `playlist_url` | `str` | YouTube playlist URL |

**Process:**
1. Extract playlist via `yt-dlp` (`extract_flat` mode for speed)
2. Create a `QueuedSong` for each entry with the video title and ID
3. Queue all songs — playback starts automatically via the queue manager

### `/play search <query>`

Search YouTube and play the first result.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Search terms |

Uses the YouTube Data API v3 (`config.search.ytkey`) to find the top result, then queues it.

### `/skip`

Skip the currently playing track. The queue manager automatically starts the next song. Any user in the same voice channel as the bot can skip; moderators can skip from anywhere.

### `/queue list`

List all songs currently in the queue with their positions.

### `/queue drop`

Clear the entire queue and stop playback.

**Permission:** `mute_members`

## How Playback Works

1. **User requests a song** — a `QueuedSong` object is created with a fetcher function and metadata
2. **`Audio.play()`** adds it to the guild's queue buffer
3. **`Audio._queue_manager`** (1-second loop) detects the queue has items and the bot isn't currently playing
4. **`QueuedSong.fetch_buffer()`** is called — downloads audio via `yt-dlp`, converts with `ffmpeg` to `FFmpegOpusAudio`
5. **`Audio._play()`** joins the voice channel (if not already) and starts streaming
6. When playback finishes, the queue manager picks up the next song

## Audio Pipeline

```
URL → yt-dlp (extract info) → HTTP download → ffmpeg (loudnorm filter, opus encoding) → Discord voice
```

- **Caching:** Video metadata cached in a `TTLCache` (10-minute TTL, 100 entries max)
- **Download directory:** `tmp/` (temporary files)
- **Timeout:** Bot automatically leaves voice after 600 seconds of inactivity (`Audio._timeout_manager`)

## Queue System

The queue is stored per-guild in `Audio.buffer[guild_id][BufferKey.QUEUE]` as a list of `QueuedSong` objects. The `QueueMixin` class provides:

- `_has_queue(guild_id)` — Check if queue is non-empty
- `_clear_queue(guild_id)` — Empty the queue

## Configuration

```yaml
audio:
  buffer_limit: 5    # Max queued songs per guild

search:
  ytkey: your_youtube_api_key    # Required for /play search
```
