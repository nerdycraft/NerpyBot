# -*- coding: utf-8 -*-
"""
Handling Audio Transmission to discord api
"""

import asyncio
import enum
import logging
import queue
from collections import defaultdict, deque
from datetime import UTC, datetime

import discord
from discord import Interaction, VoiceChannel, VoiceClient
from discord.ext import tasks
from utils.helpers import send_paginated


class BufferKey(enum.Enum):
    """Keys for the guild queue"""

    CHANNEL = 1
    QUEUE = 2
    VOICE_CLIENT = 3


class QueueMixin:
    """Mixin providing queue management methods."""

    queue: dict
    audio: "Audio"

    def _has_queue(self, guild_id: int) -> bool:
        return guild_id in self.queue

    def _clear_queue(self, guild_id: int) -> None:
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()

    async def _send_queue_list(self, interaction: Interaction) -> None:
        """Format and send the paginated queue listing."""
        audio_queue = self.audio.list_queue(interaction.guild.id)
        if not audio_queue:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return

        msg = ""
        for i, t in enumerate(audio_queue, start=1):
            msg += f"`{i}` {t.title}\n"

        await send_paginated(interaction, msg, title="\U0001f3b5 Queue", color=0x0099FF)

    def _stop_and_clear_queue(self, guild_id: int) -> None:
        """Stop playback, clear the audio buffer, and clear the module queue."""
        self.audio.stop(guild_id)
        self.audio.clear_buffer(guild_id)
        self._clear_queue(guild_id)


class QueuedSong:
    """Models Class for Queued Songs"""

    def __init__(
        self,
        channel: VoiceChannel,
        fetcher,
        fetch_data,
        title: str = None,
        idn: str = None,
        duration: int = None,
        requester=None,
        thumbnail: str = None,
    ):
        self.stream = None
        self.title = title
        self.idn = idn
        self.channel = channel
        self._fetcher = fetcher
        self.fetch_data = fetch_data
        self.duration = duration
        self.requester = requester
        self.thumbnail = thumbnail
        self.log = logging.getLogger("nerpybot")

    async def fetch_buffer(self):
        """Fetches the buffer for the song"""
        self._fetcher(self)


