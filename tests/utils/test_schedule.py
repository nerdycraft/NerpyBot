# -*- coding: utf-8 -*-
"""Tests for utils/schedule.py — next-fire-time computation for reminders."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from utils.schedule import compute_next_fire


class TestComputeNextFireInterval:
    """Tests for interval-based reminders."""

    def test_interval_adds_seconds(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire("interval", interval_seconds=3600, after=now)
        assert result == datetime(2026, 3, 1, 13, 0, 0, tzinfo=UTC)

    def test_interval_requires_interval_seconds(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="interval_seconds"):
            compute_next_fire("interval", after=now)


class TestComputeNextFireDaily:
    """Tests for daily schedule."""

    def test_daily_next_day_if_past_today(self):
        # It's 14:00, schedule is 09:00 → next is tomorrow 09:00
        now = datetime(2026, 3, 1, 14, 0, 0, tzinfo=UTC)
        result = compute_next_fire("daily", schedule_time=time(9, 0), after=now)
        assert result == datetime(2026, 3, 2, 9, 0, 0, tzinfo=UTC)

    def test_daily_today_if_not_yet(self):
        # It's 06:00, schedule is 09:00 → next is today 09:00
        now = datetime(2026, 3, 1, 6, 0, 0, tzinfo=UTC)
        result = compute_next_fire("daily", schedule_time=time(9, 0), after=now)
        assert result == datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC)

    def test_daily_with_timezone(self):
        # 09:00 Europe/Berlin = 08:00 UTC (during CET, no DST)
        tz = ZoneInfo("Europe/Berlin")
        now = datetime(2026, 1, 15, 7, 0, 0, tzinfo=UTC)  # 08:00 Berlin
        result = compute_next_fire("daily", schedule_time=time(9, 0), timezone=tz, after=now)
        assert result == datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC)

    def test_daily_requires_schedule_time(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="schedule_time"):
            compute_next_fire("daily", after=now)


class TestComputeNextFireWeekly:
    """Tests for weekly schedule."""

    def test_weekly_same_day_future_time(self):
        # Monday 06:00, schedule Monday 09:00 → today 09:00
        now = datetime(2026, 3, 2, 6, 0, 0, tzinfo=UTC)  # Monday
        result = compute_next_fire("weekly", schedule_time=time(9, 0), schedule_day_of_week=0, after=now)
        assert result == datetime(2026, 3, 2, 9, 0, 0, tzinfo=UTC)

    def test_weekly_same_day_past_time(self):
        # Monday 14:00, schedule Monday 09:00 → next Monday 09:00
        now = datetime(2026, 3, 2, 14, 0, 0, tzinfo=UTC)  # Monday
        result = compute_next_fire("weekly", schedule_time=time(9, 0), schedule_day_of_week=0, after=now)
        assert result == datetime(2026, 3, 9, 9, 0, 0, tzinfo=UTC)

    def test_weekly_future_day(self):
        # Monday 12:00, schedule Wednesday 09:00 → this Wednesday
        now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)  # Monday
        result = compute_next_fire("weekly", schedule_time=time(9, 0), schedule_day_of_week=2, after=now)
        assert result == datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)

    def test_weekly_requires_schedule_time_and_day(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="schedule_time and schedule_day_of_week"):
            compute_next_fire("weekly", after=now)


class TestComputeNextFireMonthly:
    """Tests for monthly schedule."""

    def test_monthly_same_month_future_day(self):
        # March 1, schedule day 15 → March 15
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire("monthly", schedule_time=time(9, 0), schedule_day_of_month=15, after=now)
        assert result == datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC)

    def test_monthly_next_month_if_past(self):
        # March 20, schedule day 15 → April 15
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire("monthly", schedule_time=time(9, 0), schedule_day_of_month=15, after=now)
        assert result == datetime(2026, 4, 15, 9, 0, 0, tzinfo=UTC)

    def test_monthly_december_wraps_to_january(self):
        # Dec 20, schedule day 15 → Jan 15 next year
        now = datetime(2026, 12, 20, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire("monthly", schedule_time=time(9, 0), schedule_day_of_month=15, after=now)
        assert result == datetime(2027, 1, 15, 9, 0, 0, tzinfo=UTC)

    def test_monthly_day_31_in_short_month(self):
        """Day 31 in a 30-day month should clamp to day 30."""
        now = datetime(2026, 4, 1, 6, 0, 0, tzinfo=UTC)  # April has 30 days
        result = compute_next_fire("monthly", schedule_time=time(9, 0), schedule_day_of_month=31, after=now)
        assert result == datetime(2026, 4, 30, 9, 0, 0, tzinfo=UTC)

    def test_monthly_requires_schedule_time_and_day(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="schedule_time and schedule_day_of_month"):
            compute_next_fire("monthly", after=now)


class TestComputeNextFireOnce:
    """Tests for one-shot reminders."""

    def test_once_returns_none(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire("once", after=now)
        assert result is None


class TestComputeNextFireInvalidType:
    """Tests for invalid schedule types."""

    def test_invalid_type_raises(self):
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="Unknown schedule type"):
            compute_next_fire("bogus", after=now)
