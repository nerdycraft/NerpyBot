# Crafting Order Board

Guild administrators can set up a crafting order board where members post requests for craftable items (equippable gear, housing decor, consumables, and more). Crafters with the appropriate profession role accept orders, communicate via threads, and mark them complete.

## Concepts

**Board** is a persistent embed posted in a designated channel. It contains two buttons: "Create Crafting Order" (equippable/consumable flow) and "Request Housing Item" (housing decor flow). One board per guild, managed via `/wow craftingorder create`, `/wow craftingorder edit`, and `/wow craftingorder remove`.

**Profession Roles** are Discord roles that represent WoW professions (e.g. Blacksmithing, Alchemy). When creating a board, roles are auto-matched to Blizzard profession IDs by name. Only matched roles appear in the profession dropdown during order creation.

**Recipe Cache** (`CraftingRecipeCache`) is a bot-global table populated by `!sync recipes` (or the dashboard operator tab). It covers two recipe types:

- `"crafted"` — recipes from the top 2 expansion skill tiers for all crafting professions (Blacksmithing, Leatherworking, Tailoring, Jewelcrafting, Engineering, Inscription, Alchemy, Enchanting, Cooking). Categorized by Blizzard `item_class`/`item_subclass` (e.g. Armor/Plate, Weapon/Sword, Consumable/Flask).
- `"housing"` — housing decor recipes sourced from the Blizzard Housing Decor API (`/data/wow/decor/index`), spanning all expansions. These use spell IDs on Wowhead (`/spell=…`) rather than item IDs.

**Role Mapping** (`CraftingRoleMapping`) maps Discord role IDs to Blizzard profession IDs per guild. Auto-populated during board creation by matching role names against the crafting professions. Unmapped roles are excluded from the profession dropdown.

**Orders** are individual crafting requests. Each order tracks who posted it, which profession is needed, the item name, icon URL, Wowhead URL, status, and optionally a discussion thread.

**Wowhead Links** are stored on each order at creation time and surfaced in the order embed. Equippable/consumable items link to `wowhead.com/item={ItemId}`; housing items link to `wowhead.com/spell={RecipeId}`.

## Flows

### Board Setup

1. Admin runs `/wow craftingorder create <channel> <roles>` with an optional `description` or `description-message`
2. If no description is provided, a modal opens for the admin to type the board description (supports markdown and emojis)
3. If `description` is provided inline, a pre-filled modal opens for review/tweaking
4. If `description-message` is provided, the bot fetches the referenced message's text
5. Bot validates the roles, auto-matches them to Blizzard professions, creates `CraftingBoardConfig` and `CraftingRoleMapping` rows, and posts the board embed
6. The board embed has two persistent buttons: **"Create Crafting Order"** and **"Request Housing Item"**
7. Unmapped roles (no profession name match) are warned about — they won't appear in the dropdown

### Board Editing

1. Admin runs `/wow craftingorder edit` with an optional `roles` parameter
2. If new roles are provided, old mappings are deleted and new ones are auto-matched
3. A modal opens pre-filled with the current board description
4. On submit, the board embed is updated in-place (housing button is preserved)

### Recipe Sync

Two triggers:

- **CLI (operator-only)**: `!sync recipes`
- **Dashboard**: Operator tab → "Recipe Cache" → Sync button

Both invoke `sync_crafting_recipes()` which runs two phases:

**Phase A — Crafted items (profession tier walk):**

1. For each of the 9 crafting professions (including Cooking), walk the top 2 expansion skill tiers
2. For each recipe, fetch `recipe()` → `item()` → `item_media()` to resolve item class, subclass, name, and icon
3. Cache ALL recipes as `RecipeType="crafted"`, storing `ItemClassId/Name` and `ItemSubClassId/Name`

**Phase B — Housing decor:**

