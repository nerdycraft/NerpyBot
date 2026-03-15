# -*- coding: utf-8 -*-
"""Blizzard/WoW API utilities, account resolution, and helper functions.

Consolidates all WoW-related helper logic:
- Blizzard API response handling (rate limits, asset extraction)
- Character failure tracking
- Mount set comparison heuristics
- Account grouping via name/mount/temporal signals
- Raider.io API helpers
- Profile URL builders
"""

import difflib
import itertools
import json
import unicodedata
from urllib.parse import quote
from collections import Counter, defaultdict
from datetime import UTC, datetime
from datetime import datetime as dt
from datetime import timedelta as td

import requests


# ── Blizzard API helpers ─────────────────────────────────────────────


class RateLimited(Exception):
    """Raised when a Blizzard API call returns HTTP 429."""


def check_rate_limit(response) -> None:
    """Raise RateLimited if the API response indicates a 429."""
    if isinstance(response, dict) and response.get("code") == 429:
        raise RateLimited()


def get_asset_url(response, key: str = "icon") -> str | None:
    """Extract an asset URL from a Blizzard media response."""
    if not isinstance(response, dict):
        return None
    for asset in response.get("assets", []):
        if asset.get("key") == key:
            return asset.get("value")
    return None


# Professions mappable in the crafting order board.
# Excludes gathering (Skinning, Mining, Herbalism).
# Cooking is included for role-based coordination (e.g. food tables) even though
# it does not support the in-game crafting order system.
CRAFTING_PROFESSIONS = {
    "Blacksmithing": 164,
    "Leatherworking": 165,
    "Tailoring": 197,
    "Engineering": 202,
    "Enchanting": 333,
    "Alchemy": 171,
    "Inscription": 773,
    "Jewelcrafting": 755,
    "Cooking": 185,
}

# Locale strings used in API calls per (region, language) combination.
_BLIZZ_LOCALE = {
    ("eu", "de"): "de_DE",
    ("eu", "en"): "en_GB",
    ("us", "en"): "en_US",
    ("us", "de"): "en_US",
    ("kr", "en"): "ko_KR",
    ("tw", "en"): "zh_TW",
}

# Maps bot language codes to Blizzard API locale strings for multi-locale extraction.
# item_search returns all locales in the response dict — we use this to build locale caches.
_BOT_LANG_TO_BLIZZ: dict[str, str] = {
    "en": "en_GB",
    "de": "de_DE",
}

# Expansion prefix → canonical WoW expansion name.
_EXPANSION_MAP: dict[str, str] = {
    "classic": "Classic",
    "outland": "The Burning Crusade",
    "northrend": "Wrath of the Lich King",
    "cataclysm": "Cataclysm",
    "pandaria": "Mists of Pandaria",
    "draenor": "Warlords of Draenor",
    "legion": "Legion",
    "kul tiran": "Battle for Azeroth",
    "zandalari": "Battle for Azeroth",
    "shadowlands": "Shadowlands",
    "dragon isles": "Dragonflight",
    "khaz algar": "The War Within",
    "midnight": "Midnight",
}

# Category names that produce no cacheable item recipes.
_SKIP_CATEGORIES: frozenset[str] = frozenset({"Recrafting", "Appendix I - Terms", "Appendix II - Stats", "Smelting"})

# Pre-sorted expansion keys (longest first) for prefix matching in _resolve_expansion.
_EXPANSION_KEYS: tuple[str, ...] = tuple(sorted(_EXPANSION_MAP, key=len, reverse=True))


def _resolve_expansion(tier_name: str) -> str:
    """Map a skill tier name to a canonical WoW expansion name.

    Scans _EXPANSION_KEYS from longest key to shortest and returns the first
    match where the tier name starts with that key.  Falls back to the raw
    tier name if nothing matches.
    """
    tier_lower = tier_name.lower()
    for key in _EXPANSION_KEYS:
        if tier_lower.startswith(key):
            return _EXPANSION_MAP[key]
    return tier_name


