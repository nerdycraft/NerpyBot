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


# Only crafting professions that support the crafting order system.
# Excludes gathering (Skinning, Mining, Herbalism) and Cooking.
CRAFTING_PROFESSIONS = {
    "Blacksmithing": 164,
    "Leatherworking": 165,
    "Tailoring": 197,
    "Engineering": 202,
    "Enchanting": 333,
    "Alchemy": 171,
    "Inscription": 773,
    "Jewelcrafting": 755,
}


async def _blizzard_item_search(api, recipe_name, region="eu", locale="en_US"):
    """Search for items by name using the Blizzard Item Search API.

    Uses raw HTTP because blizzapi doesn't expose the search endpoint.
    Returns list of matching items with id, name, is_equippable, etc.
    """
    import asyncio

    # Get OAuth token from blizzapi's internal state
    if not getattr(api, "_access_token", None):
        # Force token acquisition by making a lightweight call
        await asyncio.to_thread(api.professions_index)

    token = getattr(api, "_access_token", None)
    if not token:
        return []

    def _do_search():
        url = f"https://{region}.api.blizzard.com/data/wow/search/item"
        params = {
            "namespace": f"static-{region}",
            f"name.{locale}": recipe_name,
            "orderby": "id:desc",
            "_page": 1,
        }
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 429:
            raise RateLimited()
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("results", [])

    return await asyncio.to_thread(_do_search)


async def _resolve_recipe_item(api, recipe_id, recipe_name, log):
    """Resolve a recipe to its crafted item.

    Tries the recipe detail API first (``api.recipe()`` → ``crafted_item`` →
    ``api.item()``), giving a direct item ID with no name matching required.
    Falls back to the item search API when ``crafted_item`` is absent (common
    for quality-tiered recipes in TWW/Midnight).

    Returns:
        dict with ``item_id``, ``item_name``, ``is_equippable``, ``is_bop``
        or ``None`` if no valid item could be resolved.
    """
    import asyncio

    # Method 1: Recipe detail API → crafted_item → item detail
    try:
        recipe_detail = await asyncio.to_thread(api.recipe, recipe_id)
        check_rate_limit(recipe_detail)
        crafted_item = recipe_detail.get("crafted_item")
        if crafted_item:
            item_id = crafted_item["id"]
            item_name = crafted_item.get("name", recipe_name)
            item_detail = await asyncio.to_thread(api.item, item_id)
            check_rate_limit(item_detail)

            is_equippable = item_detail.get("is_equippable", False)
            binding_type = item_detail.get("preview_item", {}).get("binding", {}).get("type")
            is_bop = binding_type == "ON_ACQUIRE"

            log.debug(
                "[recipe-sync]   '%s' (recipe=%d) → item '%s' (id=%d) via recipe detail (equip=%s, bop=%s)",
                recipe_name,
                recipe_id,
                item_name,
                item_id,
                is_equippable,
                is_bop,
            )
            return {"item_id": item_id, "item_name": item_name, "is_equippable": is_equippable, "is_bop": is_bop}

        log.debug(
            "[recipe-sync]   '%s' (recipe=%d): no crafted_item in recipe detail (quality-tiered?)",
            recipe_name,
            recipe_id,
        )
    except RateLimited:
        raise
    except Exception as ex:
        log.debug("[recipe-sync]   '%s' (recipe=%d): recipe detail failed: %s", recipe_name, recipe_id, ex)

    # Method 2: Fall back to item search by name
    try:
        results = await _blizzard_item_search(api, recipe_name)
    except RateLimited:
        raise
    except Exception as ex:
        log.debug("[recipe-sync]   '%s': item search failed: %s", recipe_name, ex)
        return None

    for result in results:
        item_data = result.get("data", {})
        name_obj = item_data.get("name", {})
        item_name_en = name_obj.get("en_US") or name_obj.get("en_GB") or ""

        if item_name_en != recipe_name:
            continue

        item_id = item_data.get("id")
        is_equippable = item_data.get("is_equippable", False)
        binding_type = item_data.get("preview_item", {}).get("binding", {}).get("type")
        is_bop = binding_type == "ON_ACQUIRE"

        log.debug(
            "[recipe-sync]   '%s' → item '%s' (id=%d) via search (equip=%s, bop=%s)",
            recipe_name,
            item_name_en,
            item_id,
            is_equippable,
            is_bop,
        )
        return {"item_id": item_id, "item_name": item_name_en, "is_equippable": is_equippable, "is_bop": is_bop}

    log.debug(
        "[recipe-sync]   '%s' (recipe=%d): no item found (%d search results, no exact match)",
        recipe_name,
        recipe_id,
        len(results),
    )
    return None


