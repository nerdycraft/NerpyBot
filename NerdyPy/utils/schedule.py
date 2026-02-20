# -*- coding: utf-8 -*-
"""Next-fire-time computation for reminder schedules."""

import calendar
from datetime import UTC, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo


def compute_next_fire(
    schedule_type: str,
    *,
    interval_seconds: int | None = None,
    schedule_time: time | None = None,
    schedule_day_of_week: int | None = None,
    schedule_day_of_month: int | None = None,
    timezone: ZoneInfo | None = None,
    after: datetime | None = None,
) -> datetime | None:
    """Compute the next fire time in UTC for a given schedule type.

    Returns None for 'once' (one-shot reminders that should be deleted after firing).
    """
    if after is None:
        after = datetime.now(UTC)

    tz = timezone or UTC

    if schedule_type == "once":
        return None

    if schedule_type == "interval":
        if interval_seconds is None:
            raise ValueError("interval_seconds is required for interval schedule type")
        return after + timedelta(seconds=interval_seconds)

    if schedule_type == "daily":
        if schedule_time is None:
            raise ValueError("schedule_time is required for daily schedule type")
        return _next_daily(schedule_time, tz, after)

    if schedule_type == "weekly":
        if schedule_time is None or schedule_day_of_week is None:
            raise ValueError("schedule_time and schedule_day_of_week are required for weekly schedule type")
        return _next_weekly(schedule_time, schedule_day_of_week, tz, after)

    if schedule_type == "monthly":
        if schedule_time is None or schedule_day_of_month is None:
            raise ValueError("schedule_time and schedule_day_of_month are required for monthly schedule type")
        return _next_monthly(schedule_time, schedule_day_of_month, tz, after)

    raise ValueError(f"Unknown schedule type: '{schedule_type}'")


def _next_daily(t: time, tz: tzinfo, after: datetime) -> datetime:
    """Next occurrence of a daily schedule at time *t* in timezone *tz*, returned as UTC."""
    local_now = after.astimezone(tz)
    candidate = local_now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC).replace(tzinfo=UTC)


def _next_weekly(t: time, day_of_week: int, tz: tzinfo, after: datetime) -> datetime:
    """Next occurrence of a weekly schedule on *day_of_week* at *t*."""
    local_now = after.astimezone(tz)
    candidate = local_now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    # Advance to the target weekday
    days_ahead = (day_of_week - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)

    if candidate <= local_now:
        candidate += timedelta(weeks=1)
    return candidate.astimezone(UTC).replace(tzinfo=UTC)


def _next_monthly(t: time, day_of_month: int, tz: tzinfo, after: datetime) -> datetime:
    """Next occurrence of a monthly schedule on *day_of_month* at *t*."""
    local_now = after.astimezone(tz)
    year, month = local_now.year, local_now.month

    def _build(y, m):
        clamped_day = min(day_of_month, calendar.monthrange(y, m)[1])
        return local_now.replace(
            year=y, month=m, day=clamped_day, hour=t.hour, minute=t.minute, second=0, microsecond=0
        )

    candidate = _build(year, month)
    if candidate <= local_now:
        month += 1
        if month > 12:
            year += 1
            month = 1
        candidate = _build(year, month)

    return candidate.astimezone(UTC).replace(tzinfo=UTC)
