# -*- coding: utf-8 -*-
"""Application form management cog — admin commands, templates, and manager role."""

import asyncio
import io
import json
from typing import Optional

import discord
from discord import Embed, Interaction, Role, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import GroupCog
from sqlalchemy.exc import SQLAlchemyError

from models.application import (
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    TEMPLATE_KEY_MAP,
    seed_built_in_templates,
)
from modules.conversations.application import (
    ApplicationCreateConversation,
    ApplicationEditConversation,
)
from modules.views.application import check_override_permission
from utils.cog import NerpyBotCog
from utils.helpers import fetch_message_content
from utils.strings import get_guild_language, get_raw, get_string


async def _send_ephemeral(interaction: Interaction, msg: str) -> None:
    """Send an ephemeral message, choosing response vs followup based on whether the response is used."""
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)


def _localize_field(field: discord.ui.TextInput, lang: str, key_prefix: str, default: str = "") -> None:
    """Set label, placeholder, and default on a TextInput from locale keys."""
    field.label = get_string(lang, f"{key_prefix}_label")
    field.placeholder = get_string(lang, f"{key_prefix}_placeholder")
    field.default = default


def _filter_choices(items, current: str) -> list[app_commands.Choice[str]]:
    """Build autocomplete choices from items with a .Name attribute, filtering by current input."""
    choices = []
    for item in items:
        if current and current.lower() not in item.Name.lower():
            continue
        choices.append(app_commands.Choice(name=item.Name[:100], value=item.Name))
    return choices[:25]


