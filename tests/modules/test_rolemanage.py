# -*- coding: utf-8 -*-
"""Tests for modules.rolemanage — localized delegated role management responses."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.rolemanage import RoleMapping
from modules.rolemanage import RoleManage
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture(autouse=True)
def _bypass_role_checks(monkeypatch):
    """Bypass is_role_assignable/is_role_below_bot — tested separately in test_checks.py."""

    async def _always_true(*_args, **_kwargs):
        return True

    monkeypatch.setattr("modules.rolemanage.is_role_assignable", _always_true)
    monkeypatch.setattr("modules.rolemanage.is_role_below_bot", _always_true)


@pytest.fixture
def cog(mock_bot):
    cog = RoleManage.__new__(RoleManage)
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


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


# ---------------------------------------------------------------------------
# /rolemanage allow
# ---------------------------------------------------------------------------


class TestAllow:
    async def test_allow_success(self, cog, interaction, source_role, target_role):
        await RoleManage._allow.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "can now assign" in msg
        assert "Moderator" in msg
        assert "Verified" in msg

    async def test_allow_already_exists(self, cog, interaction, source_role, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()

        await RoleManage._allow.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already assign" in msg

    async def test_allow_german(self, cog, interaction, source_role, target_role, db_session):
        _set_german(db_session)

        await RoleManage._allow.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "darf jetzt" in msg


# ---------------------------------------------------------------------------
# /rolemanage deny
# ---------------------------------------------------------------------------


class TestDeny:
    async def test_deny_success(self, cog, interaction, source_role, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()

        await RoleManage._deny.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "no longer assign" in msg

    async def test_deny_not_found(self, cog, interaction, source_role, target_role):
        await RoleManage._deny.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No matching mapping" in msg

    async def test_deny_german(self, cog, interaction, source_role, target_role, db_session):
        _set_german(db_session)
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()

        await RoleManage._deny.callback(cog, interaction, source_role, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht mehr zuweisen" in msg


# ---------------------------------------------------------------------------
# /rolemanage list
# ---------------------------------------------------------------------------


class TestList:
    async def test_list_empty(self, cog, interaction):
        await RoleManage._list.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No role mappings" in msg

    async def test_list_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await RoleManage._list.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Rollenzuordnungen" in msg


# ---------------------------------------------------------------------------
# /rolemanage assign
# ---------------------------------------------------------------------------


class TestAssign:
    async def test_assign_no_permission(self, cog, interaction, member, target_role):
        await RoleManage._assign.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "permission to assign" in msg

    async def test_assign_success(self, cog, interaction, member, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]

        await RoleManage._assign.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Assigned" in msg
        assert "Verified" in msg
        member.add_roles.assert_called_once()

    async def test_assign_german(self, cog, interaction, member, target_role, db_session):
        _set_german(db_session)
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]

        await RoleManage._assign.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "zugewiesen" in msg


# ---------------------------------------------------------------------------
# /rolemanage remove
# ---------------------------------------------------------------------------


class TestRemove:
    async def test_remove_no_permission(self, cog, interaction, member, target_role):
        await RoleManage._remove.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "permission to remove" in msg

    async def test_remove_success(self, cog, interaction, member, target_role, db_session):
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]
        member.roles = [target_role]

        await RoleManage._remove.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Removed" in msg
        assert "Verified" in msg
        member.remove_roles.assert_called_once()

    async def test_remove_german(self, cog, interaction, member, target_role, db_session):
        _set_german(db_session)
        db_session.add(RoleMapping(GuildId=987654321, SourceRoleId=111, TargetRoleId=222))
        db_session.commit()
        interaction.user.roles = [MagicMock(id=111)]
        member.roles = [target_role]

        await RoleManage._remove.callback(cog, interaction, member, target_role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "entfernt" in msg
