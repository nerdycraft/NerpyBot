"""Tests for ErrorCounter sliding-window 24h error counter."""

import time

from NerdyPy.utils.error_throttle import ErrorCounter


class TestErrorCounter:
    """Test ErrorCounter class."""

    def test_record_and_count(self):
        """Record 3 errors and verify count returns 3."""
        counter = ErrorCounter()
        counter.record()
        counter.record()
        counter.record()
        assert counter.count() == 3

    def test_count_empty(self):
        """Count on empty counter returns 0."""
        counter = ErrorCounter()
        assert counter.count() == 0

    def test_count_evicts_old_timestamps(self):
        """Verify count evicts old timestamps outside the 24h window."""
        counter = ErrorCounter()
        current_time = time.monotonic()

        # Manually insert an old timestamp (100 seconds before the cutoff)
        old_timestamp = current_time - (ErrorCounter.WINDOW + 100)
        counter._timestamps.append(old_timestamp)

        # Insert a fresh timestamp
        counter._timestamps.append(current_time)

        # count() should evict the old timestamp and return 1
        assert counter.count() == 1
        # Verify the old timestamp is gone
        assert len(counter._timestamps) == 1
        assert counter._timestamps[0] == current_time

    def test_multiple_records_increment(self):
        """Record multiple times and verify count increments."""
        counter = ErrorCounter()
        assert counter.count() == 0

        counter.record()
        assert counter.count() == 1

        counter.record()
        assert counter.count() == 2

        counter.record()
        counter.record()
        counter.record()
        assert counter.count() == 5
