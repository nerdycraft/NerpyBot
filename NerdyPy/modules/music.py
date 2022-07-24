import io
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
    command,
    bot_has_permissions,
)


class Music(Cog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]

    @command(name="skip")
    async def _skip_audio(self, ctx):
        """skip current track"""
        self.bot.log.info(f"{ctx.guild.name} requesting skip!")
        self.bot.audio.stop(ctx.guild.id)

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
        msg = ""
        _index = 0

        if queue is not None:
            for t in queue:
                msg += f"\n# Position {_index} #\n- "
                msg += f"{t.title}"
                _index = _index + 1

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            if page:
                await self.bot.sendc(ctx, fmt.box(page, "md"))
            else:
                await self.bot.sendc(ctx, fmt.box("Queue is empty."))

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
                await ctx.message.add_reaction("🤓")
                await self._send_to_queue(ctx, args[1])

    @_play_music.command(name="playlist")
    @bot_has_permissions(send_messages=True)
    async def _add_playlist(self, ctx, playlist_url):
        await ctx.message.add_reaction("🤓")
        await self.bot.sendc(ctx, "Please bear with me. This can take a while.")
        playlist_infos = fetch_yt_infos(playlist_url)

        if "_type" not in playlist_infos:
            await self.bot.sendc(
                ctx, "This is not a playlist. Please add a single video directly with the play command."
            )
            await ctx.send_help(ctx.command)
        else:
            playlist_entries = playlist_infos["entries"]
            for entry in playlist_entries:
                await self._send_to_queue(ctx, entry["webpage_url"])

    @_play_music.command(name="search", aliases=["find", "lookup"])
    @bot_has_permissions(send_messages=True)
    async def _search_music(self, ctx, *, query):
        """Search for music. Currently only Youtube is supported"""
        video_url = youtube(self.config["ytkey"], "url", query)
        if video_url is not None:
            await self._send_to_queue(ctx, video_url)
        else:
            await self.bot.sendc(ctx, "Your search did not yield any results.")

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    async def _send_to_queue(self, ctx, video_url):
        if ctx.author.voice is None:
            raise NerpyException("Not connected to a voice channel.")
        if not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
            raise NerpyException("Missing permission to connect to channel.")

        video_infos = fetch_yt_infos(video_url)

        if "_type" in video_infos:
            await self.bot.sendc(ctx, "Please use the playlist command for playlists.")
            await ctx.send_help(ctx.command)
        else:
            video_title = video_infos["title"]
            video_thumbnail = video_infos["thumbnails"][0]["url"]
            self.bot.log.info(f"{ctx.guild.name} requesting {video_title} to play")
            emb = Embed(
                title="Added Song to Queue!",
                color=Color(value=int("0099ff", 16)),
                description=f"[{video_title}]({video_url})",
            )
            emb.set_thumbnail(url=video_thumbnail)

            # song = QueuedSong(self.bot.get_channel(606539392319750170), volume, self._fetch)
            song = QueuedSong(ctx.author.voice.channel, self._fetch, video_url, video_title)
            await self.bot.audio.play(ctx.guild.id, song)
            await self.bot.sendc(ctx, "", emb)

    def _fetch(self, song: QueuedSong):
        sound_data = download(song.fetch_data, self.bot.debug)
        song.stream = io.BytesIO(sound_data)

    def _clear_queue(self, guild_id):
        """Clears the Audio Queue"""
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()


def setup(bot):
    bot.add_cog(Music(bot))
