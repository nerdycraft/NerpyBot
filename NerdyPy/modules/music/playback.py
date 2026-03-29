# -*- coding: utf-8 -*-

import asyncio

import discord
from discord import Interaction, app_commands
from discord.ext import tasks
from discord.ext.commands import Cog

from modules.music.audio import QueuedSong, QueueMixin
from modules.music.download import fetch_yt_infos
from modules.music.views import NowPlayingView, build_now_playing_embed
from utils.checks import can_leave_voice, can_stop_playback, is_connected_to_voice
from utils.cog import NerpyBotCog
from utils.helpers import register_before_loop, youtube
from utils.strings import get_string


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True, speak=True)
class MusicPlayback(NerpyBotCog, QueueMixin, Cog):
    """Music playback commands and progress tracking."""

    def __init__(self, bot):
        super().__init__(bot)
        self.config = self.bot.config["music"]
        self.queue = {}
        self.audio = self.bot.audio
        self._background_tasks: set[asyncio.Task] = set()
        register_before_loop(bot, self._progress_updater, "Progress Updater")

    async def cog_load(self):
        self.audio._on_song_start_hook = self._handle_song_start
        self._progress_updater.start()

    async def cog_unload(self):
        self._progress_updater.cancel()
        self.audio._on_song_start_hook = None
        await super().cog_unload()

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
            except (discord.NotFound, discord.Forbidden):
                self.audio.now_playing_message.pop(guild_id, None)
                try:
                    msg = await song.channel.send(embed=emb, view=view)
                    self.audio.now_playing_message[guild_id] = msg
                except discord.HTTPException as e:
                    self.bot.log.error(f"[{guild_id}]: Failed to re-send now-playing embed: {e}")
            except discord.HTTPException as e:
                self.bot.log.warning(f"[{guild_id}]: Transient error editing now-playing embed: {e}")

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
            except discord.HTTPException as e:
                self.bot.log.warning(f"[{guild_id}]: Transient error updating progress embed: {e}")

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

        try:
            info = await asyncio.to_thread(fetch_yt_infos, url)
        except Exception:
            await interaction.followup.send(get_string(lang, "music.play.fetch_error"), ephemeral=True)
            return

        if info.get("_type") == "playlist":
            entries = info.get("entries", [])
            if not entries:
                await interaction.followup.send(
                    get_string(lang, "music.play.added_playlist", count=0, title=info.get("title", "Playlist")),
                    ephemeral=True,
                )
                return
            await interaction.followup.send(get_string(lang, "music.playlist.loading"), ephemeral=True)
            self._create_background_task(self._load_playlist_entries(interaction, entries))
            return

        enqueued = await self._enqueue(interaction, url, info)
        if enqueued:
            title = info.get("title", url)
            await interaction.followup.send(get_string(lang, "music.play.added", title=title), ephemeral=True)

    async def _load_playlist_entries(self, interaction: Interaction, entries: list) -> None:
        """Background task: fetch info and enqueue each playlist entry without blocking interactions."""
        try:
            for entry in entries:
                if interaction.user.voice is None:
                    break
                entry_url = entry.get("webpage_url", entry.get("url", ""))
                if not entry_url:
                    continue
                try:
                    entry_info = await asyncio.to_thread(fetch_yt_infos, entry_url)
                except Exception:
                    continue
                await self._enqueue(interaction, entry_url, entry_info)
        except Exception as e:
            self.bot.log.error(f"[{interaction.guild_id}]: playlist load failed mid-stream: {e}")

    # ── Voice control commands ────────────────────────────────────────────

    @app_commands.command(name="stop")
    @app_commands.guild_only()
    @app_commands.check(can_stop_playback)
    async def _bot_stop_playing(self, interaction: Interaction):
        """bot stops playing audio [bot-moderator]"""
        self.bot.audio.stop_and_clear(interaction.guild.id)
        await interaction.response.send_message("\U0001f44d", ephemeral=True)

    @app_commands.command(name="leave")
    @app_commands.guild_only()
    @app_commands.check(can_leave_voice)
    async def _bot_leave_channel(self, interaction: Interaction):
        """bot leaves the voice channel [bot-moderator]"""
        await self.bot.audio.leave(interaction.guild.id)
        await interaction.response.send_message("\U0001f44b", ephemeral=True)