def _extract_locale_dict(source: dict | None) -> dict[str, str]:
    """Extract non-English bot locale strings from a Blizzard multi-locale name dict.

    Returns a dict of {bot_lang: localized_name} for every non-English language in
    _BOT_LANG_TO_BLIZZ whose Blizzard locale key is present in ``source``.
    Returns an empty dict (falsy) when ``source`` is not a dict or has no matches.
    """
    if not isinstance(source, dict):
        return {}
    return {
        bot_lang: source[blizz_loc]
        for bot_lang, blizz_loc in _BOT_LANG_TO_BLIZZ.items()
        if bot_lang != "en" and blizz_loc in source
    }


async def sync_crafting_recipes(
    bot,
    region: str = "eu",
    language: str = "en",
    expansion: str | None = None,
    progress_callback=None,
) -> dict:
    """Sync WoW crafting recipes into CraftingRecipeCache.

    Walks all expansion skill tiers for every CRAFTING_PROFESSIONS entry.
    For each recipe:
      - Strategy 1 (Shadowlands and older): ``crafted_item`` is present in the
        recipe response; fetch item details directly via ``item()``.
      - Strategy 2 (Dragonflight+): no ``crafted_item``; search by recipe name
        via ``item_search()`` to resolve item class/subclass metadata.

    Housing detection is category-based: any category whose name contains
    "house decor" (case-insensitive) is treated as housing.  The Blizzard
    decor index API is no longer used.

    Expansion scoping: if ``expansion`` is set (e.g. ``"Midnight"``), gear
    recipes from non-matching tiers are skipped.  Housing recipes from ALL
    tiers are always cached regardless of the expansion filter.

    Returns {"crafted": N, "housing": N, "errors": N, "duration_seconds": float}.
    """
    import asyncio
    import logging
    import time

    from blizzapi import Language, Region, RetailClient

    from models.wow import RECIPE_TYPE_CRAFTED, RECIPE_TYPE_HOUSING, CraftingRecipeCache

    log = logging.getLogger("nerpybot")
    start = time.monotonic()

    client_id = bot.config.get("wow", {}).get("wow_id")
    client_secret = bot.config.get("wow", {}).get("wow_secret")
    if not client_id or not client_secret:
        raise ValueError("WoW API credentials (wow_id / wow_secret) not configured")

    locale = _BLIZZ_LOCALE.get((region, language), "en_GB")
    blizz_lang = (
        Language.German if language == "de" else (Language.English_GreatBritian if region == "eu" else Language.English)
    )
    api = RetailClient(
        client_id=client_id,
        client_secret=client_secret,
        region=Region(region),
        language=blizz_lang,
    )

    sem = asyncio.Semaphore(15)
    errors = 0
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc)

    async def _call(fn, *args, required: bool = True, **kwargs):
        nonlocal errors
        async with sem:
            for attempt in range(3):
                try:
                    result = await asyncio.to_thread(fn, *args, **kwargs)
                    check_rate_limit(result)
                    return result
                except RateLimited:
                    log.warning("sync_crafting_recipes: rate limited")
                    errors += 1
                    return None
                except json.JSONDecodeError as exc:
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    if required:
                        log.debug("sync_crafting_recipes: API call failed: %s", exc)
                        errors += 1
                    return None
                except Exception as exc:
                    if required:
                        log.debug("sync_crafting_recipes: API call failed: %s", exc)
                        errors += 1
                    return None
        await asyncio.sleep(0.05)  # throttle outside semaphore — releases slot immediately

    all_rows: list[dict] = []

    async def _sync_profession(prof_name: str, prof_id: int):
        prof_data = await _call(api.profession, professionId=prof_id)
        if not isinstance(prof_data, dict):
            return
        skill_tiers = prof_data.get("skill_tiers", [])
        await asyncio.gather(*[_sync_tier(prof_name, prof_id, tier) for tier in skill_tiers])

    async def _sync_tier(prof_name: str, prof_id: int, tier: dict):
        tier_id = tier.get("id")
        tier_name = tier.get("name", "")
        if not tier_id:
            return
        expansion_name = _resolve_expansion(tier_name)
        tier_data = await _call(api.profession_skill_tier, professionId=prof_id, skillTierId=tier_id)
        if not isinstance(tier_data, dict):
            return
        tasks = []
        for cat in tier_data.get("categories", []):
            cat_name = cat.get("name", "")
            is_housing_cat = "house decor" in cat_name.lower()
            # Skip categories that produce no cacheable items.
            if cat_name in _SKIP_CATEGORIES:
                continue
            # Skip non-housing recipes from non-matching expansions (if filter is set).
            if expansion and not is_housing_cat:
                if expansion.lower() not in expansion_name.lower():
                    continue
            for recipe_stub in cat.get("recipes", []):
                recipe_id = recipe_stub.get("id")
                if recipe_id:
                    tasks.append(_sync_recipe(prof_name, prof_id, recipe_id, expansion_name, cat_name, is_housing_cat))
        await asyncio.gather(*tasks)

    async def _sync_recipe(
        prof_name: str, prof_id: int, recipe_id: int, expansion_name: str, category_name: str, is_housing: bool
    ):
        recipe_data = await _call(api.recipe, recipeId=recipe_id)
        if not isinstance(recipe_data, dict):
            return

        item_id = item_name = item_class_id = item_class_name = item_subclass_id = item_subclass_name = None
        icon_url = None
        item_name_locales: dict | None = None
        item_class_name_locales: dict | None = None
        item_subclass_name_locales: dict | None = None

        # Strategy 1: crafted_item present (Shadowlands and older).
        crafted_item = recipe_data.get("crafted_item") or recipe_data.get("alliance_crafted_item") or {}
        if isinstance(crafted_item, dict):
            item_id = crafted_item.get("id")
            item_name = crafted_item.get("name")

        if item_id:
            item_data = await _call(api.item, itemId=item_id)
            if isinstance(item_data, dict):
                ic = item_data.get("item_class") or {}
                isc = item_data.get("item_subclass") or {}
                item_class_id = ic.get("id")
                item_class_name = ic.get("name")
                item_subclass_id = isc.get("id")
                item_subclass_name = isc.get("name")
            media = await _call(api.item_media, itemId=item_id, required=False)
            icon_url = get_asset_url(media, "icon")
        else:
            # Strategy 2: item_search by recipe name (Dragonflight+).
            # item_search returns localized name dicts: {"en_GB": "name", ...}
            recipe_name = recipe_data.get("name", "")
            if recipe_name:
                search_result = await _call(
                    api.item_search,
                    fields={"name." + locale: quote(recipe_name, safe=""), "_pageSize": 5},
                )
                if isinstance(search_result, dict):
                    for hit in search_result.get("results", []):
                        data = hit.get("data", {})
                        name_val = data.get("name", {})
                        hit_name = name_val.get(locale, "") if isinstance(name_val, dict) else name_val
                        if hit_name == recipe_name:
                            item_id = data.get("id")
                            ic = data.get("item_class") or {}
                            isc = data.get("item_subclass") or {}
                            ic_name_raw = ic.get("name") if isinstance(ic, dict) else None
                            isc_name_raw = isc.get("name") if isinstance(isc, dict) else None
                            item_class_id = ic.get("id") if isinstance(ic, dict) else None
                            item_subclass_id = isc.get("id") if isinstance(isc, dict) else None

                            # Always use en_GB for canonical columns; fall back to recipe_name if absent.
                            item_name = (
                                name_val.get("en_GB", recipe_name) if isinstance(name_val, dict) else recipe_name
                            )
                            item_class_name = ic_name_raw.get("en_GB") if isinstance(ic_name_raw, dict) else ic_name_raw
                            item_subclass_name = (
                                isc_name_raw.get("en_GB") if isinstance(isc_name_raw, dict) else isc_name_raw
                            )

                            # Build locale dicts for non-English bot languages from the multi-locale dicts.
                            item_name_locales = _extract_locale_dict(name_val) or None
                            item_class_name_locales = _extract_locale_dict(ic_name_raw) or None
                            item_subclass_name_locales = _extract_locale_dict(isc_name_raw) or None

                            media = await _call(api.item_media, itemId=item_id, required=False)
                            icon_url = get_asset_url(media, "icon")
                            break

        # Skip recipes that produce no identifiable item.
        if not item_id and not item_name:
            return

        if not item_name:
            item_name = recipe_data.get("name", f"Recipe #{recipe_id}")

        if not icon_url:
            media = await _call(api.recipe_media, recipeId=recipe_id, required=False)
            icon_url = get_asset_url(media, "icon")

        all_rows.append(
            {
                "RecipeId": recipe_id,
                "ProfessionId": prof_id,
                "ProfessionName": prof_name,
                "ItemId": item_id,
                "ItemName": item_name,
                "ItemNameLocales": item_name_locales,
                "IconUrl": icon_url,
                "RecipeType": RECIPE_TYPE_HOUSING if is_housing else RECIPE_TYPE_CRAFTED,
                "ItemClassName": item_class_name,
                "ItemClassNameLocales": item_class_name_locales,
                "ItemClassId": item_class_id,
                "ItemSubClassName": item_subclass_name,
                "ItemSubClassNameLocales": item_subclass_name_locales,
                "ItemSubClassId": item_subclass_id,
                "ExpansionName": expansion_name,
                "CategoryName": category_name,
                "LastSynced": now,
            }
        )

    if progress_callback:
        await progress_callback("Starting recipe sync…")

    await asyncio.gather(*[_sync_profession(name, pid) for name, pid in CRAFTING_PROFESSIONS.items()])

    # ── Upsert into database ──────────────────────────────────────────────
    def _upsert():
        with bot.session_scope() as session:
            CraftingRecipeCache.delete_all(session)
            for row in all_rows:
                session.add(CraftingRecipeCache(**row))

    await asyncio.to_thread(_upsert)

    crafted_count = sum(1 for r in all_rows if r["RecipeType"] == RECIPE_TYPE_CRAFTED)
    housing_count = sum(1 for r in all_rows if r["RecipeType"] == RECIPE_TYPE_HOUSING)
    duration = round(time.monotonic() - start, 1)

    log.info(
        "sync_crafting_recipes: done — crafted=%d housing=%d errors=%d duration=%.1fs",
        crafted_count,
        housing_count,
        errors,
        duration,
    )

    return {
        "crafted": crafted_count,
        "housing": housing_count,
        "errors": errors,
        "duration_seconds": duration,
    }


