import discord
import requests
from utils.errors import NerpyException
from wowapi import WowApi, WowApiException
from discord.ext.commands import Cog, group
from datetime import datetime as dt, timedelta as td

from utils.send import send_embed, send


class WorldofWarcraft(Cog):
    """WOW API"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["wow"]
        self.api = WowApi(self.config["wow_id"], self.config["wow_secret"])
        self.regions = ["eu", "us"]

    # noinspection PyMethodMayBeStatic
    def _get_link(self, site, profile):
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

    def _get_current_season(self, region):
        namespace = f"dynamic-{region}"
        return self.api.get_mythic_keystone_season_index(region, namespace)["current_season"]["id"]

    async def _get_character(self, ctx, realm, region, name):
        namespace = f"profile-{region}"

        self.api.get_character_profile_status(region, namespace, realm, name)
        character = self.api.get_character_profile_summary(region, f"profile-{region}", realm, name)
        profile_picture = self.api.get_character_media_summary(region, f"profile-{region}", realm, name)

        return character, profile_picture

    # noinspection PyMethodMayBeStatic
    def _get_raiderio_score(self, region, realm, name, season):
        base_url = "https://raider.io/api/v1/characters/profile"
        args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_scores_by_season:season-bfa-{season}"

        req = requests.get(f"{base_url}{args}")

        if req.status_code == 200:
            resp = req.json()

            return resp["mythic_plus_scores_by_season"][0]["scores"]["all"]

    # noinspection PyMethodMayBeStatic
    def _get_best_mythic_keys(self, region, realm, name):
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

    @group(invoke_without_command=True)
    async def wow(self, ctx):
        """Get ALL the Infos about WoW"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @wow.command(aliases=["search", "char"])
    async def armory(self, ctx, name: str, realm: str, region: str = None):
        """
        search for character

        name and realm are required parameters.
        region is optional, but if you want to search on another realm than your discord server runs on, you need to set it.
        """
        try:
            async with ctx.typing():
                if region is None:
                    region = ctx.guild.region[0][:2]

                realm = realm.lower()
                name = name.lower()
                profile = f"{region}/{realm}/{name}"
                current_season = self._get_current_season(region)
                best_keys = self._get_best_mythic_keys(region, realm, name)
                rio_score = self._get_raiderio_score(region, realm, name, current_season)

                character, profile_picture = await self._get_character(ctx, realm, region, name)

                armory = self._get_link("armory", profile)
                raiderio = self._get_link("raiderio", profile)
                warcraftlogs = self._get_link("warcraftlogs", profile)
                wowprogress = self._get_link("wowprogress", profile)

                emb = discord.Embed(
                    title=f'{character["name"]} | {realm.capitalize()} | {region.upper()} | {character["active_spec"]["name"]["en_US"]} {character["character_class"]["name"]["en_US"]} | {character["equipped_item_level"]} ilvl',
                    url=armory,
                    color=discord.Color(value=int("0099ff", 16)),
                    description=f'{character["gender"]["name"]["en_US"]} {character["race"]["name"]["en_US"]}',
                )
                emb.set_thumbnail(url=profile_picture["avatar_url"])
                emb.add_field(name="Level", value=character["level"], inline=True)
                emb.add_field(name="Faction", value=character["faction"]["name"]["en_US"], inline=True)
                if "guild" in character:
                    emb.add_field(name="Guild", value=character["guild"]["name"], inline=True)
                emb.add_field(name="\u200b", value="\u200b", inline=False)

                if len(best_keys) > 0:
                    keys = ""
                    for key in best_keys:
                        keys += f'+{key["level"]} - {key["dungeon"]} - {key["clear_time"]}\n'

                    emb.add_field(name="Best M+ Keys", value=keys, inline=True)
                emb.add_field(name="M+ Score", value=rio_score, inline=True)

                emb.add_field(name="\u200b", value="\u200b", inline=False)
                emb.add_field(
                    name="External Sites",
                    value=f"[Raider.io]({raiderio}) | [Armory]({armory}) | [WarcraftLogs]({warcraftlogs}) | [WoWProgress]({wowprogress})",
                    inline=True,
                )

            await send_embed(ctx, emb)
        except WowApiException:
            await send(ctx, "No Character with this name found.")


def setup(bot):
    """adds this module to the bot"""
    if "wow" in bot.config:
        bot.add_cog(WorldofWarcraft(bot))
    else:
        raise NerpyException("Config not found.")
