import io
import utils.format as fmt
from datetime import datetime
from utils.audio import QueuedSong
from utils.download import download
from utils.errors import NerpyException
from utils.checks import is_connected_to_voice
from models.tag import Tag, TagType, TagTypeConverter
from discord import app_commands
from discord.ext.commands import (
    GroupCog,
    check,
    hybrid_group,
    clean_content,
    bot_has_permissions,
)


@app_commands.guild_only()
@bot_has_permissions(send_messages=True)
class Tagging(GroupCog, group_name="tag"):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.queue = {}

    @hybrid_group()
    @check(is_connected_to_voice)
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
    async def create(self, ctx, name: clean_content, tag_type: TagTypeConverter, content: clean_content):
        """create tag content"""
        with self.bot.session_scope() as session:
            if Tag.exists(name, ctx.guild.id, session):
                ctx.send(f'tag "{name}" already exists!', ephemeral=True)

        async with ctx.typing():
            with self.bot.session_scope() as session:
                self.bot.log.info(f'creating tag "{ctx.guild.name}/{name}" started')
                _tag = Tag(
                    Name=name,
                    Author=str(ctx.author),
                    Type=tag_type,
                    CreateDate=datetime.utcnow(),
                    Count=0,
                    Volume=100,
                    GuildId=ctx.guild.id,
                )

                Tag.add(_tag, session)
                session.flush()

                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f'creating tag "{ctx.guild.name}/{name}" finished')
        await ctx.send(f'tag "{name}" created!', ephemeral=True)

    @tag.command()
    async def add(self, ctx, name: clean_content, content: clean_content):
        """add an entry to an existing tag"""
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                ctx.send(f'tag "{name}" doesn\'t exists!', ephemeral=True)

        async with ctx.typing():
            with self.bot.session_scope() as session:
                _tag = Tag.get(name, ctx.guild.id, session)
                self._add_tag_entries(session, _tag, content)

            self.bot.log.info(f'added entry to tag "{ctx.guild.name}/{name}".')
        await ctx.send(f'Entry added to tag "{name}"!', ephemeral=True)

    @tag.command()
    async def volume(self, ctx, name: clean_content, vol):
        """adjust the volume of a sound tag"""
        self.bot.log.info(f'set volume of "{name}" to {vol} from {ctx.guild.id}')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                ctx.send(f'tag "{name}" doesn\'t exist!', ephemeral=True)

        with self.bot.session_scope() as session:
            _tag = Tag.get(name, ctx.guild.id, session)
            _tag.Volume = vol
        await ctx.send(f'changed volume of "{name}" to {vol}.', ephemeral=True)

    @tag.command()
    async def delete(self, ctx, name: clean_content):
        """delete a tag?"""
        self.bot.log.info(f'trying to delete "{name}" from "{ctx.guild.id}"')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, ctx.guild.id, session):
                ctx.send(f'tag "{name}" doesn\'t exist!', ephemeral=True)

            Tag.delete(name, ctx.guild.id, session)
        await ctx.send(f'tag "{name}" deleted!', ephemeral=True)

    @tag.command()
    async def list(self, ctx):
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

    @tag.command()
    async def info(self, ctx, name: clean_content):
        """information about the tag"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            await ctx.send(fmt.box(str(t)))

    @tag.command()
    async def raw(self, ctx, name: clean_content):
        """raw tag data"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, ctx.guild.id, session)
            msg = f"==== {t.Name} ====\n\n"

            for entry in t.entries.all():
                msg += entry.TextContent

            await ctx.send(fmt.box(msg))

    async def _send(self, ctx, tag_name):
        self.bot.log.info(f'{ctx.guild.name} requesting "{tag_name}" tag')
        with self.bot.session_scope() as session:
            _tag = Tag.get(tag_name, ctx.guild.id, session)
            if _tag is None:
                raise NerpyException(f'I searched everywhere, but could not find a Tag called "{tag_name}"!')

            if TagType(_tag.Type) is TagType.sound:
                song = QueuedSong(ctx.author.voice.channel, self._fetch, tag_name)
                await self.bot.audio.play(ctx.guild.id, song)
            else:
                random_entry = _tag.get_random_entry()
                await ctx.send(random_entry.TextContent)

    def _fetch(self, song: QueuedSong):
        with self.bot.session_scope() as session:
            _tag = Tag.get(song.fetch_data, song.channel.guild.id, session)
            random_entry = _tag.get_random_entry()

            song.stream = io.BytesIO(random_entry.ByteContent)
            song.volume = _tag.Volume

    @staticmethod
    def _add_tag_entries(session, _tag, entry):
        if _tag.Type == TagType.text.value or _tag.Type == TagType.url.value:
            _tag.add_entry(entry, session)
        elif _tag.Type is TagType.sound.value:
            _tag.add_entry(entry, session, byt=download(entry))


async def setup(bot):
    await bot.add_cog(Tagging(bot))
