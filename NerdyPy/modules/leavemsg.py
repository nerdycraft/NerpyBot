# -*- coding: utf-8 -*-
"""Module for server leave message announcements"""

from discord import Member, TextChannel
from discord.app_commands import checks
from discord.ext.commands import Cog, Context, hybrid_group
from models.leavemsg import LeaveMessage

from utils.errors import NerpyException
from utils.helpers import empty_subcommand, send_hidden_message


DEFAULT_LEAVE_MESSAGE = "{member} left the server :("


class LeaveMsg(Cog):
    """Cog for managing server leave messages"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

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
                f"Leave channel {leave_config.ChannelId} not found or not a text channel for guild {member.guild.id}"
            )
            return

        message = leave_config.Message or DEFAULT_LEAVE_MESSAGE
        formatted_message = message.format(member=member.display_name)

        try:
            await channel.send(formatted_message)
        except Exception as ex:
            self.bot.log.error(f"Failed to send leave message in guild {member.guild.id}: {ex}")

    @hybrid_group()
    @checks.has_permissions(administrator=True)
    async def leavemsg(self, ctx: Context) -> None:
        """Manage leave messages for the server [administrator]"""
        await empty_subcommand(ctx)

    @leavemsg.command(name="enable")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_enable(self, ctx: Context, channel: TextChannel) -> None:
        """Enable leave messages in the specified channel. [administrator]

        Parameters
        ----------
        ctx
        channel: TextChannel
            The channel where leave messages will be sent.
        """
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(ctx.guild.id, session)
            if leave_config is None:
                leave_config = LeaveMessage(
                    GuildId=ctx.guild.id,
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

        await send_hidden_message(ctx, f"Leave messages enabled in {channel.mention}.")

    @leavemsg.command(name="disable")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_disable(self, ctx: Context) -> None:
        """Disable leave messages for this server. [administrator]"""
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(ctx.guild.id, session)
            if leave_config is None:
                raise NerpyException("Leave messages are not configured for this server.")
            leave_config.Enabled = False

        await send_hidden_message(ctx, "Leave messages disabled.")

    @leavemsg.command(name="message")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_message(self, ctx: Context, *, message: str) -> None:
        """Set a custom leave message. Use {member} as placeholder. [administrator]

        Parameters
        ----------
        ctx
        message: str
            The message template. Use {member} for the member's display name.
        """
        if "{member}" not in message:
            raise NerpyException("Message must contain {member} placeholder for the member name.")

        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(ctx.guild.id, session)
            if leave_config is None:
                raise NerpyException("Please enable leave messages first using `/leavemsg enable #channel`.")
            leave_config.Message = message

        await send_hidden_message(ctx, f"Leave message updated to: {message}")

    @leavemsg.command(name="status")
    @checks.has_permissions(administrator=True)
    async def _leavemsg_status(self, ctx: Context) -> None:
        """Show current leave message configuration. [administrator]"""
        with self.bot.session_scope() as session:
            leave_config = LeaveMessage.get(ctx.guild.id, session)

        if leave_config is None or not leave_config.Enabled:
            await send_hidden_message(ctx, "Leave messages are not enabled for this server.")
            return

        channel = ctx.guild.get_channel(leave_config.ChannelId)
        channel_mention = channel.mention if channel else "Unknown channel"
        message = leave_config.Message or DEFAULT_LEAVE_MESSAGE

        await send_hidden_message(
            ctx, f"**Leave messages:** Enabled\n**Channel:** {channel_mention}\n**Message:** {message}"
        )


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(LeaveMsg(bot))
