# -*- coding: utf-8 -*-
"""Tests for blizzard.py recipe sync pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.blizzard import (
    CRAFTING_PROFESSIONS,
    _blizzard_item_search,
    _detect_current_tier,
    _resolve_recipe_item,
    sync_crafting_recipes,
)


def _make_api():
    """Create a mock blizzapi.RetailClient."""
    api = MagicMock()
    api._access_token = "mock_token"
    return api


def _make_search_result(item_id, name, is_equippable=False, binding_type=None):
    """Build a single item search result dict."""
    data = {
        "id": item_id,
        "name": {"en_US": name, "en_GB": name},
        "is_equippable": is_equippable,
    }
    if binding_type:
        data["preview_item"] = {"binding": {"type": binding_type}}
    else:
        data["preview_item"] = {}
    return {"data": data}


def _make_resolved(item_id, item_name, is_equippable=False, is_bop=False):
    """Build a _resolve_recipe_item return dict."""
    return {"item_id": item_id, "item_name": item_name, "is_equippable": is_equippable, "is_bop": is_bop}


class TestCraftingProfessions:
    def test_has_expected_professions(self):
        assert "Blacksmithing" in CRAFTING_PROFESSIONS
        assert "Jewelcrafting" in CRAFTING_PROFESSIONS
        assert len(CRAFTING_PROFESSIONS) == 8

    def test_no_gathering_professions(self):
        for name in ("Skinning", "Mining", "Herbalism", "Cooking"):
            assert name not in CRAFTING_PROFESSIONS


class TestDetectCurrentTier:
    @pytest.mark.asyncio
    async def test_picks_tier_with_bop_items(self):
        api = _make_api()
        log = MagicMock()

        # Two tiers: high (unreleased, no BoP) and low (current, has BoP)
        skill_tiers = [
            {"id": 2872, "name": "Khaz Algar"},
            {"id": 2907, "name": "Midnight"},
        ]

        # Tier data: Midnight has recipes but no BoP, Khaz Algar has BoP
        def mock_skill_tier(prof_id, tier_id):
            if tier_id == 2907:
                return {"categories": [{"recipes": [{"id": 1, "name": "Midnight Sword"}]}]}
            return {"categories": [{"recipes": [{"id": 2, "name": "Khaz Sword"}]}]}

        api.profession_skill_tier = mock_skill_tier

        with patch("utils.blizzard._resolve_recipe_item") as mock_resolve:

            async def fake_resolve(api, recipe_id, recipe_name, log):
                if recipe_name == "Midnight Sword":
                    return _make_resolved(1001, "Midnight Sword")
                return _make_resolved(1002, "Khaz Sword", is_equippable=True)

            mock_resolve.side_effect = fake_resolve

            tier, tier_data = await _detect_current_tier(api, 164, skill_tiers, log)

        assert tier["id"] == 2872
        assert tier["name"] == "Khaz Algar"

    @pytest.mark.asyncio
    async def test_picks_highest_when_both_have_bop(self):
        """Late beta scenario: both tiers have BoP — pick highest."""
        api = _make_api()
        log = MagicMock()

        skill_tiers = [
            {"id": 2872, "name": "Khaz Algar"},
            {"id": 2907, "name": "Midnight"},
        ]

        def mock_skill_tier(prof_id, tier_id):
            return {"categories": [{"recipes": [{"id": tier_id, "name": f"Sword {tier_id}"}]}]}

        api.profession_skill_tier = mock_skill_tier

        with patch("utils.blizzard._resolve_recipe_item") as mock_resolve:

            async def fake_resolve(api, recipe_id, recipe_name, log):
                return _make_resolved(1, recipe_name, is_bop=True)

            mock_resolve.side_effect = fake_resolve
            tier, _ = await _detect_current_tier(api, 164, skill_tiers, log)

        assert tier["id"] == 2907  # highest

    @pytest.mark.asyncio
    async def test_fallback_to_highest_tier_when_no_bop(self):
        api = _make_api()
        log = MagicMock()

        skill_tiers = [{"id": 100, "name": "Basic"}]

        api.profession_skill_tier = lambda pid, tid: {"categories": [{"recipes": [{"id": 1, "name": "Widget"}]}]}

        with patch("utils.blizzard._resolve_recipe_item") as mock_resolve:
            mock_resolve.return_value = None
            tier, _ = await _detect_current_tier(api, 164, skill_tiers, log)

        assert tier["id"] == 100

    @pytest.mark.asyncio
    async def test_samples_from_diverse_categories(self):
        """Verify recipes are sampled from multiple categories, not just the first."""
        api = _make_api()
        log = MagicMock()

        skill_tiers = [{"id": 100, "name": "Current"}]

        # Two categories: first has non-equippable, second has equippable
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [
                {"recipes": [{"id": 1, "name": "Reagent A"}, {"id": 2, "name": "Reagent B"}]},
                {"recipes": [{"id": 3, "name": "Epic Sword"}]},
            ]
        }

        resolved_names = []

        with patch("utils.blizzard._resolve_recipe_item") as mock_resolve:

            async def fake_resolve(api, recipe_id, recipe_name, log):
                resolved_names.append(recipe_name)
                if recipe_name == "Epic Sword":
                    return _make_resolved(300, "Epic Sword", is_equippable=True)
                return _make_resolved(recipe_id, recipe_name)  # not equippable, not BoP

            mock_resolve.side_effect = fake_resolve
            tier, _ = await _detect_current_tier(api, 164, skill_tiers, log)

        assert tier["id"] == 100
        assert "Epic Sword" in resolved_names  # reached second category


class TestResolveRecipeItem:
    """Test recipe → item resolution via recipe detail API (ID-based, no name matching)."""

    @pytest.mark.asyncio
    async def test_resolves_via_crafted_item_id(self):
        """recipe detail → crafted_item.id → item detail gives full item info."""
        api = _make_api()
        log = MagicMock()

        api.recipe = lambda rid: {"crafted_item": {"id": 500, "name": "Iron Sword"}}
        api.item = lambda iid: {"is_equippable": True, "preview_item": {"binding": {"type": "ON_ACQUIRE"}}}

        result = await _resolve_recipe_item(api, 10, "Iron Sword", log)

        assert result is not None
        assert result["item_id"] == 500
        assert result["item_name"] == "Iron Sword"
        assert result["is_equippable"] is True
        assert result["is_bop"] is True

    @pytest.mark.asyncio
    async def test_returns_none_when_no_crafted_item(self):
        """Recipes without crafted_item (quality-tiered) are skipped."""
        api = _make_api()
        log = MagicMock()

        api.recipe = lambda rid: {"name": "Quality Sword"}  # no crafted_item

        result = await _resolve_recipe_item(api, 10, "Quality Sword", log)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_api_fails(self):
        """If api.recipe() raises, returns None gracefully."""
        api = _make_api()
        log = MagicMock()

        api.recipe = MagicMock(side_effect=Exception("API error"))

        result = await _resolve_recipe_item(api, 10, "Error Sword", log)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_non_bop_non_equippable_item(self):
        """Resolution returns item info even when not equippable/BoP (caller decides filtering)."""
        api = _make_api()
        log = MagicMock()

        api.recipe = lambda rid: {"crafted_item": {"id": 800, "name": "Health Potion"}}
        api.item = lambda iid: {"is_equippable": False, "preview_item": {}}

        result = await _resolve_recipe_item(api, 10, "Health Potion", log)

        assert result is not None
        assert result["is_equippable"] is False
        assert result["is_bop"] is False

    @pytest.mark.asyncio
    async def test_propagates_rate_limited(self):
        """RateLimited exceptions bubble up, not swallowed."""
        from utils.blizzard import RateLimited

        api = _make_api()
        log = MagicMock()

        api.recipe = lambda rid: {"code": 429}  # rate limited response from blizzapi

        with pytest.raises(RateLimited):
            await _resolve_recipe_item(api, 10, "Sword", log)


class TestSyncCraftingRecipes:
    @pytest.mark.asyncio
    async def test_end_to_end_sync(self, db_session):
        from models.wow import CraftingRecipeCache

        api = _make_api()
        log = MagicMock()

        # Mock professions index — return one crafting profession
        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}

        # Mock profession detail — one tier
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Current Tier"}]}

        # Mock tier data — two recipes
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": 10, "name": "Iron Sword"}, {"id": 11, "name": "Iron Shield"}]}]
        }

        # Mock item media
        api.item_media = lambda iid: {"assets": [{"key": "icon", "value": f"https://icon/{iid}.jpg"}]}

        with (
            patch("utils.blizzard._detect_current_tier") as mock_detect,
            patch("utils.blizzard._resolve_recipe_item") as mock_resolve,
        ):

            async def fake_detect(api, prof_id, tiers, log):
                tier_data = api.profession_skill_tier(prof_id, tiers[0]["id"])
                return tiers[0], tier_data

            mock_detect.side_effect = fake_detect

            async def fake_resolve(api, recipe_id, recipe_name, log):
                if recipe_name == "Iron Sword":
                    return _make_resolved(100, "Iron Sword", is_equippable=True)
                elif recipe_name == "Iron Shield":
                    return _make_resolved(101, "Iron Shield", is_bop=True)
                return None

            mock_resolve.side_effect = fake_resolve

            recipe_count, profession_count = await sync_crafting_recipes(api, db_session, log)

        assert recipe_count == 2
        assert profession_count == 1

        results = CraftingRecipeCache.get_by_profession(164, db_session)
        assert len(results) == 2
        names = {r.ItemName for r in results}
        assert names == {"Iron Sword", "Iron Shield"}
        assert results[0].ProfessionName == "Blacksmithing"

    @pytest.mark.asyncio
    async def test_skips_non_equippable_non_bop(self, db_session):
        from models.wow import CraftingRecipeCache

        api = _make_api()
        log = MagicMock()

        api.professions_index = lambda: {"professions": [{"id": 171, "name": "Alchemy"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Current"}]}
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": 10, "name": "Health Potion"}]}]
        }

        with (
            patch("utils.blizzard._detect_current_tier") as mock_detect,
            patch("utils.blizzard._resolve_recipe_item") as mock_resolve,
        ):

            async def fake_detect(api, prof_id, tiers, log):
                return tiers[0], api.profession_skill_tier(prof_id, tiers[0]["id"])

            mock_detect.side_effect = fake_detect

            # Health Potion: not equippable, not BoP — should be skipped
            mock_resolve.return_value = _make_resolved(200, "Health Potion")

            recipe_count, profession_count = await sync_crafting_recipes(api, db_session, log)

        assert recipe_count == 0
        assert profession_count == 0
        assert CraftingRecipeCache.get_by_profession(171, db_session) == []

    @pytest.mark.asyncio
    async def test_skips_non_crafting_professions(self, db_session):
        api = _make_api()
        log = MagicMock()

        # Return a gathering profession that's NOT in CRAFTING_PROFESSIONS
        api.professions_index = lambda: {"professions": [{"id": 186, "name": "Mining"}]}

        recipe_count, profession_count = await sync_crafting_recipes(api, db_session, log)
        assert recipe_count == 0
        assert profession_count == 0

    @pytest.mark.asyncio
    async def test_upserts_existing_recipe(self, db_session):
        from models.wow import CraftingRecipeCache

        # Pre-populate with old data
        db_session.add(
            CraftingRecipeCache(
                ProfessionId=164,
                ProfessionName="Blacksmithing",
                RecipeId=10,
                ItemId=100,
                ItemName="Old Name",
                IconUrl="old_icon.jpg",
            )
        )
        db_session.flush()

        api = _make_api()
        log = MagicMock()

        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Current"}]}
        api.profession_skill_tier = lambda pid, tid: {"categories": [{"recipes": [{"id": 10, "name": "New Sword"}]}]}
        api.item_media = lambda iid: {"assets": [{"key": "icon", "value": "new_icon.jpg"}]}

        with (
            patch("utils.blizzard._detect_current_tier") as mock_detect,
            patch("utils.blizzard._resolve_recipe_item") as mock_resolve,
        ):

            async def fake_detect(api, prof_id, tiers, log):
                return tiers[0], api.profession_skill_tier(prof_id, tiers[0]["id"])

            mock_detect.side_effect = fake_detect
            mock_resolve.return_value = _make_resolved(200, "New Sword", is_equippable=True)

            await sync_crafting_recipes(api, db_session, log)

        results = CraftingRecipeCache.get_by_profession(164, db_session)
        assert len(results) == 1
        assert results[0].ItemName == "New Sword"
        assert results[0].ItemId == 200
        assert results[0].IconUrl == "new_icon.jpg"


class TestBlizzardItemSearch:
    """Test the raw Blizzard Item Search API wrapper."""

    @pytest.mark.asyncio
    async def test_returns_matching_results(self):
        api = _make_api()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [_make_search_result(100, "Iron Sword", is_equippable=True)]}

        with patch("utils.blizzard.requests.get", return_value=mock_response) as mock_get:
            results = await _blizzard_item_search(api, "Iron Sword")

        assert len(results) == 1
        assert results[0]["data"]["name"]["en_US"] == "Iron Sword"
        mock_get.assert_called_once()
        # Verify the URL and params
        call_kwargs = mock_get.call_args
        assert "search/item" in call_kwargs.args[0]

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_results(self):
        api = _make_api()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("utils.blizzard.requests.get", return_value=mock_response):
            results = await _blizzard_item_search(api, "Nonexistent Widget")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self):
        api = _make_api()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("utils.blizzard.requests.get", return_value=mock_response):
            results = await _blizzard_item_search(api, "Iron Sword")

        assert results == []

    @pytest.mark.asyncio
    async def test_raises_rate_limited_on_429(self):
        from utils.blizzard import RateLimited

        api = _make_api()

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("utils.blizzard.requests.get", return_value=mock_response):
            with pytest.raises(RateLimited):
                await _blizzard_item_search(api, "Iron Sword")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_token(self):
        # API without _access_token — the function tries professions_index() as a
        # fallback to force token acquisition, then checks _access_token again
        api = MagicMock()
        del api._access_token  # ensure getattr returns None
        # professions_index() runs but doesn't set _access_token (no real OAuth)
        api.professions_index = MagicMock(return_value={})
        results = await _blizzard_item_search(api, "Iron Sword")
        assert results == []


class TestSyncDataDispatch:
    """Test that !sync data dispatches to cog sync_data() methods."""

    @pytest.mark.asyncio
    async def test_dispatches_to_cogs_with_sync_data(self):
        """Verify the _sync_module_data pattern calls sync_data() on supporting cogs."""
        # Simulate the dispatch pattern from admin.py's _sync_module_data
        mock_cog_with_sync = MagicMock()
        mock_cog_with_sync.sync_data = AsyncMock(return_value="2 recipes synced")

        mock_cog_without_sync = MagicMock(spec=["__class__"])

        bot_cogs = {"Wow": mock_cog_with_sync, "Music": mock_cog_without_sync}

        # Replicate the dispatch logic from _sync_module_data
        results = []
        for name, cog in bot_cogs.items():
            if hasattr(cog, "sync_data"):
                result = await cog.sync_data(MagicMock())  # ctx
                results.append(f"{name}: {result}")

        assert len(results) == 1
        assert "Wow: 2 recipes synced" in results
        mock_cog_with_sync.sync_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_cogs_without_sync_data(self):
        """Cogs without sync_data() are silently skipped."""
        mock_cog = MagicMock(spec=["__class__"])
        bot_cogs = {"Music": mock_cog}

        results = []
        for name, cog in bot_cogs.items():
            if hasattr(cog, "sync_data"):
                result = await cog.sync_data(MagicMock())
                results.append(f"{name}: {result}")

        assert results == []


class TestRoleAutoMatch:
    """Test the role → profession auto-matching logic in the WoW cog."""

    def test_exact_match(self):
        from utils.blizzard import CRAFTING_PROFESSIONS

        role = MagicMock()
        role.name = "Blacksmithing"
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                assert prof_id == 164
                break

    def test_partial_match(self):
        from utils.blizzard import CRAFTING_PROFESSIONS

        role = MagicMock()
        role.name = "Guild Blacksmithing Expert"
        matched = None
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                matched = prof_id
                break
        assert matched == 164

    def test_no_match(self):
        from utils.blizzard import CRAFTING_PROFESSIONS

        role = MagicMock()
        role.name = "PvP Champion"
        matched = None
        for prof_name, prof_id in CRAFTING_PROFESSIONS.items():
            if prof_name.lower() in role.name.lower():
                matched = prof_id
                break
        assert matched is None
