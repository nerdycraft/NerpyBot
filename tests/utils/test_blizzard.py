# -*- coding: utf-8 -*-
"""Tests for blizzard.py recipe sync pipeline."""

import json
import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.blizzard import (
    CRAFTING_PROFESSIONS,
    _resolve_recipe_wowhead,
    sync_crafting_recipes,
)


def _make_api():
    """Create a mock blizzapi.RetailClient."""
    api = MagicMock()
    return api


class TestCraftingProfessions:
    def test_has_expected_professions(self):
        assert "Blacksmithing" in CRAFTING_PROFESSIONS
        assert "Jewelcrafting" in CRAFTING_PROFESSIONS
        assert len(CRAFTING_PROFESSIONS) == 8

    def test_no_gathering_professions(self):
        for name in ("Skinning", "Mining", "Herbalism", "Cooking"):
            assert name not in CRAFTING_PROFESSIONS


class TestResolveRecipeWowhead:
    """Test recipe → item resolution via Wowhead tooltip API."""

    @pytest.mark.asyncio
    async def test_resolves_equippable_item(self):
        """Parses item ID and detects equippable from tooltip HTML."""
        tooltip_html = (
            '<a href="/item=243581/evercore">Evercore</a>'
            '<span class="q3"><a href="/item=244751/evercore-zoomshroud">'
            "Evercore Zoomshroud</a></span>"
            "<br>Binds when equipped"
            "<table><tr><td>Head</td><th>Plate</th></tr></table>"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"name": "Evercore Zoomshroud", "icon": "inv_helmet_47", "quality": 3, "tooltip": tooltip_html}
        ).encode()

        with patch("utils.blizzard.urllib.request.urlopen", return_value=mock_resp):
            result = await _resolve_recipe_wowhead(52418, MagicMock())

        assert result is not None
        assert result["item_id"] == 244751
        assert result["item_name"] == "Evercore Zoomshroud"
        assert result["is_equippable"] is True
        assert result["icon_url"] == "https://wow.zamimg.com/images/wow/icons/large/inv_helmet_47.jpg"

    @pytest.mark.asyncio
    async def test_skips_utility_recipe(self):
        """Recipes with quality -1 (Recraft, Recycling) return None."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"name": "Recraft Equipment", "icon": "trade_blacksmithing", "quality": -1, "tooltip": ""}
        ).encode()

        with patch("utils.blizzard.urllib.request.urlopen", return_value=mock_resp):
            result = await _resolve_recipe_wowhead(51522, MagicMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        """Non-existent recipe returns None."""
        with patch(
            "utils.blizzard.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None),
        ):
            result = await _resolve_recipe_wowhead(99999999, MagicMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        """Timeout returns None, doesn't crash."""
        with patch("utils.blizzard.urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            result = await _resolve_recipe_wowhead(52418, MagicMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_bop_equippable_item(self):
        """BoP crafted gear (Binds when picked up + equipment slot) is equippable."""
        tooltip_html = (
            '<a href="/item=219336/glyph-etched-breastplate">Glyph-Etched Breastplate</a>'
            "<br>Binds when picked up"
            "<table><tr><td>Chest</td><th>Mail</th></tr></table>"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"name": "Glyph-Etched Breastplate", "icon": "inv_chest_mail", "quality": 4, "tooltip": tooltip_html}
        ).encode()

        with patch("utils.blizzard.urllib.request.urlopen", return_value=mock_resp):
            result = await _resolve_recipe_wowhead(50215, MagicMock())

        assert result is not None
        assert result["item_id"] == 219336
        assert result["is_equippable"] is True

    @pytest.mark.asyncio
    async def test_non_equippable_item(self):
        """Non-equippable crafted item (reagent) detected correctly."""
        tooltip_html = '<a href="/item=243574/song-gear">Song Gear</a><br>Crafting Reagent'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"name": "Song Gear", "icon": "inv_gear", "quality": 2, "tooltip": tooltip_html}
        ).encode()

        with patch("utils.blizzard.urllib.request.urlopen", return_value=mock_resp):
            result = await _resolve_recipe_wowhead(52407, MagicMock())

        assert result is not None
        assert result["item_id"] == 243574
        assert result["is_equippable"] is False

    @pytest.mark.asyncio
    async def test_no_item_link_returns_none(self):
        """Recipe with no item links in tooltip returns None."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"name": "Weird Recipe", "icon": "inv_misc", "quality": 2, "tooltip": "<table>no items</table>"}
        ).encode()

        with patch("utils.blizzard.urllib.request.urlopen", return_value=mock_resp):
            result = await _resolve_recipe_wowhead(12345, MagicMock())

        assert result is None


class TestSyncCraftingRecipes:
    @pytest.mark.asyncio
    async def test_end_to_end_sync(self, db_session):
        from models.wow import CraftingRecipeCache

        api = _make_api()
        log = MagicMock()

        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 2910, "name": "Midnight"}, {"id": 2875, "name": "TWW"}]}
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": tid * 10, "name": f"Sword {tid}"}]}]
        }

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:

            async def fake_resolve(recipe_id, log):
                return {
                    "item_id": recipe_id + 1000,
                    "item_name": f"Item {recipe_id}",
                    "is_equippable": True,
                    "icon_url": f"https://icon/{recipe_id}.jpg",
                }

            mock_resolve.side_effect = fake_resolve

            recipe_count, profession_count = await sync_crafting_recipes(api, db_session, log)

        assert recipe_count == 2  # one recipe per tier, 2 tiers
        assert profession_count == 1
        results = CraftingRecipeCache.get_by_profession(164, db_session)
        assert len(results) == 2
        assert {r.TierId for r in results} == {2910, 2875}

    @pytest.mark.asyncio
    async def test_takes_top_2_tiers_only(self, db_session):
        api = _make_api()
        log = MagicMock()

        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {
            "skill_tiers": [
                {"id": 100, "name": "Classic"},
                {"id": 200, "name": "TBC"},
                {"id": 300, "name": "Current"},
            ]
        }

        fetched_tiers = []

        def mock_skill_tier(pid, tid):
            fetched_tiers.append(tid)
            return {"categories": [{"recipes": [{"id": tid, "name": f"Recipe {tid}"}]}]}

        api.profession_skill_tier = mock_skill_tier

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 1,
                "item_name": "Item",
                "is_equippable": True,
                "icon_url": None,
            }
            await sync_crafting_recipes(api, db_session, log)

        # Only the top 2 tiers (300, 200) should be fetched — NOT 100
        assert sorted(fetched_tiers) == [200, 300]

    @pytest.mark.asyncio
    async def test_skips_non_equippable(self, db_session):
        from models.wow import CraftingRecipeCache

        api = _make_api()
        log = MagicMock()

        api.professions_index = lambda: {"professions": [{"id": 171, "name": "Alchemy"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Current"}]}
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": 10, "name": "Health Potion"}]}]
        }

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 200,
                "item_name": "Health Potion",
                "is_equippable": False,
                "icon_url": None,
            }
            recipe_count, _ = await sync_crafting_recipes(api, db_session, log)

        assert recipe_count == 0
        assert CraftingRecipeCache.get_by_profession(171, db_session) == []

    @pytest.mark.asyncio
    async def test_skips_non_crafting_professions(self, db_session):
        api = _make_api()
        log = MagicMock()
        api.professions_index = lambda: {"professions": [{"id": 186, "name": "Mining"}]}

        recipe_count, profession_count = await sync_crafting_recipes(api, db_session, log)
        assert recipe_count == 0
        assert profession_count == 0

    @pytest.mark.asyncio
    async def test_upserts_existing_recipe(self, db_session):
        from models.wow import CraftingRecipeCache

        db_session.add(
            CraftingRecipeCache(
                ProfessionId=164,
                ProfessionName="Blacksmithing",
                RecipeId=10,
                ItemId=100,
                ItemName="Old Name",
                IconUrl="old.jpg",
            )
        )
        db_session.flush()

        api = _make_api()
        log = MagicMock()
        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Current"}]}
        api.profession_skill_tier = lambda pid, tid: {"categories": [{"recipes": [{"id": 10, "name": "New Sword"}]}]}

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 200,
                "item_name": "New Sword",
                "is_equippable": True,
                "icon_url": "new.jpg",
            }
            await sync_crafting_recipes(api, db_session, log)

        results = CraftingRecipeCache.get_by_profession(164, db_session)
        assert len(results) == 1
        assert results[0].ItemName == "New Sword"
        assert results[0].IconUrl == "new.jpg"

    @pytest.mark.asyncio
    async def test_single_tier_profession(self, db_session):
        """Profession with only 1 tier still works (takes that 1 tier)."""
        api = _make_api()
        log = MagicMock()
        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 100, "name": "Only Tier"}]}
        api.profession_skill_tier = lambda pid, tid: {"categories": [{"recipes": [{"id": 1, "name": "Sword"}]}]}

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 1,
                "item_name": "Sword",
                "is_equippable": True,
                "icon_url": None,
            }
            recipe_count, _ = await sync_crafting_recipes(api, db_session, log)

        assert recipe_count == 1

    @pytest.mark.asyncio
    async def test_stores_tier_id(self, db_session):
        """Each cached recipe records which tier it belongs to."""
        from models.wow import CraftingRecipeCache

        api = _make_api()
        log = MagicMock()
        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 300, "name": "Current"}, {"id": 200, "name": "Previous"}]}
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": tid * 10, "name": f"Item {tid}"}]}]
        }

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 1,
                "item_name": "Item",
                "is_equippable": True,
                "icon_url": None,
            }
            await sync_crafting_recipes(api, db_session, log)

        all_rows = db_session.query(CraftingRecipeCache).all()
        tier_ids = {r.TierId for r in all_rows}
        assert tier_ids == {200, 300}

    @pytest.mark.asyncio
    async def test_cleans_stale_tiers(self, db_session):
        """Recipes from tiers that rotated out of the top 2 are deleted."""
        from models.wow import CraftingRecipeCache

        # Pre-populate a recipe from an old tier
        db_session.add(
            CraftingRecipeCache(
                ProfessionId=164,
                ProfessionName="Blacksmithing",
                TierId=100,
                RecipeId=999,
                ItemId=999,
                ItemName="Old Expansion Sword",
                IconUrl=None,
            )
        )
        db_session.flush()

        api = _make_api()
        log = MagicMock()
        api.professions_index = lambda: {"professions": [{"id": 164, "name": "Blacksmithing"}]}
        api.profession = lambda pid: {"skill_tiers": [{"id": 300, "name": "Current"}, {"id": 200, "name": "Previous"}]}
        api.profession_skill_tier = lambda pid, tid: {
            "categories": [{"recipes": [{"id": tid * 10, "name": f"Item {tid}"}]}]
        }

        with patch("utils.blizzard._resolve_recipe_wowhead") as mock_resolve:
            mock_resolve.return_value = {
                "item_id": 1,
                "item_name": "Item",
                "is_equippable": True,
                "icon_url": None,
            }
            await sync_crafting_recipes(api, db_session, log)

        # Old tier 100 recipe should be gone
        all_rows = db_session.query(CraftingRecipeCache).filter(CraftingRecipeCache.ProfessionId == 164).all()
        tier_ids = {r.TierId for r in all_rows}
        assert 100 not in tier_ids
        assert tier_ids == {200, 300}
        assert not any(r.RecipeId == 999 for r in all_rows)


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
