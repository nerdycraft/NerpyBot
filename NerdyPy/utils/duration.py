# -*- coding: utf-8 -*-
"""Human-friendly duration parsing using pytimeparse2."""

from datetime import timedelta

import pytimeparse2

MIN_DURATION_SECONDS = 60


def parse_duration(value: str) -> timedelta:
    """Parse a human-friendly duration string into a timedelta.

    Supports formats like '2h30m', '1d12h', '90s', '1w'.
    A plain integer (no unit suffix) is treated as minutes for backward compatibility.

    Raises ValueError if the string is unparseable or the result is less than 60 seconds.
    """
    # A bare integer (no unit suffix) is treated as minutes for backward compatibility.
    if value.strip().isdigit():
        seconds = int(value.strip()) * 60
    else:
        seconds = pytimeparse2.parse(value)

    if seconds is None:
        raise ValueError(f"Could not parse duration: '{value}'")

    total_secs: float = seconds.total_seconds() if isinstance(seconds, timedelta) else float(seconds)

    if total_secs < 0:
        raise ValueError(f"Duration cannot be negative: '{value}'")

    if total_secs < MIN_DURATION_SECONDS:
        raise ValueError(f"Duration must be at least 60 seconds, got {total_secs}s")

    return timedelta(seconds=total_secs)
