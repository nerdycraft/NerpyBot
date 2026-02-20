# -*- coding: utf-8 -*-
"""Tests for WoW mount set degradation guard and churn detection."""

import json

from utils.blizzard import parse_known_mounts, should_update_mount_set


class TestParseKnownMounts:
    """Tests for parse_known_mounts — backward-compatible storage parsing."""

    def test_legacy_list_format(self):
        """Plain JSON list → set of IDs, count = list length."""
        raw = json.dumps([1, 2, 3])
        ids, count = parse_known_mounts(raw)
        assert ids == {1, 2, 3}
        assert count == 3

    def test_new_dict_format(self):
        """New dict format → IDs from 'ids' key, count from 'last_count'."""
        raw = json.dumps({"ids": [10, 20, 30, 40], "last_count": 3})
        ids, count = parse_known_mounts(raw)
        assert ids == {10, 20, 30, 40}
        assert count == 3

    def test_empty_legacy(self):
        raw = json.dumps([])
        ids, count = parse_known_mounts(raw)
        assert ids == set()
        assert count == 0

    def test_empty_new_format(self):
        raw = json.dumps({"ids": [], "last_count": 0})
        ids, count = parse_known_mounts(raw)
        assert ids == set()
        assert count == 0


class TestDegradationGuard:
    """Tests for should_update_mount_set — guards against degraded API responses.

    Now uses count-based comparison (last_count, current_count) instead of sets.
    """

    def test_normal_update_no_removals(self):
        """Current has more mounts than last — should allow update."""
        assert should_update_mount_set(3, 5) is True

    def test_small_removal(self):
        """Small removal (1 mount from 200) — Blizzard revoked a bugged mount."""
        assert should_update_mount_set(200, 199) is True

    def test_large_drop(self):
        """Large drop (100 of 200 gone) — degraded API response."""
        assert should_update_mount_set(200, 100) is False

    def test_empty_response(self):
        """API returned nothing — should block update."""
        assert should_update_mount_set(200, 0) is False

    def test_threshold_boundary_at_limit(self):
        """Dropping exactly max(10, count*0.1) — at boundary, <= means allowed."""
        # threshold = max(10, int(200 * 0.1)) = 20
        # drop exactly 20 → 180
        assert should_update_mount_set(200, 180) is True

    def test_threshold_boundary_one_over(self):
        """Dropping one more than threshold — should block."""
        # threshold = 20, drop 21 → 179
        assert should_update_mount_set(200, 179) is False

    def test_empty_known_set(self):
        """First baseline — zero last_count should always allow."""
        assert should_update_mount_set(0, 3) is True

    def test_both_empty(self):
        """Both empty — no-op, should allow."""
        assert should_update_mount_set(0, 0) is True


class TestFailureTracking:
    """Verify 404 failure tracking via AccountGroupData._failures."""

    def test_record_failure_new_character(self):
        from utils.blizzard import record_character_failure

        failures = {}
        record_character_failure(failures, "stabtain", "blackrock")
        assert failures["stabtain:blackrock"]["count"] == 1
        assert "last" in failures["stabtain:blackrock"]

    def test_record_failure_increment(self):
        from utils.blizzard import record_character_failure

        failures = {"stabtain:blackrock": {"count": 2, "last": "2026-01-01T00:00:00"}}
        record_character_failure(failures, "stabtain", "blackrock")
        assert failures["stabtain:blackrock"]["count"] == 3

    def test_should_skip_below_threshold(self):
        from utils.blizzard import should_skip_character

        failures = {"stabtain:blackrock": {"count": 2, "last": "2026-01-01T00:00:00"}}
        assert should_skip_character(failures, "stabtain", "blackrock") is False

    def test_should_skip_at_threshold(self):
        from utils.blizzard import should_skip_character

        failures = {"stabtain:blackrock": {"count": 3, "last": "2026-01-01T00:00:00"}}
        assert should_skip_character(failures, "stabtain", "blackrock") is True

    def test_should_not_skip_unknown(self):
        from utils.blizzard import should_skip_character

        assert should_skip_character({}, "newchar", "blackrock") is False

    def test_clear_failure_on_success(self):
        from utils.blizzard import clear_character_failure

        failures = {"stabtain:blackrock": {"count": 3, "last": "2026-01-01T00:00:00"}}
        clear_character_failure(failures, "stabtain", "blackrock")
        assert "stabtain:blackrock" not in failures

    def test_clear_failure_noop_for_unknown(self):
        from utils.blizzard import clear_character_failure

        failures = {}
        clear_character_failure(failures, "stabtain", "blackrock")
        assert failures == {}