async def _detect_current_tier(api, prof_id, skill_tiers, log):
    """Detect the current expansion tier by sampling recipes for BoP items.

    Iterates tiers from highest ID to lowest. For each tier, samples recipes
    from diverse categories (up to 2 per category, max 10 total) and resolves
    them via the recipe detail API + item search fallback. The first tier with
    at least one BoP or equippable item is the current expansion.
    """
    import asyncio

    if not skill_tiers:
        log.debug("[recipe-sync] No skill tiers for profession %d, skipping", prof_id)
        return None, None

    sorted_tiers = sorted(skill_tiers, key=lambda t: t["id"], reverse=True)

    # Track highest tier data from the loop to avoid a duplicate API call on fallback
    first_tier = None
    first_tier_data = None

    for tier in sorted_tiers:
        tier_id = tier["id"]
        tier_name = tier.get("name", f"Tier {tier_id}")

        tier_data = await asyncio.to_thread(api.profession_skill_tier, prof_id, tier_id)
        check_rate_limit(tier_data)

        if first_tier is None:
            first_tier = tier
            first_tier_data = tier_data

        # Sample from diverse categories — take up to 2 recipes from each category
        sample_recipes = []
        for cat in tier_data.get("categories", []):
            for recipe_entry in cat.get("recipes", [])[:2]:
                sample_recipes.append(recipe_entry)
            if len(sample_recipes) >= 10:
                sample_recipes = sample_recipes[:10]
                break

        if not sample_recipes:
            log.debug("[recipe-sync] Tier '%s' (id=%d) has no recipes, skipping", tier_name, tier_id)
            continue

        log.debug(
            "[recipe-sync] Tier '%s' (id=%d): sampling %d recipes from %d categories",
            tier_name,
            tier_id,
            len(sample_recipes),
            len(tier_data.get("categories", [])),
        )

        # Check if any sampled recipe produces a BoP/equippable item
        for recipe_entry in sample_recipes:
            recipe_id = recipe_entry.get("id")
            recipe_name = recipe_entry.get("name", "")
            if not recipe_name or not recipe_id:
                continue

            resolved = await _resolve_recipe_item(api, recipe_id, recipe_name, log)
            if resolved and (resolved["is_equippable"] or resolved["is_bop"]):
                log.debug(
                    "[recipe-sync] Tier '%s' (id=%d): confirmed as current expansion via '%s'",
                    tier_name,
                    tier_id,
                    resolved["item_name"],
                )
                return tier, tier_data

        log.debug("[recipe-sync] Tier '%s' (id=%d): no BoP/equippable items found, trying next", tier_name, tier_id)

    # Fallback: return highest tier (already fetched in the loop — no duplicate API call)
    log.warning("[recipe-sync] No BoP items found in any tier for profession %d, falling back to highest", prof_id)
    return first_tier, first_tier_data


