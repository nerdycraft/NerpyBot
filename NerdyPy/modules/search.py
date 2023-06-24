""" Search Modul """

# -- coding: utf-8 --
import aiohttp
import discord
import utils.format as fmt
from typing import Literal
from datetime import datetime
from utils.errors import NerpyException
from utils.helpers import youtube
from discord import app_commands
from discord.ext.commands import GroupCog, hybrid_command, bot_has_permissions


@bot_has_permissions(send_messages=True)
class Search(GroupCog):
    """search module"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]

    @hybrid_command()
    async def imgur(self, ctx, query: str):
        """may the meme be with you"""
        url = f"https://api.imgur.com/3/gallery/search/viral?q={query}"

        async with aiohttp.ClientSession(headers={"Authorization": f"Client-ID {self.config['imgur']}"}) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                if data.get("success") is not None and len(data.get("data")) > 0:
                    meme = data.get("data")[0].get("link")
                else:
                    meme = "R.I.P. memes"
                await ctx.send(meme)

    @hybrid_command()
    async def urban(self, ctx, query: str):
        """urban legend"""
        url = f"http://api.urbandictionary.com/v0/define?term={query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                emb = discord.Embed(title=f'"{query}" on Urban Dictionary:')
                if len(data.get("list")) > 0:
                    item = data["list"][0]
                    emb.description = item.get("definition")
                    emb.set_author(name=item.get("author"))
                    emb.url = item.get("permalink")
                else:
                    emb.description = "no results - R.I.P. memes"
                await ctx.send(embed=emb)

    @hybrid_command()
    async def lyrics(self, ctx, query: str):
        """genius lyrics"""
        url = f"http://api.genius.com/search?q={query}&access_token={self.config['genius']}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()
                emb = discord.Embed(title=f'"{query}" on genius.com:')
                if len(data.get("response", dict()).get("hits")) > 0:
                    item = data.get("response", dict()).get("hits")[0].get("result")
                    emb.description = item.get("full_title")
                    emb.set_thumbnail(url=item.get("header_image_thumbnail_url"))
                    emb.url = item.get("url")
                else:
                    emb.description = "R.I.P. memes"
                await ctx.send(embed=emb)

    @hybrid_command()
    async def youtube(self, ctx, query: str):
        """don't stick too long, you might get lost"""
        msg = youtube(self.config["ytkey"], "url", query)

        if msg is None:
            msg = "And i thought everything is on youtube :open_mouth:"
        await ctx.send(msg)

    @hybrid_command()
    @app_commands.rename(query="name")
    @app_commands.describe(
        query_type='Which kind of Media you want to search for. Possible values are "Movie", "Series" or "Episode".',
        query="What do you want to search for?",
    )
    async def imdb(self, ctx, query_type: Literal["movie", "series", "episode"], query: str):
        """omdb movie information"""
        rip, emb = await self._imdb_search(query_type.lower(), query)
        await ctx.send(rip, embed=emb)

    @hybrid_command()
    async def games(self, ctx, query: str):
        """killerspiele"""
        url = "https://api-v3.igdb.com/games"
        main_query = (
            f'search "{query}";'
            "fields name,first_release_date,aggregated_rating,summary,genres.name,url,cover.url;"
            "limit 6;"
        )
        headers = {"user-key": self.config["igdb"], "accept": "application/json"}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=main_query) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                result = await response.json()

                if len(result) > 0:
                    data = result[0]
                    emb = discord.Embed(title=data.get("name"))
                    if "summary" in data:
                        emb.description = data.get("summary")
                    else:
                        emb.description = "Lorem ipsum dolor sit amet, consectetur adipisici elit."

                    if "cover" in data:
                        emb.set_thumbnail(url=f'https:{data.get("cover", dict()).get("url")}')

                    if "first_release_date" in data:
                        dt = datetime.utcfromtimestamp(int(data.get("first_release_date"))).strftime("%Y-%m-%d")
                        emb.add_field(name=fmt.bold("Release Date"), value=dt)
                    else:
                        emb.add_field(name=fmt.bold("Release Date"), value="no info")

                    if "aggregated_rating" in data:
                        emb.add_field(
                            name=fmt.bold("Genres"),
                            value=", ".join(g.get("name") for g in data.get("genres")),
                        )
                    else:
                        emb.add_field(name=fmt.bold("Genres"), value="no info")

                    if "aggregated_rating" in data:
                        emb.add_field(
                            name=fmt.bold("Rating"),
                            value=f"{int(data.get('aggregated_rating'))}/100",
                        )
                    else:
                        emb.add_field(name=fmt.bold("Rating"), value="no rating")

                    if len(result) > 1:
                        i = iter(result)
                        next(i)
                        emb.add_field(
                            name=fmt.bold("wrong answer? try:"),
                            value="\n".join(f' - {r.get("name")}' for r in i),
                        )

                    emb.set_footer(text=data.get("url"))

                    await ctx.send(embed=emb)
                else:
                    await ctx.send(f"Nothing found for {query}.")

    async def _imdb_search(self, query_type: str, query: str):
        emb = None
        rip = ""
        search_url = f"http://www.omdbapi.com/?apikey={self.config['omdb']}&type={query_type}&s={query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as search_response:
                if search_response.status != 200:
                    err = f"The api-webserver responded with a code:{search_response.status} - {search_response.reason}"
                    raise NerpyException(err)
                search_result = await search_response.json()

                if search_result["Response"] == "True":
                    id_url = (
                            f"http://www.omdbapi.com/?apikey={self.config['omdb']}&i="
                            + search_result["Search"][0]["imdbID"]
                    )

                    async with session.get(id_url) as id_response:
                        if id_response.status != 200:
                            err = f"The api-webserver responded with a code:{id_response.status} - {id_response.reason}"
                            raise NerpyException(err)
                        id_result = await id_response.json()

                        emb = discord.Embed(title=id_result["Title"])
                        emb.description = id_result["Plot"]
                        emb.set_thumbnail(url=id_result["Poster"])
                        emb.add_field(name=fmt.bold("Released"), value=id_result["Released"])
                        emb.add_field(name=fmt.bold("Genre"), value=id_result["Genre"])
                        emb.add_field(name=fmt.bold("Runtime"), value=id_result["Runtime"])
                        emb.add_field(name=fmt.bold("Country"), value=id_result["Country"])
                        emb.add_field(name=fmt.bold("Language"), value=id_result["Language"])
                        emb.add_field(name=fmt.bold("Director"), value=id_result["Director"])
                        emb.add_field(name=fmt.bold("Actors"), value=id_result["Actors"])
                        emb.set_footer(text="Powered by https://www.omdbapi.com/")
                else:
                    rip = fmt.inline("No movie found with this search query")
        return rip, emb


async def setup(bot):
    """adds this module to the bot"""
    if "search" in bot.config:
        await bot.add_cog(Search(bot))
    else:
        raise NerpyException("Config not found.")
