# -*- coding: utf-8 -*-

from discord import Interaction, Role, app_commands
from discord.ext.commands import Cog

from models.guild import GuildLanguageConfig
from models.permissions import BotModeratorRole
from utils.checks import is_admin_or_operator
from utils.cog import NerpyBotCog
from utils.strings import available_languages, get_string


@app_commands.default_permissions(administrator=True)
class ServerAdmin(NerpyBotCog, Cog):
    """Cog for server-level admin commands: modrole and language."""

    modrole = app_commands.Group(
        name="modrole", description="Manage the bot-moderator role for this server", guild_only=True
    )
    language = app_commands.Group(name="language", description="Manage the server language preference", guild_only=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Allow administrators and bot operators to use all server admin slash commands."""
        if await is_admin_or_operator(interaction):
            return True
        raise app_commands.CheckFailure("This command requires administrator permissions or bot operator status.")

    @modrole.command(name="get")
    async def _modrole_get(self, interaction: Interaction):
        """Show the currently configured bot-moderator role."""
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
        if entry is not None:
            role = interaction.guild.get_role(entry.RoleId)
            msg = (
                get_string(lang, "admin.modrole.get_current", role=role.name)
                if role is not None
                else get_string(lang, "admin.modrole.get_stale")
            )
        else:
            msg = get_string(lang, "admin.modrole.get_none")
        await interaction.response.send_message(msg, ephemeral=True)

    @modrole.command(name="set")
    async def _modrole_set(self, interaction: Interaction, role: Role):
        """Set the bot-moderator role for this server."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is None:
                entry = BotModeratorRole(GuildId=interaction.guild.id)
                session.add(entry)
            entry.RoleId = role.id
        # Update cache before await so any permission check in the send window sees the new role
        self.bot.guild_cache.set_modrole(interaction.guild.id, role.id)
        lang = self._lang(interaction.guild_id)
        await interaction.response.send_message(
            get_string(lang, "admin.modrole.set_success", role=role.name), ephemeral=True
        )
        self.bot.dispatch("modrole_changed", interaction.guild.id, role.id)

    @modrole.command(name="delete")
    async def _modrole_del(self, interaction: Interaction):
        """Remove the bot-moderator role configuration."""
        with self.bot.session_scope() as session:
            BotModeratorRole.delete(interaction.guild.id, session)
        # Update cache before await so any permission check in the send window sees the cleared role
        self.bot.guild_cache.set_modrole(interaction.guild.id, None)
        lang = self._lang(interaction.guild_id)
        await interaction.response.send_message(get_string(lang, "admin.modrole.delete_success"), ephemeral=True)
        self.bot.dispatch("modrole_changed", interaction.guild.id, None)

    @language.command(name="set")
    @app_commands.describe(language="Language code to set for this server")
    async def _language_set(self, interaction: Interaction, language: str):
        """Set the server's language preference for bot responses."""
        language = language.lower()
        if language not in available_languages():
            msg = self.bot.get_localized_string(
                interaction.guild.id,
                "admin.language.invalid",
                language=language,
                available=", ".join(sorted(available_languages())),
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        with self.bot.session_scope() as session:
            config = GuildLanguageConfig.get(interaction.guild.id, session)
            if config is None:
                config = GuildLanguageConfig(GuildId=interaction.guild.id)
                session.add(config)
            config.Language = language

        # Update cache immediately so confirmation reply uses the new language
        self.bot.guild_cache.set_guild_language(interaction.guild.id, language)
        msg = self.bot.get_localized_string(interaction.guild.id, "admin.language.set_success", language=language)
        await interaction.response.send_message(msg, ephemeral=True)
        self.bot.dispatch("guild_language_changed", interaction.guild.id, language)

    @language.command(name="get")
    async def _language_get(self, interaction: Interaction):
        """Show the current language preference for this server."""
        with self.bot.session_scope() as session:
            config = GuildLanguageConfig.get(interaction.guild.id, session)
        if config is not None:
            msg = self.bot.get_localized_string(
                interaction.guild.id,
                "admin.language.get_current",
                language=config.Language,
            )
        else:
            msg = self.bot.get_localized_string(interaction.guild.id, "admin.language.get_default")
        await interaction.response.send_message(msg, ephemeral=True)

    async def _language_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for available languages."""
        return [
            app_commands.Choice(name=lang, value=lang)
            for lang in sorted(available_languages())
            if current.lower() in lang.lower()
        ][:25]

    _language_set = app_commands.autocomplete(language=_language_autocomplete)(_language_set)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(ServerAdmin(bot))
