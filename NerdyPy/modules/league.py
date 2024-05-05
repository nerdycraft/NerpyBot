# -*- coding: utf-8 -*-

from enum import Enum
from typing import Literal

from aiohttp import ClientSession
from discord import Embed
from discord.app_commands import rename
from discord.ext.commands import GroupCog, hybrid_command, Context

from utils.errors import NerpyException


class LeagueCommand(Enum):
    """league regions"""

    SUMMONER_BY_NAME = "summoner/v4/summoners/by-name/"
    RANK_POSITIONS = "league/v4/entries/by-summoner/"


class League(GroupCog):
    """league of legends related stuff"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.version = None
        self.config = self.bot.config["league"]

    async def _get_latest_version(self):
        if self.version is None:
            async with ClientSession() as session:
                async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as response:
                    data = await response.json()
                    self.version = data[0]
        return self.version

    # noinspection PyMethodMayBeStatic
    def _get_url(self, region, cmd: LeagueCommand, arg: str):
        base_url = f"https://{region}.api.riotgames.com/lol/"
        return f"{base_url}{cmd.value}{arg}"

    @hybrid_command()
    @rename(summoner_name="name")
    async def summoner(self, ctx: Context, region: Literal["EUW1", "NA1"], summoner_name: str):
        """get information about the summoner"""
        rank = tier = lp = wins = losses = ""

        auth_header = {"X-Riot-Token": self.config["riot"]}
        summoner_url = self._get_url(region, LeagueCommand.SUMMONER_BY_NAME, summoner_name)

        async with ClientSession(headers=auth_header) as summoner_session:
            async with summoner_session.get(summoner_url) as summoner_response:
                data = await summoner_response.json()
                if "status" in data:  # if query is successful there is no status key
                    self.bot.log.error(data["status"])
                    raise NerpyException("Could not get data from API. Please report to Bot author.")
                else:
                    summoner_id = data.get("id")
                    name = data.get("name")
                    level = data.get("summonerLevel")
                    icon_id = data.get("profileIconId")

                    rank_url = self._get_url(region, LeagueCommand.RANK_POSITIONS, summoner_id)

                    async with ClientSession(headers=auth_header) as rank_session:
                        async with rank_session.get(rank_url) as rank_response:
                            data = await rank_response.json()
                            played_ranked = len(data) > 0
                            if played_ranked:
                                rank = data[0].get("rank")
                                tier = data[0].get("tier")
                                lp = data[0].get("leaguePoints")
                                wins = data[0].get("wins")
                                losses = data[0].get("losses")

                    ver = await self._get_latest_version()

                    emb = Embed(title=name)
                    emb.set_thumbnail(url=f"http://ddragon.leagueoflegends.com/cdn/{ver}/img/profileicon/{icon_id}.png")
                    emb.description = f"Summoner Level: {level}"

                    if played_ranked:
                        emb.add_field(name="rank", value=f"{tier} {rank}")
                        emb.add_field(name="league points", value=lp)
                        emb.add_field(name="wins", value=wins)
                        emb.add_field(name="losses", value=losses)

        await ctx.send(embed=emb)


async def setup(bot):
    """adds this module to the bot"""
    if "league" in bot.config:
        await bot.add_cog(League(bot))
    else:
        raise NerpyException("Config not found.")
