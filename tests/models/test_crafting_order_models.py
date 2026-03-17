# -*- coding: utf-8 -*-
"""Tests for crafting order database models."""

import pytest

from models.wow import (
    BIND_ON_ACQUIRE,
    BIND_ON_EQUIP,
    BIND_TO_ACCOUNT,
    RECIPE_TYPE_CRAFTED,
    CraftingOrder,
    CraftingRecipeCache,
    CraftingRoleMapping,
)


def _recipe(**kwargs) -> CraftingRecipeCache:
    """Build a CraftingRecipeCache with sensible defaults, override via kwargs."""
    defaults = {
        "ProfessionId": 164,  # Blacksmithing (gear profession)
        "ProfessionName": "Blacksmithing",
        "ItemName": "Test Item",
        "RecipeType": RECIPE_TYPE_CRAFTED,
        "ItemClassName": "Armor",
        "ItemClassId": 4,
        "ItemSubClassName": "Plate",
        "ItemSubClassId": 4,
        "BindType": BIND_ON_ACQUIRE,
        "CategoryName": "Plate Armor",
    }
    defaults.update(kwargs)
    return CraftingRecipeCache(**defaults)


class TestOrderableFilterWithBoE:
    """BoE gear items are now included in the orderable filter for gear professions."""

    def test_boe_gear_included(self, db_session):
        db_session.add(_recipe(RecipeId=1, BindType=BIND_ON_EQUIP, ProfessionId=164))
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164}, orderable_only=True
        )
        assert len(results) == 1

    def test_bop_gear_still_included(self, db_session):
        db_session.add(_recipe(RecipeId=2, BindType=BIND_ON_ACQUIRE, ProfessionId=164))
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164}, orderable_only=True
        )
        assert len(results) == 1

    def test_boa_gear_still_included(self, db_session):
        db_session.add(_recipe(RecipeId=3, BindType=BIND_TO_ACCOUNT, ProfessionId=164))
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164}, orderable_only=True
        )
        assert len(results) == 1

    def test_unbound_gear_excluded(self, db_session):
        db_session.add(_recipe(RecipeId=4, BindType=None, ProfessionId=164))
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164}, orderable_only=True
        )
        assert len(results) == 0


class TestPvPCondition:
    """_pvp_condition matches items with 'competitor' or 'pvp' in CategoryName."""

    def test_competitor_keyword_matches(self, db_session):
        db_session.add(_recipe(RecipeId=10, CategoryName="Competitor's Plate Armor", BindType=BIND_ON_ACQUIRE))
        db_session.flush()

        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session)
        assert len(results) == 1

    def test_pvp_keyword_matches(self, db_session):
        db_session.add(
            _recipe(
                RecipeId=11, ItemClassId=2, ItemClassName="Weapon", CategoryName="PvP Swords", BindType=BIND_ON_ACQUIRE
            )
        )
        db_session.flush()

        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session)
        assert len(results) == 1

    def test_non_pvp_category_excluded(self, db_session):
        db_session.add(_recipe(RecipeId=12, CategoryName="Plate Armor"))
        db_session.flush()

        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session)
        assert len(results) == 0

    def test_unbound_pvp_excluded_from_pvp_classes(self, db_session):
        # get_pvp_item_classes requires BindType IS NOT NULL
        db_session.add(_recipe(RecipeId=13, CategoryName="Competitor's Plate Armor", BindType=None))
        db_session.flush()

        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session)
        assert len(results) == 0


