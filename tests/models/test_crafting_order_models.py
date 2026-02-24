# -*- coding: utf-8 -*-
"""Tests for crafting order database models."""

import pytest
from sqlalchemy.exc import IntegrityError

from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRecipeCache, CraftingRoleMapping


class TestCraftingBoardConfig:
    def test_create_and_get_by_guild(self, db_session):
        config = CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Test board")
        db_session.add(config)
        db_session.flush()

        result = CraftingBoardConfig.get_by_guild(100, db_session)
        assert result is not None
        assert result.ChannelId == 200

    def test_unique_guild_constraint(self, db_session):
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board 1"))
        db_session.flush()
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=300, Description="Board 2"))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_delete_by_guild(self, db_session):
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board"))
        db_session.flush()
        CraftingBoardConfig.delete_by_guild(100, db_session)
        db_session.flush()
        assert CraftingBoardConfig.get_by_guild(100, db_session) is None

    def test_delete_nonexistent_returns_none(self, db_session):
        result = CraftingBoardConfig.delete_by_guild(999, db_session)
        assert result is None


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

    def test_unique_guild_role_constraint(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.flush()
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=165))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_delete_by_guild(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=2, ProfessionId=165))
        db_session.flush()

        CraftingRoleMapping.delete_by_guild(100, db_session)
        db_session.flush()
        assert CraftingRoleMapping.get_by_guild(100, db_session) == []


class TestCraftingRecipeCache:
    def test_get_by_profession_returns_all_cached_tiers(self, db_session):
        """get_by_profession returns recipes from all cached tiers, sorted alphabetically."""
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=11, ItemId=101, ItemName="Axe"))
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=200, RecipeId=13, ItemId=103, ItemName="Old Mace"))
        db_session.add(CraftingRecipeCache(ProfessionId=2, TierId=300, RecipeId=12, ItemId=102, ItemName="Potion"))
        db_session.flush()

        results = CraftingRecipeCache.get_by_profession(1, db_session)
        assert len(results) == 3  # both tiers for profession 1
        assert results[0].ItemName == "Axe"  # alphabetical

    def test_unique_recipe_constraint(self, db_session):
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.flush()
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword 2"))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_delete_all(self, db_session):
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.add(CraftingRecipeCache(ProfessionId=2, TierId=300, RecipeId=11, ItemId=101, ItemName="Potion"))
        db_session.flush()
        CraftingRecipeCache.delete_all(db_session)
        db_session.flush()
        assert CraftingRecipeCache.get_by_profession(1, db_session) == []
        assert CraftingRecipeCache.get_by_profession(2, db_session) == []

    def test_delete_stale(self, db_session):
        """delete_stale removes recipes from tiers not in the valid set."""
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=100, RecipeId=1, ItemId=1, ItemName="Ancient"))
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=200, RecipeId=2, ItemId=2, ItemName="Old"))
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=3, ItemId=3, ItemName="Current"))
        db_session.flush()

        CraftingRecipeCache.delete_stale(1, [200, 300], db_session)
        db_session.flush()

        remaining = db_session.query(CraftingRecipeCache).filter(CraftingRecipeCache.ProfessionId == 1).all()
        assert len(remaining) == 2
        assert {r.TierId for r in remaining} == {200, 300}

    def test_profession_name_stored(self, db_session):
        db_session.add(
            CraftingRecipeCache(
                ProfessionId=164, ProfessionName="Blacksmithing", TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"
            )
        )
        db_session.flush()

        results = CraftingRecipeCache.get_by_profession(164, db_session)
        assert results[0].ProfessionName == "Blacksmithing"


class TestCraftingOrder:
    def test_create_and_get_by_id(self, db_session):
        order = CraftingOrder(
            GuildId=100, ChannelId=200, CreatorId=300, ProfessionRoleId=400, ItemName="Sword", Status="open"
        )
        db_session.add(order)
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result is not None
        assert result.ItemName == "Sword"
        assert result.Status == "open"

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

    def test_state_transition_accept(self, db_session):
        order = CraftingOrder(
            GuildId=100, ChannelId=200, CreatorId=300, ProfessionRoleId=400, ItemName="Sword", Status="open"
        )
        db_session.add(order)
        db_session.flush()
        order.Status = "in_progress"
        order.CrafterId = 500
        db_session.flush()
        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "in_progress"
        assert result.CrafterId == 500

    def test_state_transition_drop(self, db_session):
        order = CraftingOrder(
            GuildId=100,
            ChannelId=200,
            CreatorId=300,
            ProfessionRoleId=400,
            ItemName="Sword",
            Status="in_progress",
            CrafterId=500,
        )
        db_session.add(order)
        db_session.flush()
        order.Status = "open"
        order.CrafterId = None
        db_session.flush()
        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "open"
        assert result.CrafterId is None
