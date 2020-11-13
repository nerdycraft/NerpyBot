import io
import datetime
import utils.format as fmt
from random import randint
from pydub import AudioSegment
from utils.audio import QueuedSong
from utils.download import download
from utils.errors import NerpyException
from utils.database import session_scope
from models.tag import Tag, TagType, TagTypeConverter
from discord.ext.commands import (
    Cog,
    group,
    clean_content,
    bot_has_permissions,
)


class Tagging(Cog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

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

    # noinspection PyMethodMayBeStatic
    def _add_tag_entries(self, session, _tag, content):
        for entry in content:
            if _tag.Type == TagType.text.value or _tag.Type == TagType.url.value:
                _tag.add_entry(entry, session)
            elif _tag.Type is TagType.sound.value:
                _tag.add_entry(entry, session, byt=download(entry))

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
                await self.bot.audio.play(ctx.guild.id, song)
            else:
                await self.bot.sendc(ctx, entry.TextContent)

            _tag.Count += 1
            session.flush()


def setup(bot):
    bot.add_cog(Tagging(bot))
