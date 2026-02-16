# -*- coding: utf-8 -*-
"""Tests for WoW mount set degradation guard."""

from modules.wow import _should_update_mount_set


class TestDegradationGuard:
    """Tests for _should_update_mount_set — guards against degraded API responses."""

    def test_normal_update_no_removals(self):
        """Current is a superset of known — should allow update."""
        known = {1, 2, 3}
        current = {1, 2, 3, 4, 5}
        assert _should_update_mount_set(known, current) is True

    def test_small_removal(self):
        """Small removal (1 mount from 200) — Blizzard revoked a bugged mount."""
        known = set(range(200))
        current = set(range(1, 200))  # mount 0 removed
        assert _should_update_mount_set(known, current) is True

    def test_large_drop(self):
        """Large drop (100 of 200 gone) — degraded API response."""
        known = set(range(200))
        current = set(range(100))  # lost mounts 100-199
        assert _should_update_mount_set(known, current) is False

    def test_empty_response(self):
        """API returned nothing — should block update."""
        known = set(range(200))
        current = set()
        assert _should_update_mount_set(known, current) is False

    def test_threshold_boundary_at_limit(self):
        """Removing exactly max(10, len*0.1) — at boundary, <= means allowed."""
        known = set(range(200))
        # threshold = max(10, int(200 * 0.1)) = 20
        # remove exactly 20 mounts
        current = set(range(200)) - set(range(20))
        assert _should_update_mount_set(known, current) is True

    def test_threshold_boundary_one_over(self):
        """Removing one more than threshold — should block."""
        known = set(range(200))
        # threshold = 20, remove 21
        current = set(range(200)) - set(range(21))
        assert _should_update_mount_set(known, current) is False

    def test_empty_known_set(self):
        """First baseline — empty known set should always allow."""
        known = set()
        current = {1, 2, 3}
        assert _should_update_mount_set(known, current) is True

    def test_both_empty(self):
        """Both empty — no-op, should allow."""
        known = set()
        current = set()
        assert _should_update_mount_set(known, current) is True


class TestFailureTracking:
    """Verify 404 failure tracking via AccountGroupData._failures."""

    def test_record_failure_new_character(self):
        from modules.wow import _record_character_failure

        failures = {}
        _record_character_failure(failures, "stabtain", "blackrock")
        assert failures["stabtain:blackrock"]["count"] == 1
        assert "last" in failures["stabtain:blackrock"]

    def test_record_failure_increment(self):
        from modules.wow import _record_character_failure

        failures = {"stabtain:blackrock": {"count": 2, "last": "2026-01-01T00:00:00"}}
        _record_character_failure(failures, "stabtain", "blackrock")
        assert failures["stabtain:blackrock"]["count"] == 3

    def test_should_skip_below_threshold(self):
        from modules.wow import _should_skip_character

        failures = {"stabtain:blackrock": {"count": 2, "last": "2026-01-01T00:00:00"}}
        assert _should_skip_character(failures, "stabtain", "blackrock") is False

    def test_should_skip_at_threshold(self):
        from modules.wow import _should_skip_character

        failures = {"stabtain:blackrock": {"count": 3, "last": "2026-01-01T00:00:00"}}
        assert _should_skip_character(failures, "stabtain", "blackrock") is True

    def test_should_not_skip_unknown(self):
        from modules.wow import _should_skip_character

        assert _should_skip_character({}, "newchar", "blackrock") is False

    def test_clear_failure_on_success(self):
        from modules.wow import _clear_character_failure

        failures = {"stabtain:blackrock": {"count": 3, "last": "2026-01-01T00:00:00"}}
        _clear_character_failure(failures, "stabtain", "blackrock")
        assert "stabtain:blackrock" not in failures

    def test_clear_failure_noop_for_unknown(self):
        from modules.wow import _clear_character_failure

        failures = {}
        _clear_character_failure(failures, "stabtain", "blackrock")
        assert failures == {}
