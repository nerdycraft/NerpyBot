# -*- coding: utf-8 -*-

import time


class ErrorThrottle:
    """In-memory error notification throttle with global suppression.

    Dedup key: ``{ExceptionType}:{context}``
    Throttle window: 15 minutes (``THROTTLE_WINDOW`` seconds).
    """

    THROTTLE_WINDOW = 900  # 15 minutes

    def __init__(self):
        self._last_notified: dict[str, float] = {}
        self._suppressed_count: dict[str, int] = {}
        self._suppressed_until: float | None = None

    @staticmethod
    def _make_key(context: str, error: Exception) -> str:
        return f"{type(error).__name__}:{context}"

    def should_notify(self, context: str, error: Exception) -> bool:
        """Return True if this error should trigger a DM notification."""
        if self._suppressed_until is not None and time.monotonic() < self._suppressed_until:
            return False

        key = self._make_key(context, error)
        now = time.monotonic()
        last = self._last_notified.get(key)

        if last is not None and (now - last) < self.THROTTLE_WINDOW:
            self._suppressed_count[key] = self._suppressed_count.get(key, 0) + 1
            return False

        self._last_notified[key] = now
        self._suppressed_count[key] = 0
        return True

    def suppress(self, seconds: float) -> None:
        """Suppress all error notifications for *seconds*."""
        self._suppressed_until = time.monotonic() + seconds

    def resume(self) -> None:
        """Cancel global suppression."""
        self._suppressed_until = None

    @property
    def is_suppressed(self) -> bool:
        if self._suppressed_until is None:
            return False
        return time.monotonic() < self._suppressed_until

    @property
    def suppressed_remaining(self) -> float | None:
        """Seconds remaining on global suppression, or None."""
        if self._suppressed_until is None:
            return None
        remaining = self._suppressed_until - time.monotonic()
        return remaining if remaining > 0 else None

    def get_status(self) -> dict:
        """Return throttle state for the ``!errors status`` command."""
        now = time.monotonic()
        buckets = {}
        for key, last in self._last_notified.items():
            buckets[key] = {
                "last_notified_ago": now - last,
                "suppressed_count": self._suppressed_count.get(key, 0),
            }
        return {
            "is_suppressed": self.is_suppressed,
            "suppressed_remaining": self.suppressed_remaining,
            "throttle_window": self.THROTTLE_WINDOW,
            "buckets": buckets,
        }
