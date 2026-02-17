# -*- coding: utf-8 -*-
"""Random Memes"""

from random import choice, randint

from aiohttp import ClientSession
from discord import Embed, Interaction, app_commands
from discord.ext.commands import Cog

import utils.format as fmt
from utils.errors import NerpyException


@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.guild_only()
class Random(Cog):
    """who is that random"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.lennys = [
            "( ͡° ͜ʖ ͡°)",
            "( ͠° ͟ʖ ͡°)",
            "ᕦ( ͡° ͜ʖ ͡°)ᕤ",
            "( ͡~ ͜ʖ ͡°)",
            "( ͡o ͜ʖ ͡o)",
            "͡(° ͜ʖ ͡ -)",
            "( ͡͡ ° ͜ ʖ ͡ °)﻿",
            "(ง ͠° ͟ل͜ ͡°)ง",
            "ヽ༼ຈل͜ຈ༽ﾉ",
        ]

    @app_commands.command()
    @app_commands.guild_only()
    async def lenny(self, interaction: Interaction) -> None:
        """Displays a random lenny face."""
        await interaction.response.send_message(choice(self.lennys))

    @app_commands.command()
    @app_commands.guild_only()
    async def quote(self, interaction: Interaction) -> None:
        """random quote"""
        url = "https://quotesondesign.com/wp-json/wp/v2/posts/?orderby=rand"

        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                await interaction.response.send_message(
                    f"{fmt.strip_tags(data[0].get('content').get('rendered'))} - {data[0].get('title').get('rendered')}"
                )

    @app_commands.command()
    @app_commands.guild_only()
    async def trump(self, interaction: Interaction) -> None:
        """random trump tweet"""
        url = "https://api.whatdoestrumpthink.com/api/v1/quotes/random"
        trump_pic = "https://www.tolonews.com/sites/default/files/styles/principal_article_image/public/Trumpppp.jpg"

        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                emb = Embed(title="Donald Trump")
                emb.description = data.get("message")
                emb.set_thumbnail(url=trump_pic)
        await interaction.response.send_message(embed=emb)

    @app_commands.command()
    @app_commands.guild_only()
    async def xkcd(self, interaction: Interaction) -> None:
        """random xkcd comic"""
        url = "https://xkcd.com/"
        urlend = "info.0.json"

        async with ClientSession() as session:
            async with session.get(url + urlend) as xkcd_id:
                if xkcd_id.status != 200:
                    err = f"The api-webserver responded with a code: {xkcd_id.status} - {xkcd_id.reason}"
                    raise NerpyException(err)
                result = await xkcd_id.json()

            async with session.get(f"{url}{randint(0, result['num'])}/{urlend}") as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
        await interaction.response.send_message(data.get("img"))

    @app_commands.command()
    @app_commands.guild_only()
    async def bunny(self, interaction: Interaction) -> None:
        """Why do I have a random bunny gif command???"""
        url = "https://api.bunnies.io/v2/loop/random/?media=gif"

        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
        await interaction.response.send_message(data.get("media").get("gif"))


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Random(bot))