async def sync_crafting_recipes(api, session, log, progress_callback=None):
    """Fetch craftable recipes from Blizzard API and cache them (bot-global).

    Args:
        api: blizzapi.RetailClient instance
        session: SQLAlchemy session
        log: logger instance
        progress_callback: async callable(str) for progress updates

    Returns:
        (recipe_count, profession_count) tuple

    Raises:
        RateLimited: if Blizzard returns 429 mid-sync
    """
    import asyncio

    from models.wow import CraftingRecipeCache

    # Step 1: Get all professions, filter to crafting-only
    professions_data = await asyncio.to_thread(api.professions_index)
    check_rate_limit(professions_data)

    professions = professions_data.get("professions", [])
    crafting_prof_ids = set(CRAFTING_PROFESSIONS.values())
    professions = [p for p in professions if p["id"] in crafting_prof_ids]
    log.debug("[recipe-sync] Found %d crafting professions from API", len(professions))

    recipe_count = 0
    profession_count = 0

    for prof in professions:
        prof_id = prof["id"]
        prof_name = prof.get("name", f"Profession {prof_id}")

        if progress_callback:
            await progress_callback(f"Scanning **{prof_name}**... ({recipe_count} recipes found so far)")

        # Step 2: Get profession detail → skill tiers
        prof_data = await asyncio.to_thread(api.profession, prof_id)
        check_rate_limit(prof_data)

        skill_tiers = prof_data.get("skill_tiers", [])
        if not skill_tiers:
            log.debug("[recipe-sync] %s (id=%d): no skill tiers, skipping", prof_name, prof_id)
            continue

        # Step 3: Detect correct tier (current expansion)
        current_tier, tier_data = await _detect_current_tier(api, prof_id, skill_tiers, log)
        if current_tier is None:
            log.debug("[recipe-sync] %s (id=%d): could not detect current tier, skipping", prof_name, prof_id)
            continue
        tier_id = current_tier["id"]
        tier_name = current_tier.get("name", f"Tier {tier_id}")
        log.debug(
            "[recipe-sync] %s (id=%d): using tier '%s' (id=%d)",
            prof_name,
            prof_id,
            tier_name,
            tier_id,
        )

        # Step 4: Collect all recipes from this tier
        categories = tier_data.get("categories", [])
        tier_recipes = []
        for cat in categories:
            for recipe_entry in cat.get("recipes", []):
                tier_recipes.append(recipe_entry)

        if not tier_recipes:
            log.debug(
                "[recipe-sync] %s: tier '%s' has %d categories but 0 recipes", prof_name, tier_name, len(categories)
            )
            continue

        log.debug(
            "[recipe-sync] %s: %d recipes in %d categories, searching items...",
            prof_name,
            len(tier_recipes),
            len(categories),
        )

        prof_recipe_count = 0
        for recipe_entry in tier_recipes:
            recipe_id = recipe_entry["id"]
            recipe_name = recipe_entry.get("name", f"Recipe {recipe_id}")

            # Step 5: Resolve recipe → item via recipe detail API or item search fallback
            resolved = await _resolve_recipe_item(api, recipe_id, recipe_name, log)
            if resolved is None:
                continue

            if not resolved["is_equippable"] and not resolved["is_bop"]:
                log.debug(
                    "[recipe-sync]   %s (id=%d): item not equippable/BoP, skipping",
                    recipe_name,
                    recipe_id,
                )
                continue

            item_id = resolved["item_id"]
            item_name = resolved["item_name"]

            # Step 6: Get item media → icon URL
            try:
                media_data = await asyncio.to_thread(api.item_media, item_id)
                check_rate_limit(media_data)
                icon_url = get_asset_url(media_data, "icon")
            except Exception:
                log.debug("[recipe-sync]   item %d: failed to fetch icon, continuing without", item_id)
                icon_url = None

            # Step 7: Upsert into cache (bot-global, keyed by RecipeId)
            existing = session.query(CraftingRecipeCache).filter(CraftingRecipeCache.RecipeId == recipe_id).first()

            now = datetime.now(UTC)
            if existing:
                existing.ItemId = item_id
                existing.ItemName = item_name
                existing.IconUrl = icon_url
                existing.ProfessionId = prof_id
                existing.ProfessionName = prof_name
                existing.LastSynced = now
            else:
                session.add(
                    CraftingRecipeCache(
                        ProfessionId=prof_id,
                        ProfessionName=prof_name,
                        RecipeId=recipe_id,
                        ItemId=item_id,
                        ItemName=item_name,
                        IconUrl=icon_url,
                        LastSynced=now,
                    )
                )

            prof_recipe_count += 1
            recipe_count += 1

        log.debug(
            "[recipe-sync] %s: %d recipes cached out of %d total", prof_name, prof_recipe_count, len(tier_recipes)
        )
        if prof_recipe_count > 0:
            profession_count += 1

    log.debug("[recipe-sync] Done. %d recipes across %d professions", recipe_count, profession_count)
    return recipe_count, profession_count


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
