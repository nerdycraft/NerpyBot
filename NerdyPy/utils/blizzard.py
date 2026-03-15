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

# Number of expansion skill tiers to sync per profession (most recent N tiers).
PROFESSION_TIER_COUNT = 2

# Blizzard API base URIs per region (mirrors blizzapi internal constant).
_BLIZZ_API_BASE = {
    "eu": "https://eu.api.blizzard.com",
    "us": "https://us.api.blizzard.com",
    "kr": "https://kr.api.blizzard.com",
    "tw": "https://tw.api.blizzard.com",
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

# Housing keyword patterns: profession skill tier category names that indicate
# housing/decoration recipes. Used as a fallback when the decor API is unavailable.
_HOUSING_KEYWORDS = {"housing", "decor", "decoration", "furniture", "fixture"}


async def sync_crafting_recipes(
    bot,
    region: str = "eu",
    language: str = "en",
    progress_callback=None,
) -> dict:
    """Sync WoW crafting recipes into CraftingRecipeCache.

    Phase A — Profession tier walk (RecipeType="crafted"):
        Walk top PROFESSION_TIER_COUNT skill tiers for every CRAFTING_PROFESSIONS
        entry, then recipe() → item() → cache all recipes with item_class metadata.

    Phase B — Housing decor API (RecipeType="housing"):
        Try GET /data/wow/decor/index.  Fall back to filtering "crafted" tiers by
        housing-keyword category names if the decor API is unavailable.

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
            try:
                result = await asyncio.to_thread(fn, *args, **kwargs)
                check_rate_limit(result)
                await asyncio.sleep(0.05)
                return result
            except RateLimited:
                log.warning("sync_crafting_recipes: rate limited")
                errors += 1
                return None
            except Exception as exc:
                if required:
                    log.debug("sync_crafting_recipes: API call failed: %s", exc)
                    errors += 1
                return None

    # ── Phase A: profession tier walk ────────────────────────────────────
    phase_a_rows: list[dict] = []

    async def _sync_profession(prof_name: str, prof_id: int):
        prof_data = await _call(api.profession, professionId=prof_id)
        if not isinstance(prof_data, dict):
            return
        skill_tiers = prof_data.get("skill_tiers", [])
        tiers = skill_tiers[-PROFESSION_TIER_COUNT:] if len(skill_tiers) >= PROFESSION_TIER_COUNT else skill_tiers
        await asyncio.gather(*[_sync_tier(prof_name, prof_id, tier) for tier in tiers])

    async def _sync_tier(prof_name: str, prof_id: int, tier: dict):
        tier_id = tier.get("id")
        tier_name = tier.get("name", "")
        if not tier_id:
            return
        tier_data = await _call(api.profession_skill_tier, professionId=prof_id, skillTierId=tier_id)
        if not isinstance(tier_data, dict):
            return
        tasks = []
        for cat in tier_data.get("categories", []):
            cat_name = cat.get("name", "")
            for recipe_stub in cat.get("recipes", []):
                recipe_id = recipe_stub.get("id")
                if recipe_id:
                    tasks.append(_sync_recipe(prof_name, prof_id, recipe_id, tier_name, cat_name))
        await asyncio.gather(*tasks)

    async def _sync_recipe(prof_name: str, prof_id: int, recipe_id: int, expansion_name: str, category_name: str):
        recipe_data = await _call(api.recipe, recipeId=recipe_id)
        if not isinstance(recipe_data, dict):
            return

        crafted_item = recipe_data.get("crafted_item") or recipe_data.get("alliance_crafted_item") or {}
        item_id = crafted_item.get("id") if isinstance(crafted_item, dict) else None
        item_name = crafted_item.get("name") if isinstance(crafted_item, dict) else None
        if not item_name:
            item_name = recipe_data.get("name", f"Recipe #{recipe_id}")

        item_class_id = item_class_name = item_subclass_id = item_subclass_name = None
        icon_url = None

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

        if not icon_url:
            media = await _call(api.recipe_media, recipeId=recipe_id, required=False)
            icon_url = get_asset_url(media, "icon")

        phase_a_rows.append(
            {
                "RecipeId": recipe_id,
                "ProfessionId": prof_id,
                "ProfessionName": prof_name,
                "ItemId": item_id,
                "ItemName": item_name,
                "IconUrl": icon_url,
                "RecipeType": RECIPE_TYPE_CRAFTED,
                "ItemClassName": item_class_name,
                "ItemClassId": item_class_id,
                "ItemSubClassName": item_subclass_name,
                "ItemSubClassId": item_subclass_id,
                "ExpansionName": expansion_name,
                "CategoryName": category_name,
                "LastSynced": now,
            }
        )

    if progress_callback:
        await progress_callback("Starting profession tier walk…")

    await asyncio.gather(*[_sync_profession(name, pid) for name, pid in CRAFTING_PROFESSIONS.items()])

    # ── Phase B: housing decor API ────────────────────────────────────────
    phase_b_rows: list[dict] = []
    base_url = _BLIZZ_API_BASE.get(region, _BLIZZ_API_BASE["eu"])
    namespace = f"static-{region}"

    if progress_callback:
        await progress_callback(f"Fetching housing decor index… ({len(phase_a_rows)} crafted recipes buffered)")

    async def _fetch_decor_index():
        url = f"{base_url}/data/wow/decor/index?namespace={namespace}&locale={locale}"
        try:
            async with sem:
                result = await asyncio.to_thread(api.get, url)
                check_rate_limit(result)
                await asyncio.sleep(0.05)
                return result
        except (RateLimited, Exception) as exc:
            log.debug("sync_crafting_recipes: decor/index unavailable: %s", exc)
            return None

    decor_data = await _fetch_decor_index()
    decor_items = decor_data.get("decors", []) if isinstance(decor_data, dict) else []

    if decor_items:

        async def _parse_decor(decor_stub: dict):
            decor_id = decor_stub.get("id")
            if not decor_id:
                return
            url = f"{base_url}/data/wow/decor/{decor_id}?namespace={namespace}&locale={locale}"
            try:
                async with sem:
                    detail = await asyncio.to_thread(api.get, url)
                    check_rate_limit(detail)
                    await asyncio.sleep(0.05)
            except (RateLimited, Exception):
                return
            if not isinstance(detail, dict):
                return

            source = detail.get("source") or {}
            prof_info = source.get("profession") if isinstance(source, dict) else None
            recipe_id = (source.get("recipe") or {}).get("id") if isinstance(source, dict) else None
            if not recipe_id:
                recipe_id = decor_id

            if not prof_info:
                return
            prof_id = prof_info.get("id")
            prof_name = prof_info.get("name", "Unknown")
            if not prof_id:
                return

            expansion_name = (detail.get("expansion") or {}).get("name")
            item_name = detail.get("name", f"Decor #{decor_id}")
            item_id = (detail.get("item") or {}).get("id")
            icon_url = None
            if item_id:
                media = await _call(api.item_media, itemId=item_id, required=False)
                icon_url = get_asset_url(media, "icon")

            phase_b_rows.append(
                {
                    "RecipeId": recipe_id,
                    "ProfessionId": prof_id,
                    "ProfessionName": prof_name,
                    "ItemId": item_id,
                    "ItemName": item_name,
                    "IconUrl": icon_url,
                    "RecipeType": RECIPE_TYPE_HOUSING,
                    "ItemClassName": None,
                    "ItemClassId": None,
                    "ItemSubClassName": None,
                    "ItemSubClassId": None,
                    "ExpansionName": expansion_name,
                    "CategoryName": "Housing",
                    "LastSynced": now,
                }
            )

        await asyncio.gather(*[_parse_decor(d) for d in decor_items])
    else:
        # Fallback: scan the crafted tier rows for housing-keyword categories.
        seen_recipe_ids: set[int] = set()
        for row in phase_a_rows:
            cat = (row.get("CategoryName") or "").lower()
            rid = row["RecipeId"]
            if rid not in seen_recipe_ids and any(kw in cat for kw in _HOUSING_KEYWORDS):
                seen_recipe_ids.add(rid)
                phase_b_rows.append({**row, "RecipeType": RECIPE_TYPE_HOUSING})

    # ── Upsert into database ──────────────────────────────────────────────
    all_rows = phase_a_rows + phase_b_rows

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
