# -*- coding: utf-8 -*-

from datetime import UTC, datetime
from io import BytesIO

from discord import FFmpegOpusAudio
from discord.app_commands import command, guild_only, rename
from discord.ext.commands import (
    Cog,
    Context,
    bot_has_permissions,
    check,
    clean_content,
    has_permissions,
    hybrid_group,
)
from models.tagging import Tag, TagType, TagTypeConverter

import utils.format as fmt
from utils.audio import QueuedSong
from utils.checks import is_connected_to_voice
from utils.download import download
from utils.errors import NerpyException
from utils.helpers import send_hidden_message


@guild_only()
@bot_has_permissions(send_messages=True)
class Tagging(Cog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.queue = {}
        self.audio = self.bot.audio

    @hybrid_group(name="tag", fallback="get", aliases=["t"])
    @check(is_connected_to_voice)
    async def _tag(self, ctx: Context, name: str):
        """sound and text tags"""
        await self._send_to_queue(ctx, name)

    @_tag.command(name="skip", hidden=True)
    async def _skip_audio(self, ctx: Context):
        """skip current track"""
        self.bot.log.info(f"{ctx.guild.name} requesting skip!")
        self.audio.stop(ctx.guild.id)

    @command(name="stop")
    async def _stop_playing_audio(self, ctx: Context):
        """bot stops playing audio [bot-moderator]"""
        await self.audio.leave(ctx.guild.id)

    @_tag.group(name="queue", hidden=True)
    async def _queue(self, ctx: Context):
        """Manage the Playlist Queue"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_queue.command(name="list", hidden=True)
    async def _list_queue(self, ctx: Context):
        """list current items in queue"""
        queue = self.audio.list_queue(ctx.guild.id)
        msg = ""
        _index = 0

        if queue is not None:
            for t in queue:
                msg += f"\n# Position {_index} #\n- "
                msg += f"{t.title}"
                _index = _index + 1

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            if page:
                await ctx.send(fmt.box(page, "md"))
            else:
                await send_hidden_message(ctx, "Queue is empty.")

    @_queue.command(name="drop", hidden=True)
    @has_permissions(mute_members=True)
    async def _drop_queue(self, ctx: Context):
        """drop the playlist entirely"""
        self.audio.stop(ctx.guild.id)
        self.audio.clear_buffer(ctx.guild.id)
        self._clear_queue(ctx.guild.id)
        await send_hidden_message(ctx, "Queue dropped.")

    @_tag.command(name="create")
    @rename(tag_type="type")
    async def _tag_create(self, ctx: Context, name: str, tag_type: TagTypeConverter, content: clean_content) -> None:
        """
        Create Tags.

        Parameters
        ----------
        ctx
        name: str
            The name of your Tag.
        tag_type: Literal["sound", "text", "url"]
            One of sound, text or url.
        content: clean_content
            The content of your Tag. (Allowed is text or a URL for sound tags)
        """
        with self.bot.session_scope() as session:
            if Tag.exists(name, ctx.guild.id, session):
                await send_hidden_message(ctx, f'tag "{name}" already exists!')

        async with ctx.typing():
            with self.bot.session_scope() as session:
                self.bot.log.info(f'creating tag "{ctx.guild.name}/{name}" started')
                _tag = Tag(
                    Name=name,
                    Author=str(ctx.author),
                    Type=tag_type,
                    CreateDate=datetime.now(UTC),
                    Count=0,
                    Volume=100,
                    GuildId=ctx.guild.id,
                )

                Tag.add(_tag, session)
                session.flush()

                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f'creating tag "{ctx.guild.name}/{name}" finished')
        await send_hidden_message(ctx, f'tag "{name}" created!')

    @_tag.command(name="add")
    async def _tag_add(self, ctx: Context, name: clean_content, content: clean_content):
        """add an entry to an existing tag"""
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                await send_hidden_message(ctx, f'tag "{name}" doesn\'t exists!')
                return

        async with ctx.typing():
            with self.bot.session_scope() as session:
                _tag = Tag.get(name, ctx.guild.id, session)
                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f'added entry to tag "{ctx.guild.name}/{name}".')
        await send_hidden_message(ctx, f'Entry added to tag "{name}"!')

    @_tag.command(name="volume")
    async def _tag_volume(self, ctx: Context, name: clean_content, vol: int):
        """adjust the volume of a sound tag"""
        if not 0 <= vol <= 200:
            await send_hidden_message(ctx, "Volume must be between 0 and 200.")
            return
        self.bot.log.info(f'set volume of "{name}" to {vol} from {ctx.guild.id}')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                await send_hidden_message(ctx, f'tag "{name}" doesn\'t exist!')

        with self.bot.session_scope() as session:
            _tag = Tag.get(name, ctx.guild.id, session)
            _tag.Volume = vol
        await send_hidden_message(ctx, f'changed volume of "{name}" to {vol}.')

    @_tag.command(name="delete")
    async def _tag_delete(self, ctx: Context, name: clean_content):
        """delete a tag?"""
        self.bot.log.info(f'trying to delete "{name}" from "{ctx.guild.id}"')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                await send_hidden_message(ctx, f'tag "{name}" doesn\'t exist!')

            Tag.delete(name, ctx.guild.id, session)
        await send_hidden_message(ctx, f'tag "{name}" deleted!')

    @_tag.command(name="list")
    async def _tag_list(self, ctx: Context):
        """a list of all available tags"""
        self.bot.log.info("list")
        with self.bot.session_scope() as session:
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
                await ctx.send(fmt.box(page, "md"))

    @_tag.command(name="info")
    async def _tag_info(self, ctx: Context, name: clean_content):
        """information about the tag"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            await ctx.send(fmt.box(str(t)))

    @_tag.command(name="raw")
    async def _tag_raw(self, ctx: Context, name: clean_content):
        """raw tag data"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            msg = f"==== {t.Name} ====\n\n"

            for entry in t.entries.all():
                msg += entry.TextContent

            await ctx.send(fmt.box(msg))

    async def _send_to_queue(self, ctx: Context, tag_name):
        self.bot.log.info(f'{ctx.guild.name} requesting "{tag_name}" tag')
        with self.bot.session_scope() as session:
            _tag = Tag.get(tag_name, ctx.guild.id, session)
            if _tag is None:
                raise NerpyException(f'I searched everywhere, but could not find a Tag called "{tag_name}"!')

            if TagType(_tag.Type) is TagType.sound:
                song = QueuedSong(ctx.author.voice.channel, self._fetch, tag_name, tag_name)
                await self.audio.play(ctx.guild.id, song)
            else:
                random_entry = _tag.get_random_entry()
                await ctx.send(random_entry.TextContent)

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    def _clear_queue(self, guild_id):
        """Clears the Audio Queue"""
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()

    def _fetch(self, song: QueuedSong):
        with self.bot.session_scope() as session:
            _tag = Tag.get(song.fetch_data, song.channel.guild.id, session)
            random_entry = _tag.get_random_entry()

            volume_multiplier = _tag.Volume / 100

            # Create FFmpegOpusAudio with volume adjustment
            data = BytesIO(random_entry.ByteContent)
            song.stream = FFmpegOpusAudio(data, pipe=True, options=f"-filter:a volume={volume_multiplier}")

    @staticmethod
    def _add_tag_entries(session, _tag, entry):
        if _tag.Type == TagType.text.value or _tag.Type == TagType.url.value:
            _tag.add_entry(entry, session)
        elif _tag.Type is TagType.sound.value:
            _tag.add_entry(entry, session, byt=download(entry, tag=True))


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Tagging(bot))
