# -*- coding: utf-8 -*-

from typing import cast

from discord import Interaction, Role, app_commands
from discord.ext.commands import Context

from bot import NerpyBot
from models.botmod import BotModeratorRole
from utils.errors import NerpyException, SilentCheckFailure


def require_operator(ctx_or_interaction: Context | Interaction) -> None:
    """Raise if the command invoker is not a bot operator.

    Accepts both prefix-command Context and slash-command Interaction.
    Raises NerpyException for prefix commands, CheckFailure for slash commands.
    """
    if isinstance(ctx_or_interaction, Context):
        if ctx_or_interaction.author.id not in ctx_or_interaction.bot.ops:
            raise NerpyException("This command is restricted to bot operators.")
    else:
        bot = cast("NerpyBot", ctx_or_interaction.client)
        if ctx_or_interaction.user.id not in bot.ops:
            raise app_commands.CheckFailure("This command is restricted to bot operators.")


async def is_admin_or_operator(interaction: Interaction) -> bool:
    """Return True if the user is a guild administrator or a bot operator."""
    bot = cast(NerpyBot, interaction.client)
    if interaction.user.id in bot.ops:
        return True
    if interaction.guild and interaction.user.guild_permissions.administrator:
        return True
    return False


async def _reject(interaction: Interaction, msg: str):
    """Send an ephemeral rejection message and raise SilentCheckFailure."""
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)
    raise SilentCheckFailure(msg)


async def _is_bot_moderator(interaction: Interaction) -> bool:
    """Check if the user has bot-moderator privileges."""
    bot = cast(NerpyBot, interaction.client)
    perms = interaction.user.guild_permissions
    if perms.mute_members or perms.manage_channels or perms.administrator or interaction.user.id in bot.ops:
        return True

    with bot.session_scope() as session:
        entry = BotModeratorRole.get(interaction.guild.id, session)
        if entry is not None:
            return any(r.id == entry.RoleId for r in interaction.user.roles)

    return False


async def is_connected_to_voice(interaction: Interaction):
    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await _reject(interaction, "I don't know where you are. Please connect to a voice channel.")
        return False
    channel = interaction.user.voice.channel
    bot_perms = channel.permissions_for(interaction.guild.me)
    if not bot_perms.connect:
        await _reject(interaction, "I'm not allowed to join you in your current channel.")
        return False
    if not bot_perms.speak:
        await _reject(interaction, "I don't have permission to speak in your voice channel.")
        return False
    return True


async def can_stop_playback(interaction: Interaction):
    """Any user in the same voice channel as the bot, or a bot-moderator from anywhere."""
    bot_voice = interaction.guild.voice_client
    if bot_voice is None:
        await _reject(interaction, "Nothing is playing right now.")
        return False

    if await _is_bot_moderator(interaction):
        return True

    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await _reject(interaction, "You need to be in a voice channel to use this command.")
        return False

    if interaction.user.voice.channel != bot_voice.channel:
        await _reject(interaction, "You need to be in the same voice channel as the bot to use this command.")
        return False

    return True


async def can_leave_voice(interaction: Interaction):
    """Bot-moderator only."""
    if await _is_bot_moderator(interaction):
        return True

    await _reject(interaction, "Only moderators can make the bot leave the voice channel.")
    return False


async def is_role_assignable(interaction: Interaction, role: Role, *, action: str = "assigned to") -> bool:
    """Return False (with ephemeral message) if the role is integration-managed."""
    if role.managed:
        await interaction.response.send_message(
            f"**{role.name}** is an integration role and cannot be {action} members.", ephemeral=True
        )
        return False
    return True


async def is_role_below_bot(interaction: Interaction, role: Role) -> bool:
    """Return False (with ephemeral message) if the role is at or above the bot's highest role."""
    if role >= interaction.guild.me.top_role:
        await interaction.response.send_message(
            f"I cannot manage **{role.name}** — it is at or above my highest role.", ephemeral=True
        )
        return False
    return True
