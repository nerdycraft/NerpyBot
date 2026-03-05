# -*- coding: utf-8 -*-
"""Tests for crafting order database models."""

from models.wow import CraftingOrder, CraftingRoleMapping


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