@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
class Application(NerpyBotCog, GroupCog, group_name="application"):
    """Cog for managing application forms, templates, and guild config."""

    template_group = app_commands.Group(name="template", description="Manage form templates", guild_only=True)
    managerole_group = app_commands.Group(name="managerole", description="Configure manager role", guild_only=True)
    reviewerrole_group = app_commands.Group(name="reviewerrole", description="Configure reviewer role", guild_only=True)

    def __init__(self, bot):
        super().__init__(bot)

    def _lang(self, guild_id: int) -> str:
        with self.bot.session_scope() as session:
            return get_guild_language(guild_id, session)

    async def cog_load(self):
        # Ensure any new tables introduced by this cog exist before seeding.
        # create_all() is idempotent: it skips tables that already exist.
        self.bot.create_all()

        try:
            with self.bot.session_scope() as session:
                seed_built_in_templates(session)
        except SQLAlchemyError:
            self.bot.log.error("application: failed to seed built-in templates", exc_info=True)

    # -- Autocomplete helpers ------------------------------------------------

    async def _form_name_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        with self.bot.session_scope() as session:
            return _filter_choices(ApplicationForm.get_all_by_guild(interaction.guild.id, session), current)

    async def _template_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            templates = ApplicationTemplate.get_available(interaction.guild.id, session)
            choices = []
            for tpl in templates:
                if tpl.IsBuiltIn:
                    yaml_key = TEMPLATE_KEY_MAP.get(tpl.Name)
                    if yaml_key:
                        try:
                            localized_name = get_raw(lang, f"application.builtin_templates.{yaml_key}.name")
                        except KeyError:
                            localized_name = tpl.Name
                    else:
                        localized_name = tpl.Name
                    prefix = get_string(lang, "application.template.list.prefix_builtin")
                    label = f"{prefix} {localized_name}"
                else:
                    localized_name = tpl.Name
                    label = tpl.Name
                if current and current.lower() not in localized_name.lower():
                    continue
                choices.append(app_commands.Choice(name=label[:100], value=tpl.Name))
            return choices[:25]

    async def _guild_template_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        with self.bot.session_scope() as session:
            return _filter_choices(ApplicationTemplate.get_guild_templates(interaction.guild.id, session), current)

    # -- Permission helper ---------------------------------------------------

    def _has_manage_permission(self, interaction: Interaction) -> bool:
        """Return True if the user is an admin or has the guild's manager role."""
        return check_override_permission(interaction, self.bot)

    # -- Helpers for modal callbacks -----------------------------------------

    async def _start_dm_conversation(self, interaction: Interaction, conv, lang: str) -> None:
        """Defer, start a DM conversation, and confirm or report DM failure."""
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.convMan.init_conversation(conv)
        except discord.Forbidden:
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return
        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)

    async def start_template_create_conversation(
        self,
        interaction: Interaction,
        template_name: str,
        approval_message: str | None,
        denial_message: str | None,
        lang: str,
    ) -> None:
        """Start the DM conversation flow for template creation (called from modal on_submit)."""
        from modules.conversations.application import ApplicationTemplateCreateConversation

        conv = ApplicationTemplateCreateConversation(
            self.bot,
            interaction.user,
            interaction.guild,
            template_name=template_name,
            approval_message=approval_message,
            denial_message=denial_message,
        )
        await self._start_dm_conversation(interaction, conv, lang)

    @staticmethod
    def _get_or_create_config(guild_id: int, session) -> "ApplicationGuildConfig":
        """Return the guild's ApplicationGuildConfig, creating one if it doesn't exist."""
        config = ApplicationGuildConfig.get(guild_id, session)
        if config is None:
            config = ApplicationGuildConfig(GuildId=guild_id)
            session.add(config)
        return config

    @staticmethod
    async def _get_form_or_respond(
        interaction: Interaction, name: str, session
    ) -> tuple[str, "ApplicationForm"] | None:
        """Look up a form by name; returns (lang, form) or sends an error and returns None."""
        lang = get_guild_language(interaction.guild_id, session)
        form = ApplicationForm.get(name, interaction.guild.id, session)
        if not form:
            await interaction.response.send_message(
                get_string(lang, "application.form_not_found", name=name), ephemeral=True
            )
            return None
        return lang, form

    async def _check_perm_and_prefill(
        self,
        interaction: Interaction,
        description_message: str | None,
        channel: TextChannel | None,
    ) -> tuple[str, str] | None:
        """Check manage permission and resolve description_message; returns (lang, prefill) or None on error."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return None

        lang = self._lang(interaction.guild_id)

        prefill = ""
        if description_message:
            content, error = await fetch_message_content(self.bot, description_message, channel, interaction, lang)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return None
            prefill = content or ""
        return lang, prefill

    async def apply_settings(
        self,
        interaction: Interaction,
        name: str,
        *,
        lang: str,
        review_channel: TextChannel | None = None,
        channel: TextChannel | None = None,
        description: str | None = None,
        approvals: int | None = None,
        denials: int | None = None,
        approval_message: str | None = None,
        denial_message: str | None = None,
    ) -> None:
        """Validate and persist form settings, then confirm (called directly or from modal on_submit)."""
        repost_apply = False
        edit_apply = False
        form_id = None

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                msg = get_string(lang, "application.form_not_found", name=name)
                await _send_ephemeral(interaction, msg)
                return

            changes = []
            if review_channel is not None:
                form.ReviewChannelId = review_channel.id
                changes.append(
                    get_string(lang, "application.settings.change_review_channel", channel=review_channel.mention)
                )
            if channel is not None:
                form.ApplyChannelId = channel.id
                changes.append(get_string(lang, "application.settings.change_channel", channel=channel.mention))
                repost_apply = True
            if description is not None:
                form.ApplyDescription = description
                changes.append(get_string(lang, "application.settings.change_description"))
                if not repost_apply and form.ApplyMessageId:
                    edit_apply = True
            if approvals is not None:
                form.RequiredApprovals = approvals
                changes.append(get_string(lang, "application.settings.change_approvals", count=approvals))
            if denials is not None:
                form.RequiredDenials = denials
                changes.append(get_string(lang, "application.settings.change_denials", count=denials))
            if approval_message is not None:
                form.ApprovalMessage = approval_message
                changes.append(get_string(lang, "application.settings.change_approval_message"))
            if denial_message is not None:
                form.DenialMessage = denial_message
                changes.append(get_string(lang, "application.settings.change_denial_message"))

            if not changes:
                msg = get_string(lang, "application.settings.nothing_to_change")
                await _send_ephemeral(interaction, msg)
                return

            form_id = form.Id

        msg = get_string(lang, "application.settings.success", name=name, changes=", ".join(changes))
        await _send_ephemeral(interaction, msg)

        if repost_apply:
            from modules.views.application import post_apply_button_message

            try:
                await post_apply_button_message(self.bot, form_id)
            except discord.HTTPException:
                self.bot.log.error("application: failed to repost apply button after settings change", exc_info=True)
        elif edit_apply:
            from modules.views.application import edit_apply_button_message

            try:
                await edit_apply_button_message(self.bot, form_id)
            except discord.HTTPException:
                self.bot.log.error("application: failed to edit apply button after description change", exc_info=True)

    # -- /application create -------------------------------------------------

    @app_commands.command(name="create")
    @app_commands.rename(review_channel="review-channel", description_message="description-message")
    @app_commands.describe(
        name="Name for the new application form",
        review_channel="Channel where reviews will be posted",
        channel="Channel where the apply button will be posted (optional)",
        description_message="Message ID or link whose text becomes the description (message is deleted)",
        approvals="Number of approvals required (default: 1)",
        denials="Number of denials required (default: 1)",
    )
    async def _create(
        self,
        interaction: Interaction,
        name: str,
        review_channel: TextChannel,
        channel: Optional[TextChannel] = None,
        description_message: Optional[str] = None,
        approvals: Optional[app_commands.Range[int, 1]] = None,
        denials: Optional[app_commands.Range[int, 1]] = None,
    ):
        """Create a new application form via DM conversation."""
        result = await self._check_perm_and_prefill(interaction, description_message, channel)
        if result is None:
            return
        lang, prefill_description = result

        with self.bot.session_scope() as session:
            existing = ApplicationForm.get(name, interaction.guild.id, session)
            if existing:
                await interaction.response.send_message(
                    get_string(lang, "application.form_already_exists", name=name), ephemeral=True
                )
                return

        # Capture all context in a closure so the modal callback can start the conversation
        bot = self.bot
        user = interaction.user
        guild = interaction.guild
        review_channel_id = review_channel.id
        apply_channel_id = channel.id if channel else None

        async def _on_submit(modal_interaction: Interaction, description, approval_message, denial_message):
            conv = ApplicationCreateConversation(
                bot,
                user,
                guild,
                name,
                review_channel_id=review_channel_id,
                apply_channel_id=apply_channel_id,
                apply_description=description,
                required_approvals=approvals,
                required_denials=denials,
                approval_message=approval_message,
                denial_message=denial_message,
            )
            await self._start_dm_conversation(modal_interaction, conv, lang)

        modal = _FormMessagesModal(
            title=get_string(lang, "application.create.modal_title"),
            lang=lang,
            callback=_on_submit,
            default_description=prefill_description,
        )
        await interaction.response.send_modal(modal)

    # -- /application delete -------------------------------------------------

    @app_commands.command(name="delete")
    @app_commands.describe(name="Name of the form to delete")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _delete(self, interaction: Interaction, name: str):
        """Delete an application form."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            result = await self._get_form_or_respond(interaction, name, session)
            if result is None:
                return
            lang, form = result
            apply_channel_id = form.ApplyChannelId
            apply_message_id = form.ApplyMessageId
            session.delete(form)

        await interaction.response.send_message(
            get_string(lang, "application.delete.success", name=name), ephemeral=True
        )

        if apply_channel_id and apply_message_id:
            from modules.views.application import delete_apply_message

            try:
                await delete_apply_message(self.bot, apply_channel_id, apply_message_id)
            except discord.HTTPException:
                self.bot.log.error("application: failed to delete apply button message on form delete", exc_info=True)

    # -- /application list ---------------------------------------------------

    @app_commands.command(name="list")
    async def _list(self, interaction: Interaction):
        """List all application forms for this server."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            forms = ApplicationForm.get_all_by_guild(interaction.guild.id, session)
            if not forms:
                await interaction.response.send_message(get_string(lang, "application.list.empty"), ephemeral=True)
                return

            lines = []
            for form in forms:
                status = (
                    get_string(lang, "application.list.status_ready")
                    if form.ReviewChannelId
                    else get_string(lang, "application.list.status_not_ready")
                )
                q_count = len(form.questions) if form.questions else 0
                lines.append(
                    get_string(lang, "application.list.entry", name=form.Name, questions=q_count, status=status)
                )

        embed = Embed(title=get_string(lang, "application.list.title"), description="\n".join(lines), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /application edit ---------------------------------------------------

    @app_commands.command(name="edit")
    @app_commands.describe(name="Name of the form to edit")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _edit(self, interaction: Interaction, name: str):
        """Edit an application form's questions via DM conversation."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            result = await self._get_form_or_respond(interaction, name, session)
            if result is None:
                return
            lang, form = result
            form_id = form.Id

        conv = ApplicationEditConversation(self.bot, interaction.user, interaction.guild, form_id)
        await self._start_dm_conversation(interaction, conv, lang)

    # -- /application settings -----------------------------------------------

    @app_commands.command(name="settings")
    @app_commands.rename(
        review_channel="review-channel",
        description_message="description-message",
        edit_description="edit-description",
    )
    @app_commands.describe(
        name="Name of the form",
        review_channel="New review channel",
        channel="Channel where the apply button will be posted",
        edit_description="Open a modal to edit the form description",
        description_message="Message ID or link whose text becomes the description (message is deleted)",
        approvals="Number of approvals required",
        denials="Number of denials required",
        approval_message="Message sent on approval",
        denial_message="Message sent on denial",
    )
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _settings(
        self,
        interaction: Interaction,
        name: str,
        review_channel: Optional[TextChannel] = None,
        channel: Optional[TextChannel] = None,
        edit_description: Optional[bool] = None,
        description_message: Optional[str] = None,
        approvals: Optional[app_commands.Range[int, 1]] = None,
        denials: Optional[app_commands.Range[int, 1]] = None,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
    ):
        """Update settings for an application form."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        description = None
        if description_message:
            content, error = await fetch_message_content(self.bot, description_message, channel, interaction, lang)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            description = content

        # If edit-description flag is set and no description yet → show modal
        if edit_description and description is None:
            with self.bot.session_scope() as session:
                form = ApplicationForm.get(name, interaction.guild.id, session)
                if not form:
                    await interaction.response.send_message(
                        get_string(lang, "application.form_not_found", name=name), ephemeral=True
                    )
                    return
                current_desc = form.ApplyDescription or ""

            # Bundle all other inline settings so the modal callback can apply them too
            settings_kwargs = {}
            if review_channel is not None:
                settings_kwargs["review_channel"] = review_channel
            if channel is not None:
                settings_kwargs["channel"] = channel
            if approvals is not None:
                settings_kwargs["approvals"] = approvals
            if denials is not None:
                settings_kwargs["denials"] = denials
            if approval_message is not None:
                settings_kwargs["approval_message"] = approval_message
            if denial_message is not None:
                settings_kwargs["denial_message"] = denial_message

            modal = _SettingsDescriptionModal(self.bot, name, current_desc, settings_kwargs, lang)
            await interaction.response.send_modal(modal)
            return

        await self.apply_settings(
            interaction,
            name,
            lang=lang,
            review_channel=review_channel,
            channel=channel,
            description=description,
            approvals=approvals,
            denials=denials,
            approval_message=approval_message,
            denial_message=denial_message,
        )

    # -- /application template list ------------------------------------------

    @template_group.command(name="list")
    async def _template_list(self, interaction: Interaction):
        """Show available application form templates."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            templates = ApplicationTemplate.get_available(interaction.guild.id, session)
            if not templates:
                await interaction.response.send_message(
                    get_string(lang, "application.template.list.empty"), ephemeral=True
                )
                return

            lines = []
            for tpl in templates:
                prefix = (
                    get_string(lang, "application.template.list.prefix_builtin")
                    if tpl.IsBuiltIn
                    else get_string(lang, "application.template.list.prefix_custom")
                )
                if tpl.IsBuiltIn:
                    yaml_key = TEMPLATE_KEY_MAP.get(tpl.Name)
                    if yaml_key:
                        try:
                            display_name = get_raw(lang, f"application.builtin_templates.{yaml_key}.name")
                        except KeyError:
                            display_name = tpl.Name
                    else:
                        display_name = tpl.Name
                else:
                    display_name = tpl.Name
                q_count = len(tpl.questions) if tpl.questions else 0
                lines.append(
                    get_string(
                        lang, "application.template.list.entry", prefix=prefix, name=display_name, questions=q_count
                    )
                )

        embed = Embed(
            title=get_string(lang, "application.template.list.title"), description="\n".join(lines), color=0x5865F2
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /application template view -------------------------------------------

    @template_group.command(name="view")
    @app_commands.describe(name="Template to inspect")
    @app_commands.autocomplete(name=_template_autocomplete)
    async def _template_view(self, interaction: Interaction, name: str):
        """Show the contents of a template (questions, approval/denial messages)."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            tpl = ApplicationTemplate.get_by_name(name, interaction.guild.id, session)
            if not tpl:
                await interaction.response.send_message(
                    get_string(lang, "application.template.not_found", name=name), ephemeral=True
                )
                return

            # Resolve display name and questions for built-in templates from YAML
            questions = None
            display_name = tpl.Name
            if tpl.IsBuiltIn:
                yaml_key = TEMPLATE_KEY_MAP.get(tpl.Name)
                if yaml_key:
                    try:
                        display_name = get_raw(lang, f"application.builtin_templates.{yaml_key}.name")
                    except KeyError:
                        pass
                    try:
                        questions = get_raw(lang, f"application.builtin_templates.{yaml_key}.questions")
                    except KeyError:
                        pass
                type_label = get_string(lang, "application.template.view.type_builtin")
            else:
                type_label = get_string(lang, "application.template.view.type_custom")

            # Fall back to DB questions
            if questions is None:
                questions = [q.QuestionText for q in tpl.questions] if tpl.questions else []

            if questions:
                q_lines = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
            else:
                q_lines = get_string(lang, "application.template.view.no_questions")

            not_set = get_string(lang, "application.template.view.not_set")
            approval = tpl.ApprovalMessage or not_set
            denial = tpl.DenialMessage or not_set

        embed = Embed(
            title=get_string(lang, "application.template.view.title", name=display_name),
            description=type_label,
            color=0x5865F2,
        )
        embed.add_field(name=get_string(lang, "application.template.view.questions_title"), value=q_lines, inline=False)
        embed.add_field(name=get_string(lang, "application.template.view.approval_title"), value=approval, inline=False)
        embed.add_field(name=get_string(lang, "application.template.view.denial_title"), value=denial, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /application template create ----------------------------------------

    @template_group.command(name="create")
    @app_commands.describe(name="Name for the new template")
    async def _template_create(
        self,
        interaction: Interaction,
        name: str,
    ):
        """Create a new guild template via DM conversation."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            existing = ApplicationTemplate.get_by_name(name, interaction.guild.id, session)
            if existing and not existing.IsBuiltIn:
                await interaction.response.send_message(
                    get_string(lang, "application.template.already_exists", name=name), ephemeral=True
                )
                return

        modal = _TemplateCreateMessagesModal(self.bot, interaction.user, interaction.guild, name, lang)
        await interaction.response.send_modal(modal)

    # -- /application template use -------------------------------------------

    @template_group.command(name="use")
    @app_commands.rename(review_channel="review-channel", description_message="description-message")
    @app_commands.describe(
        template="Template to use",
        name="Name for the new form",
        review_channel="Channel where reviews will be posted",
        channel="Channel where the apply button will be posted (optional)",
        description_message="Message ID or link whose text becomes the description (message is deleted)",
    )
    @app_commands.autocomplete(template=_template_autocomplete)
    async def _template_use(
        self,
        interaction: Interaction,
        template: str,
        name: str,
        review_channel: TextChannel,
        channel: Optional[TextChannel] = None,
        description_message: Optional[str] = None,
    ):
        """Create a new form from a template."""
        result = await self._check_perm_and_prefill(interaction, description_message, channel)
        if result is None:
            return
        lang, prefill_description = result

        with self.bot.session_scope() as session:
            tpl = ApplicationTemplate.get_by_name(template, interaction.guild.id, session)
            if not tpl:
                await interaction.response.send_message(
                    get_string(lang, "application.template.not_found", name=template), ephemeral=True
                )
                return

            existing = ApplicationForm.get(name, interaction.guild.id, session)
            if existing:
                await interaction.response.send_message(
                    get_string(lang, "application.form_already_exists", name=name), ephemeral=True
                )
                return

            # Capture template defaults for pre-filling the modal
            default_approval = tpl.ApprovalMessage or ""
            default_denial = tpl.DenialMessage or ""

        # Capture context in a closure so the modal callback can create the form
        bot = self.bot
        guild_id = interaction.guild.id
        review_channel_id = review_channel.id
        apply_channel_id = channel.id if channel else None

        async def _on_submit(modal_interaction: Interaction, description, approval_message, denial_message):
            form_id = None
            with bot.session_scope() as db_session:
                # Re-query template (session closed after permission checks above)
                tmpl = ApplicationTemplate.get_by_name(template, guild_id, db_session)

                # Resolve questions: for built-in templates, use localized YAML questions
                questions = None
                if tmpl and tmpl.IsBuiltIn:
                    yaml_key = TEMPLATE_KEY_MAP.get(tmpl.Name)
                    if yaml_key:
                        try:
                            questions = get_raw(lang, f"application.builtin_templates.{yaml_key}.questions")
                        except KeyError:
                            bot.log.warning(
                                "No YAML questions for built-in template %s (lang=%s, key=%s); falling back to DB",
                                tmpl.Name,
                                lang,
                                yaml_key,
                            )

                # Use user-provided values; fall back to template defaults when user leaves a field empty
                final_approval = (
                    approval_message if approval_message is not None else (tmpl.ApprovalMessage if tmpl else None)
                )
                final_denial = denial_message if denial_message is not None else (tmpl.DenialMessage if tmpl else None)

                form = ApplicationForm(
                    GuildId=guild_id,
                    Name=name,
                    ReviewChannelId=review_channel_id,
                    ApplyChannelId=apply_channel_id,
                    ApplyDescription=description,
                    ApprovalMessage=final_approval,
                    DenialMessage=final_denial,
                )
                db_session.add(form)
                db_session.flush()

                if questions is not None:
                    for i, q_text in enumerate(questions, start=1):
                        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText=q_text, SortOrder=i))
                elif tmpl:
                    for tpl_q in tmpl.questions:
                        db_session.add(
                            ApplicationQuestion(
                                FormId=form.Id, QuestionText=tpl_q.QuestionText, SortOrder=tpl_q.SortOrder
                            )
                        )
                form_id = form.Id

            await modal_interaction.response.send_message(
                get_string(lang, "application.template.use.success", name=name, template=template), ephemeral=True
            )

            if apply_channel_id and form_id:
                from modules.views.application import post_apply_button_message

                try:
                    await post_apply_button_message(bot, form_id)
                except discord.HTTPException:
                    bot.log.error("application: failed to post apply button after template use", exc_info=True)

        modal = _FormMessagesModal(
            title=get_string(lang, "application.template.use.modal_title"),
            lang=lang,
            callback=_on_submit,
            default_description=prefill_description,
            default_approval=default_approval,
            default_denial=default_denial,
        )
        await interaction.response.send_modal(modal)

    # -- /application template save ------------------------------------------

    @template_group.command(name="save")
    @app_commands.describe(form="Form to save as template", template_name="Name for the new template")
    @app_commands.autocomplete(form=_form_name_autocomplete)
    async def _template_save(self, interaction: Interaction, form: str, template_name: str):
        """Save an existing form as a guild template."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            src_form = ApplicationForm.get(form, interaction.guild.id, session)
            if not src_form:
                await interaction.response.send_message(
                    get_string(lang, "application.form_not_found", name=form), ephemeral=True
                )
                return

            existing_tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
            if existing_tpl:
                await interaction.response.send_message(
                    get_string(lang, "application.template.already_exists", name=template_name), ephemeral=True
                )
                return

            tpl = ApplicationTemplate(
                GuildId=interaction.guild.id,
                Name=template_name,
                IsBuiltIn=False,
                ApprovalMessage=src_form.ApprovalMessage,
                DenialMessage=src_form.DenialMessage,
            )
            session.add(tpl)
            session.flush()

            for q in src_form.questions:
                session.add(
                    ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText=q.QuestionText, SortOrder=q.SortOrder)
                )

        await interaction.response.send_message(
            get_string(lang, "application.template.save.success", template_name=template_name, form=form),
            ephemeral=True,
        )

    # -- /application template delete ----------------------------------------

    @template_group.command(name="delete")
    @app_commands.describe(template_name="Name of the guild template to delete")
    @app_commands.autocomplete(template_name=_guild_template_autocomplete)
    async def _template_delete(self, interaction: Interaction, template_name: str):
        """Delete a guild custom template."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
            if not tpl:
                await interaction.response.send_message(
                    get_string(lang, "application.template.not_found", name=template_name), ephemeral=True
                )
                return
            if tpl.IsBuiltIn:
                await interaction.response.send_message(
                    get_string(lang, "application.template.delete.builtin_forbidden"), ephemeral=True
                )
                return
            session.delete(tpl)

        await interaction.response.send_message(
            get_string(lang, "application.template.delete.success", name=template_name), ephemeral=True
        )

    # -- /application template edit-messages ---------------------------------

    async def save_template_messages(
        self,
        interaction: Interaction,
        template_name: str,
        approval_message: str | None,
        denial_message: str | None,
        lang: str,
    ) -> None:
        """Validate and persist template message changes, then confirm."""
        with self.bot.session_scope() as session:
            tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
            if not tpl:
                msg = get_string(lang, "application.template.not_found", name=template_name)
                await _send_ephemeral(interaction, msg)
                return
            if tpl.IsBuiltIn:
                msg = get_string(lang, "application.template.edit_messages.builtin_forbidden")
                await _send_ephemeral(interaction, msg)
                return

            changes = []
            if approval_message is not None:
                tpl.ApprovalMessage = approval_message
                changes.append(get_string(lang, "application.template.edit_messages.change_approval"))
            if denial_message is not None:
                tpl.DenialMessage = denial_message
                changes.append(get_string(lang, "application.template.edit_messages.change_denial"))

        if not changes:
            msg = get_string(lang, "application.template.edit_messages.nothing_to_update")
        else:
            msg = get_string(
                lang, "application.template.edit_messages.success", name=template_name, changes=", ".join(changes)
            )

        await _send_ephemeral(interaction, msg)

    @template_group.command(name="edit-messages")
    @app_commands.describe(
        template_name="Name of the guild template to update",
        approval_message="New default approval message (optional, opens a modal if all omitted)",
        denial_message="New default denial message (optional, opens a modal if all omitted)",
        approval_message_source="Message ID or link whose text becomes the approval message (message is deleted)",
        denial_message_source="Message ID or link whose text becomes the denial message (message is deleted)",
    )
    @app_commands.rename(
        approval_message_source="approval-message-source",
        denial_message_source="denial-message-source",
    )
    @app_commands.autocomplete(template_name=_guild_template_autocomplete)
    async def _template_edit_messages(
        self,
        interaction: Interaction,
        template_name: str,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
        approval_message_source: Optional[str] = None,
        denial_message_source: Optional[str] = None,
    ):
        """Update default approval/denial messages for a custom template."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        # Fetch from message references if provided
        if approval_message_source:
            content, error = await fetch_message_content(
                self.bot,
                approval_message_source,
                None,
                interaction,
                lang,
                key_prefix="application.template.fetch_message",
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            approval_message = content

        if denial_message_source:
            content, error = await fetch_message_content(
                self.bot,
                denial_message_source,
                None,
                interaction,
                lang,
                key_prefix="application.template.fetch_message",
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            denial_message = content

        # When no text provided at all → open modal pre-filled with current values
        if approval_message is None and denial_message is None:
            with self.bot.session_scope() as session:
                tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
                if not tpl:
                    await interaction.response.send_message(
                        get_string(lang, "application.template.not_found", name=template_name), ephemeral=True
                    )
                    return
                if tpl.IsBuiltIn:
                    await interaction.response.send_message(
                        get_string(lang, "application.template.edit_messages.builtin_forbidden"), ephemeral=True
                    )
                    return
                current_approval = tpl.ApprovalMessage or ""
                current_denial = tpl.DenialMessage or ""

            modal = _TemplateMessagesModal(self.bot, template_name, current_approval, current_denial, lang)
            await interaction.response.send_modal(modal)
            return

        await self.save_template_messages(interaction, template_name, approval_message, denial_message, lang)

    # -- /application export -------------------------------------------------

    @app_commands.command(name="export")
    @app_commands.describe(name="Name of the form to export")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _export(self, interaction: Interaction, name: str):
        """Export an application form as a JSON file via DM."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(
                    get_string(lang, "application.form_not_found", name=name), ephemeral=True
                )
                return

            form_dict = {
                "name": form.Name,
                "required_approvals": form.RequiredApprovals,
                "required_denials": form.RequiredDenials,
                "approval_message": form.ApprovalMessage,
                "denial_message": form.DenialMessage,
                "questions": [{"text": q.QuestionText, "order": q.SortOrder} for q in form.questions],
            }

        data = json.dumps(form_dict, indent=2)
        file = discord.File(io.BytesIO(data.encode()), filename=f"{name}.json")

        await interaction.response.send_message(get_string(lang, "application.check_dms"), ephemeral=True)

        try:
            await interaction.user.send(file=file)
        except (discord.Forbidden, discord.NotFound):
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)

    # -- /application import -------------------------------------------------

    @app_commands.command(name="import")
    async def _import_form(self, interaction: Interaction):
        """Import an application form from a JSON file via DM."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.send(get_string(lang, "application.import.upload_prompt"))
        except (discord.Forbidden, discord.NotFound):
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return

        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)

        def check(m):
            return m.author.id == interaction.user.id and m.guild is None and m.attachments

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            try:
                await interaction.user.send(get_string(lang, "application.import.timeout"))
            except (discord.Forbidden, discord.NotFound):
                self.bot.log.debug("Could not send import timeout DM to user %s", interaction.user.id)
            return

        attachment = msg.attachments[0]
        if attachment.size > 1_000_000:  # 1 MB
            await interaction.user.send(get_string(lang, "application.import.file_too_large"))
            return
        try:
            raw = await attachment.read()
            form_data = json.loads(raw.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            await interaction.user.send(get_string(lang, "application.import.invalid_json"))
            return

        # Validate required fields
        if not isinstance(form_data.get("name"), str) or not form_data["name"].strip():
            await interaction.user.send(get_string(lang, "application.import.missing_name"))
            return

        questions = form_data.get("questions")
        if not isinstance(questions, list) or len(questions) == 0:
            await interaction.user.send(get_string(lang, "application.import.invalid_questions"))
            return

        for i, q in enumerate(questions):
            if not isinstance(q, dict) or not isinstance(q.get("text"), str) or not q["text"].strip():
                await interaction.user.send(get_string(lang, "application.import.invalid_question", index=i + 1))
                return

        approvals = form_data.get("required_approvals", 1)
        denials = form_data.get("required_denials", 1)
        if not isinstance(approvals, int) or approvals < 1 or not isinstance(denials, int) or denials < 1:
            await interaction.user.send(get_string(lang, "application.import.invalid_counts"))
            return

        form_name = form_data["name"].strip()

        with self.bot.session_scope() as session:
            existing = ApplicationForm.get(form_name, interaction.guild.id, session)
            if existing:
                await interaction.user.send(get_string(lang, "application.import.form_exists", name=form_name))
                return

            form = ApplicationForm(
                GuildId=interaction.guild.id,
                Name=form_name,
                RequiredApprovals=approvals,
                RequiredDenials=denials,
                ApprovalMessage=form_data.get("approval_message"),
                DenialMessage=form_data.get("denial_message"),
            )
            session.add(form)
            session.flush()

            for i, q in enumerate(questions):
                session.add(
                    ApplicationQuestion(FormId=form.Id, QuestionText=q["text"].strip(), SortOrder=q.get("order", i + 1))
                )

        await interaction.user.send(
            get_string(lang, "application.import.success", name=form_name, count=len(questions))
        )

    # -- /application managerole set -----------------------------------------

    @managerole_group.command(name="set")
    @checks.has_permissions(administrator=True)
    @app_commands.describe(role="Role that can manage applications")
    async def _managerole_set(self, interaction: Interaction, role: Role):
        """Set the application manager role for this server."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            config = self._get_or_create_config(interaction.guild.id, session)
            config.ManagerRoleId = role.id

        await interaction.response.send_message(
            get_string(lang, "application.managerole.set_success", role=role.name), ephemeral=True
        )

    # -- /application managerole remove --------------------------------------

    @managerole_group.command(name="remove")
    @checks.has_permissions(administrator=True)
    async def _managerole_remove(self, interaction: Interaction):
        """Remove the application manager role for this server."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None or config.ManagerRoleId is None:
                await interaction.response.send_message(
                    get_string(lang, "application.managerole.not_configured"), ephemeral=True
                )
                return
            config.ManagerRoleId = None

        await interaction.response.send_message(
            get_string(lang, "application.managerole.remove_success"), ephemeral=True
        )

    # -- /application reviewerrole set -----------------------------------------

    @reviewerrole_group.command(name="set")
    @checks.has_permissions(administrator=True)
    @app_commands.describe(role="Role that can vote on applications")
    async def _reviewerrole_set(self, interaction: Interaction, role: Role):
        """Set the application reviewer role for this server."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            config = self._get_or_create_config(interaction.guild.id, session)
            config.ReviewerRoleId = role.id

        await interaction.response.send_message(
            get_string(lang, "application.reviewerrole.set_success", role=role.name), ephemeral=True
        )

    # -- /application reviewerrole remove ---------------------------------------

    @reviewerrole_group.command(name="remove")
    @checks.has_permissions(administrator=True)
    async def _reviewerrole_remove(self, interaction: Interaction):
        """Remove the application reviewer role for this server."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None or config.ReviewerRoleId is None:
                await interaction.response.send_message(
                    get_string(lang, "application.reviewerrole.not_configured"), ephemeral=True
                )
                return
            config.ReviewerRoleId = None

        await interaction.response.send_message(
            get_string(lang, "application.reviewerrole.remove_success"), ephemeral=True
        )


class _TemplateMessagesModal(discord.ui.Modal):
    """Two-field modal for editing template approval/denial messages."""

    approval_input = discord.ui.TextInput(
        label="Approval Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )
    denial_input = discord.ui.TextInput(
        label="Denial Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )

    def __init__(self, bot, template_name: str, current_approval: str, current_denial: str, lang: str):
        super().__init__(title=get_string(lang, "application.template.edit_messages.modal_title"))
        self.bot = bot
        self.template_name = template_name
        self.lang = lang
        _p = "application.template.edit_messages.modal_approval"
        _localize_field(self.approval_input, lang, _p, current_approval)
        _p = "application.template.edit_messages.modal_denial"
        _localize_field(self.denial_input, lang, _p, current_denial)

    async def on_submit(self, interaction: Interaction):
        approval = self.approval_input.value.strip() or None
        denial = self.denial_input.value.strip() or None
        cog = self.bot.get_cog("Application")
        await cog.save_template_messages(interaction, self.template_name, approval, denial, self.lang)


class _FormMessagesModal(discord.ui.Modal):
    """Shared 3-field modal (description + approval + denial), driven by a callback closure."""

    description_input = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )
    approval_input = discord.ui.TextInput(
        label="Approval Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )
    denial_input = discord.ui.TextInput(
        label="Denial Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )

    def __init__(
        self,
        *,
        title: str,
        lang: str,
        callback,
        default_description: str = "",
        default_approval: str = "",
        default_denial: str = "",
    ):
        super().__init__(title=title)
        self._callback = callback
        _f = "application.modal_fields"
        _localize_field(self.description_input, lang, f"{_f}.description", default_description)
        _localize_field(self.approval_input, lang, f"{_f}.approval", default_approval)
        _localize_field(self.denial_input, lang, f"{_f}.denial", default_denial)

    async def on_submit(self, interaction: Interaction):
        desc = self.description_input.value.strip() or None
        approval = self.approval_input.value.strip() or None
        denial = self.denial_input.value.strip() or None
        await self._callback(interaction, desc, approval, denial)


class _TemplateCreateMessagesModal(discord.ui.Modal):
    """Two-field modal (approval + denial) for template create — stores context to start conversation."""

    approval_input = discord.ui.TextInput(
        label="Approval Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )
    denial_input = discord.ui.TextInput(
        label="Denial Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )

    def __init__(self, bot, user, guild, template_name: str, lang: str):
        super().__init__(title=get_string(lang, "application.template.create.modal_title"))
        self.bot = bot
        self.user = user
        self.guild = guild
        self.template_name = template_name
        self.lang = lang
        _f = "application.modal_fields"
        _localize_field(self.approval_input, lang, f"{_f}.approval")
        _localize_field(self.denial_input, lang, f"{_f}.denial")

    async def on_submit(self, interaction: Interaction):
        approval = self.approval_input.value.strip() or None
        denial = self.denial_input.value.strip() or None
        cog = self.bot.get_cog("Application")
        await cog.start_template_create_conversation(interaction, self.template_name, approval, denial, self.lang)


class _SettingsDescriptionModal(discord.ui.Modal):
    """Single-field modal (description) for /application settings edit-description."""

    description_input = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False,
    )

    def __init__(self, bot, form_name: str, current_description: str, settings_kwargs: dict, lang: str):
        super().__init__(title=get_string(lang, "application.settings.modal_title"))
        self.bot = bot
        self.form_name = form_name
        self.settings_kwargs = settings_kwargs
        self.lang = lang
        _localize_field(self.description_input, lang, "application.modal_fields.description", current_description)

    async def on_submit(self, interaction: Interaction):
        desc = self.description_input.value.strip() or None
        cog = self.bot.get_cog("Application")
        await cog.apply_settings(interaction, self.form_name, description=desc, lang=self.lang, **self.settings_kwargs)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Application(bot))
