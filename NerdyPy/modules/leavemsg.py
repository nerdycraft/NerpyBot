# -*- coding: utf-8 -*-
"""Module for server leave message announcements"""

from discord import Interaction, Member, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import Cog, GroupCog
from models.leavemsg import LeaveMessage
from utils.cog import NerpyBotCog

from utils.errors import NerpyException
from utils.permissions import validate_channel_permissions


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

        await interaction.response.send_message(f"Leave messages enabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="disable")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_disable(self, interaction: Interaction) -> None:
        """Disable leave messages for this server. [administrator]"""
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(interaction.guild.id, session)
            if leave_config is None:
                raise NerpyException("Leave messages are not configured for this server.")
            leave_config.Enabled = False

        await interaction.response.send_message("Leave messages disabled.", ephemeral=True)

    @app_commands.command(name="message")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_message(self, interaction: Interaction, message: str) -> None:
        """Set a custom leave message. Use {member} as placeholder. [administrator]

        Parameters
        ----------
        interaction
        message: str
            The message template. Use {member} for the member's display name.
        """
        if "{member}" not in message:
            raise NerpyException("Message must contain {member} placeholder for the member name.")

        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(interaction.guild.id, session)
            if leave_config is None:
                raise NerpyException("Please enable leave messages first using `/leavemsg enable #channel`.")
            leave_config.Message = message

        await interaction.response.send_message(f"Leave message updated to: {message}", ephemeral=True)

    @app_commands.command(name="status")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_status(self, interaction: Interaction) -> None:
        """Show current leave message configuration. [administrator]"""
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(interaction.guild.id, session)

        if leave_config is None or not leave_config.Enabled:
            await interaction.response.send_message("Leave messages are not enabled for this server.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(leave_config.ChannelId)
        channel_mention = channel.mention if channel else "Unknown channel"
        message = leave_config.Message or DEFAULT_LEAVE_MESSAGE

        await interaction.response.send_message(
            f"**Leave messages:** Enabled\n**Channel:** {channel_mention}\n**Message:** {message}", ephemeral=True
        )


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(LeaveMsg(bot))
