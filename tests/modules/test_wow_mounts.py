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