# ── Mount set comparison ─────────────────────────────────────────────


def should_update_mount_set(known_count: int, current_count: int) -> bool:
    """Check whether the stored mount set should be updated with current API data.

    Guards against degraded Blizzard API responses that return fewer mounts
    than reality. Small removals (e.g., Blizzard revoking bugged mounts) are
    allowed; large drops are blocked. Compares the real API counts (not the
    union set size) to avoid false positives from accumulated variant IDs.
    """
    if known_count == 0:
        return True
    dropped = known_count - current_count
    threshold = max(10, int(known_count * 0.1))
    return dropped <= threshold


# ── Character failure tracking ───────────────────────────────────────

FAILURE_THRESHOLD = 3


def record_character_failure(failures: dict[str, dict[str, int | str]], char_name: str, char_realm: str) -> None:
    """Record a 404/403 failure for a character."""
    key = f"{char_name}:{char_realm}"
    entry = failures.setdefault(key, {"count": 0})
    entry["count"] += 1
    entry["last"] = datetime.now(UTC).isoformat()


def should_skip_character(failures: dict[str, dict[str, int | str]], char_name: str, char_realm: str) -> bool:
    """Return True if the character has reached the failure threshold."""
    entry = failures.get(f"{char_name}:{char_realm}")
    return entry is not None and entry.get("count", 0) >= FAILURE_THRESHOLD


