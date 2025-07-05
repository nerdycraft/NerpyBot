# -*- coding: utf-8 -*-
"""
Handling Audio Transmission to discord api
"""

import asyncio
import enum
import io
import queue
from datetime import datetime

from discord import PCMVolumeTransformer, FFmpegOpusAudio, VoiceChannel, PCMAudio
from discord.ext import tasks


class BufferKey(enum.Enum):
    """Keys for the guild queue"""

    CHANNEL = 1
    QUEUE = 2
    VOICE_CLIENT = 3


class QueuedSong:
    """Models Class for Queued Songs"""

    def __init__(self, channel: VoiceChannel, fetcher, fetch_data, title=None):
        self.stream = None
        self.title = title
        self.channel = channel
        self.volume = 100
        self._fetcher = fetcher
        self.fetch_data = fetch_data

    def fetch_buffer(self):
        self._fetcher(self)
        if isinstance(self.stream, io.BytesIO):
            self.convert_audio()
            return
        if not isinstance(self.stream, FFmpegOpusAudio):
            sound = self.stream
            self.stream = FFmpegOpusAudio(sound)
            return

    def convert_audio(self):
        sound = AudioSegment.from_file(self.stream)
        if sound.channels != 2:
            sound = sound.set_channels(2)
        if sound.frame_rate != 48000:
            sound = sound.set_frame_rate(48000)
        self.stream = io.BytesIO(sound.raw_data)


class Audio:
    """Handles all audio transmission to the discord api"""

    def __init__(self, bot):
        self.bot = bot
        self.buffer = {}
        self.lastPlayed = {}
        self.buffer_limit = self.bot.config["audio"]["buffer_limit"]

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

    @tasks.loop(seconds=5)
    async def _queue_manager(self):
        last = dict(self.lastPlayed)
        for guild_id in last:
            if self._has_buffer(guild_id) and self._has_item_in_buffer(guild_id) and not self._is_playing(guild_id):
                queued_song = self.buffer[guild_id][BufferKey.QUEUE].get()
                await self._play(queued_song)
                self._update_buffer(guild_id)

    async def setup_loops(self):
        self._queue_manager.start()
        self._timeout_manager.start()

    async def _play(self, song):
        if song.stream is None:
            song.fetch_buffer()
        await self._join_channel(song.channel)
        await asyncio.sleep(2)
        if isinstance(song.stream, FFmpegOpusAudio) and song.stream.is_opus():
            source = song.stream
        else:
            source = PCMVolumeTransformer(PCMAudio(song.stream))
            source.volume = song.volume / 100
        self.bot.log.debug(f"Playing Song {song.title}")
        song.channel.guild.voice_client.play(
            source,
            after=lambda e: self.bot.log.error(f"Player error: {e}") if e else None,
        )

        self.lastPlayed[song.channel.guild.id] = datetime.now()

    async def _join_channel(self, channel: VoiceChannel):
        if channel.guild.voice_client is not None and channel.guild.voice_client.is_connected():
            if self.buffer[channel.guild.id][BufferKey.CHANNEL].id != channel.id:
                self.bot.log.debug(f"Moving to channel {channel}")
                await channel.guild.voice_client.move_to(channel)
        else:
            self.bot.log.debug(f"Connecting to channel {channel}")
            vc = await channel.connect()
            self.buffer[channel.guild.id][BufferKey.VOICE_CLIENT] = vc

        self.buffer[channel.guild.id][BufferKey.CHANNEL] = channel

    def _setup_buffer(self, guild_id):
        self.lastPlayed[guild_id] = datetime.now()
        self.buffer[guild_id] = {
            BufferKey.CHANNEL: None,
            BufferKey.QUEUE: queue.Queue(),
            BufferKey.VOICE_CLIENT: None,
        }

    def _update_buffer(self, guild_id):
        _index = 0
        for s in self.list_queue(guild_id):
            if _index >= self.buffer_limit:
                break
            if s.stream is None:
                s.fetch_buffer()
            _index = _index + 1

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
            self._update_buffer(guild_id)
        else:
            self._setup_buffer(guild_id)
            await self._play(song)

    def clear_buffer(self, guild_id):
        """Clears the Audio Buffer"""
        if self._has_buffer(guild_id):
            self.buffer.get(guild_id).pop(BufferKey.QUEUE)
            self.lastPlayed.pop(guild_id)

    def list_queue(self, guild_id):
        """lists audio queue"""
        if self._has_buffer(guild_id):
            if self.buffer[guild_id].get(BufferKey.QUEUE) is not None:
                return list(self.buffer[guild_id].get(BufferKey.QUEUE).queue)

    def stop(self, guild_id):
        """Stops current audio from playing"""
        if self._has_buffer(guild_id):
            self.buffer[guild_id][BufferKey.VOICE_CLIENT].stop()

    async def leave(self, guild_id):
        await self.buffer[guild_id][BufferKey.VOICE_CLIENT].disconnect()
        self.clear_buffer(guild_id)

    @_timeout_manager.before_loop
    async def _before_timeout_manager(self):
        self.bot.log.info("Timeout Manager: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @_queue_manager.before_loop
    async def _before_queue_manager(self):
        self.bot.log.info("Queue Manager: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()
