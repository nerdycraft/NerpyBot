# -*- coding: utf-8 -*-
"""Tests for crafting order database models."""

import pytest
from sqlalchemy.exc import IntegrityError

from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRoleMapping


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
