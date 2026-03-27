# -*- coding: utf-8 -*-
"""WoW characters cog: armory lookup, realm cache, shared API helpers."""

import asyncio
from enum import Enum
from typing import LiteralString

import discord
from blizzapi import Language, Region, RetailClient
from discord import Color, Embed, Interaction, app_commands

from modules.wow.api import (
    RateLimited,
    check_rate_limit,
    get_best_mythic_keys,
    get_profile_link,
    get_raiderio_score,
)
from utils.errors import NerpyInfraException, NerpyNotFoundError, NerpyUserException
from utils.strings import get_string


class WowApiLanguage(Enum):
    """Language Enum for WoW API"""

    DE = "de_DE"
    EN = "en_US"
    EN_GB = "en_GB"


# Embed colors for guild news notifications
COLOR_ACHIEVEMENT = Color.gold()
COLOR_ENCOUNTER = Color.red()
COLOR_MOUNT = Color.purple()
COLOR_ITEM_LINK = Color(value=0x0099FF)  # WoW blue item link color


class WowCharactersMixin:
    """Shared WoW helpers and armory command.

    Mixed into the WorldofWarcraft GroupCog via __init__.py.
    """

    def _init_characters(self, bot):
        self.config = bot.config
        self.client_id = self.config["wow"]["wow_id"]
        self.client_secret = self.config["wow"]["wow_secret"]
        self.regions = ["eu", "us"]

        # Realm cache: "slug-region" -> {"name": "Blackrock", "region": "eu", "slug": "blackrock"}
        self._realm_cache: dict[str, dict] = {}
        self._realm_cache_lock = asyncio.Lock()

    # ── Realm cache & autocomplete ─────────────────────────────────────

    async def _ensure_realm_cache(self):
        """Lazily populate the realm cache from both EU and US regions."""
        if self._realm_cache:
            return

        async with self._realm_cache_lock:
            # Double-check after acquiring lock
            if self._realm_cache:
                return

            cache = {}
            for region in self.regions:
                try:
                    api = self._get_retailclient(region, "en")
                    data = await asyncio.to_thread(api.realms_index)
                    check_rate_limit(data)
                    for realm in data.get("realms", []):
                        slug = realm.get("slug", "")
                        name = realm.get("name", slug)
                        if slug:
                            cache[f"{slug}-{region}"] = {"name": name, "region": region, "slug": slug}
                except Exception as ex:
                    self.bot.log.warning(f"Failed to fetch realm index for {region}: {ex}")

            self._realm_cache = cache
            self.bot.log.info(f"Realm cache populated with {len(cache)} entries")

    # noinspection PyUnusedLocal
    async def _realm_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice[str]]:
        """Autocomplete callback for the realm parameter."""
        await self._ensure_realm_cache()

        current_lower = current.lower()
        matches = []
        for key, info in self._realm_cache.items():
            if current_lower in info["name"].lower() or current_lower in info["slug"]:
                label = f"{info['name']} ({info['region'].upper()})"
                matches.append(discord.app_commands.Choice(name=label, value=key))
            if len(matches) >= 25:
                break

        return matches

    # ── Shared helpers ──────────────────────────────────────────────────

    async def _parse_realm(self, realm: str, lang: str = "en") -> tuple[str, str]:
        """Parse a realm string like 'blackrock-eu' into (realm_slug, region).

        Validates against the realm cache if populated. Plain slugs default to EU.
        """
        realm = realm.lower()
        if "-" in realm:
            parts = realm.rsplit("-", 1)
            if parts[1] in self.regions:
                realm_slug, region = parts[0], parts[1]
            else:
                realm_slug, region = realm, "eu"
        else:
            realm_slug, region = realm, "eu"

        await self._ensure_realm_cache()
        cache_key = f"{realm_slug}-{region}"
        if self._realm_cache and cache_key not in self._realm_cache:
            raise NerpyNotFoundError(get_string(lang, "wow.realm_not_found", realm=realm_slug, region=region.upper()))

        return realm_slug, region

    def _get_retailclient(self, region: str, language: str):
        if region not in self.regions:
            raise ValueError(f"Invalid region: {region}. Valid regions are: {', '.join(self.regions)}")

        if language == "de":
            api_language = WowApiLanguage.DE.value
        elif region == "eu":
            api_language = WowApiLanguage.EN_GB.value
        else:
            api_language = WowApiLanguage.EN.value

        try:
            # noinspection PyTypeChecker
            return RetailClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                region=Region(region),
                language=Language(api_language),
            )
        except ValueError as ex:
            raise NerpyInfraException("Failed to initialise WoW API client.") from ex

    def _get_character(self, realm: str, region: str, name: str, language: str) -> tuple[dict, LiteralString]:
        """Get character profile and media from the WoW API."""
        api = self._get_retailclient(region, language)

        character = api.character_profile_summary(realmSlug=realm, characterName=name)
        media = api.character_media(realmSlug=realm, characterName=name)
        assets = media.get("assets", []) if isinstance(media, dict) else []
        profile_picture = "".join(asset.get("value") for asset in assets if asset.get("key") == "avatar")

        return character, profile_picture

    async def _call_api(self, api_method, config_id, label, *args, rate_limited_event=None, stats=None, **kwargs):
        """Call a Blizzard API method with standard rate-limit and error handling.

        Returns the result on success, or None on failure (already logged).
        Sets rate_limited_event and increments stats["skipped_error"] when provided.
        """
        self.bot.log.debug(f"Guild news #{config_id}: {label}")
        try:
            result = await asyncio.to_thread(api_method, *args, **kwargs)
            check_rate_limit(result)
            return result
        except RateLimited:
            self.bot.log.warning(f"Guild news #{config_id}: rate limited on {label}")
            if rate_limited_event:
                rate_limited_event.set()
            return None
        except Exception as ex:
            log_fn = self.bot.log.debug if stats is not None else self.bot.log.warning
            log_fn(f"Guild news #{config_id}: {label} failed: {ex}")
            if stats is not None:
                stats["skipped_error"] += 1
            return None

    # ── Armory command ──────────────────────────────────────────────────

    @app_commands.command(name="armory")
    async def _wow_armory(
        self,
        interaction: Interaction,
        name: str,
        realm: str,
    ):
        """
        search for character

        name and realm are required parameters.
        realm accepts autocomplete suggestions (e.g. "blackrock-eu") or a plain slug (defaults to EU).
        """
        try:
            await interaction.response.defer()
            lang = self._lang(interaction.guild_id)
            realm_slug, region = await self._parse_realm(realm, lang)
            name = name.lower()
            profile = f"{region}/{realm_slug}/{name}"

            # noinspection PyTypeChecker
            character, profile_picture = self._get_character(realm_slug, region, name, lang)

            if not isinstance(character, dict) or character.get("code") == 404:
                raise NerpyNotFoundError(get_string(lang, "wow.armory.not_found"))

            best_keys = get_best_mythic_keys(region, realm_slug, name)
            rio_score = get_raiderio_score(region, realm_slug, name)

            armory = get_profile_link("armory", profile)
            raiderio = get_profile_link("raiderio", profile)
            warcraftlogs = get_profile_link("warcraftlogs", profile)
            wowprogress = get_profile_link("wowprogress", profile)

            emb = Embed(
                title=f"{character['name']} | {realm_slug.capitalize()} | {region.upper()} | {character['active_spec']['name']} {character['character_class']['name']} | {character['equipped_item_level']} ilvl",
                url=armory,
                color=COLOR_ITEM_LINK,
                description=f"{character['gender']['name']} {character['race']['name']}",
            )
            emb.set_thumbnail(url=profile_picture)
            emb.add_field(name=get_string(lang, "wow.armory.level"), value=character["level"], inline=True)
            emb.add_field(name=get_string(lang, "wow.armory.faction"), value=character["faction"]["name"], inline=True)
            if "guild" in character:
                emb.add_field(name=get_string(lang, "wow.armory.guild"), value=character["guild"]["name"], inline=True)
            emb.add_field(name="\u200b", value="\u200b", inline=False)

            if best_keys:
                keys = ""
                for key in best_keys:
                    keys += f"+{key['level']} - {key['dungeon']} - {key['clear_time']}\n"

                emb.add_field(name=get_string(lang, "wow.armory.best_keys"), value=keys, inline=True)
            if rio_score is not None:
                emb.add_field(name=get_string(lang, "wow.armory.mplus_score"), value=rio_score, inline=True)

            emb.add_field(name="\u200b", value="\u200b", inline=False)
            emb.add_field(
                name=get_string(lang, "wow.armory.external_sites"),
                value=f"[Raider.io]({raiderio}) | [Armory]({armory}) | [WarcraftLogs]({warcraftlogs}) | [WoWProgress]({wowprogress})",
                inline=True,
            )

            await interaction.followup.send(embed=emb)
        except NerpyUserException as ex:
            await interaction.followup.send(str(ex), ephemeral=True)

    @_wow_armory.autocomplete("realm")
    async def _realm_autocomplete_handler(self, interaction: discord.Interaction, current: str):
        return await self._realm_autocomplete(interaction, current)