def clear_character_failure(failures: dict[str, dict[str, int | str]], char_name: str, char_realm: str) -> None:
    """Remove a character's failure record after a successful check."""
    failures.pop(f"{char_name}:{char_realm}", None)


# ── Raider.io helpers ────────────────────────────────────────────────

_RAIDERIO_BASE_URL = "https://raider.io/api/v1/characters/profile"


def get_raiderio_score(region: str, realm: str, name: str) -> float | None:
    """Fetch the current Mythic+ score from Raider.io."""
    args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_scores_by_season:current"
    req = requests.get(f"{_RAIDERIO_BASE_URL}{args}")

    if req.status_code == 200:
        resp = req.json()
        if len(resp["mythic_plus_scores_by_season"]) > 0:
            return resp["mythic_plus_scores_by_season"][0]["scores"]["all"]
    return None


# noinspection GrazieInspection
def get_best_mythic_keys(region: str, realm: str, name: str) -> list[dict] | None:
    """Fetch best mythic+ key runs from Raider.io."""
    args = f"?region={region}&realm={realm}&name={name}&fields=mythic_plus_best_runs"
    req = requests.get(f"{_RAIDERIO_BASE_URL}{args}")

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


# ── Profile URL builder ──────────────────────────────────────────────

_PROFILE_SITES = {
    "armory": "https://worldofwarcraft.com/en-us/character",
    "raiderio": "https://raider.io/characters",
    "warcraftlogs": "https://www.warcraftlogs.com/character",
    "wowprogress": "https://www.wowprogress.com/character",
}


