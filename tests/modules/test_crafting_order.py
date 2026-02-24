# -*- coding: utf-8 -*-
"""Tests for crafting order feature."""

from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRecipeCache, CraftingRoleMapping


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
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=11, ItemId=101, ItemName="Axe"))
        db_session.flush()

        results = CraftingRecipeCache.get_by_profession(1, db_session)
        assert len(results) == 2
        assert results[0].ItemName == "Axe"

    def test_delete_all(self, db_session):
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.flush()

        CraftingRecipeCache.delete_all(db_session)
        db_session.flush()
        assert CraftingRecipeCache.get_by_profession(1, db_session) == []

    def test_no_guild_isolation_needed(self, db_session):
        """Recipe cache is bot-global — same recipe is stored once regardless of guild."""
        db_session.add(CraftingRecipeCache(ProfessionId=1, TierId=300, RecipeId=10, ItemId=100, ItemName="Sword"))
        db_session.flush()

        results = CraftingRecipeCache.get_by_profession(1, db_session)
        assert len(results) == 1
        assert results[0].ItemName == "Sword"


class TestRoleMapping:
    """Test role-to-profession mapping."""

    def test_get_by_guild_isolates_guilds(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.add(CraftingRoleMapping(GuildId=200, RoleId=2, ProfessionId=164))
        db_session.flush()

        results = CraftingRoleMapping.get_by_guild(100, db_session)
        assert len(results) == 1
        assert results[0].RoleId == 1

    def test_get_profession_id(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.flush()

        assert CraftingRoleMapping.get_profession_id(100, 1, db_session) == 164
        assert CraftingRoleMapping.get_profession_id(100, 999, db_session) is None

    def test_delete_by_guild_only_affects_target(self, db_session):
        db_session.add(CraftingRoleMapping(GuildId=100, RoleId=1, ProfessionId=164))
        db_session.add(CraftingRoleMapping(GuildId=200, RoleId=2, ProfessionId=165))
        db_session.flush()

        CraftingRoleMapping.delete_by_guild(100, db_session)
        db_session.flush()

        assert CraftingRoleMapping.get_by_guild(100, db_session) == []
        assert len(CraftingRoleMapping.get_by_guild(200, db_session)) == 1
