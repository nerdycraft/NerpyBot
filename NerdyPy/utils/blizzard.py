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
# Uses three signals: name patterns, mount set identity, and temporal correlation.


def parse_known_mounts(raw: str) -> tuple[set[int], int]:
    """Parse stored mount data, supporting both legacy and new formats.

    Legacy format: JSON list of mount IDs, e.g. [1, 2, 3]
    New format: JSON dict with union set and real API count,
                e.g. {"ids": [1, 2, 3], "last_count": 73}

    Returns (known_id_set, last_api_count).
    For legacy data, last_api_count equals the list length.
    """
    data = json.loads(raw)
    if isinstance(data, dict):
        ids: list[int] = data["ids"]
        return set(ids), int(data["last_count"])
    mount_list: list[int] = data
    return set(mount_list), len(mount_list)


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
        return 0.3 + 0.2 * (prefix_len / shorter)

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

    Args:
        name_a: Lowercased character name (first).
        name_b: Lowercased character name (second).
        mounts_a: JSON-encoded mount ID list (or None if no stored data).
        mounts_b: JSON-encoded mount ID list (or None if no stored data).
        temporal_data: Dict with 'correlated' and 'uncorrelated' counts (or None).

    Returns: 0.0-1.0 confidence score.
    """
    scores = []

    ns = name_similarity_score(name_a, name_b)
    if ns > 0:
        scores.append(ns)

    if mounts_a and mounts_b:
        try:
            ids_a, _ = parse_known_mounts(mounts_a)
            ids_b, _ = parse_known_mounts(mounts_b)
        except (ValueError, TypeError, KeyError):
            pass  # corrupt data — skip mount signal
        else:
            if len(ids_a) > 50 and len(ids_b) > 50:
                overlap = len(ids_a & ids_b)
                total = len(ids_a | ids_b)
                jaccard = overlap / total
                if jaccard >= 0.95:
                    scores.append(0.9 * jaccard)

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


def build_account_groups(
    candidates: list[dict],
    stored_mounts: dict,
    temporal_data: dict,
) -> dict[tuple, int]:
    """Cluster characters into likely-same-account groups.

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

    # Check all pairs for confidence above threshold
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
