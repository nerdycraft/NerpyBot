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

    def test_categories_returns_tuples(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in categories)

    def test_categories_includes_potions(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Elemental Potions" in names

    def test_categories_includes_flasks(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Sin'dorei Flasks" in names

    def test_categories_includes_cauldrons(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Alchemy Cauldrons" in names

    def test_categories_excludes_non_prep(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Plate Armor" not in names

    def test_categories_locale_is_none_when_not_set(self, db_session):
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        for name, locales in categories:
            assert locales is None

    def test_categories_locale_returned_when_set(self, db_session):
        db_session.add(
            _recipe(
                RecipeId=45,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Light Potions",
                CategoryNameLocales={"de": "Leichte Tränke"},
                BindType=None,
            )
        )
        db_session.flush()
        categories = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session)
        locales_map = {name: locales for name, locales in categories}
        assert locales_map.get("Light Potions") == {"de": "Leichte Tränke"}

    def test_get_items_by_category(self, db_session):
        results = CraftingRecipeCache.get_raid_prep_items(RECIPE_TYPE_CRAFTED, "Elemental Potions", db_session)
        assert len(results) == 1
        assert results[0].RecipeId == 40

    def test_profession_filter(self, db_session):
        results = CraftingRecipeCache.get_raid_prep_categories(RECIPE_TYPE_CRAFTED, db_session, profession_ids={999})
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

    def test_returns_tuples(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in categories)

    def test_includes_bags(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Embroidered Bags" in names

    def test_excludes_treatises(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Profession Treatises" not in names

    def test_excludes_armor_class(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Plate Armor" not in names

    def test_excludes_pvp(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Competitor's Bags" not in names

    def test_excludes_unbound(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Free Bags" not in names

    def test_excludes_cauldrons(self, db_session):
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        names = [t[0] for t in categories]
        assert "Alchemy Cauldrons" not in names

    def test_locale_returned_when_set(self, db_session):
        db_session.add(
            _recipe(
                RecipeId=66,
                ProfessionId=197,
                ItemClassName="Container",
                ItemClassId=1,
                ItemSubClassId=0,
                CategoryName="Embroidered Bags",
                CategoryNameLocales={"de": "Gestickte Taschen"},
                BindType=BIND_ON_ACQUIRE,
            )
        )
        db_session.flush()
        categories = CraftingRecipeCache.get_other_categories(RECIPE_TYPE_CRAFTED, db_session)
        locales_map = {name: locales for name, locales in categories}
        assert locales_map.get("Embroidered Bags") == {"de": "Gestickte Taschen"}

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


class TestHeartyItems:
    """Hearty items do not pass the cooking orderable filter after removing 'hearty' from keywords."""

    def test_hearty_feast_not_orderable(self, db_session):
        # Hearty Feast: unbound, Cooking profession
        db_session.add(
            _recipe(
                RecipeId=70,
                ProfessionId=185,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Hearty",
                BindType=None,
            )
        )
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 0, 0, db_session, profession_ids={185}, orderable_only=True
        )
        assert len(results) == 0

    def test_hearty_food_not_orderable(self, db_session):
        # Hearty Food: BoA, Cooking profession
        db_session.add(
            _recipe(
                RecipeId=71,
                ProfessionId=185,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Hearty",
                BindType=BIND_TO_ACCOUNT,
            )
        )
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 0, 0, db_session, profession_ids={185}, orderable_only=True
        )
        assert len(results) == 0

    def test_named_feasts_still_orderable(self, db_session):
        # Named feast (CategoryName="Feast"): unbound, Cooking profession — still orderable
        db_session.add(
            _recipe(
                RecipeId=72,
                ProfessionId=185,
                ItemClassName="Consumable",
                ItemClassId=0,
                ItemSubClassId=0,
                CategoryName="Feast",
                BindType=None,
            )
        )
        db_session.flush()

        results = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 0, 0, db_session, profession_ids={185}, orderable_only=True
        )
        assert len(results) == 1
        assert results[0].RecipeId == 72


class TestProfKnowledgeQueries:
    """get_prof_knowledge_items and has_prof_knowledge_items."""

    @pytest.fixture(autouse=True)
    def _seed(self, db_session):
        # Treatise: Miscellaneous class, "Profession Treatises" category
        db_session.add(
            _recipe(
                RecipeId=80,
                ProfessionId=773,
                ItemClassName="Miscellaneous",
                ItemClassId=15,
                ItemSubClassId=0,
                CategoryName="Profession Treatises",
                BindType=BIND_TO_ACCOUNT,
            )
        )
        # Skinning knife: Miscellaneous class, "Profession Equipment" category
        db_session.add(
            _recipe(
                RecipeId=81,
                ProfessionId=164,
                ItemClassName="Miscellaneous",
                ItemClassId=15,
                ItemSubClassId=0,
                CategoryName="Profession Equipment",
                BindType=BIND_ON_ACQUIRE,
            )
        )
        # Real prof gear: ItemClassName="Profession" — should NOT match
        db_session.add(
            _recipe(
                RecipeId=82,
                ProfessionId=164,
                ItemClassName="Profession",
                ItemClassId=19,
                ItemSubClassId=0,
                CategoryName="Profession Equipment",
                BindType=BIND_ON_EQUIP,
            )
        )
        db_session.flush()

    def test_includes_treatises(self, db_session):
        results = CraftingRecipeCache.get_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session)
        ids = {r.RecipeId for r in results}
        assert 80 in ids

    def test_includes_misc_profession_equipment(self, db_session):
        results = CraftingRecipeCache.get_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session)
        ids = {r.RecipeId for r in results}
        assert 81 in ids

    def test_excludes_real_profession_gear(self, db_session):
        results = CraftingRecipeCache.get_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session)
        ids = {r.RecipeId for r in results}
        assert 82 not in ids

    def test_profession_filter(self, db_session):
        results = CraftingRecipeCache.get_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session, profession_ids={773})
        ids = {r.RecipeId for r in results}
        assert 80 in ids
        assert 81 not in ids

    def test_has_items_true(self, db_session):
        assert CraftingRecipeCache.has_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session) is True

    def test_has_items_false(self, db_session):
        assert (
            CraftingRecipeCache.has_prof_knowledge_items(RECIPE_TYPE_CRAFTED, db_session, profession_ids={999}) is False
        )


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
