"""
Handling Audio Transmission to discord api
"""
import enum
import asyncio
import discord
import collections
from datetime import datetime

#if not discord.opus.is_loaded():
    #discord.opus.load_opus('libopus-0.dll')


class QueueKey(enum.Enum):
    """Keys for the guild queue"""
    CHANNEL = 1
    QUEUE = 2
    VOICE_CLIENT = 3


class QueuedSong:
    """Models Class for Queued Songs"""

    def __init__(self, stream, channel: discord.VoiceChannel, volume):
        self.stream = stream
        self.channel = channel
        self.volume = volume


class Audio:
    """Handles all audio transmission to the discord api"""

    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.doLoop = True
        self.lastPlayed = {}

        self.bot.loop.create_task(self._queue_manager())
        self.bot.loop.create_task(self._timeout_manager())

    async def _play(self, song):
        await self._join_channel(song.channel)
        source = discord.PCMVolumeTransformer(discord.PCMAudio(song.stream))
        source.volume = song.volume / 100
        song.channel.guild.voice_client.play(source,
                                             after=lambda e: self.bot.log.error('Player error: %s' % e) if e else None)

        self.lastPlayed[song.channel.guild.id] = datetime.now()

    # noinspection PyUnresolvedReferences
    async def _join_channel(self, channel: discord.VoiceChannel):
        if channel.guild.voice_client is not None:
            if self.queue[channel.guild.id][QueueKey.CHANNEL].id != channel.id:
                await channel.guild.voice_client.move_to(channel)
        else:
            vc = await channel.connect()
            self.queue[channel.guild.id][QueueKey.VOICE_CLIENT] = vc

        self.queue[channel.guild.id][QueueKey.CHANNEL] = channel

    def _setup_queue(self, guild_id):
        self.lastPlayed[guild_id] = datetime.now()
        self.queue[guild_id] = {QueueKey.CHANNEL: None,
                                QueueKey.QUEUE: collections.deque(),
                                QueueKey.VOICE_CLIENT: None}

    def _add_to_queue(self, guild_id, song):
        self.queue[guild_id][QueueKey.QUEUE].append(song)

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    def _has_item_in_queue(self, guild_id):
        return len(self.queue[guild_id][QueueKey.QUEUE]) > 0

    def _is_playing(self, guild_id):
        return self.queue[guild_id][QueueKey.VOICE_CLIENT].is_playing()

    async def _timeout_manager(self):
        self.timeout_loop_running = True
        while self.doLoop:
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
            await asyncio.sleep(1)
        self.timeout_loop_running = False

    async def _queue_manager(self):
        self.queue_loop_running = True
        while self.doLoop:
            await asyncio.sleep(2)
            last = dict(self.lastPlayed)
            for guild_id in last:
                if self._has_queue(guild_id) and self._has_item_in_queue(guild_id) and not self._is_playing(guild_id):
                    queued_song = self.queue[guild_id][QueueKey.QUEUE].popleft()
                    await self._play(queued_song)
        self.queue_loop_running = False

    async def play(self, guild_id, song: QueuedSong, force=False):
        """Plays a file from the local filesystem"""
        if guild_id in self.queue and force is False:
            self._add_to_queue(guild_id, song)
        else:
            self._setup_queue(guild_id)
            await self._play(song)

    def stop(self, guild_id):
        if self._has_queue(guild_id):
            self.queue[guild_id][QueueKey.VOICE_CLIENT].stop()

    async def leave(self, guild_id):
        await self.queue[guild_id][QueueKey.VOICE_CLIENT].disconnect()
        self.queue.pop(guild_id)
        self.lastPlayed.pop(guild_id)

    async def rip_loop(self):
        self.doLoop = False
        while self.queue_loop_running:
            await asyncio.sleep(1)
        while self.timeout_loop_running:
            await asyncio.sleep(1)
