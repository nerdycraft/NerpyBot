# -*- coding: utf-8 -*-
"""Tests for utils/audio.py — QueuedSong and Audio state."""

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.audio import Audio, BufferKey, QueuedSong


class TestQueuedSong:
    def test_default_duration_is_none(self):
        song = QueuedSong(channel=MagicMock(), fetcher=MagicMock(), fetch_data="url", title="Song", idn="abc")
        assert song.duration is None

    def test_default_requester_is_none(self):
        song = QueuedSong(channel=MagicMock(), fetcher=MagicMock(), fetch_data="url")
        assert song.requester is None

    def test_duration_set(self):
        song = QueuedSong(channel=MagicMock(), fetcher=MagicMock(), fetch_data="url", duration=240)
        assert song.duration == 240

    def test_requester_set(self):
        member = MagicMock()
        song = QueuedSong(channel=MagicMock(), fetcher=MagicMock(), fetch_data="url", requester=member)
        assert song.requester is member


def _make_audio():
    bot = MagicMock()
    bot.config = {"audio": {"buffer_limit": 5}}
    bot.log = MagicMock()
    audio = Audio.__new__(Audio)
    audio.bot = bot
    audio.buffer = {}
    audio.lastPlayed = {}
    audio.buffer_limit = 5
    audio.current_song = {}
    audio.play_start = {}
    audio.paused_at = {}
    audio.now_playing_message = {}
    audio.history = defaultdict(lambda: deque(maxlen=50))
    audio._on_song_start_hook = None
    return audio


def _make_vc(is_paused=False, is_playing=True):
    vc = MagicMock()
    vc.is_paused = MagicMock(return_value=is_paused)
    vc.is_playing = MagicMock(return_value=is_playing)
    vc.pause = MagicMock()
    vc.resume = MagicMock()
    return vc


def _attach_vc(audio, guild_id, vc):
    audio.buffer[guild_id] = {
        BufferKey.VOICE_CLIENT: vc,
        BufferKey.CHANNEL: MagicMock(),
        BufferKey.QUEUE: MagicMock(),
    }


class TestAudioPauseResume:
    def test_pause_calls_vc_pause(self):
        audio = _make_audio()
        vc = _make_vc()
        _attach_vc(audio, 1, vc)
        audio.pause(1)
        vc.pause.assert_called_once()

    def test_pause_sets_paused_at(self):
        audio = _make_audio()
        _attach_vc(audio, 1, _make_vc())
        before = datetime.now(UTC)
        audio.pause(1)
        assert audio.paused_at.get(1) is not None
        assert audio.paused_at[1] >= before

    def test_resume_calls_vc_resume(self):
        audio = _make_audio()
        vc = _make_vc(is_paused=True)
        _attach_vc(audio, 1, vc)
        audio.paused_at[1] = datetime.now(UTC)
        audio.play_start[1] = datetime.now(UTC) - timedelta(seconds=30)
        audio.resume(1)
        vc.resume.assert_called_once()

    def test_resume_clears_paused_at(self):
        audio = _make_audio()
        _attach_vc(audio, 1, _make_vc(is_paused=True))
        audio.paused_at[1] = datetime.now(UTC) - timedelta(seconds=5)
        audio.play_start[1] = datetime.now(UTC) - timedelta(seconds=30)
        audio.resume(1)
        assert audio.paused_at.get(1) is None

    def test_resume_adjusts_play_start_for_pause_duration(self):
        """After resuming, get_elapsed() should not count paused time."""
        audio = _make_audio()
        _attach_vc(audio, 1, _make_vc(is_paused=True))
        now = datetime.now(UTC)
        audio.play_start[1] = now - timedelta(seconds=30)
        audio.paused_at[1] = now - timedelta(seconds=5)  # paused 5s ago
        audio.resume(1)
        elapsed = audio.get_elapsed(1)
        # Should be ~25s (30s total - 5s paused), not 30s
        assert 23 < elapsed < 28

    def test_is_paused_true_via_vc(self):
        audio = _make_audio()
        vc = _make_vc(is_paused=True)
        _attach_vc(audio, 1, vc)
        audio.paused_at[1] = datetime.now(UTC)
        assert audio.is_paused(1) is True

    def test_is_paused_false_when_not_set(self):
        audio = _make_audio()
        assert audio.is_paused(1) is False

    def test_is_paused_uses_vc_state_as_authority(self):
        """VC reports not-paused → is_paused returns False even if paused_at has a stale entry."""
        audio = _make_audio()
        vc = _make_vc(is_paused=False)
        _attach_vc(audio, 1, vc)
        audio.paused_at[1] = datetime.now(UTC)  # stale entry
        assert audio.is_paused(1) is False

    def test_get_elapsed_no_state(self):
        audio = _make_audio()
        assert audio.get_elapsed(1) == 0.0

    def test_get_elapsed_counts_from_play_start(self):
        audio = _make_audio()
        audio.play_start[1] = datetime.now(UTC) - timedelta(seconds=42)
        elapsed = audio.get_elapsed(1)
        assert 40 < elapsed < 45

    def test_get_elapsed_does_not_count_paused_time(self):
        """get_elapsed must freeze at the moment of pause — not keep ticking."""
        audio = _make_audio()
        now = datetime.now(UTC)
        audio.play_start[1] = now - timedelta(seconds=30)
        audio.paused_at[1] = now - timedelta(seconds=5)  # paused 5s ago
        elapsed = audio.get_elapsed(1)
        # 30s total wall time - 5s paused = ~25s
        assert 23 < elapsed < 28


