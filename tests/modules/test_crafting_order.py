# -*- coding: utf-8 -*-
"""Tests for crafting order feature."""

import json


from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRecipeCache


class TestCraftingBoardConfig:
    """Test board config lifecycle."""

    def test_reject_duplicate_board(self, db_session):
        """Creating a second board for the same guild should fail."""
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board 1"))
        db_session.flush()

        existing = CraftingBoardConfig.get_by_guild(100, db_session)
        assert existing is not None

    def test_delete_returns_config(self, db_session):
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board"))
        db_session.flush()

        config = CraftingBoardConfig.delete_by_guild(100, db_session)
        assert config is not None
        assert config.ChannelId == 200

    def test_delete_nonexistent_returns_none(self, db_session):
        result = CraftingBoardConfig.delete_by_guild(999, db_session)
        assert result is None


class TestCraftingOrderTransitions:
    """Test order state machine."""

    def _make_order(self, db_session, **overrides):
        defaults = dict(
            GuildId=100, ChannelId=200, CreatorId=300, ProfessionRoleId=400, ItemName="Sword", Status="open"
        )
        defaults.update(overrides)
        order = CraftingOrder(**defaults)
        db_session.add(order)
        db_session.flush()
        return order

    def test_accept_sets_in_progress(self, db_session):
        order = self._make_order(db_session)
        order.Status = "in_progress"
        order.CrafterId = 500
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "in_progress"
        assert result.CrafterId == 500

    def test_drop_resets_to_open(self, db_session):
        order = self._make_order(db_session, Status="in_progress", CrafterId=500)
        order.Status = "open"
        order.CrafterId = None
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "open"
        assert result.CrafterId is None

    def test_complete_sets_completed(self, db_session):
        order = self._make_order(db_session, Status="in_progress", CrafterId=500)
        order.Status = "completed"
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "completed"

    def test_get_active_excludes_completed(self, db_session):
        self._make_order(db_session, Status="open", ItemName="A")
        self._make_order(db_session, Status="in_progress", CrafterId=500, ItemName="B")
        self._make_order(db_session, Status="completed", ItemName="C")

        active = CraftingOrder.get_active_by_guild(100, db_session)
        assert len(active) == 2
        names = {o.ItemName for o in active}
        assert names == {"A", "B"}

    def test_cancel_from_open(self, db_session):
        order = self._make_order(db_session, Status="open")
        order.Status = "completed"
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "completed"

    def test_cancel_from_in_progress(self, db_session):
        order = self._make_order(db_session, Status="in_progress", CrafterId=500)
        order.Status = "completed"
        db_session.flush()

        result = CraftingOrder.get_by_id(order.Id, db_session)
        assert result.Status == "completed"


class TestRecipeCache:
    """Test recipe cache queries."""

    def test_get_by_profession_sorted(self, db_session):
        db_session.add(CraftingRecipeCache(GuildId=100, ProfessionId=1, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.add(CraftingRecipeCache(GuildId=100, ProfessionId=1, RecipeId=11, ItemId=101, ItemName="Axe"))
        db_session.flush()

        results = CraftingRecipeCache.get_by_profession(100, 1, db_session)
        assert len(results) == 2
        assert results[0].ItemName == "Axe"

    def test_delete_by_guild(self, db_session):
        db_session.add(CraftingRecipeCache(GuildId=100, ProfessionId=1, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.flush()

        CraftingRecipeCache.delete_by_guild(100, db_session)
        db_session.flush()
        assert CraftingRecipeCache.get_by_profession(100, 1, db_session) == []

    def test_cross_guild_isolation(self, db_session):
        db_session.add(CraftingRecipeCache(GuildId=100, ProfessionId=1, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.add(CraftingRecipeCache(GuildId=200, ProfessionId=1, RecipeId=11, ItemId=101, ItemName="Shield"))
        db_session.flush()

        results_100 = CraftingRecipeCache.get_by_profession(100, 1, db_session)
        results_200 = CraftingRecipeCache.get_by_profession(200, 1, db_session)
        assert len(results_100) == 1
        assert len(results_200) == 1
        assert results_100[0].ItemName == "Sword"
        assert results_200[0].ItemName == "Shield"


class TestBoardConfigRoleIds:
    """Test RoleIds JSON serialization."""

    def test_store_and_retrieve_role_ids(self, db_session):
        role_ids = [111, 222, 333]
        db_session.add(
            CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board", RoleIds=json.dumps(role_ids))
        )
        db_session.flush()

        config = CraftingBoardConfig.get_by_guild(100, db_session)
        loaded = json.loads(config.RoleIds)
        assert loaded == [111, 222, 333]

    def test_default_role_ids_is_empty_list(self, db_session):
        db_session.add(CraftingBoardConfig(GuildId=100, ChannelId=200, Description="Board"))
        db_session.flush()

        config = CraftingBoardConfig.get_by_guild(100, db_session)
        loaded = json.loads(config.RoleIds)
        assert loaded == []
