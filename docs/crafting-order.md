# Crafting Order Board

Guild administrators can set up a crafting order board where members post requests for BOP (Bind-on-Pickup) items. Crafters with the appropriate profession role accept orders, communicate via threads, and mark them complete.

## Concepts

**Board** is a persistent embed posted in a designated channel. It contains a "Create Crafting Order" button. One board per guild, managed via `/wow craftingorder create` and `/wow craftingorder remove`.

**Profession Roles** are Discord roles that represent WoW professions (e.g. Blacksmithing, Alchemy). These are configured when creating the board and determine who can accept which orders.

**Recipe Cache** stores BOP recipe names and icons fetched from the Blizzard API via `/wow craftingorder recipe-sync`. This populates the item selection dropdown during order creation. The cache is per-guild and can be refreshed at any time.

**Orders** are individual crafting requests. Each order tracks who posted it, which profession is needed, the item name, status, and optionally a discussion thread.

## Flows

### Board Setup

1. Admin runs `/wow craftingorder create <channel> <roles>` with an optional `description` or `description-message`
2. If no description is provided, a modal opens for the admin to type the board description (supports markdown and emojis)
3. If `description-message` is provided, the bot fetches the referenced message's text and deletes the source message
4. Bot validates the roles, creates a `CraftingBoardConfig` row, and posts the board embed
5. The board embed has a single "Create Crafting Order" button (persistent across restarts)

### Recipe Sync (Optional)

1. Moderator runs `/wow craftingorder recipe-sync`
2. Bot fetches professions from the Blizzard API, identifies the current expansion tier (highest tier ID)
3. For each profession, fetches recipes, filters to BOP items, and caches item names + icon URLs
4. Cache enables an item selection dropdown during order creation

### Order Creation (3-Step Ephemeral Flow)

1. User clicks "Create Crafting Order" on the board embed
2. **Step 1 — Profession Select**: Ephemeral dropdown with configured profession roles
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

## Slash Commands

| Command                          | Permission        | Description                                |
| -------------------------------- | ----------------- | ------------------------------------------ |
| `/wow craftingorder create`      | `manage_channels` | Create a crafting order board in a channel |
| `/wow craftingorder remove`      | `manage_channels` | Remove the crafting order board and config |
| `/wow craftingorder recipe-sync` | Bot Moderator     | Sync BOP recipes from Blizzard API         |

## Database Models

### CraftingBoardConfig

One row per guild. Stores the board channel, message ID, description, and JSON-encoded list of profession role IDs.

### CraftingRecipeCache

Cached BOP recipes from the Blizzard API. Keyed by `(GuildId, RecipeId)`. Stores profession ID, item ID, item name, icon URL, and last sync timestamp.

### CraftingOrder

Individual crafting order. Tracks guild, channel, message ID, thread ID, creator, crafter, profession role, item name, icon URL, notes, status, and creation date.

## File Layout

| File                                      | Contents                                                              |
| ----------------------------------------- | --------------------------------------------------------------------- |
| `NerdyPy/modules/wow.py`                  | `craftingorder` command group (create, remove, recipe-sync)           |
| `NerdyPy/modules/views/crafting_order.py` | Board view, select views, modal, DynamicItem buttons, thread fallback |
| `NerdyPy/models/wow.py`                   | CraftingBoardConfig, CraftingRecipeCache, CraftingOrder               |
| `NerdyPy/utils/blizzard.py`               | `sync_crafting_recipes()` helper                                      |
| `NerdyPy/bot.py`                          | DynamicItem and persistent view registration in `setup_hook()`        |
| `NerdyPy/locales/lang_en.yaml`            | `wow.craftingorder.*` localization keys                               |
