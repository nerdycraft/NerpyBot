# -*- coding: utf-8 -*-
"""Application form management cog — admin commands, templates, and manager role."""

import asyncio
import io
import json
import re
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
from utils.strings import get_guild_language, get_raw, get_string

_MESSAGE_LINK_RE = re.compile(r"https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/channels/\d+/(\d+)/(\d+)")


async def _fetch_description_from_message(
    bot, message_ref: str, channel_hint: TextChannel | None, interaction: Interaction, lang: str = "en"
) -> tuple[str | None, str | None]:
    """Fetch message content for use as apply description, then delete the source message.

    Returns ``(content, error)``. On success ``error`` is ``None``; on failure
    ``content`` is ``None`` and ``error`` describes the problem.
    """
    message_ref = message_ref.strip()
    match = _MESSAGE_LINK_RE.match(message_ref)
    if match:
        channel_id = int(match.group(1))
        message_id = int(match.group(2))
    else:
        try:
            message_id = int(message_ref)
        except ValueError:
            return None, get_string(lang, "application.fetch_description.invalid_ref")
        channel_id = channel_hint.id if channel_hint else interaction.channel_id

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden):
            return None, get_string(lang, "application.fetch_description.channel_inaccessible")

    try:
        msg = await channel.fetch_message(message_id)
    except discord.NotFound:
        return None, get_string(lang, "application.fetch_description.message_not_found")
    except discord.Forbidden:
        return None, get_string(lang, "application.fetch_description.no_read_permission")

    content = msg.content
    if not content:
        return None, get_string(lang, "application.fetch_description.no_content")

    try:
        await msg.delete()
    except (discord.NotFound, discord.Forbidden):
        bot.log.debug("Could not delete description source message %d", message_id)

    return content, None


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
            forms = ApplicationForm.get_all_by_guild(interaction.guild.id, session)
            choices = []
            for form in forms:
                if current and current.lower() not in form.Name.lower():
                    continue
                choices.append(app_commands.Choice(name=form.Name[:100], value=form.Name))
            return choices[:25]

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
            templates = ApplicationTemplate.get_guild_templates(interaction.guild.id, session)
            choices = []
            for tpl in templates:
                if current and current.lower() not in tpl.Name.lower():
                    continue
                choices.append(app_commands.Choice(name=tpl.Name[:100], value=tpl.Name))
            return choices[:25]

    # -- Permission helper ---------------------------------------------------

    def _has_manage_permission(self, interaction: Interaction) -> bool:
        """Return True if the user is an admin or has the guild's manager role."""
        return check_override_permission(interaction, self.bot)

    # -- /application create -------------------------------------------------

    @app_commands.command(name="create")
    @app_commands.rename(review_channel="review-channel", description_message="description-message")
    @app_commands.describe(
        name="Name for the new application form",
        review_channel="Channel where reviews will be posted",
        channel="Channel where the apply button will be posted (optional)",
        description="Description shown on the apply button embed (optional)",
        description_message="Message ID or link whose text becomes the description (message is deleted)",
        approvals="Number of approvals required (default: 1)",
        denials="Number of denials required (default: 1)",
        approval_message="Message sent to applicant on approval",
        denial_message="Message sent to applicant on denial",
    )
    async def _create(
        self,
        interaction: Interaction,
        name: str,
        review_channel: TextChannel,
        channel: Optional[TextChannel] = None,
        description: Optional[str] = None,
        description_message: Optional[str] = None,
        approvals: Optional[app_commands.Range[int, 1]] = None,
        denials: Optional[app_commands.Range[int, 1]] = None,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
    ):
        """Create a new application form via DM conversation."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        if description_message:
            content, error = await _fetch_description_from_message(
                self.bot, description_message, channel, interaction, lang
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            description = content

        with self.bot.session_scope() as session:
            existing = ApplicationForm.get(name, interaction.guild.id, session)
            if existing:
                await interaction.response.send_message(
                    get_string(lang, "application.form_already_exists", name=name), ephemeral=True
                )
                return

        conv = ApplicationCreateConversation(
            self.bot,
            interaction.user,
            interaction.guild,
            name,
            review_channel_id=review_channel.id,
            apply_channel_id=channel.id if channel else None,
            apply_description=description,
            required_approvals=approvals,
            required_denials=denials,
            approval_message=approval_message,
            denial_message=denial_message,
        )
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.convMan.init_conversation(conv)
        except discord.Forbidden:
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return
        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)

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
            lang = get_guild_language(interaction.guild_id, session)
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(
                    get_string(lang, "application.form_not_found", name=name), ephemeral=True
                )
                return
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
            lang = get_guild_language(interaction.guild_id, session)
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(
                    get_string(lang, "application.form_not_found", name=name), ephemeral=True
                )
                return
            form_id = form.Id

        conv = ApplicationEditConversation(self.bot, interaction.user, interaction.guild, form_id)
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.convMan.init_conversation(conv)
        except discord.Forbidden:
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return
        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)

    # -- /application settings -----------------------------------------------

    @app_commands.command(name="settings")
    @app_commands.rename(review_channel="review-channel", description_message="description-message")
    @app_commands.describe(
        name="Name of the form",
        review_channel="New review channel",
        channel="Channel where the apply button will be posted",
        description="Description shown on the apply button embed",
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
        description: Optional[str] = None,
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

        if description_message:
            content, error = await _fetch_description_from_message(
                self.bot, description_message, channel, interaction, lang
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            description = content

        repost_apply = False
        edit_apply = False
        form_id = None

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(
                    get_string(lang, "application.form_not_found", name=name), ephemeral=True
                )
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
                await interaction.response.send_message(
                    get_string(lang, "application.settings.nothing_to_change"), ephemeral=True
                )
                return

            form_id = form.Id

        await interaction.response.send_message(
            get_string(lang, "application.settings.success", name=name, changes=", ".join(changes)), ephemeral=True
        )

        if repost_apply:
            from modules.views.application import post_apply_button_message

            try:
                await post_apply_button_message(self.bot, form_id)
            except Exception:
                self.bot.log.error("application: failed to repost apply button after settings change", exc_info=True)
        elif edit_apply:
            from modules.views.application import edit_apply_button_message

            try:
                await edit_apply_button_message(self.bot, form_id)
            except discord.HTTPException:
                self.bot.log.error("application: failed to edit apply button after description change", exc_info=True)

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

    # -- /application template create ----------------------------------------

    @template_group.command(name="create")
    @app_commands.describe(
        name="Name for the new template",
        approval_message="Default approval message for forms created from this template (optional)",
        denial_message="Default denial message for forms created from this template (optional)",
    )
    async def _template_create(
        self,
        interaction: Interaction,
        name: str,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
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

        from modules.conversations.application import ApplicationTemplateCreateConversation

        conv = ApplicationTemplateCreateConversation(
            self.bot,
            interaction.user,
            interaction.guild,
            template_name=name,
            approval_message=approval_message,
            denial_message=denial_message,
        )
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.convMan.init_conversation(conv)
        except discord.Forbidden:
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return
        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)

    # -- /application template use -------------------------------------------

    @template_group.command(name="use")
    @app_commands.rename(review_channel="review-channel", description_message="description-message")
    @app_commands.describe(
        template="Template to use",
        name="Name for the new form",
        review_channel="Channel where reviews will be posted",
        channel="Channel where the apply button will be posted (optional)",
        description="Description shown on the apply button embed (optional)",
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
        description: Optional[str] = None,
        description_message: Optional[str] = None,
    ):
        """Create a new form from a template."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        if description_message:
            content, error = await _fetch_description_from_message(
                self.bot, description_message, channel, interaction, lang
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            description = content

        form_id = None
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

            # Resolve questions: for built-in templates, use localized YAML questions
            questions = None
            if tpl.IsBuiltIn:
                yaml_key = TEMPLATE_KEY_MAP.get(tpl.Name)
                if yaml_key:
                    try:
                        questions = get_raw(lang, f"application.builtin_templates.{yaml_key}.questions")
                    except KeyError:
                        self.bot.log.warning(
                            "No YAML questions for built-in template %s (lang=%s, key=%s); falling back to DB",
                            tpl.Name,
                            lang,
                            yaml_key,
                        )

            form = ApplicationForm(
                GuildId=interaction.guild.id,
                Name=name,
                ReviewChannelId=review_channel.id,
                ApplyChannelId=channel.id if channel else None,
                ApplyDescription=description,
                ApprovalMessage=tpl.ApprovalMessage,
                DenialMessage=tpl.DenialMessage,
            )
            session.add(form)
            session.flush()

            if questions is not None:
                for i, q_text in enumerate(questions, start=1):
                    session.add(ApplicationQuestion(FormId=form.Id, QuestionText=q_text, SortOrder=i))
            else:
                for tpl_q in tpl.questions:
                    session.add(
                        ApplicationQuestion(FormId=form.Id, QuestionText=tpl_q.QuestionText, SortOrder=tpl_q.SortOrder)
                    )
            form_id = form.Id

        await interaction.response.send_message(
            get_string(lang, "application.template.use.success", name=name, template=template), ephemeral=True
        )

        if channel and form_id:
            from modules.views.application import post_apply_button_message

            try:
                await post_apply_button_message(self.bot, form_id)
            except Exception:
                self.bot.log.error("application: failed to post apply button after template use", exc_info=True)

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

    @template_group.command(name="edit-messages")
    @app_commands.describe(
        template_name="Name of the guild template to update",
        approval_message="New default approval message (optional)",
        denial_message="New default denial message (optional)",
    )
    @app_commands.autocomplete(template_name=_guild_template_autocomplete)
    async def _template_edit_messages(
        self,
        interaction: Interaction,
        template_name: str,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
    ):
        """Update default approval/denial messages for a custom template."""
        if not self._has_manage_permission(interaction):
            lang = self._lang(interaction.guild_id)
            await interaction.response.send_message(get_string(lang, "application.no_permission"), ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)

        if approval_message is None and denial_message is None:
            await interaction.response.send_message(
                get_string(lang, "application.template.edit_messages.nothing_to_update"), ephemeral=True
            )
            return

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

            changes = []
            if approval_message is not None:
                tpl.ApprovalMessage = approval_message
                changes.append(get_string(lang, "application.template.edit_messages.change_approval"))
            if denial_message is not None:
                tpl.DenialMessage = denial_message
                changes.append(get_string(lang, "application.template.edit_messages.change_denial"))

        await interaction.response.send_message(
            get_string(
                lang, "application.template.edit_messages.success", name=template_name, changes=", ".join(changes)
            ),
            ephemeral=True,
        )

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

        def check(msg):
            return msg.author.id == interaction.user.id and msg.guild is None and msg.attachments

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
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None:
                config = ApplicationGuildConfig(GuildId=interaction.guild.id)
                session.add(config)
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
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None:
                config = ApplicationGuildConfig(GuildId=interaction.guild.id)
                session.add(config)
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


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Application(bot))
