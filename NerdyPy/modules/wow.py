# -*- coding: utf-8 -*-

from datetime import datetime as dt, timedelta as td

import requests
from blizzapi import RetailClient, Region
from discord import Embed, Color
from discord.ext.commands import GroupCog, hybrid_command, bot_has_permissions, Context

from utils.errors import NerpyException
from utils.helpers import send_hidden_message


@bot_has_permissions(send_messages=True, embed_links=True)
class WorldofWarcraft(GroupCog, group_name="wow"):
    """WOW API"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = bot.config
        self.client_id = self.config["wow"]["wow_id"]
        self.client_secret = self.config["wow"]["wow_secret"]
        self.regions = ["eu", "us"]

    @staticmethod
    def _get_link(site, profile):
        url = None

        if site == "armory":
            url = "https://worldofwarcraft.com/en-us/character"
        elif site == "raiderio":
            url = "https://raider.io/characters"
        elif site == "warcraftlogs":
            url = "https://www.warcraftlogs.com/character"
        elif site == "wowprogress":
            url = "https://www.wowprogress.com/character"

        return f"{url}/{profile}"

    async def _get_character(self, realm, region, name):
        if region not in self.regions:
            raise NerpyException(f"Invalid region: {region}. Valid regions are: {', '.join(self.regions)}")
        try:
            api = RetailClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                region=Region(region),
            )
        except ValueError as ex:
            raise NerpyException(f"Invalid region: {region}") from ex

        character = api.character_profile_summary(realmSlug=realm, characterName=name)
        assets = api.character_media(realmSlug=realm, characterName=name).get("assets", list())
        profile_picture = "".join(asset.get("value") for asset in assets if asset.get("key") == "avatar")

        return character, profile_picture

    @staticmethod
    def _get_raiderio_score(region, realm, name):
        base_url = "https://raider.io/api/v1/characters/profile"
        args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_scores_by_season:current"

        req = requests.get(f"{base_url}{args}")

        if req.status_code == 200:
            resp = req.json()

            if len(resp["mythic_plus_scores_by_season"]) > 0:
                return resp["mythic_plus_scores_by_season"][0]["scores"]["all"]
            else:
                return None
        return None

    @staticmethod
    def _get_best_mythic_keys(region, realm, name):
        base_url = "https://raider.io/api/v1/characters/profile"
        args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_best_runs"

        req = requests.get(f"{base_url}{args}")

        if req.status_code == 200:
            resp = req.json()

            keys = []
            for key in resp["mythic_plus_best_runs"]:
                base_datetime = dt(1970, 1, 1)
                delta = td(milliseconds=key["clear_time_ms"])
                target_date = base_datetime + delta
                keys.append(
                    {
                        "dungeon": key["short_name"],
                        "level": key["mythic_level"],
                        "clear_time": target_date.strftime("%M:%S"),
                    }
                )

            return keys
        return None

    @hybrid_command(name="armory", aliases=["search", "char"])
    async def _wow_armory(self, ctx: Context, name: str, realm: str, region: str = "eu"):
        """
        search for character

        name and realm are required parameters.
        region is optional, but if you want to search on another realm than your discord server runs on,
            you need to set it.
        """
        try:
            async with ctx.typing():
                realm = realm.lower()
                name = name.lower()
                profile = f"{region}/{realm}/{name}"

                character, profile_picture = await self._get_character(realm, region, name)

                if character.get("code") == 404:
                    raise NerpyException("No Character with this name found.")

                best_keys = self._get_best_mythic_keys(region, realm, name)
                rio_score = self._get_raiderio_score(region, realm, name)

                armory = self._get_link("armory", profile)
                raiderio = self._get_link("raiderio", profile)
                warcraftlogs = self._get_link("warcraftlogs", profile)
                wowprogress = self._get_link("wowprogress", profile)

                emb = Embed(
                    title=f'{character["name"]} | {realm.capitalize()} | {region.upper()} | {character["active_spec"]["name"]} {character["character_class"]["name"]} | {character["equipped_item_level"]} ilvl',
                    url=armory,
                    color=Color(value=int("0099ff", 16)),
                    description=f'{character["gender"]["name"]} {character["race"]["name"]}',
                )
                emb.set_thumbnail(url=profile_picture)
                emb.add_field(name="Level", value=character["level"], inline=True)
                emb.add_field(name="Faction", value=character["faction"]["name"], inline=True)
                if "guild" in character:
                    emb.add_field(name="Guild", value=character["guild"]["name"], inline=True)
                emb.add_field(name="\u200b", value="\u200b", inline=False)

                if len(best_keys) > 0:
                    keys = ""
                    for key in best_keys:
                        keys += f'+{key["level"]} - {key["dungeon"]} - {key["clear_time"]}\n'

                    emb.add_field(name="Best M+ Keys", value=keys, inline=True)
                if rio_score is not None:
                    emb.add_field(name="M+ Score", value=rio_score, inline=True)

                emb.add_field(name="\u200b", value="\u200b", inline=False)
                emb.add_field(
                    name="External Sites",
                    value=f"[Raider.io]({raiderio}) | [Armory]({armory}) | [WarcraftLogs]({warcraftlogs}) | [WoWProgress]({wowprogress})",
                    inline=True,
                )

            await ctx.send(embed=emb)
        except NerpyException as ex:
            await send_hidden_message(ctx, str(ex))


async def setup(bot):
    """adds this module to the bot"""
    if "wow" in bot.config:
        await bot.add_cog(WorldofWarcraft(bot))
    else:
        raise NerpyException("Config not found.")
