# -*- coding: utf-8 -*-
"""Application form management cog — admin commands, templates, and manager role."""

from typing import Optional

from discord import Embed, Interaction, Role, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import GroupCog

from models.application import (
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    seed_built_in_templates,
)
from modules.conversations.application import (
    ApplicationCreateConversation,
    ApplicationEditConversation,
    ApplicationSubmitConversation,
)
from utils.cog import NerpyBotCog


@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
class Application(NerpyBotCog, GroupCog, group_name="application"):
    """Cog for managing application forms, templates, and guild config."""

    template_group = app_commands.Group(name="template", description="Manage form templates", guild_only=True)
    managerole_group = app_commands.Group(name="managerole", description="Configure manager role", guild_only=True)

    def __init__(self, bot):
        super().__init__(bot)
        with self.bot.session_scope() as session:
            seed_built_in_templates(session)

    # -- Top-level /apply command --------------------------------------------

    async def cog_load(self):
        self._apply_command = app_commands.Command(
            name="apply",
            description="Submit an application",
            callback=self._apply,
            guild_only=True,
        )
        self._apply_command.autocomplete("form_name")(self._ready_form_autocomplete)
        self.bot.tree.add_command(self._apply_command)

    async def cog_unload(self):
        self.bot.tree.remove_command("apply")

    @app_commands.guild_only()
    @app_commands.describe(form_name="Application form to fill out")
    async def _apply(self, interaction: Interaction, form_name: str):
        """Submit an application via DM conversation."""
        with self.bot.session_scope() as session:
            form = ApplicationForm.get(form_name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(f"Form **{form_name}** not found.", ephemeral=True)
                return
            if not form.ReviewChannelId:
                await interaction.response.send_message("This form isn't set up yet.", ephemeral=True)
                return
            form_id = form.Id
            name = form.Name
            questions = [(q.Id, q.QuestionText) for q in form.questions]

        conv = ApplicationSubmitConversation(
            self.bot,
            interaction.user,
            interaction.guild,
            form_id=form_id,
            form_name=name,
            questions=questions,
        )
        await self.bot.convMan.init_conversation(conv)
        await interaction.response.send_message("Check your DMs!", ephemeral=True)

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

    async def _ready_form_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        with self.bot.session_scope() as session:
            forms = ApplicationForm.get_ready_by_guild(interaction.guild.id, session)
            choices = []
            for form in forms:
                if current and current.lower() not in form.Name.lower():
                    continue
                choices.append(app_commands.Choice(name=form.Name[:100], value=form.Name))
            return choices[:25]

    async def _template_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        with self.bot.session_scope() as session:
            templates = ApplicationTemplate.get_available(interaction.guild.id, session)
            choices = []
            for tpl in templates:
                label = f"{'[Built-in] ' if tpl.IsBuiltIn else ''}{tpl.Name}"
                if current and current.lower() not in tpl.Name.lower():
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
        if interaction.user.guild_permissions.administrator:
            return True
        with self.bot.session_scope() as session:
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config and config.ManagerRoleId:
                return any(r.id == config.ManagerRoleId for r in interaction.user.roles)
        return False

    # -- /application create -------------------------------------------------

    @app_commands.command(name="create")
    @app_commands.describe(name="Name for the new application form")
    async def _create(self, interaction: Interaction, name: str):
        """Create a new application form via DM conversation."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            existing = ApplicationForm.get(name, interaction.guild.id, session)
            if existing:
                await interaction.response.send_message(f"A form named **{name}** already exists.", ephemeral=True)
                return

        conv = ApplicationCreateConversation(self.bot, interaction.user, interaction.guild, name)
        await self.bot.convMan.init_conversation(conv)
        await interaction.response.send_message("Check your DMs!", ephemeral=True)

    # -- /application delete -------------------------------------------------

    @app_commands.command(name="delete")
    @app_commands.describe(name="Name of the form to delete")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _delete(self, interaction: Interaction, name: str):
        """Delete an application form."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(f"Form **{name}** not found.", ephemeral=True)
                return
            session.delete(form)

        await interaction.response.send_message(f"Form **{name}** deleted.", ephemeral=True)

    # -- /application list ---------------------------------------------------

    @app_commands.command(name="list")
    async def _list(self, interaction: Interaction):
        """List all application forms for this server."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            forms = ApplicationForm.get_all_by_guild(interaction.guild.id, session)
            if not forms:
                await interaction.response.send_message("No application forms configured.", ephemeral=True)
                return

            lines = []
            for form in forms:
                status = "ready" if form.ReviewChannelId else "not ready"
                q_count = len(form.questions) if form.questions else 0
                lines.append(f"**{form.Name}** — {q_count} question(s) — {status}")

        embed = Embed(title="Application Forms", description="\n".join(lines), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /application edit ---------------------------------------------------

    @app_commands.command(name="edit")
    @app_commands.describe(name="Name of the form to edit")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _edit(self, interaction: Interaction, name: str):
        """Edit an application form's questions via DM conversation."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(f"Form **{name}** not found.", ephemeral=True)
                return
            form_id = form.Id

        conv = ApplicationEditConversation(self.bot, interaction.user, interaction.guild, form_id)
        await self.bot.convMan.init_conversation(conv)
        await interaction.response.send_message("Check your DMs!", ephemeral=True)

    # -- /application channel ------------------------------------------------

    @app_commands.command(name="channel")
    @app_commands.describe(name="Name of the form", channel="Channel to send reviews to")
    @app_commands.autocomplete(name=_form_name_autocomplete)
    async def _channel(self, interaction: Interaction, name: str, channel: TextChannel):
        """Set the review channel for an application form."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(f"Form **{name}** not found.", ephemeral=True)
                return
            form.ReviewChannelId = channel.id

        await interaction.response.send_message(
            f"Review channel for **{name}** set to {channel.mention}.", ephemeral=True
        )

    # -- /application settings -----------------------------------------------

    @app_commands.command(name="settings")
    @app_commands.describe(
        name="Name of the form",
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
        approvals: Optional[app_commands.Range[int, 1]] = None,
        denials: Optional[app_commands.Range[int, 1]] = None,
        approval_message: Optional[str] = None,
        denial_message: Optional[str] = None,
    ):
        """Update settings for an application form."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            form = ApplicationForm.get(name, interaction.guild.id, session)
            if not form:
                await interaction.response.send_message(f"Form **{name}** not found.", ephemeral=True)
                return

            changes = []
            if approvals is not None:
                form.RequiredApprovals = approvals
                changes.append(f"approvals={approvals}")
            if denials is not None:
                form.RequiredDenials = denials
                changes.append(f"denials={denials}")
            if approval_message is not None:
                form.ApprovalMessage = approval_message
                changes.append("approval message updated")
            if denial_message is not None:
                form.DenialMessage = denial_message
                changes.append("denial message updated")

            if not changes:
                await interaction.response.send_message("Nothing to change.", ephemeral=True)
                return

        await interaction.response.send_message(
            f"Settings for **{name}** updated: {', '.join(changes)}.", ephemeral=True
        )

    # -- /application template list ------------------------------------------

    @template_group.command(name="list")
    async def _template_list(self, interaction: Interaction):
        """Show available application form templates."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            templates = ApplicationTemplate.get_available(interaction.guild.id, session)
            if not templates:
                await interaction.response.send_message("No templates available.", ephemeral=True)
                return

            lines = []
            for tpl in templates:
                prefix = "[Built-in]" if tpl.IsBuiltIn else "[Custom]"
                q_count = len(tpl.questions) if tpl.questions else 0
                lines.append(f"{prefix} **{tpl.Name}** — {q_count} question(s)")

        embed = Embed(title="Application Templates", description="\n".join(lines), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -- /application template use -------------------------------------------

    @template_group.command(name="use")
    @app_commands.describe(template="Template to use", name="Name for the new form")
    @app_commands.autocomplete(template=_template_autocomplete)
    async def _template_use(self, interaction: Interaction, template: str, name: str):
        """Create a new form from a template."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            tpl = ApplicationTemplate.get_by_name(template, interaction.guild.id, session)
            if not tpl:
                await interaction.response.send_message(f"Template **{template}** not found.", ephemeral=True)
                return

            existing = ApplicationForm.get(name, interaction.guild.id, session)
            if existing:
                await interaction.response.send_message(f"A form named **{name}** already exists.", ephemeral=True)
                return

            form = ApplicationForm(GuildId=interaction.guild.id, Name=name)
            session.add(form)
            session.flush()

            for tpl_q in tpl.questions:
                session.add(
                    ApplicationQuestion(FormId=form.Id, QuestionText=tpl_q.QuestionText, SortOrder=tpl_q.SortOrder)
                )

        await interaction.response.send_message(
            f"Form **{name}** created from template **{template}**.", ephemeral=True
        )

    # -- /application template save ------------------------------------------

    @template_group.command(name="save")
    @app_commands.describe(form="Form to save as template", template_name="Name for the new template")
    @app_commands.autocomplete(form=_form_name_autocomplete)
    async def _template_save(self, interaction: Interaction, form: str, template_name: str):
        """Save an existing form as a guild template."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            src_form = ApplicationForm.get(form, interaction.guild.id, session)
            if not src_form:
                await interaction.response.send_message(f"Form **{form}** not found.", ephemeral=True)
                return

            existing_tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
            if existing_tpl:
                await interaction.response.send_message(
                    f"A template named **{template_name}** already exists.", ephemeral=True
                )
                return

            tpl = ApplicationTemplate(GuildId=interaction.guild.id, Name=template_name, IsBuiltIn=False)
            session.add(tpl)
            session.flush()

            for q in src_form.questions:
                session.add(
                    ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText=q.QuestionText, SortOrder=q.SortOrder)
                )

        await interaction.response.send_message(
            f"Template **{template_name}** saved from form **{form}**.", ephemeral=True
        )

    # -- /application template delete ----------------------------------------

    @template_group.command(name="delete")
    @app_commands.describe(template_name="Name of the guild template to delete")
    @app_commands.autocomplete(template_name=_guild_template_autocomplete)
    async def _template_delete(self, interaction: Interaction, template_name: str):
        """Delete a guild custom template."""
        if not self._has_manage_permission(interaction):
            await interaction.response.send_message("You don't have permission to manage applications.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            tpl = ApplicationTemplate.get_by_name(template_name, interaction.guild.id, session)
            if not tpl:
                await interaction.response.send_message(f"Template **{template_name}** not found.", ephemeral=True)
                return
            if tpl.IsBuiltIn:
                await interaction.response.send_message("Built-in templates cannot be deleted.", ephemeral=True)
                return
            session.delete(tpl)

        await interaction.response.send_message(f"Template **{template_name}** deleted.", ephemeral=True)

    # -- /application managerole set -----------------------------------------

    @managerole_group.command(name="set")
    @checks.has_permissions(administrator=True)
    @app_commands.describe(role="Role that can manage applications")
    async def _managerole_set(self, interaction: Interaction, role: Role):
        """Set the application manager role for this server."""
        with self.bot.session_scope() as session:
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None:
                config = ApplicationGuildConfig(GuildId=interaction.guild.id)
                session.add(config)
            config.ManagerRoleId = role.id

        await interaction.response.send_message(f"Application manager role set to **{role.name}**.", ephemeral=True)

    # -- /application managerole remove --------------------------------------

    @managerole_group.command(name="remove")
    @checks.has_permissions(administrator=True)
    async def _managerole_remove(self, interaction: Interaction):
        """Remove the application manager role for this server."""
        with self.bot.session_scope() as session:
            config = ApplicationGuildConfig.get(interaction.guild.id, session)
            if config is None or config.ManagerRoleId is None:
                await interaction.response.send_message("No manager role is configured.", ephemeral=True)
                return
            config.ManagerRoleId = None

        await interaction.response.send_message("Application manager role removed.", ephemeral=True)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Application(bot))
