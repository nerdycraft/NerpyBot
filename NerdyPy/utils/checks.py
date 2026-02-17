# -*- coding: utf-8 -*-

from discord import Interaction

from models.botmod import BotModeratorRole
from utils.errors import SilentCheckFailure


async def is_admin_or_operator(interaction: Interaction) -> bool:
    """Return True if the user is a guild administrator or a bot operator."""
    if interaction.user.id in interaction.client.ops:
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
    perms = interaction.user.guild_permissions
    if (
        perms.mute_members
        or perms.manage_channels
        or perms.administrator
        or interaction.user.id in interaction.client.ops
    ):
        return True

    with interaction.client.session_scope() as session:
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


async def is_in_same_voice_channel_as_bot(interaction: Interaction):
    bot_voice = interaction.guild.voice_client

    if bot_voice is None:
        return True

    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await _reject(interaction, "You need to be in a voice channel to use this command.")
        return False

    if interaction.user.voice.channel == bot_voice.channel:
        return True

    if await _is_bot_moderator(interaction):
        return True

    await _reject(interaction, "You need to be in the same voice channel as the bot to use this command.")
    return False


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