class TestAudioPlayHook:
    @pytest.mark.asyncio
    async def test_play_sets_current_song(self):
        audio = _make_audio()
        guild_id = 1
        song = MagicMock()
        song.stream = MagicMock()  # pre-fetched, skip fetch_buffer
        song.channel = MagicMock()
        song.channel.connect = AsyncMock(return_value=MagicMock())
        song.channel.name = "voice"
        song.channel.id = 111
        song.channel.guild.id = guild_id
        song.channel.guild.name = "Test Guild"
        vc = MagicMock()
        vc.is_connected = MagicMock(return_value=True)
        vc.play = MagicMock()
        song.channel.guild.voice_client = vc
        audio.buffer[guild_id] = {
            BufferKey.VOICE_CLIENT: vc,
            BufferKey.CHANNEL: song.channel,
            BufferKey.QUEUE: MagicMock(),
        }
        audio.lastPlayed[guild_id] = datetime.now(UTC)

        await audio._play(song)

        assert audio.current_song.get(guild_id) is song
        assert audio.play_start.get(guild_id) is not None
        assert audio.paused_at.get(guild_id) is None

    @pytest.mark.asyncio
    async def test_play_appends_old_song_to_history(self):
        audio = _make_audio()
        guild_id = 1
        old_song = MagicMock()
        old_song.title = "Old Song"
        audio.current_song[guild_id] = old_song

        new_song = MagicMock()
        new_song.stream = MagicMock()
        new_song.channel = MagicMock()
        new_song.channel.connect = AsyncMock(return_value=MagicMock())
        new_song.channel.name = "voice"
        new_song.channel.id = 111
        new_song.channel.guild.id = guild_id
        new_song.channel.guild.name = "Test Guild"
        vc = MagicMock()
        vc.is_connected = MagicMock(return_value=True)
        vc.play = MagicMock()
        new_song.channel.guild.voice_client = vc
        audio.buffer[guild_id] = {
            BufferKey.VOICE_CLIENT: vc,
            BufferKey.CHANNEL: new_song.channel,
            BufferKey.QUEUE: MagicMock(),
        }
        audio.lastPlayed[guild_id] = datetime.now(UTC)

        await audio._play(new_song)

        assert old_song in audio.history[guild_id]

    @pytest.mark.asyncio
    async def test_play_calls_song_start_hook(self):
        audio = _make_audio()
        guild_id = 1
        hook_called = []

        async def fake_hook(gid, s):
            hook_called.append((gid, s))

        audio._on_song_start_hook = fake_hook

        song = MagicMock()
        song.stream = MagicMock()
        song.channel = MagicMock()
        song.channel.connect = AsyncMock(return_value=MagicMock())
        song.channel.name = "voice"
        song.channel.id = 111
        song.channel.guild.id = guild_id
        song.channel.guild.name = "Test Guild"
        vc = MagicMock()
        vc.is_connected = MagicMock(return_value=True)
        vc.play = MagicMock()
        song.channel.guild.voice_client = vc
        audio.buffer[guild_id] = {
            BufferKey.VOICE_CLIENT: vc,
            BufferKey.CHANNEL: song.channel,
            BufferKey.QUEUE: MagicMock(),
        }
        audio.lastPlayed[guild_id] = datetime.now(UTC)

        await audio._play(song)

        assert hook_called == [(guild_id, song)]


class TestAudioLeaveCleanup:
    @pytest.mark.asyncio
    async def test_leave_deletes_now_playing_message(self):
        audio = _make_audio()
        guild_id = 1
        msg = AsyncMock()
        msg.delete = AsyncMock()
        audio.now_playing_message[guild_id] = msg
        vc = AsyncMock()
        vc.disconnect = AsyncMock()
        _attach_vc(audio, guild_id, vc)
        audio.buffer[guild_id][BufferKey.VOICE_CLIENT] = vc

        await audio.leave(guild_id)

        msg.delete.assert_called_once()
        assert audio.now_playing_message.get(guild_id) is None

    @pytest.mark.asyncio
    async def test_leave_handles_missing_message(self):
        """Should not raise if now_playing_message is None."""
        audio = _make_audio()
        guild_id = 1
        vc = AsyncMock()
        vc.disconnect = AsyncMock()
        _attach_vc(audio, guild_id, vc)
        audio.buffer[guild_id][BufferKey.VOICE_CLIENT] = vc

        await audio.leave(guild_id)  # no error

    @pytest.mark.asyncio
    async def test_leave_handles_deleted_message(self):
        """discord.NotFound on delete should be swallowed."""
        import discord

        audio = _make_audio()
        guild_id = 1
        msg = AsyncMock()
        msg.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404, reason="Not Found"), "not found"))
        audio.now_playing_message[guild_id] = msg
        vc = AsyncMock()
        vc.disconnect = AsyncMock()
        _attach_vc(audio, guild_id, vc)
        audio.buffer[guild_id][BufferKey.VOICE_CLIENT] = vc

        await audio.leave(guild_id)  # should not raise

    @pytest.mark.asyncio
    async def test_leave_clears_session_state(self):
        audio = _make_audio()
        guild_id = 1
        audio.current_song[guild_id] = MagicMock()
        audio.play_start[guild_id] = datetime.now(UTC)
        audio.paused_at[guild_id] = None
        vc = AsyncMock()
        vc.disconnect = AsyncMock()
        _attach_vc(audio, guild_id, vc)
        audio.buffer[guild_id][BufferKey.VOICE_CLIENT] = vc

        await audio.leave(guild_id)

        assert guild_id not in audio.current_song
        assert guild_id not in audio.play_start
