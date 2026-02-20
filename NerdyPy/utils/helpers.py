# -*- coding: utf-8 -*-

import logging
from traceback import format_exception

from discord import Color, Embed, Interaction
from discord.ext.commands import Context
from googleapiclient.discovery import build

log = logging.getLogger("nerpybot")


def parse_id(value: int | str) -> int:
    """Coerce a config value to an integer Discord ID.

    Accepts both int and str to guard against YAML formatter corruption
    of large numeric values.
    """
    return int(value)


async def send_hidden_message(interaction: Interaction, msg: str | None = None, **kwargs) -> None:
    """Send an ephemeral message via slash command interaction."""
    if not interaction.response.is_done():
        return await interaction.response.send_message(msg, ephemeral=True, **kwargs)
    return await interaction.followup.send(msg, ephemeral=True, **kwargs)


DISCORD_MESSAGE_LIMIT = 2000
# Embed description supports up to 4096 characters
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096


async def send_paginated(
    interaction: Interaction,
    text: str,
    *,
    title: str = None,
    color: Color | int = None,
    ephemeral: bool = False,
    delims: list[str] | None = None,
    page_length: int | None = None,
) -> None:
    """Paginate text into Discord embed messages.

    Uses ``response.send_message`` for the first page and ``followup.send``
    for subsequent pages.  Adds a page footer when content spans multiple
    pages.
    """
    from utils.format import pagify

    if delims is None:
        delims = ["\n"]
    if page_length is None:
        page_length = DISCORD_EMBED_DESCRIPTION_LIMIT - 50
    if isinstance(color, int):
        color = Color(color)
    if color is None:
        color = Color(0x5865F2)

    pages = list(pagify(text, delims=delims, page_length=page_length))
    total = len(pages)

    for i, page in enumerate(pages):
        embed = Embed(description=page, color=color)
        if title:
            embed.title = title
        if total > 1:
            embed.set_footer(text=f"Page {i + 1}/{total}")

        if i == 0:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


def error_context(source: Context | Interaction) -> str:
    """Build a log prefix with command, user, and guild info.

    Accepts both Interaction (slash) and Context (prefix fallback).
    """
    if hasattr(source, "interaction"):
        # Context (prefix commands) — has an .interaction attribute
        cmd = source.command.qualified_name if source.command else "unknown"
        user = f"{source.author} ({source.author.id})"
        guild = f"{source.guild.name} ({source.guild.id})" if source.guild else "DM"
    else:
        # Interaction (slash commands)
        cmd = source.command.qualified_name if source.command else "unknown"
        user = f"{source.user} ({source.user.id})"
        guild = f"{source.guild.name} ({source.guild.id})" if source.guild else "DM"
    return f"[{guild}] {user} -> /{cmd}"


async def notify_error(bot, context: str, error: Exception) -> None:
    """DM configured error recipients with details about an unhandled error.

    Fails silently if recipients have DMs disabled or IDs are invalid.
    """
    recipients = bot.config.get("notifications", {}).get("error_recipients", [])
    if not recipients:
        return

    if not bot.error_throttle.should_notify(context, error):
        log.debug(f"Error notification throttled: {type(error).__name__} in {context}")
        return

    tb = "".join(format_exception(type(error), error, error.__traceback__))
    # Truncate traceback to fit Discord's 2000-char message limit
    max_tb = 1400
    if len(tb) > max_tb:
        tb = tb[:max_tb] + "\n... (truncated)"

    msg = f"**Error:** `{type(error).__name__}: {error}`\n**Context:** {context}\n```\n{tb}\n```"

    for uid in recipients:
        try:
            user = await bot.fetch_user(parse_id(uid))
            await user.send(msg)
        except Exception as dm_err:
            log.debug(f"Could not DM error notification to {uid}: {dm_err}")


def youtube(yt_key: str, return_type: str, query: str) -> str | None:
    yt = build("youtube", "v3", developerKey=yt_key)
    search_response = yt.search().list(q=query, part="id,snippet", type="video", maxResults=1).execute()
    items = search_response.get("items", [])

    if len(items) > 0:
        if return_type == "url":
            ret = f"https://www.youtube.com/watch?v={items[0]['id']['videoId']}"
        else:
            ret = items[0]["id"]["videoId"]
    else:
        ret = None

    return ret
