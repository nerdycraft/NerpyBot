import utils.format as fmt
from utils.audio import Audio, QueuedSong
from utils.checks import is_botmod, is_connected_to_voice
from utils.download import download, fetch_yt_infos
from utils.helpers import youtube
from utils.errors import NerpyException
from discord import Embed, Color
from discord.ext.commands import (
    GroupCog,
    hybrid_group,
    check,
    hybrid_command,
    bot_has_permissions,
)


@bot_has_permissions(send_messages=True)
class Music(GroupCog, Audio):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        super().__init__(bot)
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]
        self.queue = {}

    def cog_unload(self):
        self._queue_manager.cancel()
        self._timeout_manager.cancel()

    @hybrid_command(name="skip")
    async def _skip_audio(self, ctx):
        """skip current track"""
        self.bot.log.info(f"{ctx.guild.name} requesting skip!")
        self.stop(ctx.guild.id)

    @hybrid_group(name="queue")
    async def _queue(self, ctx):
        """Manage the Playlist Queue"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_queue.command(name="list")
    async def _list_queue(self, ctx):
        """list current items in queue"""
        queue = self.list_queue(ctx.guild.id)
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
                await ctx.send("Queue is empty.", ephemeral=True)

    @_queue.command(name="drop")
    @check(is_botmod)
    async def _drop_queue(self, ctx):
        """drop the playlist entirely"""
        self.stop(ctx.guild.id)
        self.clear_buffer(ctx.guild.id)
        self._clear_queue(ctx.guild.id)

    @hybrid_group(name="play")
    @check(is_connected_to_voice)
    async def _play_music(self, ctx):
        """Play your favorite Music from YouTube and many more!"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await ctx.message.add_reaction("🤓")
                await self._send_to_queue(ctx, args[1])

    @_play_music.command(name="song", hidden=True)
    @check(is_connected_to_voice)
    async def _play_song(self, ctx, song_url):
        """Play a Song from URL"""
        await ctx.defer()
        followup = ctx.interaction.followup
        await self._send_to_queue(ctx, song_url, followup)

    @_play_music.command(name="playlist")
    @check(is_connected_to_voice)
    async def _add_playlist(self, ctx, playlist_url):
        """Add an entire playlist to the Queue. Currently only YouTube is supported."""
        await ctx.message.add_reaction("🤓")
        await ctx.send("Please bear with me. This can take a while.")
        playlist_infos = fetch_yt_infos(playlist_url)

        if "_type" not in playlist_infos:
            await ctx.send("This is not a playlist. Please add a single video directly with the play command.")
            await ctx.send_help(ctx.command)
        else:
            playlist_entries = playlist_infos["entries"]
            for entry in playlist_entries:
                await self._send_to_queue(ctx, entry["webpage_url"])

    @_play_music.command(name="search", aliases=["find", "lookup"])
    @check(is_connected_to_voice)
    async def _search_music(self, ctx, *, query):
        """Search for music. Currently only YouTube is supported"""
        video_url = youtube(self.config["ytkey"], "url", query)
        if video_url is not None:
            await self._send_to_queue(ctx, video_url)
        else:
            await ctx.send("Your search did not yield any results.", ephemeral=True)

    async def _send_to_queue(self, ctx, video_url, followup=None):
        video_infos = fetch_yt_infos(video_url)

        if "_type" in video_infos and video_infos.get("_type") == "playlist":
            await ctx.send("Please use the playlist command for playlists.")
            await ctx.send_help(ctx.command)
        else:
            video_title = video_infos["title"]
            video_thumbnail = video_infos.get("thumbnails", [dict()])[0].get("url")
            self.bot.log.info(f'"{ctx.guild.name}" requesting "{video_title}" to play')
            emb = Embed(
                title="Added Song to Queue!",
                color=Color(value=int("0099ff", 16)),
                description=f"[{video_title}]({video_url})",
            )
            if video_thumbnail is not None:
                emb.set_thumbnail(url=video_thumbnail)

            song = QueuedSong(ctx.author.voice.channel, self._fetch, video_url, video_title)
            await self.play(ctx.guild.id, song)
            if ctx.interaction is not None:
                await followup.send(embed=emb)
            else:
                await ctx.send(embed=emb)

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    def _clear_queue(self, guild_id):
        """Clears the Audio Queue"""
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()

    @staticmethod
    def _fetch(song: QueuedSong):
        sound_data = download(song.fetch_data)
        song.stream = sound_data


async def setup(bot):
    await bot.add_cog(Music(bot))