class TestExcludePvP:
    """exclude_pvp=True removes PvP items from get_item_classes / get_item_subclasses / get_by_type_and_subclass."""

    def test_get_item_classes_excludes_pvp_only_items(self, db_session):
        db_session.add(_recipe(RecipeId=20, ItemClassId=4, CategoryName="Competitor's Plate"))
        db_session.flush()

        results = CraftingRecipeCache.get_item_classes(RECIPE_TYPE_CRAFTED, db_session, exclude_pvp=True)
        assert len(results) == 0

    def test_get_item_classes_keeps_non_pvp(self, db_session):
        db_session.add(_recipe(RecipeId=21, ItemClassId=4, CategoryName="Plate Armor"))
        db_session.flush()

        results = CraftingRecipeCache.get_item_classes(RECIPE_TYPE_CRAFTED, db_session, exclude_pvp=True)
        assert len(results) == 1

    def test_get_item_subclasses_excludes_pvp(self, db_session):
        db_session.add(_recipe(RecipeId=22, ItemClassId=4, ItemSubClassId=4, CategoryName="Competitor's Plate"))
        db_session.flush()

        results = CraftingRecipeCache.get_item_subclasses(RECIPE_TYPE_CRAFTED, 4, db_session, exclude_pvp=True)
        assert len(results) == 0

    def test_get_by_type_and_subclass_excludes_pvp(self, db_session):
        db_session.add(_recipe(RecipeId=23, ItemClassId=4, ItemSubClassId=4, CategoryName="Competitor's Plate"))
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, exclude_pvp=True)
        assert len(results) == 0


