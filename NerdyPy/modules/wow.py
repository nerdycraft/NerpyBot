import discord
import requests
import utils.format as fmt
from random import choice
from models.wow import WoW
from datetime import datetime
from utils.errors import NerpyException
from wowapi import WowApi, WowApiException
from datetime import datetime as dt, timedelta as td
from discord.ext.commands import Cog, group, clean_content, MissingRequiredArgument, Converter


class WorldofWarcraft(Cog):
    """WOW API"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["wow"]
        self.api = WowApi(self.config["wow_id"], self.config["wow_secret"])
        self.regions = ["eu", "us"]
        self.dungeon_names = {
            "NW": "Necrotic Wake",
            "SOA": "Spires of Ascension",
            "PF": "Plaguefall",
            "TOP": "Theater of Pain",
            "MOTS": "Mists of Tirna Scithe",
            "DOS": "De Other Side",
            "HOA": "Halls of Atonement",
            "SD": "Sanguine Depths"
        }
        self.dungeon_names_de = {
            "die nekrotische schneise": "NW",
            "nekrotische schneise": "NW",
            "spitzen des aufstiegs": "SOA",
            "seuchensturz": "PF",
            "das theater der schmerzen": "TOP",
            "theater der schmerzen": "TOP",
            "die nebel von tirna scithe": "MOTS",
            "nebel von tirna scithe": "MOTS",
            "die andre seite": "DOS",
            "andre seite": "DOS",
            "die hallen der sühne": "HOA",
            "hallen der sühne": "HOA",
            "die blutigen tiefen": "SD",
            "blutige tiefen": "SD"
        }
        self.dungeon_names_en = {
            "necrotic wake": "NW",
            "spires of ascension": "SOA",
            "plaguefall": "PF",
            "theater of pain": "TOP",
            "mists of tirna scithe": "MOTS",
            "de other side": "DOS",
            "halls of atonement": "HOA",
            "sanguine depths": "SD"
        }
        self.footer_text = [
            "Brought to you by your friendly neighborhood spider. ;)",
            "These are not the droids you're looking for.",
            "Chewie, we're home.",
            "They call it a Royale with cheese.",
            "That'll do, pig. That'll do.",
            "My precious.",
            "It's alive! It's alive!",
            "Help me, Obi-Wan Kenobi. You're my only hope.",
            "Mama says, 'Stupid is as stupid does.'",
            "Roads? Where we're going we don't need roads.",
            "Here's Johnny!",
            "To infinity and beyond!",
            "Yippie-ki-yay, motherfucker!",
            "I'll be back.",
            "Why so serious?",
            "Frankly, my dear, I don't give a damn."
        ]

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

    async def _get_character(self, ctx, realm, region, name):
        namespace = f"profile-{region}"

        self.api.get_character_profile_status(region, namespace, realm, name)
        character = self.api.get_character_profile_summary(region, f"profile-{region}", realm, name)
        assets = self.api.get_character_media_summary(region, f"profile-{region}", realm, name)["assets"]
        profile_picture = [asset for asset in assets if asset["key"] == "avatar"][0]["value"]

        return character, profile_picture

    # noinspection PyMethodMayBeStatic
    def _get_raiderio_score(self, region, realm, name):
        base_url = "https://raider.io/api/v1/characters/profile"
        args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_scores_by_season:current"

        req = requests.get(f"{base_url}{args}")

        if req.status_code == 200:
            resp = req.json()

            if len(resp["mythic_plus_scores_by_season"]) > 0:
                return resp["mythic_plus_scores_by_season"][0]["scores"]["all"]
            else:
                return None

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

    # noinspection PyMethodMayBeStatic
    def _get_current_affixes(self, region):
        base_url = "https://raider.io/api/v1/mythic-plus/affixes"
        args = f"?region={region}&locale=en"

        req = requests.get(f"{base_url}{args}")

        if req.status_code == 200:
            resp = req.json()

            first = True
            affix_list = ""
            for affix in resp["affix_details"]:
                if first:
                    first = False
                    affix_list += f'[{affix["name"]}]({affix["wowhead_url"]})'
                else:
                    affix_list += f' / [{affix["name"]}]({affix["wowhead_url"]})'

            return affix_list

    # noinspection PyMethodMayBeStatic
    def _convert_dungeon_names(self, name):
        dungeon_name = None
        name_lower = name.lower()

        if name_lower in self.dungeon_names_en:
            dungeon_name = self.dungeon_names_en[name_lower]
        if name_lower in self.dungeon_names_de:
            dungeon_name = self.dungeon_names_de[name_lower]

        return dungeon_name

    # noinspection PyMethodMayBeStatic
    def _format_keystones_to_embed(self, ctx, keys):
        emb = discord.Embed(
            title=f"Keystones for {ctx.guild.name}",
            color=discord.Color(value=int("0099ff", 16)),
            description="Not sorted at all",
        )

        ks_name = ""
        ks_level = ""
        char = ""

        for key in keys:
            keyname = key["KeystoneName"].upper()
            ks_name += f'{self.dungeon_names[keyname]}\n'
            ks_level += f'{key["KeystoneLevel"]}\n'
            char += f'{key["Character"]}\n'

        emb.add_field(name="Dungeon", value=ks_name, inline=True)
        emb.add_field(name="Level", value=ks_level, inline=True)
        emb.add_field(name="Character", value=char, inline=True)
        emb.add_field(name="Affixes", value=self._get_current_affixes(ctx.guild.region[0][:2]), inline=True)

        emb.set_footer(text=choice(self.footer_text))

        return emb

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

                character, profile_picture = await self._get_character(ctx, realm, region, name)

                best_keys = self._get_best_mythic_keys(region, realm, name)
                rio_score = self._get_raiderio_score(region, realm, name)

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
                emb.set_thumbnail(url=profile_picture)
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
                if rio_score is not None:
                    emb.add_field(name="M+ Score", value=rio_score, inline=True)

                emb.add_field(name="\u200b", value="\u200b", inline=False)
                emb.add_field(
                    name="External Sites",
                    value=f"[Raider.io]({raiderio}) | [Armory]({armory}) | [WarcraftLogs]({warcraftlogs}) | [WoWProgress]({wowprogress})",
                    inline=True,
                )

            await self.bot.sendc(ctx, "", emb)
        except WowApiException:
            await self.bot.sendc(ctx, "No Character with this name found.")

    @wow.group(invoke_without_command=True, aliases=["mythic", "müffiks", "m+"])
    async def mplus(self, ctx):
        """Get ALL the Infos about Mythic plus keys"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @mplus.group(invoke_without_command=True, name="keystones", aliases=["ks", "keys", "stone", "key"])
    async def _mplus_keystones(self, ctx):
        if ctx.invoked_subcommand is None:
            keys = WoW.get_keystones(ctx.guild.id)
            if len(keys) > 0:
                await self.bot.sendc(ctx, "", emb=self._format_keystones_to_embed(ctx, keys))
            else:
                await self.bot.sendc(ctx, "There are no keystones.")

    @mplus.group(invoke_without_command=True, name="dungeons")
    async def _mplus_dungeons(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_mplus_dungeons.command(name="list")
    async def _mplus_dungeons_list(self, ctx):
        msg = f"\n# German Names #\n"
        for entry in self.dungeon_names_de:
            msg += f"{entry}\n"

        msg += f"\n# English Names #\n"
        for entry in self.dungeon_names_en:
            msg += f"{entry}\n"

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            await self.bot.sendc(ctx, fmt.box(page, "md"))

    @_mplus_keystones.group(invoke_without_command=True, name="get")
    async def _mplus_keystones_get(self, ctx):
        """list keystone by specific parameters"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_mplus_keystones_get.command(name="level")
    async def _mplus_keystones_get_by_level(self, ctx, level: clean_content):
        """get all keystones by a specific level"""
        keys = WoW.get_keystone_by_level(ctx.guild.id, level)
        if len(keys) > 0:
            await self.bot.sendc(ctx, "", emb=self._format_keystones_to_embed(ctx, keys))
        else:
            await self.bot.sendc(ctx, "There are no keystones.")

    @_mplus_keystones_get.command(name="dungeon")
    async def _mplus_keystones_get_by_dungeon(self, ctx, *dungeon):
        """get all keystones by a specific dungeon"""
        _clean_dungeon = ' '.join(dungeon)
        if len(_clean_dungeon) > 4:
            _short_dungeon_name = self._convert_dungeon_names(_clean_dungeon)
            if _short_dungeon_name is None:
                raise NerpyException("Seems like you searched for a dungeon I do not know. Please verify if you spelled it correctly.")
            else:
                keys = WoW.get_keystone_by_name(ctx.guild.id, _short_dungeon_name)
        else:
            keys = WoW.get_keystone_by_name(ctx.guild.id, dungeon)

        if len(keys) > 0:
            await self.bot.sendc(ctx, "", emb=self._format_keystones_to_embed(ctx, keys))
        else:
            await self.bot.sendc(ctx, "There are no keystones.")

    @_mplus_keystones_get.command(name="character")
    async def _mplus_keystones_get_by_character(self, ctx, character: clean_content):
        """get all keystones by a specific character"""
        keys = WoW.get_keystone_by_character(ctx.guild.id, character)
        if len(keys) > 0:
            await self.bot.sendc(ctx, "", emb=self._format_keystones_to_embed(ctx, keys))
        else:
            await self.bot.sendc(ctx, "There are no keystones.")

    @_mplus_keystones.command(name="add", ignore_extra=True)
    async def _mplus_keystones_add(self, ctx, keystone_name, keystone_level, character):
        creation_date = datetime.utcnow()
        if WoW.exists(ctx.guild.id, character):
            raise NerpyException("Keystone already exists for this character!")
        else:
            try:
                WoW.add(ctx.guild.id, keystone_name, keystone_level, character, creation_date, ctx.author.name)
            except:
                raise NerpyException("Could not add keystone to database.")

            await self.bot.sendc(ctx, "Keystone added to database.")

    @_mplus_keystones_add.error
    async def _mplus_keystones_add_error(self, ctx, error):
        if isinstance(error, MissingRequiredArgument):
            await ctx.send_help(ctx.command)

    @_mplus_keystones.command(name="remove", aliases=["rm", "delete", "del"])
    async def _mplus_keystones_remove(self, ctx, character):
        if WoW.exists(ctx.guild.id, character):
            WoW.delete(ctx.guild.id, character)
            await self.bot.sendc(ctx, "Keystone successfully deleted.")
        else:
            raise NerpyException(f"There is no saved key for character {character}.")

    @_mplus_keystones_remove.error
    async def _mplus_keystones_remove_error(self, ctx, error):
        if isinstance(error, MissingRequiredArgument):
            await ctx.send_help(ctx.command)


def setup(bot):
    """adds this module to the bot"""
    if "wow" in bot.config:
        bot.add_cog(WorldofWarcraft(bot))
    else:
        raise NerpyException("Config not found.")
