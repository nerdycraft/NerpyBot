# -*- coding: utf-8 -*-
"""Tests for NowPlayingView helpers — progress bar and embed builder."""

import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.views.music import build_progress_bar, build_now_playing_embed, NowPlayingView
from utils.strings import load_strings


class TestBuildProgressBar:
    def test_at_zero_elapsed(self):
        bar = build_progress_bar(0, 300)
        assert bar.startswith("`[")
        assert "0:00 / 5:00" in bar

    def test_at_half_elapsed(self):
        bar = build_progress_bar(150, 300)
        assert "2:30 / 5:00" in bar

    def test_at_full_elapsed(self):
        bar = build_progress_bar(300, 300)
        assert "5:00 / 5:00" in bar

    def test_no_duration_returns_empty(self):
        bar = build_progress_bar(10, 0)
        assert bar == ""

    def test_elapsed_beyond_duration_clamped(self):
        """Should not crash or show > 100% progress."""
        bar = build_progress_bar(400, 300)
        assert "5:00 / 5:00" in bar

    def test_bar_contains_arrow(self):
        bar = build_progress_bar(60, 300)
        assert ">" in bar

    def test_minutes_and_seconds_formatting(self):
        bar = build_progress_bar(65, 125)
        assert "1:05 / 2:05" in bar


class TestBuildNowPlayingEmbed:
    @pytest.fixture(autouse=True)
    def _load_locale_strings(self):
        load_strings()

    def _make_song(self, title="Test Song", duration=300, requester=None, thumbnail=None):
        song = MagicMock()
        song.title = title
        song.fetch_data = "https://youtube.com/watch?v=test"
        song.duration = duration
        song.requester = requester
        song.thumbnail = thumbnail
        return song

    def test_embed_has_title(self):
        song = self._make_song()
        emb = build_now_playing_embed(song, 60, "en")
        assert isinstance(emb, discord.Embed)
        assert emb.title == "Now Playing"

    def test_embed_has_progress_bar_when_duration(self):
        song = self._make_song(duration=300)
        emb = build_now_playing_embed(song, 60, "en")
        assert any(f.value for f in emb.fields if ">" in f.value or "=" in f.value)

    def test_embed_no_progress_bar_when_no_duration(self):
        song = self._make_song(duration=0)
        emb = build_now_playing_embed(song, 0, "en")
        assert len(emb.fields) == 0

    def test_embed_footer_when_requester_set(self):
        member = MagicMock()
        member.display_name = "Alice"
        song = self._make_song(requester=member)
        emb = build_now_playing_embed(song, 0, "en")
        assert emb.footer.text is not None
        assert "Alice" in emb.footer.text

    def test_embed_no_footer_without_requester(self):
        song = self._make_song(requester=None)
        emb = build_now_playing_embed(song, 0, "en")
        assert not emb.footer.text

    def test_embed_thumbnail_when_set(self):
        song = self._make_song(thumbnail="https://img.youtube.com/thumb.jpg")
        emb = build_now_playing_embed(song, 0, "en")
        assert emb.thumbnail.url == "https://img.youtube.com/thumb.jpg"

    def test_embed_no_thumbnail_when_none(self):
        song = self._make_song(thumbnail=None)
        emb = build_now_playing_embed(song, 0, "en")
        assert not emb.thumbnail.url


def _make_view(audio=None):
    if audio is None:
        audio = MagicMock()
        audio.is_paused = MagicMock(return_value=False)
        audio.pause = MagicMock()
        audio.resume = MagicMock()
        audio.stop = MagicMock()
        audio.clear_buffer = MagicMock()
        audio.leave = AsyncMock()
        audio.list_queue = MagicMock(return_value=[])
    return NowPlayingView(audio)


def _make_interaction(in_channel=True, guild_id=1):
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    bot_vc = MagicMock()
    bot_vc.channel = MagicMock()
    interaction.guild = MagicMock()
    interaction.guild.voice_client = bot_vc

    if in_channel:
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = bot_vc.channel
    else:
        interaction.user = MagicMock()
        interaction.user.voice = None
    return interaction


class TestNowPlayingViewPermissions:
    @pytest.fixture(autouse=True)
    def _load_locale_strings(self):
        load_strings()

    @pytest.mark.asyncio
    async def test_skip_blocked_when_not_in_channel(self):
        view = _make_view()
        interaction = _make_interaction(in_channel=False)
        await view.skip.callback(interaction)
        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "voice channel" in msg.lower()

    @pytest.mark.asyncio
    async def test_skip_defers_when_in_channel(self):
        view = _make_view()
        interaction = _make_interaction(in_channel=True)
        await view.skip.callback(interaction)
        interaction.response.defer.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_resume_blocked_when_not_in_channel(self):
        view = _make_view()
        interaction = _make_interaction(in_channel=False)
        await view.pause_resume.callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_resume_pauses_when_playing(self):
        audio = MagicMock()
        audio.is_paused = MagicMock(return_value=False)
        audio.pause = MagicMock()
        view = NowPlayingView(audio)
        interaction = _make_interaction(in_channel=True)
        await view.pause_resume.callback(interaction)
        audio.pause.assert_called_once_with(interaction.guild_id)

    @pytest.mark.asyncio
    async def test_pause_resume_resumes_when_paused(self):
        audio = MagicMock()
        audio.is_paused = MagicMock(return_value=True)
        audio.resume = MagicMock()
        view = NowPlayingView(audio)
        interaction = _make_interaction(in_channel=True)
        await view.pause_resume.callback(interaction)
        audio.resume.assert_called_once_with(interaction.guild_id)

    @pytest.mark.asyncio
    async def test_stop_calls_leave(self):
        audio = MagicMock()
        audio.leave = AsyncMock()
        view = NowPlayingView(audio)
        interaction = _make_interaction(in_channel=True)
        await view.stop.callback(interaction)
        audio.leave.assert_called_once_with(interaction.guild_id)

    @pytest.mark.asyncio
    async def test_stop_blocked_when_not_in_channel(self):
        view = _make_view()
        interaction = _make_interaction(in_channel=False)
        await view.stop.callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_in_wrong_channel_is_blocked(self):
        """User has voice state but is in a different channel than the bot."""
        view = _make_view()
        interaction = _make_interaction(in_channel=True)  # sets up same channel
        # Now put the user in a different channel
        interaction.user.voice.channel = MagicMock()  # different object = different channel
        await view.skip.callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_queue_empty(self):
        audio = MagicMock()
        audio.list_queue = MagicMock(return_value=[])
        view = NowPlayingView(audio)
        interaction = _make_interaction()
        await view.show_queue.callback(interaction)
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args
        assert args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_show_queue_non_empty(self):
        audio = MagicMock()
        song1 = MagicMock()
        song1.title = "Song One"
        song2 = MagicMock()
        song2.title = "Song Two"
        audio.list_queue = MagicMock(return_value=[song1, song2])
        view = NowPlayingView(audio)
        interaction = _make_interaction()
        await view.show_queue.callback(interaction)
        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "Song One" in msg
        assert "Song Two" in msg

    @pytest.mark.asyncio
    async def test_show_queue_caps_at_10(self):
        """More than 10 songs should show '… and N more'."""
        audio = MagicMock()
        songs = [MagicMock(title=f"Song {i}") for i in range(15)]
        audio.list_queue = MagicMock(return_value=songs)
        view = NowPlayingView(audio)
        interaction = _make_interaction()
        await view.show_queue.callback(interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "5 more" in msg