def get_profile_link(site: str, profile: str) -> str:
    """Generate a URL for an external WoW profile site."""
    base = _PROFILE_SITES.get(site)
    return f"{base}/{profile}"


# ── Account resolution ───────────────────────────────────────────────
# Heuristics for grouping WoW characters by likely Battle.net account.
# Uses five signals: name patterns, achievement points, mount set identity,
# mount count similarity, and temporal correlation.

AP_TOLERANCE = 100  # achievement points tolerance for timing drift between polls
MOUNT_COUNT_MIN = 20  # minimum mount count for count-based comparison


def parse_known_mounts(raw: str) -> tuple[set[int], int, int | None]:
    """Parse stored mount data, supporting both legacy and new formats.

    Legacy format: JSON list of mount IDs, e.g. [1, 2, 3]
    New format: JSON dict with union set, real API count, and optional
                achievement points, e.g. {"ids": [1, 2, 3], "last_count": 73,
                "achievement_points": 15430}

    Returns (known_id_set, last_api_count, achievement_points_or_none).
    For legacy data, last_api_count equals the list length and AP is None.
    """
    data = json.loads(raw)
    if isinstance(data, dict):
        ids: list[int] = data["ids"]
        return set(ids), int(data["last_count"]), data.get("achievement_points")
    mount_list: list[int] = data
    return set(mount_list), len(mount_list), None


def strip_diacritics(name: str) -> str:
    """Normalize a character name for comparison by removing diacritics.

    Examples: 'Morzâ' -> 'morza', 'MorzA' -> 'morza'
    """
    nfkd = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def name_similarity_score(name_a: str, name_b: str) -> float:
    """Score 0.0-1.0 indicating how likely two character names belong to the same player.

    Checks (in priority order):
    1. Exact match after diacritics removal (score 0.9)
    2. Shared prefix >= 3 chars covering >= 40% of the shorter name (score 0.3-0.5)
    3. General sequence similarity >= 0.6 (score 0.3-0.5)
    """
    norm_a = strip_diacritics(name_a)
    norm_b = strip_diacritics(name_b)

    if norm_a == norm_b:
        return 0.9

    prefix_len = 0
    for a, b in zip(norm_a, norm_b):
        if a != b:
            break
        prefix_len += 1
    shorter = min(len(norm_a), len(norm_b))
    if shorter > 0 and prefix_len >= 3 and prefix_len / shorter >= 0.4:
        coverage = prefix_len / shorter
        if prefix_len >= 5:
            length_bonus = min(0.35, 0.07 * (prefix_len - 4))
            return min(0.9, 0.3 + 0.2 * coverage + length_bonus)
        return 0.3 + 0.2 * coverage

    ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    if ratio >= 0.6:
        return ratio * 0.5

    return 0.0


