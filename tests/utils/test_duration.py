# -*- coding: utf-8 -*-
"""Tests for utils/duration.py — human-friendly duration parsing."""

import pytest
from datetime import timedelta

from utils.duration import parse_duration


class TestParseDuration:
    """Tests for parse_duration()."""

    def test_seconds_only(self):
        assert parse_duration("90s") == timedelta(seconds=90)

    def test_minutes_only(self):
        assert parse_duration("5m") == timedelta(minutes=5)

    def test_hours_only(self):
        assert parse_duration("2h") == timedelta(hours=2)

    def test_days_only(self):
        assert parse_duration("1d") == timedelta(days=1)

    def test_weeks_only(self):
        assert parse_duration("1w") == timedelta(weeks=1)

    def test_combined_hours_minutes(self):
        assert parse_duration("2h30m") == timedelta(hours=2, minutes=30)

    def test_combined_days_hours(self):
        assert parse_duration("1d12h") == timedelta(days=1, hours=12)

    def test_integer_minutes_fallback(self):
        """Plain integer string should be treated as minutes for backward compat."""
        assert parse_duration("60") == timedelta(minutes=60)

    def test_below_minimum_raises(self):
        with pytest.raises(ValueError, match="at least 60 seconds"):
            parse_duration("30s")

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="at least 60 seconds"):
            parse_duration("0s")

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_duration("notaduration")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_duration("")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            parse_duration("-5m")
