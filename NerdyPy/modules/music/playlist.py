# -*- coding: utf-8 -*-

import asyncio

from discord import Interaction, app_commands
from discord.ext.commands import Cog

from sqlalchemy import func, insert as sa_insert

from models.music import Playlist, PlaylistEntry
from modules.music.audio import QueueMixin, QueuedSong
from utils.cache import build_name_choices, cached_autocomplete, invalidate_autocomplete
from utils.checks import is_connected_to_voice
from utils.cog import NerpyBotCog
from modules.music.download import fetch_yt_infos
from utils.strings import get_string


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True, speak=True)
class MusicPlaylist(NerpyBotCog, QueueMixin, Cog):
    """Playlist save/load management."""

    playlist = app_commands.Group(name="playlist", description="Manage your saved playlists", guild_only=True)

    def __init__(self, bot):
        super().__init__(bot)
        self.audio = self.bot.audio
        self._background_tasks: set[asyncio.Task] = set()

    # ── Autocomplete helpers ───────────────────────────────────────────────

    async def _ac_playlist_name(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for playlist name from the user's saved playlists."""
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        def _fetch():
            with self.bot.session_scope() as session:
                return [p.Name for p in Playlist.get_by_user(guild_id, user_id, session)]

        return build_name_choices(await cached_autocomplete(("playlists", guild_id, user_id), _fetch), current)

    async def _ac_playlist_url(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for song URL within a named playlist (reads sibling `name` field)."""
        name = interaction.namespace.name
        if not name:
            return []
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                return []
            entries = PlaylistEntry.get_by_playlist(pl.Id, session)
        return [
            app_commands.Choice(name=e.Title[:100], value=e.Url)
            for e in entries
            if current.lower() in e.Title.lower() or current.lower() in e.Url.lower()
        ][:25]

    async def _ac_queue_url(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for song URL from the current queue and recent history."""
        candidates: list[QueuedSong] = []
        current_song = self.audio.current_song.get(interaction.guild_id)
        if current_song:
            candidates.append(current_song)
        candidates.extend(self.audio.list_queue(interaction.guild_id))
        candidates.extend(reversed(list(self.audio.history.get(interaction.guild_id, []))))
        seen: set[str] = set()
        choices: list[app_commands.Choice[str]] = []
        for s in candidates:
            if s.fetch_data in seen:
                continue
            seen.add(s.fetch_data)
            label = (s.title or s.fetch_data)[:100]
            if current.lower() in label.lower() or current.lower() in s.fetch_data.lower():
                choices.append(app_commands.Choice(name=label, value=s.fetch_data))
            if len(choices) >= 25:
                break
        return choices

    # ── Playlist commands ──────────────────────────────────────────────────

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
        invalidate_autocomplete(("playlists", interaction.guild_id, interaction.user.id))
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
        header = get_string(lang, "music.playlist.list_header")
        await interaction.followup.send(f"\U0001f4c2 **{header}**\n{lines}", ephemeral=True)

    @playlist.command(name="show")
    @app_commands.describe(name="Playlist name to display")
    @app_commands.autocomplete(name=_ac_playlist_name)
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
    @app_commands.autocomplete(name=_ac_playlist_name, url=_ac_queue_url)
    async def _playlist_add(self, interaction: Interaction, name: str, url: str):
        """Add a song to one of your playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        try:
            info = await asyncio.to_thread(fetch_yt_infos, url)
        except Exception:
            await interaction.followup.send(get_string(lang, "music.play.fetch_error"), ephemeral=True)
            return
        title = info.get("title", url)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            duplicate = (
                session.query(PlaylistEntry).filter(PlaylistEntry.PlaylistId == pl.Id, PlaylistEntry.Url == url).count()
            )
            if duplicate:
                await interaction.followup.send(get_string(lang, "music.playlist.already_in_playlist"), ephemeral=True)
                return
            max_pos = session.query(func.max(PlaylistEntry.Position)).filter(PlaylistEntry.PlaylistId == pl.Id).scalar()
            position = (max_pos + 1) if max_pos is not None else 0
            session.add(PlaylistEntry(PlaylistId=pl.Id, Url=url, Title=title, Position=position))
        await interaction.followup.send(
            get_string(lang, "music.playlist.added_song", title=title, name=name), ephemeral=True
        )

    @playlist.command(name="save")
    @app_commands.describe(
        name="Name for the playlist",
        count="Number of recently played songs to save (omit to save current queue)",
    )
    @app_commands.autocomplete(name=_ac_playlist_name)
    async def _playlist_save(self, interaction: Interaction, name: str, count: int = None):
        """Save the current queue (or last N played songs) as a playlist."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)

        if count is not None:
            history = list(self.audio.history.get(interaction.guild_id, []))
            available = len(history)
            if available < count:
                await interaction.followup.send(
                    get_string(lang, "music.playlist.history_insufficient", available=available, count=count),
                    ephemeral=True,
                )
                return
            songs = history[-count:]
        else:
            songs = self.audio.list_queue(interaction.guild_id)

        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                pl = Playlist(
                    GuildId=interaction.guild_id,
                    UserId=interaction.user.id,
                    Name=name,
                )
                session.add(pl)
                session.flush()
            else:
                session.query(PlaylistEntry).filter(PlaylistEntry.PlaylistId == pl.Id).delete()
                session.flush()

            entries = [
                {"PlaylistId": pl.Id, "Url": song.fetch_data, "Title": song.title or song.fetch_data, "Position": pos}
                for pos, song in enumerate(songs)
            ]
            if entries:
                session.execute(sa_insert(PlaylistEntry), entries)

        invalidate_autocomplete(("playlists", interaction.guild_id, interaction.user.id))
        await interaction.followup.send(
            get_string(lang, "music.playlist.saved", count=len(songs), name=name), ephemeral=True
        )

    @playlist.command(name="remove")
    @app_commands.describe(name="Playlist name", url="Song URL to remove")
    @app_commands.autocomplete(name=_ac_playlist_name, url=_ac_playlist_url)
    async def _playlist_remove(self, interaction: Interaction, name: str, url: str):
        """Remove a song from one of your playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            deleted = PlaylistEntry.delete_by_url(pl.Id, url, session)
            if deleted == 0:
                await interaction.followup.send(get_string(lang, "music.playlist.song_not_found"), ephemeral=True)
                return
        await interaction.followup.send(get_string(lang, "music.playlist.removed"), ephemeral=True)

    @playlist.command(name="delete")
    @app_commands.describe(name="Playlist name to delete")
    @app_commands.autocomplete(name=_ac_playlist_name)
    async def _playlist_delete(self, interaction: Interaction, name: str):
        """Delete one of your playlists and all its songs."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            session.delete(pl)
        invalidate_autocomplete(("playlists", interaction.guild_id, interaction.user.id))
        await interaction.followup.send(get_string(lang, "music.playlist.deleted", name=name), ephemeral=True)

    @playlist.command(name="load")
    @app_commands.check(is_connected_to_voice)
    @app_commands.describe(name="Playlist name to queue")
    @app_commands.autocomplete(name=_ac_playlist_name)
    async def _playlist_load(self, interaction: Interaction, name: str):
        """Queue all songs from one of your saved playlists."""
        await interaction.response.defer(ephemeral=True)
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            pl = Playlist.get_by_name(interaction.guild_id, interaction.user.id, name, session)
            if pl is None:
                await interaction.followup.send(get_string(lang, "music.playlist.not_found", name=name), ephemeral=True)
                return
            entries = PlaylistEntry.get_by_playlist(pl.Id, session)

        if not entries:
            await interaction.followup.send(get_string(lang, "music.playlist.load_empty", name=name), ephemeral=True)
            return

        await interaction.followup.send(get_string(lang, "music.playlist.loading"), ephemeral=True)
        task = asyncio.create_task(self._load_saved_playlist(interaction, entries))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _load_saved_playlist(self, interaction: Interaction, entries: list) -> None:
        """Background task: re-fetch yt-dlp info for each saved entry (needed for video_id) and enqueue."""
        try:
            for entry in entries:
                if interaction.user.voice is None:
                    break
                try:
                    info = await asyncio.to_thread(fetch_yt_infos, entry.Url)
                except Exception:
                    continue
                await self._enqueue(interaction, entry.Url, info)
        except Exception as e:
            self.bot.log.error(f"[{interaction.guild_id}]: saved playlist load failed mid-stream: {e}")
