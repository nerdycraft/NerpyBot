import enum
import io
import discord
import asyncio
import datetime
import collections
import utils.format as fmt
from random import randint
from datetime import datetime
from pydub import AudioSegment

from utils.checks import is_botmod
from utils.download import download
from utils.errors import NerpyException
from utils.database import session_scope
from models.tag import Tag, TagType, TagTypeConverter
from discord.ext.commands import (
    Cog,
    group,
    clean_content,
    bot_has_permissions, command, check,
)


class QueueKey(enum.Enum):
    """Keys for the guild queue"""

    CHANNEL = 1
    QUEUE = 2
    VOICE_CLIENT = 3


class QueuedSong:
    """Models Class for Queued Songs"""

    def __init__(self, stream, channel: discord.VoiceChannel, vol):
        self.stream = stream
        self.channel = channel
        self.volume = vol


class Audio(Cog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.queue = {}
        self.doLoop = True
        self.lastPlayed = {}

        self.task_queue = self.bot.loop.create_task(self._queue_manager())
        self.task_timeout = self.bot.loop.create_task(self._timeout_manager())

    def cog_unload(self):
        self.task_queue.cancel()
        self.task_timeout.cancel()

    async def _play(self, song):
        await self._join_channel(song.channel)
        source = discord.PCMVolumeTransformer(discord.PCMAudio(song.stream))
        source.volume = song.volume / 100
        song.channel.guild.voice_client.play(
            source,
            after=lambda e: self.bot.log.error("Player error: %s" % e) if e else None,
        )

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
        self.queue[guild_id] = {
            QueueKey.CHANNEL: None,
            QueueKey.QUEUE: collections.deque(),
            QueueKey.VOICE_CLIENT: None,
        }

    def _add_to_queue(self, guild_id, song):
        self.queue[guild_id][QueueKey.QUEUE].append(song)

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    def _has_item_in_queue(self, guild_id):
        return len(self.queue[guild_id][QueueKey.QUEUE]) > 0

    def _is_playing(self, guild_id):
        return self.queue[guild_id][QueueKey.VOICE_CLIENT].is_playing()

    async def _timeout_manager(self):
        while self.doLoop:
            last = dict(self.lastPlayed)
            for guild_id in last:
                delta = datetime.now() - last[guild_id]
                if delta.total_seconds() > 600:
                    client = self.bot.get_guild(guild_id).voice_client
                    if client is not None:
                        if not client.is_playing():
                            await self._leave(guild_id)
                        else:
                            self.lastPlayed[guild_id] = datetime.now()
            await asyncio.sleep(1)

    async def _queue_manager(self):
        while self.doLoop:
            await asyncio.sleep(2)
            last = dict(self.lastPlayed)
            for guild_id in last:
                if self._has_queue(guild_id) and self._has_item_in_queue(guild_id) and not self._is_playing(
                        guild_id):
                    queued_song = self.queue[guild_id][QueueKey.QUEUE].popleft()
                    await self._play(queued_song)

    async def play(self, guild_id, song: QueuedSong, force=False):
        """Plays a file from the local filesystem"""
        if guild_id in self.queue and force is False:
            self._add_to_queue(guild_id, song)
        else:
            self._setup_queue(guild_id)
            await self._play(song)

    def _stop(self, guild_id):
        if self._has_queue(guild_id):
            self.queue[guild_id][QueueKey.VOICE_CLIENT].stop()

    async def _leave(self, guild_id):
        await self.queue[guild_id][QueueKey.VOICE_CLIENT].disconnect()
        self.queue.pop(guild_id)
        self.lastPlayed.pop(guild_id)

    # noinspection PyMethodMayBeStatic
    def _add_tag_entries(self, session, _tag, content):
        for entry in content:
            if _tag.Type == TagType.text.value or _tag.Type == TagType.url.value:
                _tag.add_entry(entry, session)
            elif _tag.Type is TagType.sound.value:
                _tag.add_entry(entry, session, byt=download(entry))

    @group(invoke_without_command=True, aliases=["t"])
    async def tag(self, ctx):
        """sound and text tags"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await self._send(ctx, args[1])

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def create(
        self,
        ctx,
        name: clean_content,
        tag_type: TagTypeConverter,
        *content: clean_content,
    ):
        """create tag content"""
        if Tag.exists(name, ctx.guild.id):
            raise NerpyException("tag already exists!")

        async with ctx.typing():
            with session_scope() as session:
                self.bot.log.info(f"creating tag {ctx.guild.name}/{name} started")
                _tag = Tag(
                    Name=name,
                    Author=str(ctx.author),
                    Type=tag_type,
                    CreateDate=datetime.datetime.utcnow(),
                    Count=0,
                    Volume=100,
                    GuildId=ctx.guild.id,
                )

                Tag.add(_tag, session)
                session.flush()

                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f"creating tag {ctx.guild.name}/{name} finished")
        await self.bot.sendc(ctx, f"tag {name} created!")

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def add(self, ctx, name: clean_content, *content: clean_content):
        """add an entry to an existing tag"""
        if not Tag.exists(name, ctx.guild.id):
            raise NerpyException("tag doesn't exists!")

        async with ctx.typing():
            with session_scope() as session:
                _tag = Tag.get(name, ctx.guild.id, session)
                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f"added entry to tag {ctx.guild.name}/{name}.")
        await self.bot.sendc(ctx, f"Entry added to tag {name}!")

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def volume(self, ctx, name: clean_content, vol):
        """adjust the volume of a sound tag (WIP)"""
        if not Tag.exists(name, ctx.guild.id):
            raise NerpyException("tag doesn't exist!")

        with session_scope() as session:
            _tag = Tag.get(name, ctx.guild.id, session)
            _tag.Volume = vol
            session.flush()

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def delete(self, ctx, name: clean_content):
        """delete a tag?"""
        self.bot.log.info(f"trying to delete {name} from {ctx.guild.id}")
        if not Tag.exists(name, ctx.guild.id):
            raise NerpyException("tag doesn't exist!")

        Tag.delete(name, ctx.guild.id)
        await self.bot.sendc(ctx, "tag deleted!")

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def list(self, ctx):
        """a list of all available tags"""
        self.bot.log.info("list")
        with session_scope() as session:
            tags = Tag.get_all_from_guild(ctx.guild.id, session)

            msg = ""
            last_header = "^"
            for t in tags:
                if t.Name[0] is not last_header:
                    last_header = t.Name[0]
                    msg += f"\n# {last_header} #\n- "
                msg += f"[{t.Name}]"
                typ = TagType(t.Type).name.upper()[0]
                msg += f"({typ}|{t.entries.count()}) - "

            for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
                await self.bot.sendc(ctx, fmt.box(page, "md"))

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def info(self, ctx, name: clean_content):
        """information about the tag"""
        with session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            await self.bot.sendc(ctx, fmt.box(str(t)))

    @tag.command()
    @bot_has_permissions(send_messages=True)
    async def raw(self, ctx, name: clean_content):
        """raw tag data"""
        with session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            msg = f"==== {t.Name} ====\n\n"

            for entry in t.entries.all():
                msg += entry.TextContent

            await self.bot.sendc(ctx, fmt.box(msg))

    async def _send(self, ctx, tag_name):
        self.bot.log.info(f"{ctx.guild.name} requesting {tag_name} tag")
        with session_scope() as session:
            _tag = Tag.get(tag_name, ctx.guild.id, session)
            if _tag is None:
                raise NerpyException("No such tag found")

            entries = _tag.entries.all()

            entry = entries[randint(0, (len(entries) - 1))]
            if TagType(_tag.Type) is TagType.sound:
                if ctx.author.voice is None:
                    raise NerpyException("Not connected to a voice channel.")
                if not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
                    raise NerpyException("Missing permission to connect to channel.")

                sound = AudioSegment.from_file(io.BytesIO(entry.ByteContent))
                if sound.channels != 2:
                    sound = sound.set_channels(2)
                if sound.frame_rate < 40000:
                    sound = sound.set_frame_rate(44100)

                song = QueuedSong(io.BytesIO(sound.raw_data), ctx.author.voice.channel, _tag.Volume)
                await self.play(ctx.guild.id, song)
            else:
                await self.bot.sendc(ctx, entry.TextContent)

            _tag.Count += 1
            session.flush()

    @command()
    @check(is_botmod)
    async def stop(self, ctx):
        """stop sound playing [bot-moderator]"""
        self._stop(ctx.guild.id)

    @command()
    @check(is_botmod)
    async def leave(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self._leave(ctx.guild.id)


def setup(bot):
    bot.add_cog(Audio(bot))