class Audio:
    """Handles all audio transmission to the discord api"""

    def __init__(self, bot):
        self.bot = bot
        self.buffer = {}
        self.lastPlayed = {}
        self.buffer_limit = self.bot.config["audio"]["buffer_limit"]
        self.current_song: dict = {}
        self.play_start: dict = {}
        self.paused_at: dict = {}
        self.now_playing_message: dict = {}
        self.history: dict = defaultdict(lambda: deque(maxlen=50))
        self._on_song_start_hook = None

    @tasks.loop(seconds=10)
    async def _timeout_manager(self):
        last = dict(self.lastPlayed)
        for guild_id in last:
            delta = datetime.now() - last[guild_id]
            if delta.total_seconds() > 600:
                client = self.bot.get_guild(guild_id).voice_client
                if client is not None:
                    if not client.is_playing():
                        await self.leave(guild_id)
                    else:
                        self.lastPlayed[guild_id] = datetime.now()

    @tasks.loop(seconds=1)
    async def _queue_manager(self):
        last = dict(self.lastPlayed)
        for guild_id in last:
            if self._has_buffer(guild_id) and self._has_item_in_buffer(guild_id) and not self._is_playing(guild_id):
                queued_song = self.buffer[guild_id][BufferKey.QUEUE].get()
                await self._play(queued_song)
                await self._update_buffer(guild_id)

    async def setup_loops(self):
        self._queue_manager.start()
        self._timeout_manager.start()

    async def _play(self, song):
        if song.stream is None:
            self.bot.log.debug(
                f"Fetching song buffer for {song.title} in channel {song.channel.name} ({song.channel.id})"
            )
            await song.fetch_buffer()
        await self._join_channel(song.channel)

        guild_id = song.channel.guild.id

        if not song.channel.guild.voice_client or not song.channel.guild.voice_client.is_connected():
            guild = song.channel.guild
            self.bot.log.error(
                f"[{guild.name} ({guild.id})]: "
                f"failed to connect to voice channel {song.channel.name} ({song.channel.id})"
            )
            return

        # Save old song to history before overwriting
        old = self.current_song.get(guild_id)
        if old is not None:
            self.history[guild_id].append(old)

        # Update session state
        self.current_song[guild_id] = song
        self.play_start[guild_id] = datetime.now(UTC)
        self.paused_at.pop(guild_id, None)

        self.bot.log.debug(f"Playing Song {song.title} in channel {song.channel.name} ({song.channel.id})")
        song.channel.guild.voice_client.play(
            song.stream,
            after=lambda e: (
                self.bot.log.error(f"[{song.channel.guild.name} ({song.channel.guild.id})]: player error: {e}")
                if e
                else None
            ),
        )
        self.lastPlayed[guild_id] = datetime.now()

        if self._on_song_start_hook is not None:
            await self._on_song_start_hook(guild_id, song)

    async def _join_channel(self, channel: VoiceChannel):
        try:
            vc = channel.guild.voice_client
            if isinstance(vc, VoiceClient) and vc.is_connected():
                if self.buffer[channel.guild.id][BufferKey.CHANNEL].id != channel.id:
                    self.bot.log.debug(f"Moving to channel {channel}")
                    await vc.move_to(channel)
            else:
                self.bot.log.debug(f"Connecting to channel {channel}")
                try:
                    vc = await channel.connect(self_deaf=True, self_mute=True, timeout=5)
                except asyncio.TimeoutError as e:
                    self.bot.log.error(
                        f"[{channel.guild.name} ({channel.guild.id})]: "
                        f"failed to connect to voice channel {channel.name} ({channel.id}): {e}"
                    )
                    return
                else:
                    self.buffer[channel.guild.id][BufferKey.VOICE_CLIENT] = vc
        finally:
            self.buffer[channel.guild.id][BufferKey.CHANNEL] = channel

    def _setup_buffer(self, guild_id):
        self.lastPlayed[guild_id] = datetime.now()
        if guild_id in self.buffer:
            channel = self.buffer[guild_id][BufferKey.CHANNEL]
            voice_client = self.buffer[guild_id][BufferKey.VOICE_CLIENT]
        else:
            channel = None
            voice_client = None
        self.buffer[guild_id] = {
            BufferKey.CHANNEL: channel,
            BufferKey.QUEUE: queue.Queue(),
            BufferKey.VOICE_CLIENT: voice_client,
        }

    async def _update_buffer(self, guild_id):
        _index = 0
        _tasks = []
        for s in self.list_queue(guild_id)[: self.buffer_limit]:
            if _index >= self.buffer_limit:
                break
            if s.stream is None:
                _tasks.append(s.fetch_buffer())
            _index = _index + 1

        if _tasks:
            await asyncio.gather(*_tasks)

    def _add_to_buffer(self, guild_id, song):
        self.buffer[guild_id][BufferKey.QUEUE].put(song)

    def _has_buffer(self, guild_id):
        return guild_id in self.buffer

    def _has_item_in_buffer(self, guild_id):
        return self.buffer[guild_id][BufferKey.QUEUE].qsize() > 0

    def _is_playing(self, guild_id):
        return (
            self.buffer[guild_id][BufferKey.VOICE_CLIENT] is not None
            and self.buffer[guild_id][BufferKey.VOICE_CLIENT].is_playing()
        )

    async def play(self, guild_id, song: QueuedSong):
        """Plays a file from the local filesystem"""
        if guild_id in self.buffer and BufferKey.QUEUE in self.buffer[guild_id]:
            self._add_to_buffer(guild_id, song)
            await self._update_buffer(guild_id)
        else:
            self._setup_buffer(guild_id)
            await self._play(song)

    def clear_buffer(self, guild_id):
        """Clears the Audio Buffer"""
        if self._has_buffer(guild_id):
            self.buffer.get(guild_id).pop(BufferKey.QUEUE, None)
            self.lastPlayed.pop(guild_id, None)

    def list_queue(self, guild_id):
        """lists audio queue"""
        if self._has_buffer(guild_id):
            if self.buffer[guild_id].get(BufferKey.QUEUE) is not None:
                return list(self.buffer[guild_id].get(BufferKey.QUEUE).queue)
        return []

    def stop(self, guild_id):
        """Stops current audio from playing"""
        if self._has_buffer(guild_id):
            vc = self.buffer[guild_id].get(BufferKey.VOICE_CLIENT)
            if vc is not None:
                vc.stop()

    async def leave(self, guild_id):
        if self._has_buffer(guild_id):
            vc = self.buffer[guild_id].get(BufferKey.VOICE_CLIENT)
            if vc is not None:
                await vc.disconnect()
        # Delete the now-playing embed (marks end of session)
        msg = self.now_playing_message.pop(guild_id, None)
        if msg is not None:
            try:
                await msg.delete()
            except discord.NotFound:
                pass
        self.clear_buffer(guild_id)
        self.current_song.pop(guild_id, None)
        self.play_start.pop(guild_id, None)
        self.paused_at.pop(guild_id, None)

    def pause(self, guild_id: int) -> None:
        """Pause playback and record the pause start time."""
        if not self._has_buffer(guild_id):
            return
        vc = self.buffer[guild_id].get(BufferKey.VOICE_CLIENT)
        if vc is not None and vc.is_playing():
            vc.pause()
            self.paused_at[guild_id] = datetime.now(UTC)

    def resume(self, guild_id: int) -> None:
        """Resume playback and adjust play_start so elapsed time stays accurate."""
        if not self._has_buffer(guild_id):
            return
        vc = self.buffer[guild_id].get(BufferKey.VOICE_CLIENT)
        if vc is None or not vc.is_paused():
            return
        paused_since = self.paused_at.pop(guild_id, None)
        if paused_since is not None and guild_id in self.play_start:
            pause_duration = datetime.now(UTC) - paused_since
            self.play_start[guild_id] = self.play_start[guild_id] + pause_duration
        vc.resume()

    def is_paused(self, guild_id: int) -> bool:
        """Return True if the guild is currently paused."""
        vc = self.buffer.get(guild_id, {}).get(BufferKey.VOICE_CLIENT)
        if vc is not None:
            return vc.is_paused()
        return self.paused_at.get(guild_id) is not None

    def get_elapsed(self, guild_id: int) -> float:
        """Return seconds elapsed since playback started, excluding any paused time."""
        start = self.play_start.get(guild_id)
        if start is None:
            return 0.0
        elapsed = (datetime.now(UTC) - start).total_seconds()
        paused_since = self.paused_at.get(guild_id)
        if paused_since is not None:
            elapsed -= (datetime.now(UTC) - paused_since).total_seconds()
        return max(0.0, elapsed)

    @_timeout_manager.before_loop
    async def _before_timeout_manager(self):
        self.bot.log.info("Timeout Manager: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @_queue_manager.before_loop
    async def _before_queue_manager(self):
        self.bot.log.info("Queue Manager: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()
