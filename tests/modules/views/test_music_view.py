# -*- coding: utf-8 -*-
"""Tests for NowPlayingView helpers — progress bar and embed builder."""

import discord
import pytest
from unittest.mock import MagicMock

from modules.views.music import build_progress_bar, build_now_playing_embed
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
