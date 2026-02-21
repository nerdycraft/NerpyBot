# tests/modules/test_application.py
# -*- coding: utf-8 -*-
"""Tests for modules/application.py — Application cog commands."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from datetime import UTC, datetime

from models.application import (
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    seed_built_in_templates,
)
from modules.application import Application


@pytest.fixture
def app_cog(mock_bot):
    """Create an Application cog, skipping __init__ side effects (template seeding)."""
    cog = Application.__new__(Application)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def admin_interaction(mock_interaction):
    """Mock interaction with administrator permissions."""
    mock_interaction.user.guild_permissions = MagicMock(administrator=True)
    mock_interaction.user.roles = []
    return mock_interaction


@pytest.fixture
def non_admin_interaction(mock_interaction):
    """Mock interaction without administrator permissions and no manager role."""
    mock_interaction.user.guild_permissions = MagicMock(administrator=False)
    mock_interaction.user.roles = []
    return mock_interaction


def _make_form(db_session, guild_id=987654321, name="TestForm", review_channel_id=None):
    """Helper to create an ApplicationForm with one question."""
    form = ApplicationForm(GuildId=guild_id, Name=name, ReviewChannelId=review_channel_id)
    db_session.add(form)
    db_session.flush()
    db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="What is your name?", SortOrder=1))
    db_session.commit()
    return form


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


class TestHasManagePermission:
    def test_admin_has_permission(self, app_cog, admin_interaction):
        assert app_cog._has_manage_permission(admin_interaction) is True

    def test_non_admin_without_role_denied(self, app_cog, non_admin_interaction):
        assert app_cog._has_manage_permission(non_admin_interaction) is False

    def test_non_admin_with_manager_role_allowed(self, app_cog, non_admin_interaction, db_session):
        # Set up manager role config
        config = ApplicationGuildConfig(GuildId=non_admin_interaction.guild.id, ManagerRoleId=42)
        db_session.add(config)
        db_session.commit()

        role = MagicMock()
        role.id = 42
        non_admin_interaction.user.roles = [role]

        assert app_cog._has_manage_permission(non_admin_interaction) is True

    def test_non_admin_with_wrong_role_denied(self, app_cog, non_admin_interaction, db_session):
        config = ApplicationGuildConfig(GuildId=non_admin_interaction.guild.id, ManagerRoleId=42)
        db_session.add(config)
        db_session.commit()

        role = MagicMock()
        role.id = 99
        non_admin_interaction.user.roles = [role]

        assert app_cog._has_manage_permission(non_admin_interaction) is False

    def test_reviewer_role_cannot_manage(self, app_cog, non_admin_interaction, db_session):
        """Reviewer-role holders must not be able to manage forms."""
        config = ApplicationGuildConfig(GuildId=non_admin_interaction.guild.id, ReviewerRoleId=888)
        db_session.add(config)
        db_session.commit()

        role = MagicMock()
        role.id = 888
        non_admin_interaction.user.roles = [role]

        assert app_cog._has_manage_permission(non_admin_interaction) is False


# ---------------------------------------------------------------------------
# /application create
# ---------------------------------------------------------------------------


class TestApplicationCreate:
    @pytest.mark.asyncio
    async def test_create_starts_conversation(self, app_cog, admin_interaction):
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._create.callback(app_cog, admin_interaction, name="NewForm")

        app_cog.bot.convMan.init_conversation.assert_called_once()
        admin_interaction.response.defer.assert_called_once()
        call_args = str(admin_interaction.followup.send.call_args)
        assert "DMs" in call_args

    @pytest.mark.asyncio
    async def test_create_rejects_duplicate_name(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Existing")
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._create.callback(app_cog, admin_interaction, name="Existing")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already exists" in call_args

    @pytest.mark.asyncio
    async def test_create_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._create.callback(app_cog, non_admin_interaction, name="Nope")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application delete
# ---------------------------------------------------------------------------


class TestApplicationDelete:
    @pytest.mark.asyncio
    async def test_delete_happy_path(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="ToDelete")

        await app_cog._delete.callback(app_cog, admin_interaction, name="ToDelete")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "deleted" in call_args.lower()
        assert ApplicationForm.get("ToDelete", admin_interaction.guild.id, db_session) is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, app_cog, admin_interaction):
        await app_cog._delete.callback(app_cog, admin_interaction, name="NonExistent")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_delete_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._delete.callback(app_cog, non_admin_interaction, name="Nope")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application list
# ---------------------------------------------------------------------------


class TestApplicationList:
    @pytest.mark.asyncio
    async def test_list_shows_forms(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Form1")
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Form2", review_channel_id=12345)

        await app_cog._list.callback(app_cog, admin_interaction)

        call_kwargs = admin_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get("embed") or call_kwargs[1].get("embed")
        desc = embed.description
        assert "Form1" in desc
        assert "not ready" in desc
        assert "Form2" in desc
        assert "ready" in desc

    @pytest.mark.asyncio
    async def test_list_empty(self, app_cog, admin_interaction):
        await app_cog._list.callback(app_cog, admin_interaction)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "no application forms" in call_args.lower()

    @pytest.mark.asyncio
    async def test_list_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._list.callback(app_cog, non_admin_interaction)

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application edit
# ---------------------------------------------------------------------------


class TestApplicationEdit:
    @pytest.mark.asyncio
    async def test_edit_starts_conversation(self, app_cog, admin_interaction, db_session):
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="EditMe")
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._edit.callback(app_cog, admin_interaction, name="EditMe")

        app_cog.bot.convMan.init_conversation.assert_called_once()
        conv = app_cog.bot.convMan.init_conversation.call_args[0][0]
        assert conv.form_id == form.Id
        admin_interaction.response.defer.assert_called_once()
        call_args = str(admin_interaction.followup.send.call_args)
        assert "DMs" in call_args

    @pytest.mark.asyncio
    async def test_edit_not_found(self, app_cog, admin_interaction):
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._edit.callback(app_cog, admin_interaction, name="Missing")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._edit.callback(app_cog, non_admin_interaction, name="Nope")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application channel
# ---------------------------------------------------------------------------


class TestApplicationChannel:
    @pytest.mark.asyncio
    async def test_channel_sets_review_channel(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="ChForm")

        channel = MagicMock()
        channel.id = 555
        channel.mention = "#reviews"

        await app_cog._channel.callback(app_cog, admin_interaction, name="ChForm", channel=channel)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "review channel" in call_args.lower()
        updated = ApplicationForm.get("ChForm", admin_interaction.guild.id, db_session)
        assert updated.ReviewChannelId == 555

    @pytest.mark.asyncio
    async def test_channel_form_not_found(self, app_cog, admin_interaction):
        channel = MagicMock()
        channel.id = 555

        await app_cog._channel.callback(app_cog, admin_interaction, name="Missing", channel=channel)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_channel_permission_denied(self, app_cog, non_admin_interaction):
        channel = MagicMock()
        channel.id = 555

        await app_cog._channel.callback(app_cog, non_admin_interaction, name="Form", channel=channel)

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application settings
# ---------------------------------------------------------------------------


class TestApplicationSettings:
    @pytest.mark.asyncio
    async def test_settings_updates_approvals(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="SetForm")

        await app_cog._settings.callback(
            app_cog,
            admin_interaction,
            name="SetForm",
            approvals=3,
            denials=None,
            approval_message=None,
            denial_message=None,
        )

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "approvals=3" in call_args
        updated = ApplicationForm.get("SetForm", admin_interaction.guild.id, db_session)
        assert updated.RequiredApprovals == 3

    @pytest.mark.asyncio
    async def test_settings_updates_multiple(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="MultiSet")

        await app_cog._settings.callback(
            app_cog,
            admin_interaction,
            name="MultiSet",
            approvals=2,
            denials=2,
            approval_message="Welcome!",
            denial_message="Sorry!",
        )

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "approvals=2" in call_args
        assert "denials=2" in call_args
        updated = ApplicationForm.get("MultiSet", admin_interaction.guild.id, db_session)
        assert updated.RequiredApprovals == 2
        assert updated.RequiredDenials == 2
        assert updated.ApprovalMessage == "Welcome!"
        assert updated.DenialMessage == "Sorry!"

    @pytest.mark.asyncio
    async def test_settings_nothing_to_change(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Nochange")

        await app_cog._settings.callback(
            app_cog,
            admin_interaction,
            name="Nochange",
            approvals=None,
            denials=None,
            approval_message=None,
            denial_message=None,
        )

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "nothing to change" in call_args.lower()

    @pytest.mark.asyncio
    async def test_settings_form_not_found(self, app_cog, admin_interaction):
        await app_cog._settings.callback(
            app_cog,
            admin_interaction,
            name="Missing",
            approvals=1,
            denials=None,
            approval_message=None,
            denial_message=None,
        )

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_settings_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._settings.callback(
            app_cog,
            non_admin_interaction,
            name="Form",
            approvals=1,
            denials=None,
            approval_message=None,
            denial_message=None,
        )

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application template list
# ---------------------------------------------------------------------------


class TestTemplateList:
    @pytest.mark.asyncio
    async def test_template_list_shows_templates(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()

        await app_cog._template_list.callback(app_cog, admin_interaction)

        call_kwargs = admin_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get("embed") or call_kwargs[1].get("embed")
        desc = embed.description
        assert "[Built-in]" in desc
        assert "Guild Membership" in desc

    @pytest.mark.asyncio
    async def test_template_list_includes_guild_templates(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        tpl = ApplicationTemplate(GuildId=admin_interaction.guild.id, Name="My Custom", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        await app_cog._template_list.callback(app_cog, admin_interaction)

        call_kwargs = admin_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get("embed") or call_kwargs[1].get("embed")
        desc = embed.description
        assert "[Custom]" in desc
        assert "My Custom" in desc

    @pytest.mark.asyncio
    async def test_template_list_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._template_list.callback(app_cog, non_admin_interaction)

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application template use
# ---------------------------------------------------------------------------


class TestTemplateUse:
    @pytest.mark.asyncio
    async def test_template_use_creates_form(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()

        await app_cog._template_use.callback(
            app_cog, admin_interaction, template="Guild Membership", name="NewFromTemplate"
        )

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "created from template" in call_args.lower()

        form = ApplicationForm.get("NewFromTemplate", admin_interaction.guild.id, db_session)
        assert form is not None
        assert len(form.questions) == 6  # Guild Membership has 6 questions

    @pytest.mark.asyncio
    async def test_template_use_template_not_found(self, app_cog, admin_interaction):
        await app_cog._template_use.callback(app_cog, admin_interaction, template="NonExistent", name="NewForm")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_template_use_duplicate_form_name(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Existing")

        await app_cog._template_use.callback(app_cog, admin_interaction, template="Guild Membership", name="Existing")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already exists" in call_args

    @pytest.mark.asyncio
    async def test_template_use_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._template_use.callback(
            app_cog, non_admin_interaction, template="Guild Membership", name="NewForm"
        )

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application template save
# ---------------------------------------------------------------------------


class TestTemplateSave:
    @pytest.mark.asyncio
    async def test_template_save_creates_template(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="SaveMe")

        await app_cog._template_save.callback(app_cog, admin_interaction, form="SaveMe", template_name="SavedTemplate")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "saved" in call_args.lower()

        tpl = ApplicationTemplate.get_by_name("SavedTemplate", admin_interaction.guild.id, db_session)
        assert tpl is not None
        assert tpl.IsBuiltIn is False
        assert len(tpl.questions) == 1

    @pytest.mark.asyncio
    async def test_template_save_form_not_found(self, app_cog, admin_interaction):
        await app_cog._template_save.callback(app_cog, admin_interaction, form="Missing", template_name="Tpl")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_template_save_duplicate_name(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Source")
        tpl = ApplicationTemplate(GuildId=admin_interaction.guild.id, Name="Dupe", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        await app_cog._template_save.callback(app_cog, admin_interaction, form="Source", template_name="Dupe")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already exists" in call_args

    @pytest.mark.asyncio
    async def test_template_save_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._template_save.callback(app_cog, non_admin_interaction, form="Form", template_name="Tpl")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application template delete
# ---------------------------------------------------------------------------


class TestTemplateDelete:
    @pytest.mark.asyncio
    async def test_template_delete_guild_template(self, app_cog, admin_interaction, db_session):
        tpl = ApplicationTemplate(GuildId=admin_interaction.guild.id, Name="MyTpl", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        await app_cog._template_delete.callback(app_cog, admin_interaction, template_name="MyTpl")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "deleted" in call_args.lower()
        assert ApplicationTemplate.get_by_name("MyTpl", admin_interaction.guild.id, db_session) is None

    @pytest.mark.asyncio
    async def test_template_delete_builtin_rejected(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()

        await app_cog._template_delete.callback(app_cog, admin_interaction, template_name="Guild Membership")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "built-in" in call_args.lower()

    @pytest.mark.asyncio
    async def test_template_delete_not_found(self, app_cog, admin_interaction):
        await app_cog._template_delete.callback(app_cog, admin_interaction, template_name="Missing")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_template_delete_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._template_delete.callback(app_cog, non_admin_interaction, template_name="Tpl")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()


# ---------------------------------------------------------------------------
# /application managerole set / remove
# ---------------------------------------------------------------------------


class TestManagerRole:
    @pytest.mark.asyncio
    async def test_managerole_set(self, app_cog, admin_interaction, db_session):
        role = MagicMock()
        role.id = 42
        role.name = "App Manager"

        await app_cog._managerole_set.callback(app_cog, admin_interaction, role=role)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "app manager" in call_args.lower()

        config = ApplicationGuildConfig.get(admin_interaction.guild.id, db_session)
        assert config is not None
        assert config.ManagerRoleId == 42

    @pytest.mark.asyncio
    async def test_managerole_set_updates_existing(self, app_cog, admin_interaction, db_session):
        # Pre-populate config
        config = ApplicationGuildConfig(GuildId=admin_interaction.guild.id, ManagerRoleId=1)
        db_session.add(config)
        db_session.commit()

        role = MagicMock()
        role.id = 99
        role.name = "New Role"

        await app_cog._managerole_set.callback(app_cog, admin_interaction, role=role)

        updated = ApplicationGuildConfig.get(admin_interaction.guild.id, db_session)
        assert updated.ManagerRoleId == 99

    @pytest.mark.asyncio
    async def test_managerole_remove(self, app_cog, admin_interaction, db_session):
        config = ApplicationGuildConfig(GuildId=admin_interaction.guild.id, ManagerRoleId=42)
        db_session.add(config)
        db_session.commit()

        await app_cog._managerole_remove.callback(app_cog, admin_interaction)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "removed" in call_args.lower()
        updated = ApplicationGuildConfig.get(admin_interaction.guild.id, db_session)
        assert updated.ManagerRoleId is None

    @pytest.mark.asyncio
    async def test_managerole_remove_no_config(self, app_cog, admin_interaction):
        await app_cog._managerole_remove.callback(app_cog, admin_interaction)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "no manager role" in call_args.lower()


# ---------------------------------------------------------------------------
# /application export
# ---------------------------------------------------------------------------


class TestExport:
    @pytest.mark.asyncio
    async def test_export_happy_path(self, app_cog, admin_interaction, db_session):
        """Export produces a valid JSON file and DMs it to the user."""
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="ExportMe")
        # Set some custom settings
        form.RequiredApprovals = 3
        form.RequiredDenials = 2
        form.ApprovalMessage = "Welcome!"
        form.DenialMessage = "Sorry!"
        db_session.commit()

        admin_interaction.user.send = AsyncMock()

        await app_cog._export.callback(app_cog, admin_interaction, name="ExportMe")

        # Verify the DM was sent with a file
        admin_interaction.user.send.assert_called_once()
        call_kwargs = admin_interaction.user.send.call_args
        sent_file = call_kwargs.kwargs.get("file") or call_kwargs[1].get("file")
        assert sent_file is not None
        assert sent_file.filename == "ExportMe.json"

        # Read the file content and validate JSON
        sent_file.fp.seek(0)
        data = json.loads(sent_file.fp.read().decode())
        assert data["name"] == "ExportMe"
        assert data["required_approvals"] == 3
        assert data["required_denials"] == 2
        assert data["approval_message"] == "Welcome!"
        assert data["denial_message"] == "Sorry!"
        assert len(data["questions"]) == 1
        assert data["questions"][0]["text"] == "What is your name?"
        assert data["questions"][0]["order"] == 1

        # Verify ephemeral response
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "DMs" in call_args

    @pytest.mark.asyncio
    async def test_export_form_not_found(self, app_cog, admin_interaction):
        await app_cog._export.callback(app_cog, admin_interaction, name="NonExistent")

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_export_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._export.callback(app_cog, non_admin_interaction, name="Form")

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_export_dm_forbidden(self, app_cog, admin_interaction, db_session):
        """If DMs are disabled, send a followup error after the initial response."""
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="NoDMs")
        admin_interaction.user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send"))

        await app_cog._export.callback(app_cog, admin_interaction, name="NoDMs")

        # Initial response is "Check your DMs!" — then followup with the error
        admin_interaction.response.send_message.assert_called_once()
        call_args = str(admin_interaction.followup.send.call_args)
        assert "dm" in call_args.lower() or "DM" in call_args


# ---------------------------------------------------------------------------
# /application import
# ---------------------------------------------------------------------------


class TestImport:
    def _make_dm_message(self, user_id, form_data):
        """Create a mock DM message with a JSON attachment."""
        msg = MagicMock()
        msg.author = MagicMock()
        msg.author.id = user_id
        msg.guild = None

        attachment = MagicMock()
        raw = json.dumps(form_data).encode()
        attachment.read = AsyncMock(return_value=raw)
        msg.attachments = [attachment]
        return msg

    @pytest.mark.asyncio
    async def test_import_happy_path(self, app_cog, admin_interaction, db_session):
        """Import parses JSON from attachment and creates form with questions."""
        form_data = {
            "name": "Imported Form",
            "required_approvals": 2,
            "required_denials": 3,
            "approval_message": "Approved!",
            "denial_message": "Denied!",
            "questions": [
                {"text": "First question?", "order": 1},
                {"text": "Second question?", "order": 2},
            ],
        }
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        # Verify ephemeral "Check your DMs"
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "DMs" in call_args

        # Verify the form was created
        form = ApplicationForm.get("Imported Form", admin_interaction.guild.id, db_session)
        assert form is not None
        assert form.RequiredApprovals == 2
        assert form.RequiredDenials == 3
        assert form.ApprovalMessage == "Approved!"
        assert form.DenialMessage == "Denied!"
        assert len(form.questions) == 2
        assert form.questions[0].QuestionText == "First question?"
        assert form.questions[1].QuestionText == "Second question?"

        # Verify confirmation DM
        last_send = admin_interaction.user.send.call_args_list[-1]
        assert "imported successfully" in str(last_send).lower()

    @pytest.mark.asyncio
    async def test_import_invalid_json(self, app_cog, admin_interaction):
        """Invalid JSON file produces a DM error."""
        msg = MagicMock()
        msg.author = MagicMock()
        msg.author.id = admin_interaction.user.id
        msg.guild = None
        attachment = MagicMock()
        attachment.read = AsyncMock(return_value=b"not valid json {{{")
        msg.attachments = [attachment]

        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "invalid json" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_missing_name(self, app_cog, admin_interaction):
        """Missing name field produces a DM error."""
        form_data = {"questions": [{"text": "Question?"}]}
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "name" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_missing_questions(self, app_cog, admin_interaction):
        """Missing questions field produces a DM error."""
        form_data = {"name": "NoQuestions"}
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "questions" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_empty_questions(self, app_cog, admin_interaction):
        """Empty questions list produces a DM error."""
        form_data = {"name": "EmptyQ", "questions": []}
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "questions" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_question_missing_text(self, app_cog, admin_interaction):
        """Question without text field produces a DM error."""
        form_data = {"name": "BadQ", "questions": [{"order": 1}]}
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "text" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_duplicate_form_name(self, app_cog, admin_interaction, db_session):
        """Duplicate form name produces a DM error."""
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Existing")
        form_data = {"name": "Existing", "questions": [{"text": "Question?"}]}
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "already exists" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_timeout(self, app_cog, admin_interaction):
        """Timeout sends a cancellation DM."""
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(side_effect=asyncio.TimeoutError)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        last_send = str(admin_interaction.user.send.call_args_list[-1])
        assert "timed out" in last_send.lower()

    @pytest.mark.asyncio
    async def test_import_permission_denied(self, app_cog, non_admin_interaction):
        await app_cog._import_form.callback(app_cog, non_admin_interaction)

        call_args = str(non_admin_interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_import_dm_forbidden(self, app_cog, admin_interaction):
        """If DMs are disabled, respond with an ephemeral error."""
        admin_interaction.user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send"))

        await app_cog._import_form.callback(app_cog, admin_interaction)

        call_args = str(admin_interaction.response.send_message.call_args)
        assert "dm" in call_args.lower() or "DM" in call_args

    @pytest.mark.asyncio
    async def test_import_defaults_when_optional_fields_missing(self, app_cog, admin_interaction, db_session):
        """Import with minimal JSON uses defaults for optional fields."""
        form_data = {
            "name": "Minimal",
            "questions": [{"text": "Only question?"}],
        }
        dm_msg = self._make_dm_message(admin_interaction.user.id, form_data)
        admin_interaction.user.send = AsyncMock()
        app_cog.bot.wait_for = AsyncMock(return_value=dm_msg)

        await app_cog._import_form.callback(app_cog, admin_interaction)

        form = ApplicationForm.get("Minimal", admin_interaction.guild.id, db_session)
        assert form is not None
        assert form.RequiredApprovals == 1
        assert form.RequiredDenials == 1
        assert form.ApprovalMessage is None
        assert form.DenialMessage is None
        assert len(form.questions) == 1
        assert form.questions[0].SortOrder == 1


# ---------------------------------------------------------------------------
# /apply (top-level command)
# ---------------------------------------------------------------------------


class TestApplyCommand:
    @pytest.mark.asyncio
    async def test_apply_starts_conversation(self, app_cog, admin_interaction, db_session):
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="ReadyForm", review_channel_id=12345)
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="ReadyForm")

        app_cog.bot.convMan.init_conversation.assert_called_once()
        conv = app_cog.bot.convMan.init_conversation.call_args[0][0]
        assert conv.form_id == form.Id
        assert conv.form_name == "ReadyForm"
        assert len(conv.questions) == 1
        admin_interaction.response.defer.assert_called_once()
        call_args = str(admin_interaction.followup.send.call_args)
        assert "DMs" in call_args

    @pytest.mark.asyncio
    async def test_apply_form_not_found(self, app_cog, admin_interaction):
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="NonExistent")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_apply_form_not_ready(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="NotReady")
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="NotReady")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "set up yet" in call_args

    @pytest.mark.asyncio
    async def test_apply_blocked_when_pending(self, app_cog, admin_interaction, db_session):
        """User with a pending submission must be blocked from applying again."""
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="ActiveForm", review_channel_id=12345)
        db_session.add(
            ApplicationSubmission(
                FormId=form.Id,
                GuildId=admin_interaction.guild.id,
                UserId=admin_interaction.user.id,
                UserName="Applicant",
                Status="pending",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.commit()
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="ActiveForm")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already applied" in call_args.lower()

    @pytest.mark.asyncio
    async def test_apply_blocked_when_approved(self, app_cog, admin_interaction, db_session):
        """User with an approved submission must be blocked from applying again."""
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="ApprovedForm", review_channel_id=12345)
        db_session.add(
            ApplicationSubmission(
                FormId=form.Id,
                GuildId=admin_interaction.guild.id,
                UserId=admin_interaction.user.id,
                UserName="Applicant",
                Status="approved",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.commit()
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="ApprovedForm")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already applied" in call_args.lower()

    @pytest.mark.asyncio
    async def test_apply_blocked_when_denied(self, app_cog, admin_interaction, db_session):
        """User with a denied submission must be blocked from applying again."""
        form = _make_form(db_session, guild_id=admin_interaction.guild.id, name="DeniedForm", review_channel_id=12345)
        db_session.add(
            ApplicationSubmission(
                FormId=form.Id,
                GuildId=admin_interaction.guild.id,
                UserId=admin_interaction.user.id,
                UserName="Applicant",
                Status="denied",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.commit()
        app_cog.bot.convMan = MagicMock()
        app_cog.bot.convMan.init_conversation = AsyncMock()

        await app_cog._apply(admin_interaction, form_name="DeniedForm")

        app_cog.bot.convMan.init_conversation.assert_not_called()
        call_args = str(admin_interaction.response.send_message.call_args)
        assert "already applied" in call_args.lower()


# ---------------------------------------------------------------------------
# Autocomplete methods
# ---------------------------------------------------------------------------


class TestAutocomplete:
    @pytest.mark.asyncio
    async def test_form_name_autocomplete_returns_matching(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Alpha")
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Beta")

        results = await app_cog._form_name_autocomplete(admin_interaction, "alp")
        assert len(results) == 1
        assert results[0].value == "Alpha"

    @pytest.mark.asyncio
    async def test_form_name_autocomplete_returns_all_when_empty(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Alpha")
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Beta")

        results = await app_cog._form_name_autocomplete(admin_interaction, "")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_ready_form_autocomplete_only_ready(self, app_cog, admin_interaction, db_session):
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="NotReady")
        _make_form(db_session, guild_id=admin_interaction.guild.id, name="Ready", review_channel_id=123)

        results = await app_cog._ready_form_autocomplete(admin_interaction, "")
        assert len(results) == 1
        assert results[0].value == "Ready"

    @pytest.mark.asyncio
    async def test_template_autocomplete_includes_builtin(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()

        results = await app_cog._template_autocomplete(admin_interaction, "")
        names = [r.value for r in results]
        assert "Guild Membership" in names

    @pytest.mark.asyncio
    async def test_guild_template_autocomplete_excludes_builtin(self, app_cog, admin_interaction, db_session):
        seed_built_in_templates(db_session)
        tpl = ApplicationTemplate(GuildId=admin_interaction.guild.id, Name="Custom", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        results = await app_cog._guild_template_autocomplete(admin_interaction, "")
        names = [r.value for r in results]
        assert "Custom" in names
        assert "Guild Membership" not in names
