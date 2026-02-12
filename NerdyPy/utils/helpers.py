# -*- coding: utf-8 -*-

from discord.ext.commands import Context
from googleapiclient.discovery import build
from utils.errors import NerpyException


def send_hidden_message(ctx: Context, msg: str):
    return ctx.send(msg, ephemeral=True)


async def empty_subcommand(ctx: Context):
    if ctx.invoked_subcommand is None:
        args = str(ctx.message.clean_content).split(" ")
        if len(args) > 2:
            raise NerpyException("Command not found!")
        elif len(args) <= 1:
            await ctx.send_help(ctx.command)
    return


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
