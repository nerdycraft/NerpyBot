# -*- coding: utf-8 -*-
"""Tests for blizzard.py utilities."""

from unittest.mock import MagicMock

from utils.blizzard import CRAFTING_PROFESSIONS


class TestCraftingProfessions:
    def test_has_expected_professions(self):
        assert "Blacksmithing" in CRAFTING_PROFESSIONS
        assert "Jewelcrafting" in CRAFTING_PROFESSIONS
        assert "Cooking" in CRAFTING_PROFESSIONS
        assert len(CRAFTING_PROFESSIONS) == 9

    def test_no_gathering_professions(self):
        for name in ("Skinning", "Mining", "Herbalism"):
            assert name not in CRAFTING_PROFESSIONS


class TestRoleAutoMatch:
    """Test the role → profession auto-matching logic in the WoW cog."""

    def test_exact_match(self):
        role = MagicMock()
        role.name = "Blacksmithing"
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                assert prof_id == 164
                break

    def test_partial_match(self):
        role = MagicMock()
        role.name = "Guild Blacksmithing Expert"
        matched = None
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                matched = prof_id
                break
        assert matched == 164

    def test_no_match(self):
        role = MagicMock()
        role.name = "PvP Champion"
        matched = None
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                matched = prof_id
                break
        assert matched is None
