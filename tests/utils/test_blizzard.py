# -*- coding: utf-8 -*-
"""Tests for blizzard.py utilities."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from models.wow import CraftingRecipeCache, _recipe_cache
from modules.wow.api import CRAFTING_PROFESSIONS


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


def _make_bot():
    """Return a (bot, session) pair with a working session_scope context manager."""
    session = MagicMock()

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
        bot, session = _make_bot()
        with patch("blizzapi.RetailClient", return_value=_make_client(fail=False)):
            with patch.object(CraftingRecipeCache, "count", return_value=5):
                from modules.wow.api import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] == 0
        assert result["cache_updated"] is True

    async def test_errors_with_populated_cache_skips_swap(self):
        """errors>0 and cache has rows → keep stale cache, do not wipe."""
        bot, session = _make_bot()
        with patch("blizzapi.RetailClient", return_value=_make_client(fail=True)):
            with patch.object(CraftingRecipeCache, "count", return_value=10):
                from modules.wow.api import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] > 0
        assert result["cache_updated"] is False
        # delete_all must NOT have been called — stale rows are preserved
        session.query.return_value.delete.assert_not_called()

    async def test_errors_with_empty_cache_writes_partial_data(self):
        """errors>0 but cache is empty → partial rows are written (something > nothing)."""
        import threading

        bot, session = _make_bot()

        # First profession call returns one skill tier with one recipe; all others raise.
        # threading.Lock ensures the call counter is safe across asyncio.to_thread workers.
        _lock = threading.Lock()
        _n = [0]

        def _profession_side_effect(**kwargs):
            with _lock:
                _n[0] += 1
                n = _n[0]
            if n == 1:
                return {"skill_tiers": [{"id": 1, "name": "Shadowlands Blacksmithing"}]}
            raise RuntimeError("Blizzard API unavailable")

        client = MagicMock()
        client.profession.side_effect = _profession_side_effect
        client.profession_skill_tier.return_value = {
            "categories": [{"name": "Gear", "recipes": [{"id": 100, "name": "Iron Sword"}]}]
        }
        client.recipe.return_value = {"id": 100, "crafted_item": {"id": 200, "name": "Iron Sword"}}
        client.item.return_value = {
            "id": 200,
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 0, "name": "Sword"},
        }
        client.item_media.return_value = None
        client.item_search.return_value = None
        client.recipe_media.return_value = None

        with patch("blizzapi.RetailClient", return_value=client):
            with patch.object(CraftingRecipeCache, "count", return_value=0):
                from modules.wow.api import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["errors"] > 0
        assert result["cache_updated"] is True
        assert result["crafted"] > 0  # partial rows were actually written

    async def test_cache_updated_true_invalidates_recipe_cache(self):
        """When the DB swap succeeds (cache_updated=True), _recipe_cache must be cleared."""
        bot, _ = _make_bot()

        # Pre-populate the recipe cache with a sentinel so we can detect the invalidation.
        _recipe_cache["sentinel_key"] = ["stale"]

        with patch("blizzapi.RetailClient", return_value=_make_client(fail=False)):
            with patch.object(CraftingRecipeCache, "count", return_value=5):
                from modules.wow.api import sync_crafting_recipes

                result = await sync_crafting_recipes(bot)

        assert result["cache_updated"] is True
        assert "sentinel_key" not in _recipe_cache  # sentinel must have been cleared
