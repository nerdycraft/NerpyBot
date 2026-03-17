# -*- coding: utf-8 -*-

from discord import Interaction, Role, app_commands
from discord.ext.commands import Cog

from models.admin import BotModeratorRole, GuildLanguageConfig
from utils.checks import is_admin_or_operator
from utils.cog import NerpyBotCog
from utils.strings import available_languages, get_guild_language, get_localized_string, get_string


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
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is not None:
                role = interaction.guild.get_role(entry.RoleId)
                if role is not None:
                    await interaction.response.send_message(
                        get_string(lang, "admin.modrole.get_current", role=role.name), ephemeral=True
                    )
                else:
                    await interaction.response.send_message(get_string(lang, "admin.modrole.get_stale"), ephemeral=True)
            else:
                await interaction.response.send_message(get_string(lang, "admin.modrole.get_none"), ephemeral=True)

    @modrole.command(name="set")
    async def _modrole_set(self, interaction: Interaction, role: Role):
        """Set the bot-moderator role for this server."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is None:
                entry = BotModeratorRole(GuildId=interaction.guild.id)
                session.add(entry)
            entry.RoleId = role.id
        await interaction.response.send_message(
            get_string(lang, "admin.modrole.set_success", role=role.name), ephemeral=True
        )

    @modrole.command(name="delete")
    async def _modrole_del(self, interaction: Interaction):
        """Remove the bot-moderator role configuration."""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            BotModeratorRole.delete(interaction.guild.id, session)
        await interaction.response.send_message(get_string(lang, "admin.modrole.delete_success"), ephemeral=True)

    @language.command(name="set")
    @app_commands.describe(language="Language code to set for this server")
    async def _language_set(self, interaction: Interaction, language: str):
        """Set the server's language preference for bot responses."""
        language = language.lower()
        if language not in available_languages():
            with self.bot.session_scope() as session:
                msg = get_localized_string(
                    interaction.guild.id,
                    "admin.language.invalid",
                    session,
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

        # Read back with new language so confirmation is in the newly set language
        with self.bot.session_scope() as session:
            msg = get_localized_string(
                interaction.guild.id,
                "admin.language.set_success",
                session,
                language=language,
            )
        await interaction.response.send_message(msg, ephemeral=True)
        self.bot.dispatch("guild_language_changed", interaction.guild.id, language)

    @language.command(name="get")
    async def _language_get(self, interaction: Interaction):
        """Show the current language preference for this server."""
        with self.bot.session_scope() as session:
            config = GuildLanguageConfig.get(interaction.guild.id, session)
            if config is not None:
                msg = get_localized_string(
                    interaction.guild.id,
                    "admin.language.get_current",
                    session,
                    language=config.Language,
                )
            else:
                msg = get_localized_string(interaction.guild.id, "admin.language.get_default", session)
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