def temporal_score(correlated: int, uncorrelated: int) -> float:
    """Compute confidence from temporal mount/achievement correlation.

    Weak with few events, scales with evidence, caps at 0.8.
    Variance (uncorrelated events) weakens the signal.
    """
    if correlated <= 0:
        return 0.0
    if uncorrelated < 0:
        uncorrelated = 0
    ratio = correlated / (correlated + uncorrelated)
    confidence = ratio * min(1.0, correlated / 5)
    return min(0.8, confidence)


def account_confidence(
    name_a: str,
    name_b: str,
    mounts_a: str | None,
    mounts_b: str | None,
    temporal_data: dict | None,
) -> float:
    """Combine all signals into a single same-account confidence score.

    Signals (in evaluation order):
    1. Name similarity (diacritics, shared prefix, sequence matching)
    2. Achievement points (account-wide, deterministic within tolerance)
    3. Mount set identity (Jaccard on full collection, 50+ mounts)
    4. Mount count similarity (supplementary, 20+ mounts)
    5. Temporal correlation (mount acquisition patterns across poll cycles)

    Args:
        name_a: Lowercased character name (first).
        name_b: Lowercased character name (second).
        mounts_a: JSON-encoded mount data (or None if no stored data).
        mounts_b: JSON-encoded mount data (or None if no stored data).
        temporal_data: Dict with 'correlated' and 'uncorrelated' counts (or None).

    Returns: 0.0-1.0 confidence score.
    """
    scores = []

    ns = name_similarity_score(name_a, name_b)
    if ns > 0:
        scores.append(ns)

    if mounts_a and mounts_b:
        try:
            ids_a, count_a, ap_a = parse_known_mounts(mounts_a)
            ids_b, count_b, ap_b = parse_known_mounts(mounts_b)
        except (ValueError, TypeError, KeyError):
            pass  # corrupt data — skip mount signals
        else:
            # Achievement points: account-wide and deterministic.
            if ap_a is not None and ap_b is not None and ap_a > 0 and ap_b > 0:
                if abs(ap_a - ap_b) <= AP_TOLERANCE:
                    scores.append(0.9)

            # Mount set identity: Jaccard on the full collection.
            if len(ids_a) > 50 and len(ids_b) > 50:
                overlap = len(ids_a & ids_b)
                total = len(ids_a | ids_b)
                jaccard = overlap / total
                if jaccard >= 0.95:
                    scores.append(0.9 * jaccard)

            # Mount count similarity: weaker supplementary signal.
            if count_a >= MOUNT_COUNT_MIN and count_b >= MOUNT_COUNT_MIN:
                count_ratio = min(count_a, count_b) / max(count_a, count_b)
                if count_ratio >= 0.90:
                    scores.append(0.3 + 0.2 * count_ratio)

    if temporal_data:
        ts = temporal_score(temporal_data.get("correlated", 0), temporal_data.get("uncorrelated", 0))
        if ts > 0:
            scores.append(ts)

    if not scores:
        return 0.0

    base = max(scores)
    confirming = sum(1 for s in scores if s > 0.2)
    boost = max(0, (confirming - 1)) * 0.1
    return min(1.0, base + boost)


CONFIDENCE_THRESHOLD = 0.7


def make_pair_key(char_a_key: tuple, char_b_key: tuple) -> str:
    """Create a canonical pair key for temporal data lookup.

    Keys are sorted alphabetically so (A,B) and (B,A) produce the same key.
    Format: 'name:realm|name:realm'
    """
    a = f"{char_a_key[0]}:{char_a_key[1]}"
    b = f"{char_b_key[0]}:{char_b_key[1]}"
    return "|".join(sorted([a, b]))


MIN_PREFIX_FAMILY_LEN = 3
MIN_PREFIX_FAMILY_SIZE = 3


