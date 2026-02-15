# -*- coding: utf-8 -*-

from models.botmod import BotModeratorRole
from utils.errors import SilentCheckFailure


async def is_admin_or_operator(ctx) -> bool:
    """Return True if the user is a guild administrator or a bot operator."""
    if ctx.author.id in ctx.bot.ops:
        return True
    if ctx.guild and ctx.author.guild_permissions.administrator:
        return True
    return False


async def _reject(ctx, msg: str):
    """Send a check rejection message and raise SilentCheckFailure.

    Silently does nothing when called during a help-command probe.
    """
    if ctx.invoked_with == "help":
        raise SilentCheckFailure(msg)
    if ctx.interaction is not None:
        await ctx.send(msg, ephemeral=True)
    else:
        await ctx.author.send(msg)
    raise SilentCheckFailure(msg)


async def _is_bot_moderator(ctx) -> bool:
    """Check if the user has bot-moderator privileges (mod perms, bot operator, or configured role)."""
    perms = ctx.author.guild_permissions
    if perms.mute_members or perms.manage_channels or perms.administrator or ctx.author.id in ctx.bot.ops:
        return True

    with ctx.bot.session_scope() as session:
        entry = BotModeratorRole.get(ctx.guild.id, session)
        if entry is not None:
            return any(r.id == entry.RoleId for r in ctx.author.roles)

    return False


async def is_connected_to_voice(ctx):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await _reject(ctx, "I don't know where you are. Please connect to a voice channel.")
        return False
    channel = ctx.author.voice.channel
    bot_perms = channel.permissions_for(ctx.guild.me)
    if not bot_perms.connect:
        await _reject(ctx, "I'm not allowed to join you in your current channel.")
        return False
    if not bot_perms.speak:
        await _reject(ctx, "I don't have permission to speak in your voice channel.")
        return False
    return True


async def is_in_same_voice_channel_as_bot(ctx):
    bot_voice = ctx.guild.voice_client

    # Bot not in voice — allow; the command will fail gracefully on its own
    if bot_voice is None:
        return True

    # User not in any voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await _reject(ctx, "You need to be in a voice channel to use this command.")
        return False

    # Same channel — allow
    if ctx.author.voice.channel == bot_voice.channel:
        return True

    # Mod / operator override
    if await _is_bot_moderator(ctx):
        return True

    await _reject(ctx, "You need to be in the same voice channel as the bot to use this command.")
    return False


async def can_stop_playback(ctx):
    """Any user in the same voice channel as the bot, or a bot-moderator from anywhere."""
    bot_voice = ctx.guild.voice_client
    if bot_voice is None:
        await _reject(ctx, "Nothing is playing right now.")
        return False

    if await _is_bot_moderator(ctx):
        return True

    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await _reject(ctx, "You need to be in a voice channel to use this command.")
        return False

    if ctx.author.voice.channel != bot_voice.channel:
        await _reject(ctx, "You need to be in the same voice channel as the bot to use this command.")
        return False

    return True


async def can_leave_voice(ctx):
    """Bot-moderator only."""
    if await _is_bot_moderator(ctx):
        return True

    await _reject(ctx, "Only moderators can make the bot leave the voice channel.")
    return False