1. Call `GET /data/wow/decor/index` via raw API client (this endpoint isn't wrapped by blizzapi yet)
2. Map decor items to professions and expansion names
3. Fallback: if the decor endpoint is unavailable, scan Phase A results for housing-keyword categories
4. Cache as `RecipeType="housing"`, `ExpansionName` set to the WoW expansion name

Returns `{"crafted": N, "housing": N, "errors": N, "duration_seconds": float}`.

### Order Creation — Equippable/Consumable Flow

1. User clicks **"Create Crafting Order"** on the board embed
2. If cache has `"crafted"` recipes: **Item Type Select** — dropdown with item classes (Armor, Weapon, Consumable, …)
3. **Item Subtype Select** — dropdown with subclasses for the chosen type (Plate, Leather, Flask, Feast, …)
4. **Item Select** — up to 24 matching recipe options + "Other". "Other" skips to free-text modal.
5. On item selection: profession role is auto-resolved from the cache + `CraftingRoleMapping`; modal opens pre-filled with item name and icon
6. Modal submit creates the `CraftingOrder` row with icon URL + Wowhead link, then posts the order embed
7. If cache is empty at any step: graceful fallback to **Profession Select** → free-text modal

### Order Creation — Housing Flow

1. User clicks **"Request Housing Item"** on the board embed
2. If cache has `"housing"` recipes: **Profession Select** — only professions that have housing recipes
3. **Expansion Select** — expansion names (Classic through Midnight) for the chosen profession
4. **Item Select** — up to 24 housing recipes for that profession + expansion, + "Other"
5. On item selection: modal opens pre-filled; Wowhead link uses `/spell=` URL format
6. If cache is empty: graceful fallback to free-text **Profession Select** → modal

### Order Lifecycle (State Machine)

```
Open
 └─[Accept]──► In Progress
                ├─[Drop]────► Open
                └─[Complete]► Completed (embed deleted)
Open / In Progress
 └─[Cancel]──► Completed (embed deleted)
```

| Button       | Guard                                              | New Status  | Side Effects                                     |
| ------------ | -------------------------------------------------- | ----------- | ------------------------------------------------ |
| Accept       | Has profession role, status=open                   | in_progress | Set CrafterId                                    |
| Drop         | Is crafter OR admin, status=in_progress            | open        | Clear CrafterId                                  |
| Complete     | Is crafter OR admin, status=in_progress            | completed   | DM creator → delete embed                        |
| Cancel       | Is creator OR admin, status in {open, in_progress} | completed   | Conditional DM → delete embed                    |
| Ask Question | Anyone                                             | (no change) | Create/reuse thread, post question, ping creator |

### DM Notifications

- **Complete**: DM creator "Your crafting order has been completed!"
- **Cancel by admin**: DM creator "Your crafting order has been cancelled!"
- **Cancel by creator**: No DM
- **DM failure**: Falls back to creating/reusing a thread on the order message and pinging the creator there

## Commands

### Slash Commands

| Command                     | Permission        | Description                                    |
| --------------------------- | ----------------- | ---------------------------------------------- |
| `/wow craftingorder create` | `manage_channels` | Create a crafting order board in a channel     |
| `/wow craftingorder edit`   | `manage_channels` | Edit description and/or roles of the board     |
| `/wow craftingorder remove` | `manage_channels` | Remove the crafting order board and all config |

### Prefix Commands (Operator-Only)

| Command         | Description                                    |
| --------------- | ---------------------------------------------- |
| `!sync recipes` | Sync crafting recipe cache (crafted + housing) |

### Dashboard (Operator Tab)

The **Recipe Cache** tab in the operator section of the guild dashboard provides:

- Cache stats: count of `"crafted"` and `"housing"` recipes currently stored
- **Sync** button: triggers `!sync recipes` asynchronously via Valkey IPC
- Status auto-refreshes 5 seconds after triggering a sync

API endpoints:

| Method | Path                           | Description                      |
| ------ | ------------------------------ | -------------------------------- |
| POST   | `/operator/recipe-sync`        | Trigger async recipe sync        |
| GET    | `/operator/recipe-sync/status` | Return current cache type counts |

## Database Models

### CraftingBoardConfig

One row per guild. Stores the board channel, message ID, and description.

### CraftingRoleMapping

Maps Discord role IDs to Blizzard profession IDs, per guild. Auto-populated during board creation by matching role names. The role list for a guild's board is derived by querying this table.

### CraftingRecipeCache

Bot-global cache of craftable recipes from the Blizzard API. Keyed by `RecipeId`.

| Column             | Type          | Description                                                   |
| ------------------ | ------------- | ------------------------------------------------------------- |
| `RecipeId`         | Integer (PK)  | Blizzard recipe or spell ID                                   |
| `ProfessionId`     | Integer       | Blizzard profession ID                                        |
| `ProfessionName`   | Unicode 100   | e.g. "Blacksmithing"                                          |
| `ItemId`           | Integer (opt) | Blizzard crafted item ID                                      |
| `ItemName`         | Unicode 200   | Display name                                                  |
| `IconUrl`          | Unicode 500   | Icon URL from Blizzard media API                              |
| `RecipeType`       | String 20     | `"crafted"` or `"housing"`                                    |
| `ItemClassName`    | Unicode 100   | Blizzard item_class name (e.g. "Armor", "Weapon")             |
| `ItemClassId`      | Integer (opt) | Blizzard item_class.id (2=Weapon, 4=Armor)                    |
| `ItemSubClassName` | Unicode 100   | item_subclass name (e.g. "Plate", "Cloth", "Flask")           |
| `ItemSubClassId`   | Integer (opt) | item_subclass.id                                              |
| `ExpansionName`    | Unicode 100   | Skill tier / expansion name (e.g. "Midnight", "Dragonflight") |
| `CategoryName`     | Unicode 200   | Category within the profession tier                           |
| `LastSynced`       | DateTime      | UTC timestamp of last sync                                    |

### CraftingOrder

Individual crafting order. Tracks guild, channel, message ID, thread ID, creator, crafter, profession role, item name, icon URL, Wowhead URL, notes, status, and creation date.

| Column       | Type        | Description                                    |
| ------------ | ----------- | ---------------------------------------------- |
| `WowheadUrl` | Unicode 500 | Wowhead URL stored at creation time (nullable) |

The `WowheadUrl` column was added in migration `012`.

## File Layout

| File                                                                 | Contents                                                                         |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `NerdyPy/modules/wow.py`                                             | `craftingorder` command group (create, edit, remove)                             |
| `NerdyPy/modules/views/crafting_order.py`                            | Board view, select views (type/subtype/item/expansion/housing profession), modal |
| `NerdyPy/models/wow.py`                                              | CraftingBoardConfig, CraftingRoleMapping, CraftingRecipeCache, CraftingOrder     |
| `NerdyPy/utils/blizzard.py`                                          | `sync_crafting_recipes()`, housing decor API calls                               |
| `NerdyPy/utils/valkey.py`                                            | `recipe_sync` + `recipe_sync_status` Valkey IPC handlers                         |
| `NerdyPy/modules/admin.py`                                           | `!sync recipes` CLI command                                                      |
| `web/routes/operator.py`                                             | `/operator/recipe-sync` POST + GET endpoints                                     |
| `web/frontend/src/views/guild/tabs/OperatorRecipeSyncTab.vue`        | Dashboard operator tab for recipe cache management                               |
| `NerdyPy/bot.py`                                                     | DynamicItem and persistent view registration in `setup_hook()`                   |
| `NerdyPy/locales/lang_en.yaml`                                       | `wow.craftingorder.*` localization keys                                          |
| `database-migrations/versions/012_add_crafting_order_wowhead_url.py` | Alembic migration: adds `WowheadUrl` to `CraftingOrder`                          |
