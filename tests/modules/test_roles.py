# -*- coding: utf-8 -*-
"""Tests for modules.roles — delegated role management commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from models.rolemanage import RoleMapping
from modules.roles import Roles
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture(autouse=True)
def _bypass_role_checks(monkeypatch):
    """Bypass is_role_assignable/is_role_below_bot — tested separately in test_checks.py."""

    async def _always_true(*_args, **_kwargs):
        return True

    monkeypatch.setattr("modules.roles.is_role_assignable", _always_true)
    monkeypatch.setattr("modules.roles.is_role_below_bot", _always_true)


@pytest.fixture
def cog(mock_bot):
    cog = Roles.__new__(Roles)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


@pytest.fixture
def source_role():
    role = MagicMock()
    role.id = 111
    role.name = "Moderator"
    return role


@pytest.fixture
def target_role():
    role = MagicMock()
    role.id = 222
    role.name = "Verified"
    role.managed = False
    role.is_integration = MagicMock(return_value=False)
    return role


@pytest.fixture
def member():
    m = MagicMock()
    m.display_name = "TestUser"
    m.roles = []
    m.add_roles = AsyncMock()
    m.remove_roles = AsyncMock()
    return m


# ---------------------------------------------------------------------------
# /rolemanage allow
# ---------------------------------------------------------------------------


class TestAllow:
    async def test_allow_success(self, cog, interaction, source_role, target_role):
        await Roles._rolemanage_allow.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "can now assign" in msg
        assert "Moderator" in msg
        assert "Verified" in msg

    async def test_allow_already_exists(self, cog, interaction, source_role, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()

        await Roles._rolemanage_allow.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already assign" in msg


# ---------------------------------------------------------------------------
# /rolemanage deny
# ---------------------------------------------------------------------------


class TestDeny:
    async def test_deny_success(self, cog, interaction, source_role, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()

        await Roles._rolemanage_deny.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "no longer assign" in msg

    async def test_deny_not_found(self, cog, interaction, source_role, target_role):
        await Roles._rolemanage_deny.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No matching mapping" in msg


# ---------------------------------------------------------------------------
# /rolemanage list
# ---------------------------------------------------------------------------


class TestList:
    async def test_list_empty(self, cog, interaction):
        await Roles._rolemanage_list.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No role mappings" in msg


# ---------------------------------------------------------------------------
# /rolemanage assign
# ---------------------------------------------------------------------------


class TestAssign:
    async def test_assign_no_permission(self, cog, interaction, member, target_role):
        await Roles._rolemanage_assign.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "permission to assign" in msg

    async def test_assign_success(self, cog, interaction, member, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]

        await Roles._rolemanage_assign.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Assigned" in msg
        assert "Verified" in msg
        member.add_roles.assert_called_once()


# ---------------------------------------------------------------------------
# /rolemanage remove
# ---------------------------------------------------------------------------


class TestRemove:
    async def test_remove_no_permission(self, cog, interaction, member, target_role):
        await Roles._rolemanage_remove.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "permission to remove" in msg

    async def test_remove_success(self, cog, interaction, member, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]
        member.roles = [target_role]

        await Roles._rolemanage_remove.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Removed" in msg
        assert "Verified" in msg
        member.remove_roles.assert_called_once()
