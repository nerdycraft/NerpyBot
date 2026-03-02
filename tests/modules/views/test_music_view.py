# -*- coding: utf-8 -*-
"""Tests for NowPlayingView helpers — progress bar and embed builder."""

from modules.views.music import build_progress_bar


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
