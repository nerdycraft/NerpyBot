# -*- coding: utf-8 -*-

from discord import Color, Embed, Interaction, app_commands
from discord.ext.commands import GroupCog

from utils.audio import QueuedSong, QueueMixin
from utils.checks import can_stop_playback, is_connected_to_voice
from utils.cog import NerpyBotCog
from utils.download import download, fetch_yt_infos
from utils.helpers import error_context, youtube
from utils.strings import get_guild_language, get_string


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True, speak=True)
class Music(NerpyBotCog, QueueMixin, GroupCog):
    """Command group for sound and text tags"""

    queue_group = app_commands.Group(name="queue", description="Manage the Playlist Queue")
    play = app_commands.Group(name="play", description="Play music from YouTube and more")

    def __init__(self, bot):
        super().__init__(bot)
        self.config = self.bot.config["music"]
        self.queue = {}
        self.audio = self.bot.audio

    def _lang(self, guild_id: int) -> str:
        with self.bot.session_scope() as session:
            return get_guild_language(guild_id, session)

    @app_commands.command(name="skip")
    @app_commands.check(can_stop_playback)
    async def _skip_audio(self, interaction: Interaction):
        """skip current track"""
        self.audio.stop(interaction.guild.id)
        lang = self._lang(interaction.guild_id)
        await interaction.response.send_message(get_string(lang, "music.skip.success"), ephemeral=True)

    @queue_group.command(name="list")
    async def _list_queue(self, interaction: Interaction):
        """list current items in queue"""
        await self._send_queue_list(interaction)

    @queue_group.command(name="drop")
    @app_commands.checks.has_permissions(mute_members=True)
    async def _drop_queue(self, interaction: Interaction):
        """drop the playlist entirely"""
        self._stop_and_clear_queue(interaction.guild.id)
        lang = self._lang(interaction.guild_id)
        await interaction.response.send_message(get_string(lang, "music.queue.drop_success"), ephemeral=True)

    @play.command(name="song")
    @app_commands.check(is_connected_to_voice)
    async def _play_song(self, interaction: Interaction, song_url: str):
        """Play a Song from URL"""
        await interaction.response.defer()
        lang = self._lang(interaction.guild_id)
        await self._send_to_queue(interaction, song_url, lang)

    @play.command(name="playlist")
    @app_commands.check(is_connected_to_voice)
    async def _add_playlist(self, interaction: Interaction, playlist_url: str):
        """Add an entire playlist to the Queue. Currently only YouTube is supported."""
        await interaction.response.defer()
        lang = self._lang(interaction.guild_id)
        playlist_infos = fetch_yt_infos(playlist_url)

        if "_type" not in playlist_infos:
            await interaction.followup.send(
                get_string(lang, "music.playlist.not_a_playlist"),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(get_string(lang, "music.playlist.loading"))
            playlist_entries = playlist_infos["entries"]
            for entry in playlist_entries:
                await self._send_to_queue(interaction, entry["webpage_url"], lang)

    @play.command(name="search")
    @app_commands.check(is_connected_to_voice)
    async def _search_music(self, interaction: Interaction, query: str):
        """Search for music. Currently only YouTube is supported"""
        await interaction.response.defer()
        lang = self._lang(interaction.guild_id)
        video_url = youtube(self.config["ytkey"], "url", query)
        if video_url is not None:
            await self._send_to_queue(interaction, video_url, lang)
        else:
            await interaction.followup.send(get_string(lang, "music.search.no_results"), ephemeral=True)

    async def _send_to_queue(self, interaction: Interaction, video_url, lang: str):
        video_infos = fetch_yt_infos(video_url)

        if "_type" in video_infos and video_infos.get("_type") == "playlist":
            await interaction.followup.send(get_string(lang, "music.playlist.use_playlist_command"))
            return

        video_title = video_infos["title"]
        video_idn = video_infos["id"]
        video_thumbnail = video_infos.get("thumbnails", [dict()])[0].get("url")
        self.bot.log.info(f'{error_context(interaction)}: requesting "{video_title}" to play')
        emb = Embed(
            title=f"\U0001f3b5 {get_string(lang, 'music.queue.added')}",
            color=Color(0x0099FF),
            description=f"[{video_title}]({video_url})",
        )
        if video_thumbnail is not None:
            emb.set_thumbnail(url=video_thumbnail)

        song = QueuedSong(interaction.user.voice.channel, self._fetch, video_url, video_title, video_idn)
        await interaction.followup.send(embed=emb)
        await self.audio.play(interaction.guild.id, song)

    @staticmethod
    def _fetch(song: QueuedSong):
        song.stream = download(song.fetch_data, video_id=song.idn)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Music(bot))
