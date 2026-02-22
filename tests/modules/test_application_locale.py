# -*- coding: utf-8 -*-
"""Tests for application module — localized responses (EN/DE)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.application import (
    ApplicationAnswer,
    ApplicationForm,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    SubmissionStatus,
    seed_built_in_templates,
)
from modules.application import Application
from modules.views.application import (
    ApplicationApplyView,
    ApplicationReviewView,
    DenyVoteModal,
    MessageModal,
    OverrideModal,
    build_apply_embed,
    build_review_embed,
)
from utils.strings import load_strings


GUILD_ID = 987654321
REVIEW_MSG_ID = 777888999
REVIEW_CHANNEL_ID = 100200300
APPLICANT_USER_ID = 111222333
REVIEWER_USER_ID = 444555666


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    cog = Application.__new__(Application)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = GUILD_ID
    mock_interaction.guild_id = GUILD_ID
    mock_interaction.user.guild_permissions = MagicMock(administrator=True)
    mock_interaction.user.roles = []
    return mock_interaction


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=GUILD_ID, Language="de"))
    db_session.commit()


def _make_form(db_session, name="TestForm", review_channel_id=None):
    form = ApplicationForm(GuildId=GUILD_ID, Name=name, ReviewChannelId=review_channel_id)
    db_session.add(form)
    db_session.flush()
    db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Why?", SortOrder=1))
    db_session.commit()
    return form


def _seed_submission(db_session, form):
    """Insert a pending submission with one answer for the given form."""
    sub = ApplicationSubmission(
        FormId=form.Id,
        GuildId=GUILD_ID,
        UserId=APPLICANT_USER_ID,
        UserName="Applicant",
        Status="pending",
        SubmittedAt=datetime.now(UTC),
        ReviewMessageId=REVIEW_MSG_ID,
    )
    db_session.add(sub)
    db_session.flush()
    q = db_session.query(ApplicationQuestion).filter_by(FormId=form.Id).first()
    db_session.add(ApplicationAnswer(SubmissionId=sub.Id, QuestionId=q.Id, AnswerText="Because!"))
    db_session.commit()
    return sub


def _make_reviewer_interaction(mock_bot, *, message_id=REVIEW_MSG_ID):
    interaction = MagicMock()
    interaction.client = mock_bot
    interaction.user = MagicMock()
    interaction.user.id = REVIEWER_USER_ID
    interaction.user.guild_permissions = MagicMock(administrator=True)
    interaction.user.roles = []
    interaction.guild = MagicMock()
    interaction.guild.id = GUILD_ID
    interaction.guild_id = GUILD_ID
    interaction.message = MagicMock()
    interaction.message.id = message_id
    interaction.message.channel = MagicMock()
    interaction.message.channel.id = REVIEW_CHANNEL_ID
    interaction.message.edit = AsyncMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


# ---------------------------------------------------------------------------
# /application delete
# ---------------------------------------------------------------------------


class TestDeleteLocale:
    async def test_success_english(self, cog, interaction, db_session):
        _make_form(db_session, name="ToDelete")
        await Application._delete.callback(cog, interaction, name="ToDelete")
        msg = interaction.response.send_message.call_args[0][0]
        assert "deleted" in msg.lower()

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        _make_form(db_session, name="ToDelete")
        await Application._delete.callback(cog, interaction, name="ToDelete")
        msg = interaction.response.send_message.call_args[0][0]
        assert "gelöscht" in msg

    async def test_not_found_english(self, cog, interaction, db_session):
        await Application._delete.callback(cog, interaction, name="Missing")
        msg = interaction.response.send_message.call_args[0][0]
        assert "not found" in msg.lower()

    async def test_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._delete.callback(cog, interaction, name="Missing")
        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht gefunden" in msg


# ---------------------------------------------------------------------------
# /application list
# ---------------------------------------------------------------------------


class TestListLocale:
    async def test_empty_english(self, cog, interaction, db_session):
        await Application._list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No application forms" in msg

    async def test_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Bewerbungsformulare" in msg

    async def test_with_forms_english(self, cog, interaction, db_session):
        _make_form(db_session, name="MyForm", review_channel_id=123)
        await Application._list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Application Forms" in emb.title
        assert "ready" in emb.description

    async def test_with_forms_german(self, cog, interaction, db_session):
        _set_german(db_session)
        _make_form(db_session, name="MyForm", review_channel_id=123)
        await Application._list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Bewerbungsformulare" in emb.title
        assert "bereit" in emb.description


# ---------------------------------------------------------------------------
# /application settings
# ---------------------------------------------------------------------------


class TestSettingsLocale:
    async def test_nothing_to_change_english(self, cog, interaction, db_session):
        _make_form(db_session, name="Form")
        await Application._settings.callback(cog, interaction, name="Form")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nothing to change" in msg

    async def test_nothing_to_change_german(self, cog, interaction, db_session):
        _set_german(db_session)
        _make_form(db_session, name="Form")
        await Application._settings.callback(cog, interaction, name="Form")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nichts zu ändern" in msg

    async def test_success_english(self, cog, interaction, db_session):
        _make_form(db_session, name="Form")
        await Application._settings.callback(cog, interaction, name="Form", approvals=5)
        msg = interaction.response.send_message.call_args[0][0]
        assert "updated" in msg.lower()
        assert "approvals=5" in msg

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        _make_form(db_session, name="Form")
        await Application._settings.callback(cog, interaction, name="Form", approvals=5)
        msg = interaction.response.send_message.call_args[0][0]
        assert "aktualisiert" in msg
        assert "Genehmigungen=5" in msg


# ---------------------------------------------------------------------------
# /application template list
# ---------------------------------------------------------------------------


class TestTemplateListLocale:
    async def test_empty_english(self, cog, interaction, db_session):
        await Application._template_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No templates" in msg

    async def test_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._template_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Vorlagen" in msg

    async def test_builtin_prefix_english(self, cog, interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "[Built-in]" in emb.description

    async def test_builtin_prefix_german(self, cog, interaction, db_session):
        _set_german(db_session)
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "[Integriert]" in emb.description

    async def test_builtin_names_localized_german(self, cog, interaction, db_session):
        _set_german(db_session)
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Gildenmitgliedschaft" in emb.description
        assert "Personal / Moderator" in emb.description

    async def test_builtin_names_english_default(self, cog, interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_list.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Guild Membership" in emb.description
        assert "Staff / Moderator" in emb.description


# ---------------------------------------------------------------------------
# /application template use
# ---------------------------------------------------------------------------


class TestTemplateUseLocale:
    async def test_success_english(self, cog, interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()
        review_channel = MagicMock()
        review_channel.id = 444
        await Application._template_use.callback(
            cog, interaction, template="Guild Membership", name="NewForm", review_channel=review_channel
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "created from template" in msg.lower()

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        seed_built_in_templates(db_session)
        db_session.commit()
        review_channel = MagicMock()
        review_channel.id = 444
        await Application._template_use.callback(
            cog, interaction, template="Guild Membership", name="NewForm", review_channel=review_channel
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "aus Vorlage" in msg

    async def test_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        review_channel = MagicMock()
        review_channel.id = 444
        await Application._template_use.callback(
            cog, interaction, template="Nope", name="X", review_channel=review_channel
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht gefunden" in msg


# ---------------------------------------------------------------------------
# /application template save
# ---------------------------------------------------------------------------


class TestTemplateSaveLocale:
    async def test_success_english(self, cog, interaction, db_session):
        _make_form(db_session, name="Src")
        await Application._template_save.callback(cog, interaction, form="Src", template_name="Tpl")
        msg = interaction.response.send_message.call_args[0][0]
        assert "saved" in msg.lower()

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        _make_form(db_session, name="Src")
        await Application._template_save.callback(cog, interaction, form="Src", template_name="Tpl")
        msg = interaction.response.send_message.call_args[0][0]
        assert "gespeichert" in msg


# ---------------------------------------------------------------------------
# /application template delete
# ---------------------------------------------------------------------------


class TestTemplateDeleteLocale:
    async def test_success_english(self, cog, interaction, db_session):
        tpl = ApplicationTemplate(GuildId=GUILD_ID, Name="MyTpl", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()
        await Application._template_delete.callback(cog, interaction, template_name="MyTpl")
        msg = interaction.response.send_message.call_args[0][0]
        assert "deleted" in msg.lower()

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        tpl = ApplicationTemplate(GuildId=GUILD_ID, Name="MyTpl", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()
        await Application._template_delete.callback(cog, interaction, template_name="MyTpl")
        msg = interaction.response.send_message.call_args[0][0]
        assert "gelöscht" in msg

    async def test_builtin_forbidden_english(self, cog, interaction, db_session):
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_delete.callback(cog, interaction, template_name="Guild Membership")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Built-in" in msg

    async def test_builtin_forbidden_german(self, cog, interaction, db_session):
        _set_german(db_session)
        seed_built_in_templates(db_session)
        db_session.commit()
        await Application._template_delete.callback(cog, interaction, template_name="Guild Membership")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Integrierte Vorlagen" in msg


# ---------------------------------------------------------------------------
# /application template edit-messages
# ---------------------------------------------------------------------------


class TestTemplateEditMessagesLocale:
    async def test_nothing_to_update_english(self, cog, interaction, db_session):
        await Application._template_edit_messages.callback(cog, interaction, template_name="X")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nothing to update" in msg

    async def test_nothing_to_update_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._template_edit_messages.callback(cog, interaction, template_name="X")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nichts zu aktualisieren" in msg


# ---------------------------------------------------------------------------
# /application managerole set / remove
# ---------------------------------------------------------------------------


class TestManagerRoleLocale:
    async def test_set_english(self, cog, interaction, db_session):
        role = MagicMock()
        role.id = 42
        role.name = "Manager"
        await Application._managerole_set.callback(cog, interaction, role=role)
        msg = interaction.response.send_message.call_args[0][0]
        assert "manager role set" in msg.lower()

    async def test_set_german(self, cog, interaction, db_session):
        _set_german(db_session)
        role = MagicMock()
        role.id = 42
        role.name = "Manager"
        await Application._managerole_set.callback(cog, interaction, role=role)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Manager-Rolle" in msg

    async def test_remove_not_configured_english(self, cog, interaction, db_session):
        await Application._managerole_remove.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No manager role" in msg

    async def test_remove_not_configured_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._managerole_remove.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Manager-Rolle" in msg


# ---------------------------------------------------------------------------
# /application reviewerrole set / remove
# ---------------------------------------------------------------------------


class TestReviewerRoleLocale:
    async def test_set_english(self, cog, interaction, db_session):
        role = MagicMock()
        role.id = 55
        role.name = "Reviewer"
        await Application._reviewerrole_set.callback(cog, interaction, role=role)
        msg = interaction.response.send_message.call_args[0][0]
        assert "reviewer role set" in msg.lower()

    async def test_set_german(self, cog, interaction, db_session):
        _set_german(db_session)
        role = MagicMock()
        role.id = 55
        role.name = "Reviewer"
        await Application._reviewerrole_set.callback(cog, interaction, role=role)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Prüfer-Rolle" in msg

    async def test_remove_not_configured_english(self, cog, interaction, db_session):
        await Application._reviewerrole_remove.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No reviewer role" in msg

    async def test_remove_not_configured_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Application._reviewerrole_remove.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Prüfer-Rolle" in msg


# ---------------------------------------------------------------------------
# build_review_embed
# ---------------------------------------------------------------------------


class TestBuildReviewEmbedLocale:
    def test_english_field_names(self, db_session):
        form = _make_form(db_session, name="Form", review_channel_id=123)
        sub = _seed_submission(db_session, form)
        embed = build_review_embed(sub, form, db_session, lang="en")
        field_names = [f.name for f in embed.fields]
        assert "Applicant" in field_names
        assert "Submitted" in field_names
        assert "Approvals: 0/1" in embed.footer.text

    def test_german_field_names(self, db_session):
        form = _make_form(db_session, name="Form", review_channel_id=123)
        sub = _seed_submission(db_session, form)
        embed = build_review_embed(sub, form, db_session, lang="de")
        field_names = [f.name for f in embed.fields]
        assert "Bewerber" in field_names
        assert "Eingereicht" in field_names
        assert "Genehmigungen: 0/1" in embed.footer.text


# ---------------------------------------------------------------------------
# build_apply_embed
# ---------------------------------------------------------------------------


class TestBuildApplyEmbedLocale:
    def test_default_description_english(self):
        embed = build_apply_embed("Form", None, lang="en")
        assert "Click the button" in embed.description

    def test_default_description_german(self):
        embed = build_apply_embed("Form", None, lang="de")
        assert "Klicke auf den Button" in embed.description


# ---------------------------------------------------------------------------
# Review view vote button
# ---------------------------------------------------------------------------


class TestReviewVoteLocale:
    async def test_no_permission_english(self, mock_bot, db_session):
        form = _make_form(db_session, name="F", review_channel_id=123)
        _seed_submission(db_session, form)
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.user.guild_permissions.administrator = False
        view = ApplicationReviewView(bot=mock_bot)
        await view.vote.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "permission" in msg.lower()

    async def test_no_permission_german(self, mock_bot, db_session):
        _set_german(db_session)
        form = _make_form(db_session, name="F", review_channel_id=123)
        _seed_submission(db_session, form)
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.user.guild_permissions.administrator = False
        view = ApplicationReviewView(bot=mock_bot)
        await view.vote.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "Berechtigung" in msg

    async def test_already_decided_english(self, mock_bot, db_session):
        form = _make_form(db_session, name="F", review_channel_id=123)
        sub = _seed_submission(db_session, form)
        sub.Status = "approved"
        db_session.commit()
        interaction = _make_reviewer_interaction(mock_bot)
        view = ApplicationReviewView(bot=mock_bot)
        await view.vote.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "already been decided" in msg.lower()

    async def test_already_decided_german(self, mock_bot, db_session):
        _set_german(db_session)
        form = _make_form(db_session, name="F", review_channel_id=123)
        sub = _seed_submission(db_session, form)
        sub.Status = "approved"
        db_session.commit()
        interaction = _make_reviewer_interaction(mock_bot)
        view = ApplicationReviewView(bot=mock_bot)
        await view.vote.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "bereits entschieden" in msg


# ---------------------------------------------------------------------------
# Review view override button
# ---------------------------------------------------------------------------


class TestOverrideButtonLocale:
    async def test_pending_rejected_english(self, mock_bot, db_session):
        form = _make_form(db_session, name="F", review_channel_id=123)
        _seed_submission(db_session, form)
        interaction = _make_reviewer_interaction(mock_bot)
        view = ApplicationReviewView(bot=mock_bot)
        await view.override.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "pending" in msg.lower()

    async def test_pending_rejected_german(self, mock_bot, db_session):
        _set_german(db_session)
        form = _make_form(db_session, name="F", review_channel_id=123)
        _seed_submission(db_session, form)
        interaction = _make_reviewer_interaction(mock_bot)
        view = ApplicationReviewView(bot=mock_bot)
        await view.override.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "ausstehend" in msg


# ---------------------------------------------------------------------------
# Modal titles
# ---------------------------------------------------------------------------


class TestModalTitlesLocale:
    async def test_deny_modal_title_english(self, mock_bot):
        modal = DenyVoteModal(submission_id=1, bot=mock_bot, review_channel_id=0, review_message_id=0, lang="en")
        assert modal.title == "Deny Application"

    async def test_deny_modal_title_german(self, mock_bot):
        modal = DenyVoteModal(submission_id=1, bot=mock_bot, review_channel_id=0, review_message_id=0, lang="de")
        assert modal.title == "Bewerbung ablehnen"

    async def test_message_modal_title_english(self, mock_bot):
        modal = MessageModal(user_id=1, bot=mock_bot, lang="en")
        assert modal.title == "Message Applicant"

    async def test_message_modal_title_german(self, mock_bot):
        modal = MessageModal(user_id=1, bot=mock_bot, lang="de")
        assert modal.title == "Nachricht an Bewerber"

    async def test_override_modal_title_english(self, mock_bot):
        modal = OverrideModal(
            current_status=SubmissionStatus.APPROVED,
            submission_id=1,
            bot=mock_bot,
            review_channel_id=0,
            review_message_id=0,
            lang="en",
        )
        assert "Approved" in modal.title and "Denied" in modal.title

    async def test_override_modal_title_german(self, mock_bot):
        modal = OverrideModal(
            current_status=SubmissionStatus.APPROVED,
            submission_id=1,
            bot=mock_bot,
            review_channel_id=0,
            review_message_id=0,
            lang="de",
        )
        assert "Überstimmen" in modal.title


# ---------------------------------------------------------------------------
# Apply button
# ---------------------------------------------------------------------------


class TestApplyButtonLocale:
    def _make_apply_interaction(self, mock_bot, *, message_id=888999000):
        interaction = MagicMock()
        interaction.client = mock_bot
        interaction.user = MagicMock()
        interaction.user.id = APPLICANT_USER_ID
        interaction.user.name = "Applicant"
        interaction.guild = MagicMock()
        interaction.guild.id = GUILD_ID
        interaction.guild_id = GUILD_ID
        interaction.message = MagicMock()
        interaction.message.id = message_id
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    async def test_not_available_english(self, mock_bot, db_session):
        view = ApplicationApplyView(bot=mock_bot)
        interaction = self._make_apply_interaction(mock_bot, message_id=999999)
        await view.apply_button.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "no longer available" in msg.lower()

    async def test_not_available_german(self, mock_bot, db_session):
        _set_german(db_session)
        view = ApplicationApplyView(bot=mock_bot)
        interaction = self._make_apply_interaction(mock_bot, message_id=999999)
        await view.apply_button.callback(interaction)
        msg = str(interaction.response.send_message.call_args)
        assert "nicht mehr verfügbar" in msg
