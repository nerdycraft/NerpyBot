# -- coding: utf-8 --
"""Search Modul"""

import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote

import utils.format as fmt
from aiohttp import ClientSession
from discord import Embed
from discord.app_commands import rename
from discord.ext.commands import Context, GroupCog, bot_has_permissions, hybrid_command
from igdb.wrapper import IGDBWrapper
from requests import post
from utils.errors import NerpyException
from utils.helpers import check_api_response, youtube


@bot_has_permissions(send_messages=True)
class Search(GroupCog):
    """search module"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["search"]
        self.igdb_token = {}

    @hybrid_command()
    @rename(query="meme")
    async def imgur(self, ctx: Context, query: str):
        """may the meme be with you

        Parameters
        ----------
        ctx: Context
        query: str
            Meme/Picture/Gif to search for.
        """
        url = f"https://api.imgur.com/3/gallery/search/viral?q={quote(query)}"

        async with ClientSession(headers={"Authorization": f"Client-ID {self.config['imgur']}"}) as session:
            async with session.get(url) as response:
                await check_api_response(response, "Imgur API")
                data = await response.json()
                if data.get("success") is not None and len(data.get("data")) > 0:
                    meme = data.get("data")[0].get("link")
                else:
                    meme = "R.I.P. memes"
                await ctx.send(meme)

    @hybrid_command()
    async def urban(self, ctx: Context, query: str):
        """urban legend"""
        url = f"https://api.urbandictionary.com/v0/define?term={quote(query)}"

        async with ClientSession() as session:
            async with session.get(url) as response:
                await check_api_response(response, "Urban Dictionary API")
                data = await response.json()
                emb = Embed(title=f'"{query}" on Urban Dictionary:')
                if len(data.get("list")) > 0:
                    item = data["list"][0]
                    emb.description = item.get("definition")
                    emb.set_author(name=item.get("author"))
                    emb.url = item.get("permalink")
                else:
                    emb.description = "no results - R.I.P. memes"
                await ctx.send(embed=emb)

    @hybrid_command()
    async def lyrics(self, ctx: Context, query: str):
        """genius lyrics"""
        url = f"https://api.genius.com/search?q={quote(query)}"

        async with ClientSession(headers={"Authorization": f"Bearer {self.config['genius']}"}) as session:
            async with session.get(url) as response:
                await check_api_response(response, "Genius API")
                data = await response.json()
                emb = Embed(title=f'"{query}" on genius.com:')
                if len(data.get("response", dict()).get("hits")) > 0:
                    item = data.get("response", dict()).get("hits")[0].get("result")
                    emb.description = item.get("full_title")
                    emb.set_thumbnail(url=item.get("header_image_thumbnail_url"))
                    emb.url = item.get("url")
                else:
                    emb.description = "R.I.P. memes"
                await ctx.send(embed=emb)

    @hybrid_command()
    async def youtube(self, ctx: Context, query: str):
        """don't stick too long, you might get lost"""
        msg = youtube(self.config["ytkey"], "url", query)

        if msg is None:
            msg = "And i thought everything is on youtube :open_mouth:"
        await ctx.send(msg)

    async def _imdb_search(self, query_type: str, query: str):
        emb = None
        rip = ""
        search_url = f"https://www.omdbapi.com/?apikey={self.config['omdb']}&type={quote(query_type)}&s={quote(query)}"

        async with ClientSession() as session:
            async with session.get(search_url) as search_response:
                await check_api_response(search_response, "OMDB API")
                search_result = await search_response.json()

                if search_result["Response"] == "True":
                    id_url = f"https://www.omdbapi.com/?apikey={self.config['omdb']}&i={search_result['Search'][0]['imdbID']}"

                    async with session.get(id_url) as id_response:
                        await check_api_response(id_response, "OMDB API")
                        id_result = await id_response.json()

                        emb = Embed(title=id_result["Title"])
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

    @hybrid_command()
    @rename(query_type="type", query="name")
    async def imdb(self, ctx: Context, query_type: Literal["movie", "series", "episode"], query: str):
        """omdb movie information

        Parameters
        ----------
        ctx
        query_type: Literal["movie", "series", "episode"]
            Which kind of Media you want to search for. Possible values are "Movie", "Series" or "Episode".
        query: str
            What do you want to search for?
        """
        rip, emb = await self._imdb_search(query_type.lower(), query)
        await ctx.send(rip, embed=emb)

    def _get_igdb_access_token(self):
        client_id = self.config["igdb_client_id"]
        client_secret = self.config["igdb_client_secret"]
        twitch_oauth_url = "https://id.twitch.tv/oauth2/token"

        with post(
            twitch_oauth_url,
            data={"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"},
        ) as oauth_response:
            if oauth_response.status_code != 200:
                self.bot.log.error(
                    f"Server responded with code: {oauth_response.status_code} - {oauth_response.reason}"
                )
                raise NerpyException(
                    "Something really bad happend. If this issue persists, please report to bot author."
                )
            result = oauth_response.json()
            result["expire_time"] = datetime.now(UTC) + timedelta(seconds=result.get("expires_in"))

            return result

    @hybrid_command()
    @rename(query="name")
    async def games(self, ctx: Context, query: str):
        """killerspiele"""
        main_query = (
            f'search "{query}";'
            "fields name,first_release_date,aggregated_rating,summary,genres.name,url,cover.url;"
            "limit 6;"
        )
        if "expire_time" not in self.igdb_token or self.igdb_token["expire_time"] < datetime.now(UTC):
            self.igdb_token = self._get_igdb_access_token()

        wrapper = IGDBWrapper(self.config["igdb_client_id"], self.igdb_token.get("access_token"))
        result = json.loads(wrapper.api_request("games", main_query).decode("utf8").replace("'", '"'))

        try:
            data = result.pop(0)
            emb = Embed(title=data.get("name"))
            if "summary" in data:
                emb.description = data.get("summary")
            else:
                emb.description = "Lorem ipsum dolor sit amet, consectetur adipisici elit."

            if "cover" in data:
                emb.set_thumbnail(url=f"https:{data.get('cover', dict()).get('url')}")

            if "first_release_date" in data:
                dt = datetime.fromtimestamp(int(data.get("first_release_date")), UTC).strftime("%Y-%m-%d")
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
        except IndexError:
            await ctx.send(f"Nothing found for {query}.")
        else:
            if len(result) > 0:
                i = iter(result)
                next(i)
                emb.add_field(
                    name=fmt.bold("wrong answer? try:"),
                    value="\n".join(f" - {r.get('name')}" for r in i),
                )

            emb.set_footer(text=data.get("url"))

            await ctx.send(embed=emb)


async def setup(bot):
    """adds this module to the bot"""
    if "search" in bot.config:
        await bot.add_cog(Search(bot))
    else:
        raise NerpyException("Config not found.")
