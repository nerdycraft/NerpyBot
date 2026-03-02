# -*- coding: utf-8 -*-

import asyncio

import discord
from discord import Color, Embed, Interaction, app_commands
from discord.ext import tasks
from discord.ext.commands import Cog

from models.music import Playlist, PlaylistEntry
from modules.views.music import NowPlayingView, build_now_playing_embed
from utils.audio import QueuedSong, QueueMixin
from utils.checks import can_stop_playback, is_connected_to_voice
from utils.cog import NerpyBotCog
from utils.download import download, fetch_yt_infos
from utils.helpers import error_context, youtube
from utils.strings import get_guild_language, get_string


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True, speak=True)
class Music(NerpyBotCog, QueueMixin, Cog):
    """Music playback and playlist management."""

    queue_group = app_commands.Group(name="queue", description="Manage the Playlist Queue")
    play = app_commands.Group(name="play", description="Play music from YouTube and more")
    playlist = app_commands.Group(name="playlist", description="Manage your saved playlists")

    def __init__(self, bot):
        super().__init__(bot)
        self.config = self.bot.config["music"]
        self.queue = {}
        self.audio = self.bot.audio

    async def cog_load(self):
        self.audio._on_song_start_hook = self._handle_song_start
        self._progress_updater.start()

    async def cog_unload(self):
        self._progress_updater.cancel()
        self.audio._on_song_start_hook = None

    def _lang(self, guild_id: int) -> str:
        with self.bot.session_scope() as session:
            return get_guild_language(guild_id, session)

    async def _handle_song_start(self, guild_id: int, song: QueuedSong) -> None:
        """Called by Audio._play() when a new song starts. Creates or updates the now-playing embed."""
        lang = self._lang(guild_id)
        elapsed = self.audio.get_elapsed(guild_id)
        emb = build_now_playing_embed(song, elapsed, lang)
        view = NowPlayingView(self.audio, lang)

        existing_msg = self.audio.now_playing_message.get(guild_id)
        if existing_msg is None:
            try:
                msg = await song.channel.send(embed=emb, view=view)
                self.audio.now_playing_message[guild_id] = msg
            except discord.HTTPException as e:
                self.bot.log.error(f"[{guild_id}]: Failed to send now-playing embed: {e}")
        else:
            try:
                await existing_msg.edit(embed=emb, view=view)
            except discord.NotFound:
                try:
                    msg = await song.channel.send(embed=emb, view=view)
                    self.audio.now_playing_message[guild_id] = msg
                except discord.HTTPException as e:
                    self.bot.log.error(f"[{guild_id}]: Failed to re-send now-playing embed: {e}")
                    self.audio.now_playing_message.pop(guild_id, None)

    @tasks.loop(seconds=10)
    async def _progress_updater(self):
        """Edit the now-playing embed for every active guild to update the progress bar."""
        for guild_id, msg in list(self.audio.now_playing_message.items()):
            if msg is None:
                continue
            if self.audio.is_paused(guild_id):
                continue
            song = self.audio.current_song.get(guild_id)
            if song is None:
                continue
            lang = self._lang(guild_id)
            elapsed = self.audio.get_elapsed(guild_id)
            emb = build_now_playing_embed(song, elapsed, lang)
            try:
                await msg.edit(embed=emb)
            except (discord.NotFound, discord.Forbidden):
                self.audio.now_playing_message.pop(guild_id, None)

    @_progress_updater.before_loop
    async def _before_progress_updater(self):
        self.bot.log.info("Progress Updater: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @app_commands.command(name="play")
    @app_commands.guild_only()
    @app_commands.check(is_connected_to_voice)
    @app_commands.describe(url="Song URL, playlist URL, or search query")
    async def _play(self, interaction: Interaction, url: str):
        """Play a song, playlist, or search YouTube. Joins your voice channel automatically."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)

        is_url = "://" in url
        if not is_url:
            found = youtube(self.config.get("ytkey", ""), "url", url)
            if found is None:
                await interaction.followup.send(get_string(lang, "music.play.not_found"), ephemeral=True)
                return
            url = found

        info = await asyncio.get_event_loop().run_in_executor(None, fetch_yt_infos, url)

        if info.get("_type") == "playlist":
            entries = info.get("entries", [])
            enqueued = 0
            for entry in entries:
                entry_url = entry.get("webpage_url", entry.get("url", ""))
                if not entry_url:
                    continue
                try:
                    entry_info = await asyncio.get_event_loop().run_in_executor(None, fetch_yt_infos, entry_url)
                except Exception:
                    continue
                if await self._enqueue(interaction, entry_url, entry_info):
                    enqueued += 1
            await interaction.followup.send(
                get_string(lang, "music.play.added_playlist", count=enqueued, title=info.get("title", "Playlist")),
                ephemeral=True,
            )
            return

        await self._enqueue(interaction, url, info)
        title = info.get("title", url)
        await interaction.followup.send(get_string(lang, "music.play.added", title=title), ephemeral=True)

    async def _enqueue(self, interaction: Interaction, url: str, info: dict) -> bool:
        """Build a QueuedSong from yt-dlp info and add it to the audio queue. Returns True on success."""
        if interaction.user.voice is None:
            return False
        title = info.get("title", url)
        idn = info.get("id")
        duration = info.get("duration")
        thumbnails = info.get("thumbnails") or []
        thumbnail_url = thumbnails[0].get("url") if thumbnails else None

        song = QueuedSong(
            channel=interaction.user.voice.channel,
            fetcher=self._fetch,
            fetch_data=url,
            title=title,
            idn=idn,
            duration=duration,
            requester=interaction.user,
            thumbnail=thumbnail_url,
        )
        self.bot.log.info(f'{error_context(interaction)}: requesting "{title}" to play')
        await self.audio.play(interaction.guild.id, song)
        return True

    @staticmethod
    def _fetch(song: QueuedSong):
        song.stream = download(song.fetch_data, video_id=song.idn)

    @playlist.command(name="create")
    @app_commands.describe(name="Name for the new playlist")
    async def _playlist_create(self, interaction: Interaction, name: str):
        """Create a new empty playlist."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            existing = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if existing is not None:
                await interaction.followup.send(
                    get_string(lang, "music.playlist.already_exists", name=name), ephemeral=True
                )
                return
            session.add(
                Playlist(
                    GuildId=interaction.guild_id,
                    UserId=interaction.user.id,
                    Name=name,
                )
            )
        await interaction.followup.send(get_string(lang, "music.playlist.created", name=name), ephemeral=True)

    @playlist.command(name="list")
    async def _playlist_list(self, interaction: Interaction):
        """Show your saved playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            playlists = Playlist.get_by_user(interaction.guild_id, interaction.user.id, session)
        if not playlists:
            await interaction.followup.send(get_string(lang, "music.playlist.list_empty"), ephemeral=True)
            return
        lines = "\n".join(f"• **{p.Name}**" for p in playlists)
        await interaction.followup.send(f"\U0001f4c2 **Your playlists**\n{lines}", ephemeral=True)

    @playlist.command(name="show")
    @app_commands.describe(name="Playlist name to display")
    async def _playlist_show(self, interaction: Interaction, name: str):
        """Show songs in one of your playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            entries = PlaylistEntry.get_by_playlist(pl.Id, session)
        if not entries:
            await interaction.followup.send(get_string(lang, "music.playlist.empty"), ephemeral=True)
            return
        lines = "\n".join(f"`{i}` [{e.Title}]({e.Url})" for i, e in enumerate(entries, 1))
        await interaction.followup.send(f"\U0001f3b5 **{name}**\n{lines}", ephemeral=True)

    @playlist.command(name="add")
    @app_commands.describe(name="Playlist name", url="Song URL to add")
    async def _playlist_add(self, interaction: Interaction, name: str, url: str):
        """Add a song to one of your playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        info = await asyncio.get_event_loop().run_in_executor(None, fetch_yt_infos, url)
        title = info.get("title", url)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            existing = PlaylistEntry.get_by_playlist(pl.Id, session)
            position = len(existing)
            session.add(PlaylistEntry(PlaylistId=pl.Id, Url=url, Title=title, Position=position))
        await interaction.followup.send(
            get_string(lang, "music.playlist.added_song", title=title, name=name), ephemeral=True
        )

    @playlist.command(name="remove")
    @app_commands.describe(name="Playlist name", url="Song URL to remove")
    async def _playlist_remove(self, interaction: Interaction, name: str, url: str):
        """Remove a song from one of your playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            PlaylistEntry.delete_by_url(pl.Id, url, session)
        await interaction.followup.send(get_string(lang, "music.playlist.removed"), ephemeral=True)

    # ---- old commands below — removed in Task 13 ----

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


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Music(bot))
