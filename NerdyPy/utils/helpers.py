# -*- coding: utf-8 -*-

import logging
from traceback import format_exception

from discord.ext.commands import Context
from googleapiclient.discovery import build
from utils.errors import NerpyException

log = logging.getLogger("nerpybot")


def parse_id(value: int | str) -> int:
    """Coerce a config value to an integer Discord ID.

    Accepts both int and str to guard against YAML formatter corruption
    of large numeric values.
    """
    return int(value)


async def send_hidden_message(ctx: Context, msg: str = None, **kwargs):
    """Send a message only visible to the invoking user.

    Slash commands use ephemeral replies; prefix commands fall back to DMs
    since ephemeral is silently ignored without an interaction.
    """
    if ctx.interaction is not None:
        return await ctx.send(msg, ephemeral=True, **kwargs)
    return await ctx.author.send(msg, **kwargs)


def error_context(ctx: Context) -> str:
    """Build a log prefix with command, user, and guild info."""
    cmd = ctx.command.qualified_name if ctx.command else "unknown"
    user = f"{ctx.author} ({ctx.author.id})"
    guild = f"{ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
    return f"[{guild}] {user} -> /{cmd}"


async def empty_subcommand(ctx: Context):
    if ctx.invoked_subcommand is None:
        args = str(ctx.message.clean_content).split(" ")
        if len(args) > 2:
            raise NerpyException("Command not found!")
        elif len(args) <= 1:
            await ctx.send_help(ctx.command)
    return


async def check_api_response(response, service_name: str = "API") -> None:
    """Validate API response status and raise NerpyException on error."""
    if response.status != 200:
        raise NerpyException(f"The {service_name} responded with code: {response.status} - {response.reason}")


async def notify_error(bot, context: str, error: Exception) -> None:
    """DM configured error recipients with details about an unhandled error.

    Fails silently if recipients have DMs disabled or IDs are invalid.
    """
    recipients = bot.config.get("notifications", {}).get("error_recipients", [])
    if not recipients:
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


def youtube(yt_key, return_type, query):
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
