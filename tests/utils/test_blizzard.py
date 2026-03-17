# -*- coding: utf-8 -*-
"""Tests for blizzard.py utilities."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from models.wow import CraftingRecipeCache
from utils.blizzard import CRAFTING_PROFESSIONS


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


def _make_bot(cache_row_count: int = 0):
    """Return a (bot, session) pair with a working session_scope context manager."""
    session = MagicMock()
    session.query.return_value.count.return_value = cache_row_count

    bot = MagicMock()
    bot.config.get.return_value = {"wow_id": "fake_id", "wow_secret": "fake_secret"}

    @contextmanager
    def _scope():
        yield session

    bot.session_scope = _scope
    return bot, session


def _make_client(fail: bool = False):
    """Return a mock RetailClient whose profession() either raises or returns empty data."""
    client = MagicMock()
    if fail:
        client.profession.side_effect = RuntimeError("Blizzard API unavailable")
    else:
        client.profession.return_value = {}  # no skill_tiers → no rows collected
    return client


class TestSyncCraftingRecipesGuard:
    """Test the pre-swap guard that protects the cache on partial sync errors."""

    async def test_clean_sync_updates_cache(self):
        """errors=0 → cache is always replaced."""
        bot, session = _make_bot(cache_row_count=5)
        with patch("blizzapi.RetailClient", return_value=_make_client(fail=False)):
            with patch.object(CraftingRecipeCache, "count", return_value=5):
                from utils.blizzard import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] == 0
        assert result["cache_updated"] is True

    async def test_errors_with_populated_cache_skips_swap(self):
        """errors>0 and cache has rows → keep stale cache, do not wipe."""
        bot, session = _make_bot(cache_row_count=10)
        with patch("blizzapi.RetailClient", return_value=_make_client(fail=True)):
            with patch.object(CraftingRecipeCache, "count", return_value=10):
                from utils.blizzard import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] > 0
        assert result["cache_updated"] is False
        # delete_all must NOT have been called — stale rows are preserved
        session.query.return_value.delete.assert_not_called()

    async def test_errors_with_empty_cache_writes_partial_data(self):
        """errors>0 but cache is empty → write partial data (something > nothing)."""
        bot, session = _make_bot(cache_row_count=0)
        with patch("blizzapi.RetailClient", return_value=_make_client(fail=True)):
            with patch.object(CraftingRecipeCache, "count", return_value=0):
                from utils.blizzard import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] > 0
        assert result["cache_updated"] is True
