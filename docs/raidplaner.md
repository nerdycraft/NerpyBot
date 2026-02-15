# Raid Planer Module

Interactive raid planning tool built on a state-machine conversation system. All interaction happens via DMs with emoji reactions and text input. This is the largest module in the codebase.

## Entry Point

### `!raidplaner`

Prefix-only command. Initiates an interactive DM conversation for managing raid templates and events.

**No slash command** — the interactive DM conversation flow doesn't map well to slash command parameters.

## Conversation Flow

The entire module is driven by `RaidConversation`, a state machine with 77 states organized into 4 regions:

```
MAIN_MENU (state 0)
  ├── TEMPLATE region (101-199)
  │     ├── Create / Edit / Delete templates
  │     └── ENCOUNTER region (201-399)
  │           ├── Create / Edit / Delete encounters
  │           └── Role management (add/edit/delete roles per encounter)
  └── EVENT region (500-509)
        └── Create raid events from templates
```

### Interaction Methods

The conversation uses three input modes:

- **Reactions only** (`send_react`) — User picks an option by reacting with an emoji. Each emoji maps to a target state.
- **Text only** (`send_msg`) — User types a response. An answer handler validates the input.
- **Both** (`send_both`) — Supports either reaction or text input.

### Main Menu

From the main menu, the user can:
- **Manage Templates** — Create, edit, or delete raid templates
- **Create Event** — Schedule a raid using an existing template

### Template Management

A template defines the structure of a raid:
- **Name** (5-35 characters)
- **Description** (max 350 characters)
- **Player Count** (3-25)
- **Encounters** — Each with its own name, description, and role assignments

### Encounter Management

Each encounter within a template has:
- **Name** (5-35 characters)
- **Description** (max 150 characters)
- **Roles** — Named slots with a count (e.g., "Tank x2", "Healer x3")

### Role Constraints

- Role description: max 150 characters
- Role count must be > 0
- Total role count across all roles in an encounter must not exceed the template's player count

### Event Creation

Creates a scheduled raid event from an existing template. The conversation guides through selecting a template and setting the event details.

## Database Models

### `RaidTemplate`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| TemplateId | BigInteger (PK) | Template ID within guild |
| Name | Unicode(30) | Template name |
| Description | Unicode(255) | Template description |
| PlayerCount | Integer | Max players |
| CreateDate | DateTime | When created |

Has a cascade-delete relationship to `RaidEncounter`.

### `RaidEncounter`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| TemplateId | BigInteger (PK) | Parent template |
| EncounterId | BigInteger (PK) | Encounter ID within template |
| Name | Unicode(30) | Encounter name |
| Description | Unicode(255) | Encounter description |

FK to `RaidTemplate(GuildId, TemplateId)`. Has a cascade-delete relationship to `RaidEncounterRole`.

### `RaidEncounterRole`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| TemplateId | BigInteger (PK) | Parent template |
| EncounterId | BigInteger (PK) | Parent encounter |
| RoleId | BigInteger (PK) | Role ID within encounter |
| Name | Unicode(30) | Role name (e.g., "Tank", "Healer") |
| Description | Unicode(255) | Role description |
| Count | Integer | Number of slots for this role |
| SortIndex | Integer | Display order |

### `RaidEvent`

| Column | Type | Purpose |
|--------|------|---------|
| GuildId | BigInteger (PK) | Discord guild ID |
| EventId | BigInteger (PK) | Event ID within guild |

## How the State Machine Works

1. User runs `!raidplaner` — bot creates a `RaidConversation` and sends the main menu embed to DMs
2. Bot adds emoji reactions to the message (each emoji = a menu option)
3. User reacts — `on_raw_reaction_add` in `NerdyPy.py` routes the reaction to the active conversation
4. Conversation looks up which state the emoji maps to and transitions
5. The new state's handler method runs — sends a new embed, possibly with text input expected
6. If text input is expected, `on_message` routes the user's DM to the conversation
7. An answer handler validates the input (returns `False` to reject and stay, or advances state)
8. This continues until the user exits or the conversation times out

**Temporary state:** The conversation holds `tmpTemplate`, `tmpEncounter`, `tmpRole`, and `tmpEvent` objects in memory while editing. These are persisted to the database only when the user confirms.

## Composite Primary Keys

All raid tables use composite primary keys (`GuildId + TemplateId + ...`). This means template IDs are guild-scoped — template #1 in Guild A is completely independent from template #1 in Guild B. The relationships use complex `primaryjoin` clauses to handle these composite keys.
