""" Random Memes """
import aiohttp
import discord
import utils.format as fmt
from random import randint, choice
from utils.errors import NerpyException
from discord.ext.commands import GroupCog, hybrid_command, bot_has_permissions


@bot_has_permissions(send_messages=True)
class Random(GroupCog):
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

    @hybrid_command()
    async def lenny(self, ctx):
        """Displays a random lenny face."""
        await ctx.send(choice(self.lennys))

    @hybrid_command()
    async def chuck(self, ctx):
        """random chuck norris joke."""
        url = "http://api.icndb.com/jokes/random"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                await ctx.send(data.get("value", dict()).get("joke"))

    @hybrid_command()
    async def yomomma(self, ctx):
        """random yomomma joke"""
        url = "http://api.yomomma.info"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                await ctx.send(data.get("joke"))

    @hybrid_command()
    async def quote(self, ctx):
        """random quote"""
        url = "http://quotesondesign.com/wp-json/posts?filter[orderby]=rand"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                await ctx.send(f'{fmt.strip_tags(data[0].get("content"))} - {data[0].get("title")}')

    @hybrid_command()
    async def trump(self, ctx):
        """random trump tweet"""
        url = "https://api.whatdoestrumpthink.com/api/v1/quotes/random"
        trump_pic = "https://www.tolonews.com/sites/default/files/styles/principal_article_image/public/Trumpppp.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                emb = discord.Embed(title="Donald Trump")
                emb.description = data.get("message")
                emb.set_thumbnail(url=trump_pic)
        await ctx.send(embed=emb)

    @hybrid_command()
    async def xkcd(self, ctx):
        """random xkcd comic"""
        url = "https://xkcd.com/"
        urlend = "info.0.json"

        async with aiohttp.ClientSession() as session:
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
        await ctx.send(data.get("img"))

    @hybrid_command()
    async def bunny(self, ctx):
        """Why do I have a random bunny gif command???"""
        url = "https://api.bunnies.io/v2/loop/random/?media=gif"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
        await ctx.send(data.get("media").get("gif"))

    @hybrid_command()
    async def cat(self, ctx):
        """random cat command are legit"""
        url = "http://aws.random.cat/meow"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
        await ctx.send(data.get("file"))

    @hybrid_command()
    async def catfact(self, ctx):
        """random cat command are legit"""
        url = "https://catfact.ninja/fact"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
        await ctx.send(data.get("fact"))


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Random(bot))
