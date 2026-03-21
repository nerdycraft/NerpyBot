# -*- coding: utf-8 -*-
"""Tests for the _cache_recipe_query decorator on CraftingRecipeCache."""

from models.wow import BIND_ON_ACQUIRE, RECIPE_TYPE_CRAFTED, CraftingRecipeCache, invalidate_recipe_cache


def _recipe(**kwargs) -> CraftingRecipeCache:
    defaults = {
        "ProfessionId": 164,
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


class TestCacheRecipeQueryDecorator:
    def test_second_call_returns_cached_result(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.commit()

        r1 = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)
        r2 = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)

        assert r1 is r2

    def test_different_args_produce_separate_entries(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164, ProfessionName="Blacksmithing"))
        db_session.add(_recipe(RecipeId=2, ProfessionId=333, ProfessionName="Engineering"))
        db_session.commit()

        r1 = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)
        r2 = CraftingRecipeCache.get_by_profession(333, RECIPE_TYPE_CRAFTED, db_session)

        assert len(r1) == 1
        assert r1[0].ProfessionId == 164
        assert len(r2) == 1
        assert r2[0].ProfessionId == 333

    def test_invalidate_forces_fresh_db_query(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.commit()

        r1 = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)
        assert len(r1) == 1

        invalidate_recipe_cache()

        db_session.add(_recipe(RecipeId=2, ProfessionId=164))
        db_session.commit()

        r2 = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)
        assert len(r2) == 2
        assert r1 is not r2

    def test_set_args_are_coerced_to_frozenset_for_cache_key(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.add(_recipe(RecipeId=2, ProfessionId=333))
        db_session.commit()

        # Passing same profession IDs as a set vs frozenset should produce the same cache entry.
        from models.wow import RECIPE_TYPE_CRAFTED, CraftingRecipeCache, invalidate_recipe_cache

        invalidate_recipe_cache()
        r1 = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164})
        r2 = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164})
        assert r1 is r2

    def test_frozenset_and_set_produce_same_cache_key(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.commit()

        from models.wow import RECIPE_TYPE_CRAFTED, CraftingRecipeCache, invalidate_recipe_cache

        invalidate_recipe_cache()
        # First call with a plain set populates the cache.
        r1 = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids={164})
        # Second call with a frozenset of the same values should hit the same cache entry.
        r2 = CraftingRecipeCache.get_by_type_and_subclass(
            RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids=frozenset({164})
        )
        assert r1 is r2

    def test_none_and_empty_set_produce_same_cache_key(self, db_session):
        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.commit()

        from models.wow import RECIPE_TYPE_CRAFTED, CraftingRecipeCache, invalidate_recipe_cache

        invalidate_recipe_cache()
        # First call with None populates the cache.
        r1 = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids=None)
        # Second call with an empty set should normalize to the same key and hit the cache.
        r2 = CraftingRecipeCache.get_by_type_and_subclass(RECIPE_TYPE_CRAFTED, 4, 4, db_session, profession_ids=set())
        assert r1 is r2

    def test_cached_results_are_session_detached(self, db_session):
        from sqlalchemy import inspect as sa_inspect

        db_session.add(_recipe(RecipeId=1, ProfessionId=164))
        db_session.commit()

        results = CraftingRecipeCache.get_by_profession(164, RECIPE_TYPE_CRAFTED, db_session)
        assert len(results) == 1

        # Object must be detached (not bound to the session).
        state = sa_inspect(results[0])
        assert state.detached
