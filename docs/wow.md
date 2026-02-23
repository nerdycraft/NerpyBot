# World of Warcraft Module

Blizzard API integration for character lookups and guild news tracking. Uses the `blizzapi` library for WoW Profile API access and Raider.io for Mythic+ data.

## Commands

### `/wow armory <name> <realm> [language]`

Look up a WoW character profile.

| Parameter  | Type                  | Default      | Description                                                                                                                                          |
| ---------- | --------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`     | `str`                 | _(required)_ | Character name                                                                                                                                       |
| `realm`    | `str`                 | _(required)_ | Realm with region (e.g., `blackrock-eu`, `thrall-us`). Slash commands offer autocomplete suggestions. Plain slugs (e.g., `blackrock`) default to EU. |
| `language` | `Literal["de", "en"]` | `"en"`       | Response language                                                                                                                                    |

**Realm autocomplete:** On first use, the bot fetches all EU and US realms from the Blizzard API and caches them. Users get filtered suggestions as they type. Plain slugs (e.g., `blackrock`) default to EU; append `-us` for US realms (e.g., `blackrock-us`).

**Supports DM usage** — one of the few commands that works outside guilds.

**Aliases:** `/wow search`, `/wow char`

**Embed layout:**

```
+---------------------------------------------+
|  CharName | Realm | EU | Fury Warrior | 620i |
|  (link to armory)                            |
|  [Avatar]  Male Orc                          |
|                                              |
|  Level: 80    Faction: Horde    Guild: Name  |
|                                              |
|  Best M+ Keys:                  M+ Score:    |
|  +15 - ARA - 28:30              2450.5       |
|  +14 - MISTS - 26:15                         |
|                                              |
|  Raider.io | Armory | WarcraftLogs | WoWProg |
+---------------------------------------------+
```

**Data sources:**

1. **Blizzard API** — `character_profile_summary` for stats, `character_media` for avatar
2. **Raider.io API** — `mythic_plus_scores_by_season:current` for M+ score, `mythic_plus_best_runs` for dungeon keys

### `/wow guildnews setup <guild_name> <realm> <channel> [region] [language] [active_days]`

Register a WoW guild for news tracking.

| Parameter     | Type                  | Default      | Description                                |
| ------------- | --------------------- | ------------ | ------------------------------------------ |
| `guild_name`  | `str`                 | _(required)_ | Guild name slug (dashes for spaces)        |
| `realm`       | `str`                 | _(required)_ | Realm slug                                 |
| `channel`     | `TextChannel`         | _(required)_ | Notification channel                       |
| `region`      | `Literal["eu", "us"]` | `"eu"`       | API region                                 |
| `language`    | `Literal["de", "en"]` | `"en"`       | Notification language                      |
| `active_days` | `int`                 | `7`          | Only track characters active within N days |

**Permission:** `manage_channels`

**Validation:** Calls `guild_roster` to verify the guild exists before creating the config. First poll establishes a silent baseline.

### `/wow guildnews remove <config_id>`

Remove a tracking config and all associated mount data.

**Permission:** `manage_channels`

### `/wow guildnews list`

Show all tracked guilds for this server with their config details and notification channel.

### `/wow guildnews pause <config_id>` / `resume <config_id>`

Toggle tracking on/off without deleting the config.

**Permission:** `manage_channels`

### `/wow guildnews check <config_id>`

Trigger an immediate poll cycle for testing.

**Permission:** `manage_channels`

## Background Task — Guild News Loop

**Schedule:** Runs every **15 minutes** (configurable via `guild_news.poll_interval_minutes`).

### Phase 1: Achievement & Boss Kill Detection

Uses the **`guild_activity` endpoint** — a single API call per guild that returns a feed of recent events.

**Process:**

1. Call `api.guild_activity(realmSlug, nameSlug)` — returns activities with timestamps and types
2. Compare each activity's timestamp against `config.LastActivityTimestamp`
3. Any activity **newer** than the stored timestamp is new — build an embed
4. Advance `LastActivityTimestamp` to the newest seen timestamp
5. On **first setup**, current time is stored as baseline — only future events trigger notifications

**Activity types handled:**

- `CHARACTER_ACHIEVEMENT` — Character earned an achievement
- `ENCOUNTER` — Boss kill (includes difficulty mode)

### Phase 2: Mount Collection Tracking

There's no "mount earned" event in any API. This uses **differential polling** — comparing a character's current mount collection against what was stored last time.

**Process per character:**

1. Fetch `character_profile_summary` — check `last_login_timestamp` to skip inactive characters
2. Fetch `character_mounts_collection_summary` — returns all mount IDs the account owns
3. Look up stored `WowCharacterMounts.KnownMountIds` (JSON list)
4. Compute `new_ids = current_ids - known_ids` (set difference)
5. If non-empty, resolve mount names from the API response and post embeds
6. Update the stored set

**First scan is silent** — new characters get their mount set recorded without posting anything.

### Batching & Concurrency

- Characters are processed in **batches of 20** (configurable) with offset rotation
- Within each batch, **5 characters are polled concurrently** (`asyncio.Semaphore(5)`)
- All `blizzapi` calls are wrapped in `asyncio.to_thread()` since the library is synchronous

### Initial Sync

When unbaselined characters exist (new setup or new guild members), the loop processes **all batches continuously** instead of one-per-cycle. This completes the initial baseline in minutes instead of hours. The sync stops when either:

- All active characters are baselined
- A full rotation produces no new baselines (remaining characters are inactive/inaccessible)

### Rate Limit Handling (429)

The Blizzard API returns `{"code": 429}` on rate limits. `blizzapi` does **not** auto-retry on 429.

**Detection:** Every API response is checked via `_check_rate_limit()`. On 429:

1. An `asyncio.Event` is set — all in-flight concurrent tasks short-circuit
2. The batch loop breaks immediately
3. The current offset is saved so the **next cycle resumes where it left off**

### Degradation Guard

If a Blizzard API response returns a significantly smaller mount set than what's stored (more than `max(10, 10%)` mounts disappeared), the update is skipped entirely. This protects against partial/degraded API responses causing false "new mount" notifications on the next cycle. Small legitimate removals (e.g., Blizzard revoking bug-obtained mounts) are still processed normally.

### Account-Aware Mount Dedup

Account-wide mounts appear on every character belonging to the same Battle.net account. Without dedup, earning one mount triggers N notifications for N characters. The module uses **confidence-based account resolution** to group characters likely on the same account, then suppresses duplicate mount announcements within each group.

**Two-phase grouping with five independent signals:**

Phase 1 — Pairwise confidence scoring (signals combined, threshold ≥ 0.7):

1. **Name similarity** — Detects diacritics variants ("Mörza"/"Morza"), shared prefix patterns ("alurush"/"alublood"), and general sequence similarity. Long shared prefixes (7+ chars) can cross the threshold on their own.
2. **Achievement points** — Account-wide and deterministic. Characters within ±100 AP of each other are very likely on the same account (score 0.9).
3. **Mount set identity** — Characters with near-identical mount collections (Jaccard similarity ≥ 0.95, 50+ mounts) are almost certainly on the same account
4. **Mount count similarity** — Supplementary signal: characters with similar total mount counts (both 20+, within 10%) get a moderate boost
5. **Temporal correlation** — Characters that consistently earn the same mounts in the same poll cycles build evidence over time (persisted in `AccountGroupData`)

Phase 2 — Prefix family extension: If 3+ same-realm characters share a name prefix and a majority are already grouped from phase 1, the remaining members are pulled into the group. This handles short-prefix naming conventions (e.g. "alu\*") where individual pairs score too low but the cluster pattern is unmistakable.

Characters are grouped via union-find clustering. Only the first character in a group to announce a mount sends the Discord notification; `KnownMountIds` is still updated for all characters.

### Stale Character Cleanup

Characters who leave the guild have their mount data pruned after **30 days** (`STALE_DAYS`).

**Process (runs at the start of each mount poll):**

1. Compare stored `WowCharacterMounts` entries against the current roster
2. Any entry not in the roster whose `LastChecked` is older than 30 days gets deleted
3. The grace period prevents data loss for temporary absences (transfers, etc.)

### Character Rename Detection

When the Blizzard API returns a different canonical name than the roster name:

1. No DB entry exists under the current (new) name
2. Check if an entry exists under the API's canonical (old) name
3. If found, **migrate** the entry by updating `CharacterName` — preserving the mount baseline
4. This prevents false "new mount" floods when someone renames

## Notification Embeds

### Achievement

```
+---------------------------------------------+
|  Achievement Unlocked!        (gold color)   |
|                                              |
|  **CharName** (Realm) earned                 |
|  **Achievement Name**                        |
|                                              |
|  timestamp from activity feed                |
+---------------------------------------------+
```

### Boss Kill

```
+---------------------------------------------+
|  Boss Defeated!               (red color)    |
|                                              |
|  **CharName** (Realm) defeated               |
|  **Boss Name** (Mythic)                      |
|                                              |
|  timestamp from activity feed                |
+---------------------------------------------+
```

### New Mount

```
+---------------------------------------------+
|  New Mount Collected!         (purple color) |
|                                              |
|  **CharName** (Realm) obtained               |
|  **Mount Name**                              |
|                                              |
|  timestamp = now (no event time in API)      |
+---------------------------------------------+
```

### Localization

Achievement, boss kill, and mount collection notifications respect the guild's configured `Language` setting. Supported languages: `en` (English, default), `de` (German). Unsupported language codes fall back to English. To add a new language, extend the `_NOTIFICATION_STRINGS` dict in `modules/wow.py`.

## Database Models

### `WowGuildNewsConfig`

| Column                | Type         | Purpose                                                       |
| --------------------- | ------------ | ------------------------------------------------------------- |
| Id                    | Integer (PK) | Auto-increment                                                |
| GuildId               | BigInteger   | Discord guild ID                                              |
| ChannelId             | BigInteger   | Notification channel                                          |
| WowGuildName          | Unicode(100) | Guild name slug                                               |
| WowRealmSlug          | String(100)  | Realm slug                                                    |
| Region                | String(10)   | `"eu"` or `"us"`                                              |
| Language              | String(5)    | `"de"` or `"en"`                                              |
| MinLevel              | Integer      | Min character level to track (default 10)                     |
| ActiveDays            | Integer      | Only track chars active within N days (default 7)             |
| RosterOffset          | Integer      | Cursor for mount-check batch rotation                         |
| LastActivityTimestamp | DateTime     | Dedup timestamp for activity feed                             |
| Enabled               | Boolean      | Active/paused toggle                                          |
| AccountGroupData      | Text         | JSON dict of temporal correlation data for account resolution |
| CreateDate            | DateTime     | When configured                                               |

### `WowCharacterMounts`

| Column        | Type         | Purpose                    |
| ------------- | ------------ | -------------------------- |
| Id            | Integer (PK) | Auto-increment             |
| ConfigId      | Integer (FK) | Parent config              |
| CharacterName | Unicode(50)  | Character name (lowercase) |
| RealmSlug     | String(100)  | Realm slug                 |
| KnownMountIds | Text         | JSON array of mount IDs    |
| LastChecked   | DateTime     | Last successful check      |

**Unique constraint:** `(ConfigId, CharacterName, RealmSlug)`

## Configuration

```yaml
wow:
  wow_id: your_blizzard_client_id
  wow_secret: your_blizzard_client_secret
  # Optional guild news settings (defaults shown)
  guild_news:
    poll_interval_minutes: 15
    mount_batch_size: 20
    track_mounts: true
    active_days: 7
```

All guild news settings are optional with sensible defaults. Mount tracking can be disabled entirely with `track_mounts: false`.
