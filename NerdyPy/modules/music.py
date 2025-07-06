# -*- coding: utf-8 -*-

from discord import Embed, Color, Interaction
from discord.app_commands import command, guild_only
from discord.ext.commands import (
    GroupCog,
    hybrid_group,
    check,
    hybrid_command,
    bot_has_permissions,
    has_permissions,
    Context,
)

from utils import format as fmt
from utils.audio import QueuedSong
from utils.checks import is_connected_to_voice
from utils.download import download, fetch_yt_infos
from utils.errors import NerpyException
from utils.helpers import youtube, send_hidden_message


@guild_only()
@bot_has_permissions(send_messages=True, speak=True)
class Music(GroupCog):
    """Command group for sound and text tags"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]
        self.queue = {}
        self.audio = self.bot.audio

    @hybrid_command(name="skip")
    async def _skip_audio(self, ctx: Context):
        """skip current track"""
        self.bot.log.info(f"{ctx.guild.name} requesting skip!")
        self.audio.stop(ctx.guild.id)
        if isinstance(ctx, Interaction):
            await ctx.followup.send("Skipped current track.")

    @command(name="stop")
    async def _stop_playing_audio(self, ctx: Context):
        """bot stops playing audio"""
        self.audio.stop(ctx.guild.id)
        self._clear_queue(ctx.guild.id)
        if isinstance(ctx, Interaction):
            await ctx.followup.send("Stopped playing audio.")

    @hybrid_group(name="queue")
    async def _queue(self, ctx: Context):
        """Manage the Playlist Queue"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_queue.command(name="list")
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

    @_queue.command(name="drop")
    @has_permissions(mute_members=True)
    async def _drop_queue(self, ctx: Context):
        """drop the playlist entirely"""
        self.audio.stop(ctx.guild.id)
        self._clear_queue(ctx.guild.id)
        if isinstance(ctx, Interaction):
            await ctx.followup.send("Cleared the queue and stopped playing audio.")

    @hybrid_group(name="play")
    @check(is_connected_to_voice)
    async def _play_music(self, ctx: Context):
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
    async def _play_song(self, ctx: Context, song_url):
        """Play a Song from URL"""
        await ctx.defer()
        followup = ctx.interaction.followup
        await self._send_to_queue(ctx, song_url, followup)

    @_play_music.command(name="playlist")
    @check(is_connected_to_voice)
    async def _add_playlist(self, ctx: Context, playlist_url):
        """Add an entire playlist to the Queue. Currently only YouTube is supported."""
        await ctx.message.add_reaction("🤓")
        await ctx.send("Please bear with me. This can take a while.")
        playlist_infos = fetch_yt_infos(playlist_url)

        if "_type" not in playlist_infos:
            await send_hidden_message(
                ctx, "This is not a playlist. Please add a single video directly with the play command."
            )
        else:
            playlist_entries = playlist_infos["entries"]
            for entry in playlist_entries:
                await self._send_to_queue(ctx, entry["webpage_url"])

    @_play_music.command(name="search", aliases=["find", "lookup"])
    @check(is_connected_to_voice)
    async def _search_music(self, ctx: Context, *, query):
        """Search for music. Currently only YouTube is supported"""
        video_url = youtube(self.config["ytkey"], "url", query)
        if video_url is not None:
            await self._send_to_queue(ctx, video_url)
        else:
            await send_hidden_message(ctx, "Your search did not yield any results.")

    async def _send_to_queue(self, ctx: Context, video_url, followup=None):
        video_infos = fetch_yt_infos(video_url)

        if "_type" in video_infos and video_infos.get("_type") == "playlist":
            await ctx.send("Please use the playlist command for playlists.")
            await ctx.send_help(ctx.command)
        else:
            video_title = video_infos["title"]
            video_thumbnail = video_infos.get("thumbnails", [dict()])[0].get("url")
            stream_url = video_infos.get("url", video_infos.get("webpage_url"))
            self.bot.log.info(f'"{ctx.guild.name}" requesting "{video_title}" to play')
            emb = Embed(
                title="Added Song to Queue!",
                color=Color(value=int("0099ff", 16)),
                description=f"[{video_title}]({video_url})",
            )
            if video_thumbnail is not None:
                emb.set_thumbnail(url=video_thumbnail)

            song = QueuedSong(ctx.author.voice.channel, self._fetch, stream_url, video_title)
            if ctx.interaction is not None:
                await followup.send(embed=emb)
            else:
                await ctx.send(embed=emb)
            await self.audio.play(ctx.guild.id, song)

    def _has_queue(self, guild_id):
        return guild_id in self.queue

    def _clear_queue(self, guild_id):
        """Clears the Audio Queue"""
        self.audio.clear_buffer(guild_id)
        if self._has_queue(guild_id):
            self.queue[guild_id].clear()

    @staticmethod
    def _fetch(song: QueuedSong):
        song.stream = download(song.fetch_data, song.title)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Music(bot))
