# -*- coding: utf-8 -*-

import asyncio
import itertools
import json
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Literal, LiteralString

import discord
from blizzapi import Language, Region, RetailClient
from discord import Color, Embed, HTTPException, Interaction, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import GroupCog
from models.wow import WowCharacterMounts, WowGuildNewsConfig
from utils.blizzard import (
    RateLimited,
    build_account_groups,
    check_rate_limit,
    clear_character_failure,
    get_asset_url,
    get_best_mythic_keys,
    get_profile_link,
    get_raiderio_score,
    make_pair_key,
    parse_known_mounts,
    record_character_failure,
    should_skip_character,
    should_update_mount_set,
)
from utils.cog import NerpyBotCog
from utils.errors import (
    NerpyInfraException,
    NerpyNotFoundError,
    NerpyPermissionError,
    NerpyUserException,
    NerpyValidationError,
)
from utils.helpers import notify_error, register_before_loop, send_paginated
from utils.permissions import validate_channel_permissions


class WowApiLanguage(Enum):
    """Language Enum for WoW API"""

    DE = "de_DE"
    EN = "en_US"
    EN_GB = "en_GB"


# Embed colors for guild news notifications
COLOR_ACHIEVEMENT = Color.gold()
COLOR_ENCOUNTER = Color.red()
COLOR_MOUNT = Color.purple()

# Stale character cleanup: remove mount data for characters gone from roster after this many days
STALE_DAYS = 30

_NOTIFICATION_STRINGS = {
    "en": {
        "achievement_title": "Achievement Earned!",
        "achievement_desc": "**{name}** ({realm}) has earned the achievement **{achievement}**",
        "mount_title": "New Mount Collected!",
        "mount_desc": "**{name}** ({realm}) obtained **{mount}**",
        "boss_title": "Boss Defeated!",
        "boss_desc": "**{name}** ({realm}) defeated **{boss}**",
        "boss_desc_mode": "**{name}** ({realm}) defeated **{boss}** ({mode})",
    },
    "de": {
        "achievement_title": "Erfolg errungen!",
        "achievement_desc": "**{name}** ({realm}) hat den Erfolg **{achievement}** errungen",
        "mount_title": "Neues Reittier erhalten!",
        "mount_desc": "**{name}** ({realm}) hat **{mount}** erhalten",
        "boss_title": "Boss besiegt!",
        "boss_desc": "**{name}** ({realm}) hat **{boss}** besiegt",
        "boss_desc_mode": "**{name}** ({realm}) hat **{boss}** besiegt ({mode})",
    },
}


