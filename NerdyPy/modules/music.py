# -*- coding: utf-8 -*-

from discord import Color, Embed, Interaction, app_commands
from discord.ext.commands import GroupCog

import utils.format as fmt
from utils.audio import QueuedSong, QueueMixin
from utils.checks import can_stop_playback, is_connected_to_voice
from utils.download import download, fetch_yt_infos
from utils.helpers import error_context, youtube


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True, speak=True)
class Music(QueueMixin, GroupCog):
    """Command group for sound and text tags"""

    queue_group = app_commands.Group(name="queue", description="Manage the Playlist Queue")
    play = app_commands.Group(name="play", description="Play music from YouTube and more")

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]
        self.queue = {}
        self.audio = self.bot.audio

    @app_commands.command(name="skip")
    @app_commands.check(can_stop_playback)
    async def _skip_audio(self, interaction: Interaction):
        """skip current track"""
        self.audio.stop(interaction.guild.id)
        await interaction.response.send_message("Skipped current track.", ephemeral=True)

    @queue_group.command(name="list")
    async def _list_queue(self, interaction: Interaction):
        """list current items in queue"""
        queue = self.audio.list_queue(interaction.guild.id)
        msg = ""
        _index = 0

        if queue is not None:
            for t in queue:
                msg += f"\n# Position {_index} #\n- "
                msg += f"{t.title}"
                _index = _index + 1

        if not msg:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return

        first = True
        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            if first:
                await interaction.response.send_message(fmt.box(page, "md"))
                first = False
            else:
                await interaction.followup.send(fmt.box(page, "md"))

    @queue_group.command(name="drop")
    @app_commands.checks.has_permissions(mute_members=True)
    async def _drop_queue(self, interaction: Interaction):
        """drop the playlist entirely"""
        self.audio.stop(interaction.guild.id)
        self._clear_queue(interaction.guild.id)
        await interaction.response.send_message("Cleared the queue and stopped playing audio.", ephemeral=True)

    @play.command(name="song")
    @app_commands.check(is_connected_to_voice)
    async def _play_song(self, interaction: Interaction, song_url: str):
        """Play a Song from URL"""
        await interaction.response.defer()
        await self._send_to_queue(interaction, song_url)

    @play.command(name="playlist")
    @app_commands.check(is_connected_to_voice)
    async def _add_playlist(self, interaction: Interaction, playlist_url: str):
        """Add an entire playlist to the Queue. Currently only YouTube is supported."""
        await interaction.response.defer()
        playlist_infos = fetch_yt_infos(playlist_url)

        if "_type" not in playlist_infos:
            await interaction.followup.send(
                "This is not a playlist. Please add a single video directly with the play command.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send("Please bear with me. This can take a while.")
            playlist_entries = playlist_infos["entries"]
            for entry in playlist_entries:
                await self._send_to_queue(interaction, entry["webpage_url"])

    @play.command(name="search")
    @app_commands.check(is_connected_to_voice)
    async def _search_music(self, interaction: Interaction, query: str):
        """Search for music. Currently only YouTube is supported"""
        await interaction.response.defer()
        video_url = youtube(self.config["ytkey"], "url", query)
        if video_url is not None:
            await self._send_to_queue(interaction, video_url)
        else:
            await interaction.followup.send("Your search did not yield any results.", ephemeral=True)

    async def _send_to_queue(self, interaction: Interaction, video_url):
        video_infos = fetch_yt_infos(video_url)

        if "_type" in video_infos and video_infos.get("_type") == "playlist":
            await interaction.followup.send("Please use the playlist command for playlists.")
            return

        video_title = video_infos["title"]
        video_idn = video_infos["id"]
        video_thumbnail = video_infos.get("thumbnails", [dict()])[0].get("url")
        self.bot.log.info(f'{error_context(interaction)}: requesting "{video_title}" to play')
        emb = Embed(
            title="Added Song to Queue!",
            color=Color(value=int("0099ff", 16)),
            description=f"[{video_title}]({video_url})",
        )
        if video_thumbnail is not None:
            emb.set_thumbnail(url=video_thumbnail)

        song = QueuedSong(interaction.user.voice.channel, self._fetch, video_url, video_title, video_idn)
        await interaction.followup.send(embed=emb)
        await self.audio.play(interaction.guild.id, song)

    def _clear_queue(self, guild_id: int) -> None:
        """Clears the Audio Queue and buffer"""
        self.audio.clear_buffer(guild_id)
        super()._clear_queue(guild_id)

    @staticmethod
    def _fetch(song: QueuedSong):
        song.stream = download(song.fetch_data, video_id=song.idn)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Music(bot))