def detect_prefix_families(
    candidates: list[dict],
) -> dict[tuple, set[tuple]]:
    """Find groups of same-realm characters sharing a common name prefix.

    Scans prefix lengths from longest to shortest. Each character is assigned
    to the largest family it belongs to (longest prefix with enough members).

    Args:
        candidates: List of {"name": str, "realm": str, ...} dicts.

    Returns:
        Mapping of (name, realm) -> set of (name, realm) family peers.
        Characters not in any family are absent from the mapping.
    """
    by_realm: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for c in candidates:
        by_realm[c["realm"]].append((strip_diacritics(c["name"]), c["name"], c["realm"]))

    family_map: dict[tuple, set[tuple]] = {}
    for realm, chars in by_realm.items():
        if len(chars) < MIN_PREFIX_FAMILY_SIZE:
            continue
        for prefix_len in range(12, MIN_PREFIX_FAMILY_LEN - 1, -1):
            groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for norm, orig, r in chars:
                if len(norm) >= prefix_len:
                    groups[norm[:prefix_len]].append((orig, r))
            for members in groups.values():
                if len(members) >= MIN_PREFIX_FAMILY_SIZE:
                    member_set = set(members)
                    for m in members:
                        if m not in family_map or len(member_set) > len(family_map[m]):
                            family_map[m] = member_set
    return family_map


def build_account_groups(
    candidates: list[dict],
    stored_mounts: dict,
    temporal_data: dict,
) -> dict[tuple, int]:
    """Cluster characters into likely-same-account groups (two-phase).

    Phase 1: Pairwise comparison using name similarity, mount overlap, and
    temporal correlation.  Long shared prefixes (7+ chars) can now cross the
    confidence threshold on their own.

    Phase 2: Prefix family extension.  If 3+ same-realm characters share a
    name prefix and a majority of them are already grouped from phase 1, the
    remaining members are pulled into the group.  This handles short-prefix
    naming conventions (e.g. "alu*") where individual pairs score too low but
    the cluster pattern is unmistakable.

    Args:
        candidates: List of {"name": str, "realm": str, ...} dicts.
        stored_mounts: Mapping of (name, realm) -> JSON-encoded mount ID string (or None).
        temporal_data: Mapping of pair_key -> {"correlated": int, "uncorrelated": int}.

    Returns:
        Mapping of (name, realm) -> group_id (int). Characters in the same group
        are believed to belong to the same Battle.net account.
    """
    # Union-Find for grouping
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    keys = [(c["name"], c["realm"]) for c in candidates]
    for k in keys:
        parent[k] = k

    # Phase 1: Check all pairs for confidence above threshold
    for ca, cb in itertools.combinations(candidates, 2):
        key_a = (ca["name"], ca["realm"])
        key_b = (cb["name"], cb["realm"])

        mounts_a = stored_mounts.get(key_a)
        mounts_b = stored_mounts.get(key_b)

        pair_key = make_pair_key(key_a, key_b)
        t_data = temporal_data.get(pair_key)

        conf = account_confidence(ca["name"], cb["name"], mounts_a, mounts_b, t_data)
        if conf >= CONFIDENCE_THRESHOLD:
            union(key_a, key_b)

    # Phase 2: Prefix family extension
    # If a majority of a prefix family (3+ same-realm chars sharing a prefix)
    # is already grouped by phase 1 signals, extend the group to all members.
    phase1_root = {k: find(k) for k in keys}
    families = detect_prefix_families(candidates)
    seen_families: set[int] = set()
    for key in keys:
        family = families.get(key)
        if family is None or id(family) in seen_families:
            continue
        seen_families.add(id(family))
        phase1_roots = [phase1_root[m] for m in family if m in phase1_root]
        if not phase1_roots:
            continue
        root_counts = Counter(phase1_roots)
        dominant_root, max_count = root_counts.most_common(1)[0]
        min_required = (len(family) + 1) // 2
        if max_count >= min_required:
            anchor = next(m for m in family if phase1_root.get(m) == dominant_root)
            for m in family:
                union(anchor, m)

    # Convert to sequential group IDs
    group_map = {}
    next_id = 0
    result = {}
    for k in keys:
        root = find(k)
        if root not in group_map:
            group_map[root] = next_id
            next_id += 1
        result[k] = group_map[root]

    return result