@app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
@app_commands.guild_only()
class WorldofWarcraft(NerpyBotCog, GroupCog, group_name="wow"):
    """World of Warcraft API"""

    guildnews = app_commands.Group(name="guildnews", description="manage WoW guild news tracking")

    def __init__(self, bot):
        super().__init__(bot)
        self.config = bot.config
        self.client_id = self.config["wow"]["wow_id"]
        self.client_secret = self.config["wow"]["wow_secret"]
        self.regions = ["eu", "us"]

        # Realm cache: "slug-region" -> {"name": "Blackrock", "region": "eu", "slug": "blackrock"}
        self._realm_cache: dict[str, dict] = {}
        self._realm_cache_lock = asyncio.Lock()

        # Guild news config (optional section with defaults)
        gn_config = self.config["wow"].get("guild_news", {})
        self._poll_interval = gn_config.get("poll_interval_minutes", 15)
        self._mount_batch_size = gn_config.get("mount_batch_size", 20)
        self._track_mounts = gn_config.get("track_mounts", True)
        self._default_active_days = gn_config.get("active_days", 7)

        register_before_loop(bot, self._guild_news_loop, "Guild News")
        self._guild_news_loop.change_interval(minutes=self._poll_interval)
        self._guild_news_loop.start()

    def cog_unload(self):
        self._guild_news_loop.cancel()

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

    async def _parse_realm(self, realm: str) -> tuple[str, str]:
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
            raise NerpyNotFoundError(
                f"Unknown realm '{realm_slug}' in {region.upper()}. "
                f"Use the autocomplete suggestions or check your spelling."
            )

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

    # ── Armory command ──────────────────────────────────────────────────

    @app_commands.command(name="armory")
    async def _wow_armory(
        self,
        interaction: Interaction,
        name: str,
        realm: str,
        language: Literal["de", "en"] | None = "en",
    ):
        """
        search for character

        name and realm are required parameters.
        realm accepts autocomplete suggestions (e.g. "blackrock-eu") or a plain slug (defaults to EU).
        language is optional, defaults to English.
        """
        try:
            await interaction.response.defer()
            realm_slug, region = await self._parse_realm(realm)
            name = name.lower()
            profile = f"{region}/{realm_slug}/{name}"

            # noinspection PyTypeChecker
            character, profile_picture = self._get_character(realm_slug, region, name, language)

            if not isinstance(character, dict) or character.get("code") == 404:
                raise NerpyNotFoundError("No Character with this name found.")

            best_keys = get_best_mythic_keys(region, realm_slug, name)
            rio_score = get_raiderio_score(region, realm_slug, name)

            armory = get_profile_link("armory", profile)
            raiderio = get_profile_link("raiderio", profile)
            warcraftlogs = get_profile_link("warcraftlogs", profile)
            wowprogress = get_profile_link("wowprogress", profile)

            emb = Embed(
                title=f"{character['name']} | {realm_slug.capitalize()} | {region.upper()} | {character['active_spec']['name']} {character['character_class']['name']} | {character['equipped_item_level']} ilvl",
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

            if best_keys:
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

            await interaction.followup.send(embed=emb)
        except NerpyUserException as ex:
            await interaction.followup.send(str(ex), ephemeral=True)

    @_wow_armory.autocomplete("realm")
    async def _realm_autocomplete_handler(self, interaction: discord.Interaction, current: str):
        return await self._realm_autocomplete(interaction, current)

    # ── Guild News commands ─────────────────────────────────────────────

    @guildnews.command(name="setup")
    @checks.has_permissions(manage_channels=True)
    async def _guildnews_setup(
        self,
        interaction: Interaction,
        guild_name: str,
        realm: str,
        channel: TextChannel,
        language: Literal["de", "en"] | None = "en",
        active_days: int | None = None,
    ):
        """set up guild news tracking for a WoW guild [manage_channels]

        guild_name: WoW guild name (use dashes for spaces, e.g. my-guild)
        realm: Realm with region (e.g. blackrock-eu). Autocomplete available.
        channel: Discord channel for notifications
        """
        try:
            await interaction.response.defer(ephemeral=True)
            language = language or "en"
            realm_slug, region = await self._parse_realm(realm)
            name_slug = guild_name.lower().replace(" ", "-")

            # Validate the guild exists via API
            api = self._get_retailclient(region, language)
            roster = await asyncio.to_thread(api.guild_roster, realmSlug=realm_slug, nameSlug=name_slug)

            if isinstance(roster, dict) and roster.get("code") in (404, 403):
                raise NerpyNotFoundError(f"Guild '{guild_name}' not found on {realm_slug}-{region.upper()}.")

            guild_display = roster.get("guild", {}).get("name", guild_name)

            validate_channel_permissions(channel, interaction.guild, "view_channel", "send_messages", "embed_links")

            with self.bot.session_scope() as session:
                existing = WowGuildNewsConfig.get_existing(interaction.guild.id, name_slug, realm_slug, region, session)
                if existing:
                    raise NerpyValidationError(
                        f"Guild '{guild_display}' on {realm_slug}-{region.upper()} is already tracked "
                        f"(config #{existing.Id} in <#{existing.ChannelId}>)."
                    )

                config = WowGuildNewsConfig(
                    GuildId=interaction.guild.id,
                    ChannelId=channel.id,
                    WowGuildName=name_slug,
                    WowRealmSlug=realm_slug,
                    Region=region,
                    Language=language,
                    ActiveDays=active_days or self._default_active_days,
                    LastActivityTimestamp=datetime.now(UTC),
                    Enabled=True,
                    CreateDate=datetime.now(UTC),
                )
                session.add(config)

            await interaction.followup.send(
                f"Now tracking **{guild_display}** ({realm_slug}-{region.upper()}) in {channel.mention}. "
                f"First scan will establish a baseline silently.",
                ephemeral=True,
            )
        except NerpyUserException as ex:
            await interaction.followup.send(str(ex), ephemeral=True)

    @_guildnews_setup.autocomplete("realm")
    async def _guildnews_setup_realm_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._realm_autocomplete(interaction, current)

    async def _config_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[int]]:
        with self.bot.session_scope() as session:
            configs = WowGuildNewsConfig.get_all_by_guild(interaction.guild.id, session)
            choices = []
            for cfg in configs:
                status = "\u2705" if cfg.Enabled else "\u23f8\ufe0f"
                label = f"#{cfg.Id} {status} {cfg.WowGuildName} ({cfg.WowRealmSlug}-{cfg.Region.upper()})"
                if current and current not in str(cfg.Id) and current.lower() not in cfg.WowGuildName.lower():
                    continue
                choices.append(app_commands.Choice(name=label[:100], value=cfg.Id))
            return choices[:25]

    @guildnews.command(name="remove")
    @checks.has_permissions(manage_channels=True)
    async def _guildnews_remove(self, interaction: Interaction, config: int):
        """remove a guild news tracking config [manage_channels]"""
        with self.bot.session_scope() as session:
            cfg = WowGuildNewsConfig.get_by_id(config, interaction.guild.id, session)
            if not cfg:
                await interaction.response.send_message(f"Config #{config} not found.", ephemeral=True)
                return
            WowGuildNewsConfig.delete(config, interaction.guild.id, session)
        await interaction.response.send_message(f"Removed tracking config #{config}.", ephemeral=True)

    @guildnews.command(name="list")
    async def _guildnews_list(self, interaction: Interaction):
        """list all tracked WoW guilds for this server"""
        with self.bot.session_scope() as session:
            configs = WowGuildNewsConfig.get_all_by_guild(interaction.guild.id, session)
            if not configs:
                await interaction.response.send_message("No guild news configs for this server.", ephemeral=True)
                return
            output = ""
            for cfg in configs:
                channel = interaction.guild.get_channel(cfg.ChannelId)
                channel_name = f"#{channel.name}" if channel else f"#{cfg.ChannelId} (deleted)"
                status = "\u2705 Active" if cfg.Enabled else "\u23f8\ufe0f Paused"
                output += f"**#{cfg.Id}** {cfg.WowGuildName} (`{cfg.WowRealmSlug}-{cfg.Region.upper()}`)\n"
                output += f"> {cfg.Language} \u00b7 {status} \u00b7 Active Days: {cfg.ActiveDays}\n"
                output += f"> Channel: {channel_name}\n\n"
            await send_paginated(interaction, output, title="\u2694\ufe0f Guild News", color=0xFFB100, ephemeral=True)

    @guildnews.command(name="pause")
    @checks.has_permissions(manage_channels=True)
    async def _guildnews_pause(self, interaction: Interaction, config: int):
        """pause guild news tracking [manage_channels]"""
        with self.bot.session_scope() as session:
            cfg = WowGuildNewsConfig.get_by_id(config, interaction.guild.id, session)
            if not cfg:
                await interaction.response.send_message(f"Config #{config} not found.", ephemeral=True)
                return
            cfg.Enabled = False
        await interaction.response.send_message(f"Paused tracking for config #{config}.", ephemeral=True)

    @guildnews.command(name="resume")
    @checks.has_permissions(manage_channels=True)
    async def _guildnews_resume(self, interaction: Interaction, config: int):
        """resume guild news tracking [manage_channels]"""
        with self.bot.session_scope() as session:
            cfg = WowGuildNewsConfig.get_by_id(config, interaction.guild.id, session)
            if not cfg:
                await interaction.response.send_message(f"Config #{config} not found.", ephemeral=True)
                return
            cfg.Enabled = True
        await interaction.response.send_message(f"Resumed tracking for config #{config}.", ephemeral=True)

    @guildnews.command(name="edit")
    @checks.has_permissions(manage_channels=True)
    async def _guildnews_edit(
        self,
        interaction: Interaction,
        config: int,
        channel: TextChannel | None = None,
        language: Literal["de", "en"] | None = None,
        active_days: int | None = None,
    ):
        """edit a guild news tracking config [manage_channels]

        config: Config to edit (autocomplete shows tracked guilds)
        channel: Move notifications to this channel
        language: Change notification language (de/en)
        active_days: Change activity window (days)
        """
        if channel is None and language is None and active_days is None:
            await interaction.response.send_message(
                "Nothing to change. Specify at least one of: channel, language, active_days.", ephemeral=True
            )
            return

        if channel is not None:
            validate_channel_permissions(channel, interaction.guild, "view_channel", "send_messages", "embed_links")

        with self.bot.session_scope() as session:
            cfg = WowGuildNewsConfig.get_by_id(config, interaction.guild.id, session)
            if not cfg:
                await interaction.response.send_message(f"Config #{config} not found.", ephemeral=True)
                return

            changes = []
            if channel is not None:
                cfg.ChannelId = channel.id
                changes.append(f"channel \u2192 {channel.mention}")
            if language is not None:
                cfg.Language = language
                changes.append(f"language \u2192 {language}")
            if active_days is not None:
                cfg.ActiveDays = active_days
                changes.append(f"active_days \u2192 {active_days}")

            guild_label = f"**{cfg.WowGuildName}** ({cfg.WowRealmSlug}-{cfg.Region.upper()})"

        await interaction.response.send_message(
            f"Updated config #{config} for {guild_label}: {', '.join(changes)}.", ephemeral=True
        )

    @guildnews.command(name="check")
    async def _guildnews_check(self, interaction: Interaction, config: int):
        """trigger an immediate poll for testing [operator]"""
        if interaction.user.id not in self.bot.ops:
            raise NerpyPermissionError("This command is restricted to bot operators.")
        with self.bot.session_scope() as session:
            cfg = WowGuildNewsConfig.get_by_id(config, interaction.guild.id, session)
            if not cfg:
                await interaction.response.send_message(f"Config #{config} not found.", ephemeral=True)
                return
            if not cfg.Enabled:
                await interaction.response.send_message(f"Config #{config} is paused. Resume it first.", ephemeral=True)
                return

        await interaction.response.send_message(f"Running manual poll for config #{config}...", ephemeral=True)
        await self._poll_single_config(config, ignore_baseline=True)

    @_guildnews_remove.autocomplete("config")
    @_guildnews_pause.autocomplete("config")
    @_guildnews_resume.autocomplete("config")
    @_guildnews_edit.autocomplete("config")
    @_guildnews_check.autocomplete("config")
    async def _config_autocomplete_handler(self, interaction: Interaction, current: str):
        return await self._config_autocomplete(interaction, current)

    # ── Background task ─────────────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def _guild_news_loop(self):
        self.bot.log.debug("Start Guild News Loop!")
        try:
            with self.bot.session_scope() as session:
                configs = WowGuildNewsConfig.get_all_enabled(session)

            for config in configs:
                try:
                    await self._poll_single_config(config.Id)
                except Exception as ex:
                    self.bot.log.error(f"Guild news poll failed for config #{config.Id}: {ex}")

        except Exception as ex:
            self.bot.log.error(f"Guild news loop error: {ex}")
            await notify_error(self.bot, "Guild news background loop", ex)
        self.bot.log.debug("Stop Guild News Loop!")

    async def _poll_single_config(self, config_id: int, *, ignore_baseline: bool = False):
        """Poll a single guild news config for activity and mounts."""
        self.bot.log.debug(f"Guild news #{config_id}: starting poll")

        # Re-fetch from DB inside its own session for each phase
        with self.bot.session_scope() as session:
            config = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
            if not config or not config.Enabled:
                self.bot.log.debug(f"Guild news #{config_id}: config not found or disabled, skipping")
                return

            # Snapshot config values so we can use them outside the session
            channel_id = config.ChannelId
            wow_guild = config.WowGuildName
            realm = config.WowRealmSlug
            region = config.Region
            language = config.Language
            min_level = config.MinLevel
            active_days = config.ActiveDays
            last_activity_ts = config.LastActivityTimestamp
            if last_activity_ts and last_activity_ts.tzinfo is None:
                last_activity_ts = last_activity_ts.replace(tzinfo=UTC)
            cfg_id = config.Id

        if ignore_baseline:
            last_activity_ts = None
            self.bot.log.debug(f"Guild news #{cfg_id}: baseline ignored (manual check)")

        self.bot.log.debug(
            f"Guild news #{cfg_id}: polling {wow_guild} on {realm}-{region} (last_activity={last_activity_ts})"
        )

        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.bot.log.warning(f"Guild news config #{cfg_id}: channel {channel_id} not found, skipping.")
            return

        api = self._get_retailclient(region, language)

        # ── Phase 1: Guild Activity Feed ────────────────────────────
        await self._poll_activity(api, cfg_id, wow_guild, realm, last_activity_ts, channel, language)

        # ── Phase 2: Mount Tracking ─────────────────────────────────
        if self._track_mounts:
            await self._poll_mounts(api, cfg_id, wow_guild, realm, min_level, active_days, channel, language)
        else:
            self.bot.log.debug(f"Guild news #{cfg_id}: mount tracking disabled, skipping phase 2")

        self.bot.log.debug(f"Guild news #{cfg_id}: poll complete")

    async def _poll_activity(self, api, config_id, wow_guild, realm, last_activity_ts, channel, language="en"):
        """Fetch guild_activity and post new achievements/encounters."""
        activities = await self._call_api(
            api.guild_activity,
            config_id,
            "fetching activity feed",
            realmSlug=realm,
            nameSlug=wow_guild,
        )
        if activities is None:
            return

        if not isinstance(activities, dict) or "activities" not in activities:
            self.bot.log.debug(
                f"Guild news #{config_id}: no activities in response (keys: {list(activities.keys()) if isinstance(activities, dict) else type(activities).__name__})"
            )
            return

        total = len(activities["activities"])
        new_timestamp = last_activity_ts
        embeds_to_send = []

        for activity in activities["activities"]:
            ts_millis = activity.get("timestamp", 0)
            activity_time = datetime.fromtimestamp(ts_millis / 1000, tz=UTC)

            if last_activity_ts and activity_time <= last_activity_ts:
                continue

            if activity_time > (new_timestamp or datetime.min.replace(tzinfo=UTC)):
                new_timestamp = activity_time

            activity_type = activity.get("activity", {}).get("type", "")

            if activity_type == "CHARACTER_ACHIEVEMENT":
                ach_data = activity.get("character_achievement", {})
                character = ach_data.get("character", {})
                char_name = character.get("name", "Unknown")
                char_realm = character.get("realm", {}).get("name", realm)
                achievement = ach_data.get("achievement", {})
                ach_name = achievement.get("name", "Unknown Achievement")
                ach_id = achievement.get("id")
                strings = _NOTIFICATION_STRINGS.get(language, _NOTIFICATION_STRINGS["en"])
                emb = Embed(
                    title=strings["achievement_title"],
                    description=strings["achievement_desc"].format(
                        name=char_name, realm=char_realm, achievement=ach_name
                    ),
                    color=COLOR_ACHIEVEMENT,
                    timestamp=activity_time,
                )
                if ach_id:
                    try:
                        media = await asyncio.to_thread(api.achievement_media, achievementId=ach_id)
                        check_rate_limit(media)
                        icon_url = get_asset_url(media, "icon")
                        if icon_url:
                            emb.set_thumbnail(url=icon_url)
                    except RateLimited:
                        self.bot.log.warning(f"Guild news #{config_id}: rate limited fetching achievement media")
                    except Exception as ex:
                        self.bot.log.debug(f"Guild news #{config_id}: failed to fetch achievement icon: {ex}")
                embeds_to_send.append(emb)

            elif activity_type == "ENCOUNTER":
                enc_data = activity.get("encounter_completed", activity.get("character_achievement", {}))
                character = enc_data.get("character", {})
                char_name = character.get("name", "Unknown")
                char_realm = character.get("realm", {}).get("name", realm)
                encounter = enc_data.get("encounter", {})
                enc_name = encounter.get("name", "Unknown Encounter")
                enc_id = encounter.get("id")
                mode = enc_data.get("mode", {}).get("name", "")
                strings = _NOTIFICATION_STRINGS.get(language, _NOTIFICATION_STRINGS["en"])
                if mode:
                    desc = strings["boss_desc_mode"].format(name=char_name, realm=char_realm, boss=enc_name, mode=mode)
                else:
                    desc = strings["boss_desc"].format(name=char_name, realm=char_realm, boss=enc_name)
                emb = Embed(
                    title=strings["boss_title"],
                    description=desc,
                    color=COLOR_ENCOUNTER,
                    timestamp=activity_time,
                )
                if enc_id:
                    try:
                        journal = await asyncio.to_thread(api.journal_encounter, journalEncounterId=enc_id)
                        check_rate_limit(journal)
                        creatures = journal.get("creatures", [])
                        if creatures:
                            display_id = creatures[0].get("creature_display", {}).get("id")
                            if display_id:
                                display_media = await asyncio.to_thread(
                                    api.creature_display_media, creatureDisplayId=display_id
                                )
                                check_rate_limit(display_media)
                                boss_url = get_asset_url(display_media, "zoom")
                                if boss_url:
                                    emb.set_thumbnail(url=boss_url)
                    except RateLimited:
                        self.bot.log.warning(f"Guild news #{config_id}: rate limited fetching encounter media")
                    except Exception as ex:
                        self.bot.log.debug(f"Guild news #{config_id}: failed to fetch boss image: {ex}")
                embeds_to_send.append(emb)

            else:
                self.bot.log.debug(
                    f"Guild news #{config_id}: unknown activity type '{activity_type}', keys: {list(activity.keys())}"
                )

        self.bot.log.debug(
            f"Guild news #{config_id}: activity feed has {total} entries, {len(embeds_to_send)} new to announce"
        )

        # Send embeds oldest-first
        for emb in reversed(embeds_to_send):
            try:
                await channel.send(embed=emb)
            except HTTPException as ex:
                self.bot.log.warning(f"Guild news #{config_id}: failed to send embed: {ex}")

        # Update last activity timestamp
        if new_timestamp and new_timestamp != last_activity_ts:
            self.bot.log.debug(f"Guild news #{config_id}: advancing activity timestamp to {new_timestamp}")
            with self.bot.session_scope() as session:
                config = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
                if config:
                    config.LastActivityTimestamp = new_timestamp

    async def _poll_mounts(self, api, config_id, wow_guild, realm, min_level, active_days, channel, language="en"):
        """Check roster for new mount acquisitions.

        On initial sync (unbaselined characters exist), processes all batches
        continuously. After that, one batch per poll cycle.
        Prunes mount data for characters who left the guild after STALE_DAYS.
        Detects character renames via the profile API and migrates stored data.
        Backs off on Blizzard 429 rate limits.
        """
        roster = await self._call_api(
            api.guild_roster,
            config_id,
            "fetching roster for mount tracking",
            realmSlug=realm,
            nameSlug=wow_guild,
        )
        if roster is None:
            return

        if not isinstance(roster, dict) or "members" not in roster:
            self.bot.log.debug(f"Guild news #{config_id}: roster response has no members")
            return

        total_members = len(roster["members"])

        # Filter by min level and pick highest-level char per unique name+realm combo
        candidates = {}
        for member in roster["members"]:
            char = member.get("character", {})
            level = char.get("level", 0)
            if level < min_level:
                continue

            member_name = char.get("name", "").lower()
            member_realm = char.get("realm", {}).get("slug", realm)
            key = (member_name, member_realm)

            if key not in candidates or level > candidates[key]["level"]:
                candidates[key] = {"name": member_name, "realm": member_realm, "level": level}

        candidate_list = sorted(candidates.values(), key=lambda c: c["name"])
        candidate_keys = {(c["name"], c["realm"]) for c in candidate_list}

        self.bot.log.debug(
            f"Guild news #{config_id}: roster has {total_members} members, "
            f"{len(candidate_list)} unique candidates (lvl >= {min_level})"
        )

        # Prune mount data for characters who left the guild over STALE_DAYS ago
        stale_cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)
        with self.bot.session_scope() as session:
            deleted = WowCharacterMounts.delete_stale(config_id, candidate_keys, stale_cutoff, session)
            if deleted:
                self.bot.log.info(f"Guild news #{config_id}: pruned {deleted} stale character(s) from mount tracking")

        if not candidate_list:
            return

        # Load existing data, build account groups, determine initial sync
        with self.bot.session_scope() as session:
            existing = WowCharacterMounts.get_all_by_config(config_id, session)
            baselined_keys = {(e.CharacterName, e.RealmSlug) for e in existing}
            stored_mounts = {(e.CharacterName, e.RealmSlug): e.KnownMountIds for e in existing}

            config_record = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
            temporal_data = json.loads(config_record.AccountGroupData or "{}") if config_record else {}
            character_failures = temporal_data.pop("_failures", {})

        account_groups = build_account_groups(candidate_list, stored_mounts, temporal_data)

        # Log detected account clusters for debugging
        clusters: dict[int, list[str]] = {}
        for (name, realm), gid in account_groups.items():
            clusters.setdefault(gid, []).append(f"{name}:{realm}")
        multi = {gid: members for gid, members in clusters.items() if len(members) > 1}
        if multi:
            group_strs = [f"  group {gid}: {', '.join(members)}" for gid, members in multi.items()]
            self.bot.log.debug(f"Guild news #{config_id}: account groups:\n" + "\n".join(group_strs))
        else:
            self.bot.log.debug(
                f"Guild news #{config_id}: no account groups detected ({len(account_groups)} solo chars)"
            )

        reported_by_account = {}  # account_group_id -> set of already-reported mount IDs
        cycle_new_mounts = {}  # (name, realm) -> set of new mount IDs

        unbaselined = candidate_keys - baselined_keys
        initial_sync = len(unbaselined) > 0

        if initial_sync:
            self.bot.log.debug(
                f"Guild news #{config_id}: initial sync — {len(unbaselined)}/{len(candidate_keys)} "
                f"characters not yet baselined, will process all batches"
            )

        cutoff = datetime.now(UTC) - timedelta(days=active_days)
        semaphore = asyncio.Semaphore(5)
        rate_limited = asyncio.Event()
        total_stats = {
            "checked": 0,
            "skipped_error": 0,
            "skipped_inactive": 0,
            "skipped_degraded": 0,
            "skipped_404": 0,
            "baselined": 0,
            "new_mounts": 0,
        }

        async def _check_character(candidate):
            char_name = candidate["name"]
            char_realm = candidate["realm"]

            # Skip remaining work if we already hit a rate limit
            if rate_limited.is_set():
                return

            if should_skip_character(character_failures, char_name, char_realm):
                total_stats["skipped_404"] += 1
                return

            async with semaphore:
                profile = await self._call_api(
                    api.character_profile_summary,
                    config_id,
                    f"profile for {char_name}",
                    realmSlug=char_realm,
                    characterName=char_name,
                    rate_limited_event=rate_limited,
                    stats=total_stats,
                )
                if profile is None:
                    return

                if isinstance(profile, dict) and profile.get("code") in (404, 403):
                    self.bot.log.debug(f"Guild news #{config_id}: {char_name} returned {profile.get('code')}, skipping")
                    record_character_failure(character_failures, char_name, char_realm)
                    total_stats["skipped_error"] += 1
                    return

                clear_character_failure(character_failures, char_name, char_realm)

                last_login_ms = profile.get("last_login_timestamp", 0)
                if last_login_ms:
                    last_login = datetime.fromtimestamp(last_login_ms / 1000, tz=UTC)
                    if last_login < cutoff:
                        total_stats["skipped_inactive"] += 1
                        return

                mount_data = await self._call_api(
                    api.character_mounts_collection_summary,
                    config_id,
                    f"mounts for {char_name}",
                    realmSlug=char_realm,
                    characterName=char_name,
                    rate_limited_event=rate_limited,
                    stats=total_stats,
                )
                if mount_data is None:
                    return

                if not isinstance(mount_data, dict) or "mounts" not in mount_data:
                    self.bot.log.debug(f"Guild news #{config_id}: no mount data for {char_name}")
                    total_stats["skipped_error"] += 1
                    return

                current_mount_ids = sorted(
                    {m.get("mount", {}).get("id") for m in mount_data["mounts"] if m.get("mount")}
                )
                current_ids = set(current_mount_ids)

            total_stats["checked"] += 1

            # Detect name changes: the API returns the canonical name which may differ
            # from the roster slug we used to query. If there's an existing entry under
            # the old name with the same mount set, migrate it.
            api_name = profile.get("name", "").lower()

            # noinspection PyShadowingNames
            with self.bot.session_scope() as session:
                stored = WowCharacterMounts.get_by_character(config_id, char_name, char_realm, session)

                # Check for a renamed character: no entry under current name, but the
                # API returns a different canonical name that does have stored data.
                if stored is None and api_name and api_name != char_name:
                    old_entry = WowCharacterMounts.get_by_character(config_id, api_name, char_realm, session)
                    if old_entry:
                        self.bot.log.info(
                            f"Guild news #{config_id}: detected rename {api_name} -> {char_name}, migrating"
                        )
                        old_entry.CharacterName = char_name
                        old_entry.LastChecked = datetime.now(UTC)
                        stored = old_entry

                if stored is None:
                    self.bot.log.debug(f"Guild news #{config_id}: baseline for {char_name} — {len(current_ids)} mounts")
                    # noinspection PyShadowingNames
                    entry = WowCharacterMounts(
                        ConfigId=config_id,
                        CharacterName=char_name,
                        RealmSlug=char_realm,
                        KnownMountIds=json.dumps({"ids": sorted(current_ids), "last_count": len(current_ids)}),
                        LastChecked=datetime.now(UTC),
                    )
                    session.add(entry)
                    total_stats["baselined"] += 1
                else:
                    known_ids, last_count = parse_known_mounts(stored.KnownMountIds)
                    new_ids = current_ids - known_ids
                    removed_ids = known_ids - current_ids

                    self.bot.log.debug(
                        f"Guild news #{config_id}: {char_name} mount diff — "
                        f"known={len(known_ids)} current={len(current_ids)} new={len(new_ids)} "
                        f"removed={len(removed_ids)} last_count={last_count}"
                    )

                    # Churn detection: if IDs both appeared and disappeared with no
                    # net count increase, it's faction variant ID swapping — not real
                    # new mounts.
                    if removed_ids and new_ids:
                        net_new = len(current_ids) - last_count
                        if net_new <= 0:
                            self.bot.log.debug(
                                f"Guild news #{config_id}: {char_name} ID churn detected "
                                f"(+{len(new_ids)}/-{len(removed_ids)}, net={net_new}), "
                                f"suppressing announcements"
                            )
                            new_ids = set()

                    if not should_update_mount_set(last_count, len(current_ids)):
                        self.bot.log.warning(
                            f"Guild news #{config_id}: {char_name} mount count dropped "
                            f"(last_count={last_count} current={len(current_ids)}) — "
                            f"likely degraded API response, skipping update"
                        )
                        total_stats["skipped_degraded"] += 1
                        return

                    if new_ids:
                        mount_names = {}
                        for m in mount_data["mounts"]:
                            mid = m.get("mount", {}).get("id")
                            if mid in new_ids:
                                mount_names[mid] = m.get("mount", {}).get("name", f"Mount #{mid}")

                        display_name = profile.get("name", char_name.capitalize())
                        display_realm = profile.get("realm", {}).get("name", char_realm)

                        account_id = account_groups.get((char_name, char_realm), (char_name, char_realm))
                        already_reported = reported_by_account.setdefault(account_id, set())

                        for mid, mname in mount_names.items():
                            if mid in already_reported:
                                self.bot.log.debug(
                                    f"Guild news #{config_id}: skipping {mname} for {display_name} "
                                    f"(already reported for account group {account_id})"
                                )
                                continue
                            already_reported.add(mid)
                            self.bot.log.debug(f"Guild news #{config_id}: {display_name} got new mount: {mname}")
                            strings = _NOTIFICATION_STRINGS.get(language, _NOTIFICATION_STRINGS["en"])
                            emb = Embed(
                                title=strings["mount_title"],
                                description=strings["mount_desc"].format(
                                    name=display_name, realm=display_realm, mount=mname
                                ),
                                color=COLOR_MOUNT,
                                timestamp=datetime.now(UTC),
                            )
                            try:
                                mount_info = await asyncio.to_thread(api.mount, mountId=mid)
                                check_rate_limit(mount_info)
                                displays = mount_info.get("creature_displays", [])
                                if displays:
                                    display_id = displays[0].get("id")
                                    if display_id:
                                        display_media = await asyncio.to_thread(
                                            api.creature_display_media, creatureDisplayId=display_id
                                        )
                                        check_rate_limit(display_media)
                                        mount_url = get_asset_url(display_media, "zoom")
                                        if mount_url:
                                            emb.set_thumbnail(url=mount_url)
                            except RateLimited:
                                self.bot.log.warning(f"Guild news #{config_id}: rate limited fetching mount media")
                            except Exception as exc:
                                self.bot.log.debug(f"Guild news #{config_id}: failed to fetch mount image: {exc}")
                            try:
                                await channel.send(embed=emb)
                            except HTTPException as exc:
                                self.bot.log.warning(f"Guild news #{config_id}: failed to send mount embed: {exc}")

                        total_stats["new_mounts"] += len(new_ids)

                    stored.KnownMountIds = json.dumps(
                        {
                            "ids": sorted(known_ids | current_ids),
                            "last_count": len(current_ids),
                        }
                    )
                    stored.LastChecked = datetime.now(UTC)
                    cycle_new_mounts[(char_name, char_realm)] = new_ids

        # Process batches — loop through all during initial sync, single batch otherwise
        with self.bot.session_scope() as session:
            config = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
            if not config:
                return
            offset = config.RosterOffset or 0

        batch_num = 0
        baselined_before = total_stats["baselined"]
        start_offset = offset
        while True:
            batch = candidate_list[offset : offset + self._mount_batch_size]
            if not batch:
                offset = 0
                batch = candidate_list[: self._mount_batch_size]

            new_offset = offset + self._mount_batch_size
            if new_offset >= len(candidate_list):
                new_offset = 0

            batch_num += 1
            self.bot.log.debug(
                f"Guild news #{config_id}: mount batch #{batch_num} offset {offset}->{new_offset}, "
                f"checking {len(batch)} characters"
            )

            with self.bot.session_scope() as session:
                config = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
                if config:
                    config.RosterOffset = new_offset

            await asyncio.gather(*[_check_character(c) for c in batch])

            self.bot.log.debug(
                f"Guild news #{config_id}: batch #{batch_num} done — "
                f"checked={total_stats['checked']}, baselined={total_stats['baselined']}, "
                f"new_mounts={total_stats['new_mounts']}, "
                f"skipped_inactive={total_stats['skipped_inactive']}, skipped_error={total_stats['skipped_error']}, "
                f"skipped_degraded={total_stats['skipped_degraded']}, skipped_404={total_stats['skipped_404']}"
            )

            # Rate limited — stop immediately, resume from current offset next cycle
            if rate_limited.is_set():
                self.bot.log.warning(
                    f"Guild news #{config_id}: stopping mount poll due to rate limit, "
                    f"will resume from offset {new_offset} next cycle"
                )
                break

            offset = new_offset

            if not initial_sync:
                break

            # Full rotation completed — stop if no new baselines were added this rotation
            if offset == start_offset or (offset == 0 and start_offset >= len(candidate_list)):
                if total_stats["baselined"] == baselined_before:
                    self.bot.log.debug(
                        f"Guild news #{config_id}: full rotation with no new baselines, "
                        f"remaining characters are inactive/inaccessible"
                    )
                    break
                # New rotation — reset the counter
                baselined_before = total_stats["baselined"]
                start_offset = offset

        # Update AccountGroupData (temporal correlation + failure tracking)
        if cycle_new_mounts or character_failures:
            with self.bot.session_scope() as session:
                config_record = session.query(WowGuildNewsConfig).filter(WowGuildNewsConfig.Id == config_id).first()
                if config_record:
                    temporal_data = json.loads(config_record.AccountGroupData or "{}")
                    temporal_data.pop("_failures", None)

                    if cycle_new_mounts:
                        chars_with_new = [(k, v) for k, v in cycle_new_mounts.items() if v]
                        for (ka, new_a), (kb, new_b) in itertools.combinations(chars_with_new, 2):
                            pair_key = make_pair_key(ka, kb)
                            entry = temporal_data.setdefault(pair_key, {"correlated": 0, "uncorrelated": 0})
                            if new_a & new_b:
                                entry["correlated"] += 1
                            else:
                                entry["uncorrelated"] += 1
                            entry["last_updated"] = datetime.now(UTC).isoformat()

                    # Prune failures for characters no longer in roster, then merge back
                    pruned_failures = {
                        k: v for k, v in character_failures.items() if tuple(k.split(":", 1)) in candidate_keys
                    }
                    if pruned_failures:
                        temporal_data["_failures"] = pruned_failures

                    config_record.AccountGroupData = json.dumps(temporal_data)

        if initial_sync and not rate_limited.is_set():
            self.bot.log.debug(
                f"Guild news #{config_id}: initial sync finished in {batch_num} batches — "
                f"baselined={total_stats['baselined']}, skipped_inactive={total_stats['skipped_inactive']}, "
                f"skipped_error={total_stats['skipped_error']}, skipped_degraded={total_stats['skipped_degraded']}, "
                f"skipped_404={total_stats['skipped_404']}"
            )


async def setup(bot):
    """adds this module to the bot"""
    if "wow" in bot.config:
        await bot.add_cog(WorldofWarcraft(bot))
    else:
        raise NerpyInfraException("Config not found.")
