# -*- coding: utf-8 -*-

from discord.ext.commands import Context
from googleapiclient.discovery import build
from utils.errors import NerpyException


async def send_hidden_message(ctx: Context, msg: str = None, **kwargs):
    """Send a message only visible to the invoking user.

    Slash commands use ephemeral replies; prefix commands fall back to DMs
    since ephemeral is silently ignored without an interaction.
    """
    if ctx.interaction is not None:
        return await ctx.send(msg, ephemeral=True, **kwargs)
    return await ctx.author.send(msg, **kwargs)


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
