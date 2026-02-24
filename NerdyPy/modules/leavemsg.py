# -*- coding: utf-8 -*-
"""Module for server leave message announcements"""

from typing import Optional

import discord
from discord import Interaction, Member, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import Cog, GroupCog
from models.leavemsg import LeaveMessage
from utils.cog import NerpyBotCog

from utils.errors import NerpyValidationError
from utils.helpers import fetch_message_content
from utils.permissions import validate_channel_permissions
from utils.strings import get_guild_language, get_string


DEFAULT_LEAVE_MESSAGE = "{member} left the server :("


@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
class LeaveMsg(NerpyBotCog, GroupCog, group_name="leavemsg"):
    """Cog for managing server leave messages"""

    @Cog.listener()
    async def on_member_remove(self, member: Member) -> None:
        """Sends a farewell message when a member leaves the server"""
        if member.bot:
            return

        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(member.guild.id, session)

        if leave_config is None or not leave_config.Enabled:
            return

        channel = member.guild.get_channel(leave_config.ChannelId)
        if channel is None or not isinstance(channel, TextChannel):
            self.bot.log.warning(
                f"[{member.guild.name} ({member.guild.id})]: "
                f"leave channel {leave_config.ChannelId} not found or not a text channel"
            )
            return

        self.bot.log.debug(f"[{member.guild.name} ({member.guild.id})]: sending leave message for {member}")

        message = leave_config.Message or DEFAULT_LEAVE_MESSAGE
        member_str = f"**{member.display_name}** ({member.name})"
        formatted_message = message.format(member=member_str) if "{member}" in message else f"{message} — {member_str}"

        try:
            await channel.send(formatted_message)
        except Exception as ex:
            self.bot.log.error(
                f"[{member.guild.name} ({member.guild.id})]: failed to send leave message for {member}: {ex}"
            )

    @app_commands.command(name="enable")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_enable(self, interaction: Interaction, channel: TextChannel) -> None:
        """Enable leave messages in the specified channel. [administrator]

        Parameters
        ----------
        interaction
        channel: TextChannel
            The channel where leave messages will be sent.
        """
        validate_channel_permissions(channel, interaction.guild, "view_channel", "send_messages")

        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            leave_config = LeaveMessage.get(interaction.guild.id, session)
            if leave_config is None:
                leave_config = LeaveMessage(
                    GuildId=interaction.guild.id,
                    ChannelId=channel.id,
                    Message=DEFAULT_LEAVE_MESSAGE,
                    Enabled=True,
                )
                session.add(leave_config)
            else:
                leave_config.ChannelId = channel.id
                leave_config.Enabled = True
                if leave_config.Message is None:
                    leave_config.Message = DEFAULT_LEAVE_MESSAGE

        await interaction.response.send_message(
            get_string(lang, "leavemsg.enable.success", channel=channel.mention), ephemeral=True
        )

    @app_commands.command(name="disable")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_disable(self, interaction: Interaction) -> None:
        """Disable leave messages for this server. [administrator]"""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            leave_config = LeaveMessage.get(interaction.guild.id, session)
            if leave_config is None:
                raise NerpyValidationError(get_string(lang, "leavemsg.disable.not_configured"))
            leave_config.Enabled = False

        await interaction.response.send_message(get_string(lang, "leavemsg.disable.success"), ephemeral=True)

    async def save_leave_message(self, interaction: Interaction, message: str, lang: str) -> None:
        """Validate and persist a leave message, then confirm to the user."""
        if "{member}" not in message:
            raise NerpyValidationError(get_string(lang, "leavemsg.message.missing_placeholder"))
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(interaction.guild.id, session)
            if leave_config is None:
                raise NerpyValidationError(get_string(lang, "leavemsg.message.not_enabled"))
            leave_config.Message = message

        if not interaction.response.is_done():
            await interaction.response.send_message(
                get_string(lang, "leavemsg.message.success", message=message), ephemeral=True
            )
        else:
            await interaction.followup.send(
                get_string(lang, "leavemsg.message.success", message=message), ephemeral=True
            )

    @app_commands.command(name="message")
    @checks.has_permissions(administrator=True)
    @app_commands.describe(
        message="The message template (opens a modal if omitted). Use {member} for the member name.",
        message_source="Message ID or link whose text becomes the leave message (message is deleted)",
    )
    @app_commands.rename(message_source="message-source")
    async def _leavemsg_message(
        self,
        interaction: Interaction,
        message: Optional[str] = None,
        message_source: Optional[str] = None,
    ) -> None:
        """Set a custom leave message. Use {member} as placeholder. [administrator]"""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)

        # Path 1: fetch from an existing Discord message
        if message_source:
            content, error = await fetch_message_content(
                self.bot, message_source, None, interaction, lang, key_prefix="leavemsg.fetch_message"
            )
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            message = content

        # Path 2: open a modal when no text was provided
        if message is None:
            modal = _LeaveMessageModal(self.bot, lang)
            await interaction.response.send_modal(modal)
            return

        # Path 3: inline text provided
        await self.save_leave_message(interaction, message, lang)

    @app_commands.command(name="status")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_status(self, interaction: Interaction) -> None:
        """Show current leave message configuration. [administrator]"""
        with self.bot.session_scope() as session:
            lang = get_guild_language(interaction.guild_id, session)
            leave_config = LeaveMessage.get(interaction.guild.id, session)

        if leave_config is None or not leave_config.Enabled:
            await interaction.response.send_message(get_string(lang, "leavemsg.status.not_enabled"), ephemeral=True)
            return

        channel = interaction.guild.get_channel(leave_config.ChannelId)
        channel_mention = channel.mention if channel else "Unknown channel"
        message = leave_config.Message or DEFAULT_LEAVE_MESSAGE

        await interaction.response.send_message(
            get_string(lang, "leavemsg.status.enabled", channel=channel_mention, message=message), ephemeral=True
        )


class _LeaveMessageModal(discord.ui.Modal):
    """Paragraph modal for entering a leave message template."""

    message_input = discord.ui.TextInput(
        label="Leave Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    def __init__(self, bot, lang: str):
        super().__init__(title=get_string(lang, "leavemsg.message.modal_title"))
        self.bot = bot
        self.lang = lang
        self.message_input.placeholder = get_string(lang, "leavemsg.message.modal_placeholder")

    async def on_submit(self, interaction: Interaction):
        cog = self.bot.get_cog("LeaveMsg")
        await cog.save_leave_message(interaction, self.message_input.value.strip(), self.lang)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(LeaveMsg(bot))
