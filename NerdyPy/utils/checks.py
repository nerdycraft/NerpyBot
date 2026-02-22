# -*- coding: utf-8 -*-

from typing import cast

from bot import NerpyBot
from discord import Interaction, Role, app_commands
from discord.ext.commands import Context
from models.admin import BotModeratorRole
from utils.errors import NerpyPermissionError, SilentCheckFailure
from utils.strings import get_localized_string, get_string


def _localized(interaction: Interaction, key: str, **kwargs) -> str:
    """Look up a guild-localized string from the interaction context."""
    bot = cast("NerpyBot", interaction.client)
    if interaction.guild_id is None:
        return get_string("en", key, **kwargs)
    with bot.session_scope() as session:
        return get_localized_string(interaction.guild_id, key, session, **kwargs)


def require_operator(ctx_or_interaction: Context | Interaction) -> None:
    """Raise if the command invoker is not a bot operator.

    Accepts both prefix-command Context and slash-command Interaction.
    Raises NerpyPermissionError for prefix commands, CheckFailure for slash commands.
    """
    if isinstance(ctx_or_interaction, Context):
        if ctx_or_interaction.author.id not in ctx_or_interaction.bot.ops:
            raise NerpyPermissionError("This command is restricted to bot operators.")
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


async def reject(interaction: Interaction, msg: str):
    """Send an ephemeral rejection message and raise SilentCheckFailure."""
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)
    raise SilentCheckFailure(msg)


async def is_bot_moderator(interaction: Interaction) -> bool:
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
        await reject(interaction, _localized(interaction, "checks.voice.not_connected"))
        return False
    channel = interaction.user.voice.channel
    bot_perms = channel.permissions_for(interaction.guild.me)
    if not bot_perms.connect:
        await reject(interaction, _localized(interaction, "checks.voice.no_connect_permission"))
        return False
    if not bot_perms.speak:
        await reject(interaction, _localized(interaction, "checks.voice.no_speak_permission"))
        return False
    return True


async def can_stop_playback(interaction: Interaction):
    """Any user in the same voice channel as the bot, or a bot-moderator from anywhere."""
    bot_voice = interaction.guild.voice_client
    if bot_voice is None:
        await reject(interaction, _localized(interaction, "checks.voice.nothing_playing"))
        return False

    if await is_bot_moderator(interaction):
        return True

    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await reject(interaction, _localized(interaction, "checks.voice.user_not_in_voice"))
        return False

    if interaction.user.voice.channel != bot_voice.channel:
        await reject(interaction, _localized(interaction, "checks.voice.user_in_different_channel"))
        return False

    return True


async def can_leave_voice(interaction: Interaction):
    """Bot-moderator only."""
    if await is_bot_moderator(interaction):
        return True

    await reject(interaction, _localized(interaction, "checks.voice.leave_moderator_only"))
    return False


async def is_role_assignable(interaction: Interaction, role: Role, *, action: str = "assigned to") -> bool:
    """Return False (with ephemeral message) if the role is integration-managed."""
    if role.managed:
        key = "checks.role.integration_remove" if "remov" in action else "checks.role.integration_assign"
        msg = _localized(interaction, key, role=role.name)
        await interaction.response.send_message(msg, ephemeral=True)
        return False
    return True


async def is_role_below_bot(interaction: Interaction, role: Role) -> bool:
    """Return False (with ephemeral message) if the role is at or above the bot's highest role."""
    if role >= interaction.guild.me.top_role:
        msg = _localized(interaction, "checks.role.above_bot_role", role=role.name)
        await interaction.response.send_message(msg, ephemeral=True)
        return False
    return True
