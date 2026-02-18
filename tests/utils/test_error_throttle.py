# -*- coding: utf-8 -*-

import time
from unittest.mock import patch

from utils.error_throttle import ErrorThrottle


class TestShouldNotify:
    def test_first_error_always_notifies(self):
        throttle = ErrorThrottle()
        assert throttle.should_notify("Reminder loop", ValueError("boom")) is True

    def test_same_error_within_window_is_suppressed(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        assert throttle.should_notify("Reminder loop", ValueError("boom")) is False

    def test_different_context_is_separate_bucket(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        assert throttle.should_notify("Moderation loop", ValueError("boom")) is True

    def test_different_error_type_is_separate_bucket(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        assert throttle.should_notify("Reminder loop", TypeError("boom")) is True

    def test_notifies_again_after_window_expires(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))

        # Fast-forward past the throttle window
        with patch("utils.error_throttle.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + throttle.THROTTLE_WINDOW + 1
            assert throttle.should_notify("Reminder loop", ValueError("boom")) is True


class TestGlobalSuppression:
    def test_suppress_blocks_all_notifications(self):
        throttle = ErrorThrottle()
        throttle.suppress(3600)
        assert throttle.should_notify("Reminder loop", ValueError("boom")) is False

    def test_resume_cancels_suppression(self):
        throttle = ErrorThrottle()
        throttle.suppress(3600)
        throttle.resume()
        assert throttle.should_notify("Reminder loop", ValueError("boom")) is True

    def test_is_suppressed_property(self):
        throttle = ErrorThrottle()
        assert throttle.is_suppressed is False
        throttle.suppress(3600)
        assert throttle.is_suppressed is True
        throttle.resume()
        assert throttle.is_suppressed is False

    def test_suppressed_remaining(self):
        throttle = ErrorThrottle()
        assert throttle.suppressed_remaining is None
        throttle.suppress(3600)
        remaining = throttle.suppressed_remaining
        assert remaining is not None
        assert 3599 < remaining <= 3600


class TestBucketTracking:
    def test_suppressed_count_increments(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        throttle.should_notify("Reminder loop", ValueError("boom"))
        throttle.should_notify("Reminder loop", ValueError("boom"))

        status = throttle.get_status()
        bucket = status["buckets"]["ValueError:Reminder loop"]
        assert bucket["suppressed_count"] == 2

    def test_suppressed_count_resets_on_notify(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        throttle.should_notify("Reminder loop", ValueError("boom"))  # suppressed, count=1

        with patch("utils.error_throttle.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + throttle.THROTTLE_WINDOW + 1
            throttle.should_notify("Reminder loop", ValueError("boom"))  # notifies again, resets count

        status = throttle.get_status()
        bucket = status["buckets"]["ValueError:Reminder loop"]
        assert bucket["suppressed_count"] == 0

    def test_get_status_contains_all_buckets(self):
        throttle = ErrorThrottle()
        throttle.should_notify("Reminder loop", ValueError("boom"))
        throttle.should_notify("WoW loop", TypeError("fail"))

        status = throttle.get_status()
        assert "ValueError:Reminder loop" in status["buckets"]
        assert "TypeError:WoW loop" in status["buckets"]

    def test_get_status_shows_suppression_state(self):
        throttle = ErrorThrottle()
        status = throttle.get_status()
        assert status["is_suppressed"] is False

        throttle.suppress(3600)
        status = throttle.get_status()
        assert status["is_suppressed"] is True
        assert status["suppressed_remaining"] is not None
