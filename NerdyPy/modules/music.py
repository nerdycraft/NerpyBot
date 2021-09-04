import io
import collections
import utils.format as fmt
from utils.audio import QueuedSong
from utils.checks import is_botmod
from utils.download import download, fetch_yt_infos
from utils.helpers import youtube
from utils.errors import NerpyException
from discord import Embed, Color
from discord.ext.commands import (
    Cog,
    group,
    check,
    bot_has_permissions,
)


class Music(Cog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.queue = {}
        self.config = self.bot.config["search"]

    @group(name="queue")
    async def queue(self, ctx):
        """Manage the Playlist Queue"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @queue.command(name="list")
    @bot_has_permissions(send_messages=True)
    async def _list_sound_queue(self, ctx):
        """list current items in queue"""
        queue = self.bot.audio.list_queue(ctx.guild.id)
        _index = 0

        emb = Embed(
            title="Playlist",
            color=Color(value=int("0099ff", 16)),
            description="Current Playlist",
        )

        if queue is not None:
            for t in queue:
                emb.add_field(name="ID", value=str(_index), inline=True)
                emb.add_field(name="Title", value=t.title, inline=True)
                emb.add_field(name="\u200b", value="\u200b", inline=False)
                _index = _index + 1

        await self.bot.sendc(ctx, "", emb)

    @queue.command(name="remove", aliases=["rm", "del", "delete"])
    async def _remove_sound_from_queue(self, ctx, queue_id):
        """remove sound from queue"""
        return

    @queue.command(name="drop")
    @check(is_botmod)
    async def _drop_queue(self, ctx):
        """drop the playlist entirely"""
        self.bot.audio.clear_buffer(ctx.guild.id)
        self._clear_queue(ctx.guild.id)
        self.bot.audio.stop(ctx.guild.id)

    @group(invoke_without_command=True, name="play")
    @bot_has_permissions(send_messages=True)
    async def _play_music(self, ctx):
        """Play your favorite Music from Youtube and many more!"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await self._send_to_queue(ctx, args[1])

    @_play_music.command(name="search", aliases=["find", "lookup"])
    @bot_has_permissions(send_messages=True)
    async def _search_music(self, ctx, *, query):
        """Search for music. Currently only Youtube is supported"""
        video = youtube(self.config["ytkey"], "url", query)

        if video is not None:
            await self._send_to_queue(ctx, video)
        else:
            await self.bot.sendc(ctx, "Your search did not yield any results.")

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    async def _send_to_queue(self, ctx, url):
        if ctx.author.voice is None:
            raise NerpyException("Not connected to a voice channel.")
        if not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
            raise NerpyException("Missing permission to connect to channel.")

        title = fetch_yt_infos(url)
        volume = 100

        self.bot.log.info(f"{ctx.guild.name} requesting {title} to play")
        if ctx.guild.id not in self.queue:
            self.queue[ctx.guild.id] = collections.deque()

        self.queue[ctx.guild.id].append(url)
        await self.bot.sendc(ctx, fmt.box(f"{title} added to queue!"))

        # song = QueuedSong(self.bot.get_channel(606539392319750170), volume, self._fetch)
        song = QueuedSong(ctx.author.voice.channel, volume, self._fetch)
        await self.bot.audio.play(ctx.guild.id, song)

    def _fetch(self, song: QueuedSong):
        sound_data = download(self.queue[song.channel.guild.id].popleft(), self.bot.debug)
        song.stream = io.BytesIO(sound_data)

    def _clear_queue(self, guild_id):
        """Clears the Audio Queue"""
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()


def setup(bot):
    bot.add_cog(Music(bot))
