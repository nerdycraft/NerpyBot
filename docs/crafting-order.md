# Crafting Order Board

Guild administrators can set up a crafting order board where members post requests for craftable items (equippable gear, BoP materials, PvP gear). Crafters with the appropriate profession role accept orders, communicate via threads, and mark them complete.

## Concepts

**Board** is a persistent embed posted in a designated channel. It contains a "Create Crafting Order" button. One board per guild, managed via `/wow craftingorder create`, `/wow craftingorder edit`, and `/wow craftingorder remove`.

**Profession Roles** are Discord roles that represent WoW professions (e.g. Blacksmithing, Alchemy). When creating a board, roles are auto-matched to Blizzard profession IDs by name. Only matched roles appear in the profession dropdown during order creation.

**Recipe Cache** stores craftable recipe names and icons resolved via the Wowhead tooltip API, triggered by `!wow recipesync` or `!sync data` (operator-only). The cache is **bot-global** (shared across all guilds) since WoW recipes are static data. Only equippable items (armor, weapons) from the top 2 expansion tiers are cached.

**Role Mapping** (`CraftingRoleMapping`) maps Discord role IDs to Blizzard profession IDs per guild. Auto-populated during board creation by matching role names against the 8 crafting professions. Unmapped roles are excluded from the profession dropdown.

**Orders** are individual crafting requests. Each order tracks who posted it, which profession is needed, the item name, status, and optionally a discussion thread.

## Flows

### Board Setup

1. Admin runs `/wow craftingorder create <channel> <roles>` with an optional `description` or `description-message`
2. If no description is provided, a modal opens for the admin to type the board description (supports markdown and emojis)
3. If `description` is provided inline, a pre-filled modal opens for review/tweaking
4. If `description-message` is provided, the bot fetches the referenced message's text
5. Bot validates the roles, auto-matches them to Blizzard professions, creates `CraftingBoardConfig` and `CraftingRoleMapping` rows, and posts the board embed
6. The board embed has a single "Create Crafting Order" button (persistent across restarts)
7. Unmapped roles (no profession name match) are warned about — they won't appear in the dropdown

### Board Editing

1. Admin runs `/wow craftingorder edit` with an optional `roles` parameter
2. If new roles are provided, old mappings are deleted and new ones are auto-matched
3. A modal opens pre-filled with the current board description
4. On submit, the board embed is updated in-place

### Recipe Sync (Operator-Only)

1. Operator runs `!wow recipesync` or `!sync data`
2. Bot fetches the 8 crafting professions from the Blizzard API
3. For each profession, takes the top 2 expansion tiers (current + previous)
4. For each recipe, queries the Wowhead tooltip API to resolve the crafted item
5. Equippable items (armor, weapons) are cached with their icon URLs
6. Cache enables an item selection dropdown during order creation

### Order Creation (3-Step Ephemeral Flow)

1. User clicks "Create Crafting Order" on the board embed
2. **Step 1 — Profession Select**: Ephemeral dropdown with mapped profession roles only
3. **Step 2 — Item Select** (conditional): If recipe cache exists for the selected profession, shows up to 25 items + "Other". Skipped if no cache.
4. **Step 3 — Modal**: Item name field (pre-filled if selected from cache) and optional notes
5. Bot creates a `CraftingOrder` row, posts the order embed with @mention of the profession role

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

| Command           | Description                                  |
| ----------------- | -------------------------------------------- |
| `!wow recipesync` | Sync crafting recipes via Blizzard + Wowhead |
| `!sync data`      | Sync all module data (includes recipe cache) |

## Database Models

### CraftingBoardConfig

One row per guild. Stores the board channel, message ID, and description.

### CraftingRoleMapping

Maps Discord role IDs to Blizzard profession IDs, per guild. Auto-populated during board creation by matching role names. The role list for a guild's board is derived by querying this table.

### CraftingRecipeCache

Bot-global cache of craftable recipes resolved via Wowhead. Keyed by `RecipeId` (unique). Stores profession ID, profession name, item ID, item name, icon URL, and last sync timestamp.

### CraftingOrder

Individual crafting order. Tracks guild, channel, message ID, thread ID, creator, crafter, profession role, item name, icon URL, notes, status, and creation date.

## File Layout

| File                                      | Contents                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| `NerdyPy/modules/wow.py`                  | `craftingorder` command group (create, edit, remove) + prefix commands       |
| `NerdyPy/modules/views/crafting_order.py` | Board view, select views, modal, DynamicItem buttons, thread fallback        |
| `NerdyPy/models/wow.py`                   | CraftingBoardConfig, CraftingRoleMapping, CraftingRecipeCache, CraftingOrder |
| `NerdyPy/utils/blizzard.py`               | `sync_crafting_recipes()`, Wowhead tooltip resolver                          |
| `NerdyPy/bot.py`                          | DynamicItem and persistent view registration in `setup_hook()`               |
| `NerdyPy/locales/lang_en.yaml`            | `wow.craftingorder.*` localization keys                                      |
