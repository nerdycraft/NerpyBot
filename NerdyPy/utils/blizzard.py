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
import re
import unicodedata
import urllib.error
import urllib.request
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

_WOWHEAD_TOOLTIP_URL = "https://nether.wowhead.com/tooltip/recipe/{}?dataEnv=1&locale=0"
_WOWHEAD_ICON_URL = "https://wow.zamimg.com/images/wow/icons/large/{}.jpg"
_ITEM_LINK_RE = re.compile(r'href="(?:/\w+)?/item=(\d+)/([^"]+)"')
_EQUIP_SLOT_RE = re.compile(
    r"<td>(Head|Neck|Shoulder|Back|Chest|Shirt|Tabard|Wrist|Hands|Waist|Legs|Feet"
    r"|Finger|Trinket|Main Hand|Off Hand|One-Hand|Two-Hand|Ranged|Held In Off-hand)</td>"
)


async def _resolve_recipe_wowhead(recipe_id, log):
    """Resolve a recipe to its crafted item via the Wowhead tooltip API.

    Returns dict with item_id, item_name, is_equippable, icon_url — or None.
    """
    import asyncio

    def _fetch():
        url = _WOWHEAD_TOOLTIP_URL.format(recipe_id)
        req = urllib.request.Request(url, headers={"User-Agent": "NerpyBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    try:
        data = await asyncio.to_thread(_fetch)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.debug("[recipe-sync]   recipe %d: not found on Wowhead (404)", recipe_id)
        else:
            log.warning("[recipe-sync]   recipe %d: Wowhead HTTP %d", recipe_id, e.code)
        return None
    except Exception as ex:
        log.warning("[recipe-sync]   recipe %d: Wowhead fetch failed: %s", recipe_id, ex)
        return None

    quality = data.get("quality", -1)
    if quality == -1:
        log.debug("[recipe-sync]   '%s' (recipe=%d): utility recipe, skipping", data.get("name", "?"), recipe_id)
        return None

    tooltip = data.get("tooltip", "")
    matches = _ITEM_LINK_RE.findall(tooltip)
    if not matches:
        log.debug("[recipe-sync]   '%s' (recipe=%d): no item link in tooltip", data.get("name", "?"), recipe_id)
        return None

    # Last item link is the crafted item (reagents appear first)
    item_id_str, item_slug = matches[-1]
    item_id = int(item_id_str)
    item_name = data.get("name", item_slug.replace("-", " ").title())
    is_equippable = bool(_EQUIP_SLOT_RE.search(tooltip))
    icon = data.get("icon", "")
    icon_url = _WOWHEAD_ICON_URL.format(icon) if icon else None

    log.debug(
        "[recipe-sync]   '%s' (recipe=%d) → item %d (equip=%s)",
        item_name,
        recipe_id,
        item_id,
        is_equippable,
    )
    return {"item_id": item_id, "item_name": item_name, "is_equippable": is_equippable, "icon_url": icon_url}


async def sync_crafting_recipes(api, session, log, progress_callback=None):
    """Fetch craftable recipes and cache them via Blizzard API + Wowhead tooltips.

    Uses Blizzard API for profession structure (tiers, recipe lists) and
    Wowhead tooltip API for recipe→item resolution.

    Args:
        api: blizzapi.RetailClient instance (for profession/tier data)
        session: SQLAlchemy session
        log: logger instance
        progress_callback: async callable(str) for progress updates

    Returns:
        (recipe_count, profession_count) tuple

    Raises:
        RateLimited: if Blizzard returns 429 during profession/tier fetches
    """
    import asyncio

    from models.wow import CraftingRecipeCache

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

        prof_data = await asyncio.to_thread(api.profession, prof_id)
        check_rate_limit(prof_data)

        skill_tiers = prof_data.get("skill_tiers", [])
        if not skill_tiers:
            log.debug("[recipe-sync] %s (id=%d): no skill tiers, skipping", prof_name, prof_id)
            continue

        # Take top 2 tiers by ID (current + previous expansion)
        sorted_tiers = sorted(skill_tiers, key=lambda t: t["id"], reverse=True)[:2]
        log.debug(
            "[recipe-sync] %s: using %d tier(s): %s",
            prof_name,
            len(sorted_tiers),
            ", ".join(f"'{t.get('name', t['id'])}'" for t in sorted_tiers),
        )

        prof_recipe_count = 0
        for tier in sorted_tiers:
            tier_id = tier["id"]
            tier_name = tier.get("name", f"Tier {tier_id}")

            tier_data = await asyncio.to_thread(api.profession_skill_tier, prof_id, tier_id)
            check_rate_limit(tier_data)

            tier_recipes = [
                recipe_entry for cat in tier_data.get("categories", []) for recipe_entry in cat.get("recipes", [])
            ]

            if not tier_recipes:
                log.debug("[recipe-sync] %s: tier '%s' has 0 recipes", prof_name, tier_name)
                continue

            log.debug("[recipe-sync] %s: tier '%s' — %d recipes", prof_name, tier_name, len(tier_recipes))

            # Resolve all recipes in this tier concurrently (capped at 15)
            sem = asyncio.Semaphore(15)

            async def _resolve_throttled(rid):
                async with sem:
                    result = await _resolve_recipe_wowhead(rid, log)
                    await asyncio.sleep(0.05)  # courtesy throttle
                    return rid, result

            tasks = [_resolve_throttled(r["id"]) for r in tier_recipes]
            results = await asyncio.gather(*tasks)

            now = datetime.now(UTC)
            for recipe_id, resolved in results:
                if resolved is None or not resolved["is_equippable"]:
                    continue

                item_id = resolved["item_id"]
                item_name = resolved["item_name"]
                icon_url = resolved["icon_url"]

                existing = session.query(CraftingRecipeCache).filter(CraftingRecipeCache.RecipeId == recipe_id).first()

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

        log.debug("[recipe-sync] %s: %d recipes cached", prof_name, prof_recipe_count)
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