class TestPvPQueries:
    """get_pvp_item_classes, get_pvp_item_subclasses, get_pvp_items."""

    @pytest.fixture(autouse=True)
    def _seed(self, db_session):
        # PvP armor items
        db_session.add(
            _recipe(
                RecipeId=30,
                ItemClassId=4,
                ItemSubClassId=1,
                ItemSubClassName="Cloth",
                CategoryName="Competitor's Cloth",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        db_session.add(
            _recipe(
                RecipeId=31,
                ItemClassId=4,
                ItemSubClassId=4,
                ItemSubClassName="Plate",
                CategoryName="Competitor's Plate",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # PvP weapon
        db_session.add(
            _recipe(
                RecipeId=32,
                ItemClassId=2,
                ItemSubClassId=7,
                ItemClassName="Weapon",
                CategoryName="PvP Swords",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Non-PvP armor (same class/subclass as RecipeId=31)
        db_session.add(
            _recipe(RecipeId=33, ItemClassId=4, ItemSubClassId=4, CategoryName="Plate Armor", BindType=BIND_ON_ACQUIRE)
        )
        db_session.flush()

    def test_pvp_item_classes_returns_pvp_classes(self, db_session):
        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session)
        class_ids = {r[0] for r in results}
        assert 4 in class_ids  # Armor
        assert 2 in class_ids  # Weapon

    def test_pvp_item_subclasses_filters_by_class(self, db_session):
        results = CraftingRecipeCache.get_pvp_item_subclasses(RECIPE_TYPE_CRAFTED, 4, db_session)
        subclass_ids = {r[0] for r in results}
        assert 1 in subclass_ids  # Cloth
        assert 4 in subclass_ids  # Plate
        assert len(results) == 2

    def test_pvp_items_with_subclass(self, db_session):
        results = CraftingRecipeCache.get_pvp_items(RECIPE_TYPE_CRAFTED, 4, 4, db_session)
        assert len(results) == 1
        assert results[0].RecipeId == 31

    def test_pvp_items_without_subclass_returns_all_pvp_in_class(self, db_session):
        results = CraftingRecipeCache.get_pvp_items(RECIPE_TYPE_CRAFTED, 4, None, db_session)
        recipe_ids = {r.RecipeId for r in results}
        assert 30 in recipe_ids
        assert 31 in recipe_ids
        assert 33 not in recipe_ids  # non-PvP excluded

    def test_pvp_queries_profession_filter(self, db_session):
        results = CraftingRecipeCache.get_pvp_item_classes(RECIPE_TYPE_CRAFTED, db_session, profession_ids={999})
        assert len(results) == 0


class TestRaidPrepQueries:
    """get_raid_prep_categories and get_raid_prep_items."""

    @pytest.fixture(autouse=True)
    def _seed(self, db_session):
        # Consumables — NULL BindType, matched by keyword
        db_session.add(
            _recipe(
                RecipeId=40,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Elemental Potions",
                BindType=None,
            )
        )
        db_session.add(
            _recipe(
                RecipeId=41,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Sin'dorei Flasks",
                BindType=None,
            )
        )
        # Cauldron — bound, any BindType
        db_session.add(
            _recipe(
                RecipeId=42,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Alchemy Cauldrons",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Non-raid-prep (armor, bound)
        db_session.add(
            _recipe(
                RecipeId=43,
                ItemClassName="Armor",
                ItemClassId=4,
                ItemSubClassId=4,
                CategoryName="Plate Armor",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        db_session.flush()

    def test_categories_includes_potions(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Elemental Potions" in categories

    def test_categories_includes_flasks(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Sin'dorei Flasks" in categories

    def test_categories_includes_cauldrons(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Alchemy Cauldrons" in categories

    def test_categories_excludes_non_prep(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Plate Armor" not in categories

    def test_get_items_by_category(self, db_session):
        results = CraftingRecipeCache.get_raid_prep_items(RECIPE_TYPE_CRAFTED, "Elemental Potions", db_session)
        assert len(results) == 1
        assert results[0].RecipeId == 40

    def test_profession_filter(self, db_session):
        results = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session, profession_ids={999})
        assert len(results) == 0


class TestCategoryQueries:
    """get_category_names and get_by_type_subclass_and_category."""

    @pytest.fixture(autouse=True)
    def _seed(self, db_session):
        db_session.add(_recipe(RecipeId=50, ItemClassId=4, ItemSubClassId=1, CategoryName="Cloth Hat"))
        db_session.add(_recipe(RecipeId=51, ItemClassId=4, ItemSubClassId=1, CategoryName="Cloth Robe"))
        db_session.add(_recipe(RecipeId=52, ItemClassId=4, ItemSubClassId=1, CategoryName="Competitor's Cloth"))
        db_session.flush()

    def test_get_category_names_returns_all(self, db_session):
        names = CraftingRecipeCache.get_category_names(RECIPE_TYPE_CRAFTED, 4, 1, db_session)
        assert sorted(names) == ["Cloth Hat", "Cloth Robe", "Competitor's Cloth"]

    def test_get_category_names_excludes_pvp(self, db_session):
        names = CraftingRecipeCache.get_category_names(RECIPE_TYPE_CRAFTED, 4, 1, db_session, exclude_pvp=True)
        assert "Competitor's Cloth" not in names
        assert "Cloth Hat" in names
        assert "Cloth Robe" in names

    def test_get_by_type_subclass_and_category(self, db_session):
        results = CraftingRecipeCache.get_by_type_subclass_and_category(
            RECIPE_TYPE_CRAFTED, 4, 1, "Cloth Hat", db_session
        )
        assert len(results) == 1
        assert results[0].RecipeId == 50

    def test_get_by_type_subclass_and_category_wrong_category(self, db_session):
        results = CraftingRecipeCache.get_by_type_subclass_and_category(
            RECIPE_TYPE_CRAFTED, 4, 1, "Plate Armor", db_session
        )
        assert len(results) == 0


class TestOtherQueries:
    """get_other_categories and get_other_items."""

    @pytest.fixture(autouse=True)
    def _seed(self, db_session):
        # Bag — bound, Container class (not Armor/Weapon/Profession), not PvP
        db_session.add(
            _recipe(
                RecipeId=60,
                ProfessionId=197,
                ItemClassName="Container",
                ItemClassId=1,
                ItemSubClassId=0,
                CategoryName="Embroidered Bags",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Treatise — bound, Recipe class
        db_session.add(
            _recipe(
                RecipeId=61,
                ProfessionId=164,
                ItemClassName="Recipe",
                ItemClassId=9,
                ItemSubClassId=0,
                CategoryName="Profession Treatises",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Excluded: Armor class
        db_session.add(
            _recipe(
                RecipeId=62, ItemClassName="Armor", ItemClassId=4, CategoryName="Plate Armor", BindType=BIND_ON_ACQUIRE
            )
        )
        # Excluded: PvP
        db_session.add(
            _recipe(
                RecipeId=63,
                ItemClassName="Container",
                ItemClassId=1,
                CategoryName="Competitor's Bags",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Excluded: unbound
        db_session.add(
            _recipe(RecipeId=64, ItemClassName="Container", ItemClassId=1, CategoryName="Free Bags", BindType=None)
        )
        # Excluded: Cauldron (covered by raid prep)
        db_session.add(
            _recipe(
                RecipeId=65,
                ItemClassName="Consumable",
                ItemClassId=0,
                CategoryName="Alchemy Cauldrons",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        db_session.flush()

    def test_includes_bags_and_treatises(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Embroidered Bags" in categories
        assert "Profession Treatises" in categories

    def test_excludes_armor_class(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Plate Armor" not in categories

    def test_excludes_pvp(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Competitor's Bags" not in categories

    def test_excludes_unbound(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Free Bags" not in categories

    def test_excludes_cauldrons(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert "Alchemy Cauldrons" not in categories

    def test_get_items_by_category(self, db_session):
        results = CraftingRecipeCache.get_other_items(RECIPE_TYPE_CRAFTED, "Embroidered Bags", db_session)
        assert len(results) == 1
        assert results[0].RecipeId == 60

    def test_profession_filter(self, db_session):
        results = CraftingRecipeCache.get_other_items(
            RECIPE_TYPE_CRAFTED, "Embroidered Bags", db_session, profession_ids={164}
        )
        # RecipeId=60 has ProfessionId=197, so filtered out
        assert len(results) == 0


class TestCraftingRoleMapping:
    def test_get_by_guild(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=2, ProfessionId=165))
        db_session.add(CraftingRoleMapping(GuildId=200, RoleId=3, ProfessionId=164))
        db_session.flush()

        results = CraftingRoleMapping.get_by_guild(100, db_session)
        assert len(results) == 2

    def test_get_profession_id(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.flush()

        assert CraftingRoleMapping.get_profession_id(100, 1, db_session) == 164
        assert CraftingRoleMapping.get_profession_id(100, 999, db_session) is None


class TestCraftingOrder:
    def test_get_active_by_guild(self, db_session):
        db_session.add(
            CraftingOrder(GuildId=100, ChannelId=200, CreatorId=300, ProfessionRoleId=400, ItemName="A", Status="open")
        )
        db_session.add(
            CraftingOrder(
                GuildId=100, ChannelId=200, CreatorId=300, ProfessionRoleId=400, ItemName="B", Status="completed"
            )
        )
        db_session.flush()

        active = CraftingOrder.get_active_by_guild(100, db_session)
        assert len(active) == 1
        assert active[0].ItemName == "A"


class TestCraftingRecipeCacheFindBestMatch:
    def test_exact_match(self, db_session):
        db_session.add(_recipe(RecipeId=100, ItemName="Farstrider Rock Satchel", ItemId=244719))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("Farstrider Rock Satchel", db_session)
        assert result is not None
        assert result.ItemId == 244719

    def test_exact_match_case_insensitive(self, db_session):
        db_session.add(_recipe(RecipeId=100, ItemName="Farstrider Rock Satchel", ItemId=244719))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("farstrider rock satchel", db_session)
        assert result is not None
        assert result.ItemId == 244719

    def test_substring_match_unique_item(self, db_session):
        db_session.add(_recipe(RecipeId=100, ItemName="Farstrider Rock Satchel", ItemId=244719))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("Rock Satchel", db_session)
        assert result is not None
        assert result.ItemId == 244719

    def test_substring_match_same_item_multiple_professions(self, db_session):
        # Same ItemId crafted by two professions — should still return a result
        db_session.add(_recipe(RecipeId=101, ItemName="Farstrider Rock Satchel", ItemId=244719, ProfessionId=164))
        db_session.add(_recipe(RecipeId=102, ItemName="Farstrider Rock Satchel", ItemId=244719, ProfessionId=165))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("Farstrider Rock Satchel", db_session)
        assert result is not None
        assert result.ItemId == 244719

    def test_substring_match_ambiguous_returns_none(self, db_session):
        # Two *different* items match the substring — ambiguous, return None
        db_session.add(_recipe(RecipeId=101, ItemName="Farstrider Rock Satchel", ItemId=244719))
        db_session.add(_recipe(RecipeId=102, ItemName="Farstrider Rock Backpack", ItemId=244720))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("Farstrider Rock", db_session)
        assert result is None

    def test_no_match_returns_none(self, db_session):
        db_session.add(_recipe(RecipeId=100, ItemName="Farstrider Hardhat", ItemId=244715))
        db_session.flush()

        result = CraftingRecipeCache.find_best_match("Completely Unknown Item", db_session)
        assert result is None
