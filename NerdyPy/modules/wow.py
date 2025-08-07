# -*- coding: utf-8 -*-

from datetime import datetime as dt
from datetime import timedelta as td
from enum import Enum
from typing import Dict, Literal, LiteralString, Optional, Tuple

import requests
from blizzapi import RetailClient, Region, Language
from discord import Embed, Color
from discord.ext.commands import GroupCog, hybrid_command, bot_has_permissions, Context, hybrid_group

from models.wow import WoW

from utils.errors import NerpyException
from utils.helpers import send_hidden_message, empty_subcommand


class WowApiLanguage(Enum):
    """Language Enum for WoW API"""

    DE = "de_DE"
    EN = "en_US"
    EN_GB = "en_GB"


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

    async def _get_retailclient(self, region: str, guild_id: int):
        if region not in self.regions:
            raise NerpyException(f"Invalid region: {region}. Valid regions are: {', '.join(self.regions)}")

        language = WowApiLanguage.EN.value if region != "eu" else WowApiLanguage.EN_GB.value
        try:
            with self.bot.session_scope() as session:
                lang = WoW.get(guild_id, session).Language
            if lang:
                language = WowApiLanguage[lang].value

            # noinspection PyTypeChecker
            return RetailClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                region=Region(region),
                language=Language(language),
            )
        except ValueError as ex:
            raise NerpyException from ex

    async def _get_character(self, realm: str, region: str, name: str, guild_id: int) -> Tuple[Dict, LiteralString]:
        """Get character profile and media from the WoW API."""
        api = await self._get_retailclient(region, guild_id)

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

    @hybrid_group(name="language", aliases=["lang", "locale"])
    async def _wow_language(self, ctx: Context):
        empty_subcommand(ctx)

    @_wow_language.command(name="get")
    async def _wow_language_get(self, ctx: Context):
        """Get the current language setting for the WoW API."""
        with self.bot.session_scope() as session:
            entry = WoW.get(ctx.guild.id, session)
            if entry is None:
                await ctx.send("No language set for this guild. Defaulting to English.")
            else:
                await ctx.send(f"Current language for this guild is: {entry.Language.upper()}")

    @_wow_language.command(name="set")
    async def _wow_language_set(self, ctx: Context, lang: Literal["de", "en"]):
        """Set the language for the WoW API."""
        with self.bot.session_scope() as session:
            entry = WoW.get(ctx.guild.id, session)
            if entry is None:
                entry = WoW(GuildId=ctx.guild.id, CreateDate=dt.now(), Author=ctx.author.name)
                session.add(entry)

            entry.ModifiedDate = dt.now()
            entry.Language = lang.upper()

        await ctx.send(f"Language set to {lang.upper()} for this guild.")

    @_wow_language.command(name="delete", aliases=["remove", "rm", "del"])
    async def _wow_language_delete(self, ctx: Context):
        """Delete the current language setting for the WoW API."""
        with self.bot.session_scope() as session:
            WoW.delete(ctx.guild.id, session)
        await ctx.send("Language setting removed. Defaulting to English for this guild.")

    @hybrid_command(name="armory", aliases=["search", "char"])
    async def _wow_armory(self, ctx: Context, name: str, realm: str, region: Optional[Literal["eu", "us"]] = "eu"):
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

                # noinspection PyTypeChecker
                character, profile_picture = await self._get_character(realm, region, name, ctx.guild.id)

                if character.get("code") == 404:
                    raise NerpyException("No Character with this name found.")

                best_keys = self._get_best_mythic_keys(region, realm, name)
                rio_score = self._get_raiderio_score(region, realm, name)

                armory = self._get_link("armory", profile)
                raiderio = self._get_link("raiderio", profile)
                warcraftlogs = self._get_link("warcraftlogs", profile)
                wowprogress = self._get_link("wowprogress", profile)

                emb = Embed(
                    title=f"{character['name']} | {realm.capitalize()} | {region.upper()} | {character['active_spec']['name']} {character['character_class']['name']} | {character['equipped_item_level']} ilvl",
                    url=armory,
                    color=Color(value=int("0099ff", 16)),
                    description=f"{character['gender']['name']} {character['race']['name']}",
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
                        keys += f"+{key['level']} - {key['dungeon']} - {key['clear_time']}\n"

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
