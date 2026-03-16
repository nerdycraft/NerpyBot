#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_test_guild.py — Bootstrap a Discord test guild with all roles, categories,
and channels required to test every NerpyBot module.

Usage:
    uv run python scripts/setup_test_guild.py <guild_id>
    uv run python scripts/setup_test_guild.py <guild_id> --config NerdyPy/config.yaml
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make NerdyPy utils importable (mirrors tests/conftest.py:14)
sys.path.insert(0, str(Path(__file__).parent.parent / "NerdyPy"))

import discord
from utils.config import parse_config
from utils.permissions import REQUIRED_PERMISSIONS

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# Resource definitions
# ---------------------------------------------------------------------------

ROLES: list[str] = [
    "Bot Moderator",
    "App Manager",
    "App Reviewer",
    "Reaction Role A",
    "Reaction Role B",
    "Role Source",
    "Role Target",
    "Blacksmithing",
    "Alchemy",
    "Enchanting",
]

# Channel tuples: (channel_name, channel_type, denied_perms | None)
# denied_perms is a set of permission flag names to explicitly deny for the bot member.
# None means use the default full-access overwrite.
#
# (category_name, [(channel_name, channel_type, denied_perms | None), ...])
CATEGORIES: list[tuple[str, list[tuple[str, str, set[str] | None]]]] = [
    (
        "General",
        [
            ("general", "text", None),
            ("bot-commands", "text", None),
        ],
    ),
    (
        "Testing",
        [
            ("leave-messages", "text", None),
            ("auto-delete-test", "text", None),
            ("reminders", "text", None),
        ],
    ),
    (
        "Applications",
        [
            ("app-review", "text", None),
            ("app-apply", "text", None),
        ],
    ),
    (
        "Reaction Roles",
        [
            ("reaction-roles", "text", None),
        ],
    ),
    (
        "WoW",
        [
            ("wow-news", "text", None),
            ("crafting-orders", "text", None),
        ],
    ),
    (
        "Voice",
        [
            ("Music", "voice", None),
            ("Tagging Test", "voice", None),
        ],
    ),
    # Channels with specific permissions denied — for testing error-handling paths
    # in each module's validate_channel_permissions() calls.
    (
        "Permission Tests",
        [
            ("no-send-messages", "text", {"send_messages"}),  # all text modules
            ("no-embed-links", "text", {"embed_links"}),  # wow, music, application, league
            ("no-manage-messages", "text", {"manage_messages"}),  # moderation, reactionrole, _core
            ("no-read-history", "text", {"read_message_history"}),  # moderation, reactionrole, _core
            ("no-manage-threads", "text", {"manage_threads"}),  # wow (crafting orders)
            ("no-add-reactions", "text", {"add_reactions"}),  # reactionrole
            ("no-connect", "voice", {"connect", "speak"}),  # music, tagging
        ],
    ),
]

# Channels to populate with seed messages on every run.
# The auto-deleter consumes messages, so re-running the script refills them.
# Tuple: (channel_name, message_count, pin_first_message)
# pin_first_message=True lets testers verify delete_pinned_message=False/True behaviour.
SEED_CHANNELS: list[tuple[str, int, bool]] = [
    ("auto-delete-test", 20, True),
    # Seed the permission-denied channel too so the auto-deleter has messages to
    # attempt deletion on — verifying it handles discord.Forbidden gracefully.
    ("no-manage-messages", 20, False),
]

# Channel-level permission overwrite kwargs — derived from the union of all module
# permissions in REQUIRED_PERMISSIONS. Guild-level-only flags are excluded: Discord
# rejects channel overwrites containing them unless the bot has administrator.
_GUILD_LEVEL_ONLY = {"manage_roles", "kick_members"}
_BOT_OVERWRITE_KWARGS: dict[str, bool] = {
    p: True for perms in REQUIRED_PERMISSIONS.values() for p in perms if p not in _GUILD_LEVEL_ONLY
}

BOT_OVERWRITE = discord.PermissionOverwrite(**_BOT_OVERWRITE_KWARGS)


def _build_overwrite(denied: set[str] | None) -> discord.PermissionOverwrite:
    """Return a PermissionOverwrite with full bot access minus any explicitly denied flags."""
    if not denied:
        return BOT_OVERWRITE
    return discord.PermissionOverwrite(**{**_BOT_OVERWRITE_KWARGS, **{p: False for p in denied}})


# ---------------------------------------------------------------------------
# Setup client
# ---------------------------------------------------------------------------


class SetupClient(discord.Client):
    def __init__(self, guild_id: int) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.failed = False

    async def on_ready(self) -> None:
        try:
            await self._run_setup()
        except Exception as exc:
            print(f"\n[ERROR] Setup failed: {exc}", file=sys.stderr)
            self.failed = True
        finally:
            await self.close()

    async def _run_setup(self) -> None:
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            raise RuntimeError(f"Guild {self.target_guild_id} not found. Make sure the bot is a member of that server.")

        # Pre-flight: check bot has the guild-level permissions this script needs
        me = guild.me
        missing_perms = [p for p in ("manage_roles", "manage_channels") if not getattr(me.guild_permissions, p)]
        if missing_perms:
            raise RuntimeError(
                f"Bot is missing required guild permissions: {', '.join(missing_perms)}\n"
                "Re-invite the bot with these permissions and try again."
            )

        print("\n=== NerpyBot Test Guild Setup ===")
        print(f"Guild: {guild.name} ({guild.id})\n")

        created_count = 0
        existed_count = 0

        # --- Roles ---
        print("Roles:")
        for role_name in ROLES:
            role, was_created = await _ensure_role(guild, role_name)
            tag = "[CREATED]" if was_created else "[EXISTS] "
            if role is not None:
                print(f"  {tag}  {role_name:<22} (ID: {role.id})")
                if was_created:
                    created_count += 1
                else:
                    existed_count += 1
            else:
                print(f"  [FAILED]  {role_name}")

        # --- Categories & Channels ---
        print("\nCategories & Channels:")
        for cat_name, channels in CATEGORIES:
            cat, cat_created = await _ensure_category(guild, cat_name)
            tag = "[CREATED]" if cat_created else "[EXISTS] "
            if cat is None:
                print(f"  [FAILED]  {cat_name}")
                continue

            print(f"  {tag}  {cat_name:<22} (category, ID: {cat.id})")
            if cat_created:
                created_count += 1
            else:
                existed_count += 1

            for ch_name, ch_type, denied_perms in channels:
                ch, ch_created = await _ensure_channel(guild, cat, ch_name, ch_type, denied_perms)
                ch_tag = "[CREATED]" if ch_created else "[EXISTS] "
                prefix = "#" if ch_type == "text" else " "
                if ch is not None:
                    print(f"    {ch_tag}  {prefix}{ch_name:<20} ({ch_type}, ID: {ch.id})")
                    if ch_created:
                        created_count += 1
                    else:
                        existed_count += 1
                else:
                    print(f"    [FAILED]  {prefix}{ch_name}")

        print(f"\nDone! {created_count} created, {existed_count} already existed.")

        # --- Seed channels ---
        print("\nSeeding channels:")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for ch_name, count, pin_first in SEED_CHANNELS:
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if ch is None:
                print(f"  [SKIP]    #{ch_name} not found")
                continue
            sent, had = await _seed_channel(ch, count, pin_first, stamp)
            if sent == 0:
                print(f"  [FULL]    #{ch_name:<20} (already has {had}/{count} messages)")
            else:
                pin_note = ", 1 pinned" if pin_first and had == 0 else ""
                print(f"  [SEEDED]  #{ch_name:<20} ({sent} sent, {had + sent}/{count} total{pin_note})")


# ---------------------------------------------------------------------------
# Idempotent helpers — each returns (resource | None, created: bool)
# ---------------------------------------------------------------------------


async def _ensure_role(guild: discord.Guild, name: str) -> tuple[discord.Role | None, bool]:
    existing = discord.utils.get(guild.roles, name=name)
    if existing is not None:
        return existing, False
    try:
        role = await guild.create_role(name=name, reason="NerpyBot test guild setup")
        return role, True
    except discord.Forbidden as exc:
        print(f"    [WARN] Forbidden creating role '{name}': {exc}", file=sys.stderr)
        return None, False


async def _ensure_category(guild: discord.Guild, name: str) -> tuple[discord.CategoryChannel | None, bool]:
    existing = discord.utils.get(guild.categories, name=name)
    if existing is not None:
        return existing, False
    try:
        overwrites = {guild.me: BOT_OVERWRITE}
        cat = await guild.create_category(name=name, overwrites=overwrites, reason="NerpyBot test guild setup")
        return cat, True
    except discord.Forbidden as exc:
        print(f"    [WARN] Forbidden creating category '{name}': {exc}", file=sys.stderr)
        return None, False


async def _ensure_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    name: str,
    ch_type: str,
    denied_perms: set[str] | None = None,
) -> tuple[discord.abc.GuildChannel | None, bool]:
    overwrites = {guild.me: _build_overwrite(denied_perms)}
    if ch_type == "text":
        existing_collection = category.text_channels
        create = guild.create_text_channel
    else:  # voice
        existing_collection = category.voice_channels
        create = guild.create_voice_channel

    existing = discord.utils.get(existing_collection, name=name)
    if existing is not None:
        return existing, False
    try:
        ch = await create(name=name, category=category, overwrites=overwrites, reason="NerpyBot test guild setup")
        return ch, True
    except discord.Forbidden as exc:
        print(f"    [WARN] Forbidden creating {ch_type} channel '{name}': {exc}", file=sys.stderr)
        return None, False


async def _seed_channel(channel: discord.TextChannel, count: int, pin_first: bool, stamp: str) -> tuple[int, int]:
    """Top up *channel* to *count* messages, sending only what is missing.

    Returns (sent, had) where *had* is the number of messages already present
    before this run. If the channel already has >= count messages, sends nothing.
    Optionally pins the first new message (only when the channel was empty before).
    """
    had = sum([1 async for _ in channel.history(limit=count + 1, oldest_first=False)])
    to_send = max(0, count - had)

    first_message: discord.Message | None = None
    sent = 0
    for i in range(had + 1, had + to_send + 1):
        try:
            msg = await channel.send(f"Auto-delete test message {i}/{count} — seeded {stamp}")
            if sent == 0:
                first_message = msg
            sent += 1
        except discord.Forbidden as exc:
            print(f"    [WARN] Cannot send to #{channel.name}: {exc}", file=sys.stderr)
            break

    # Only pin when seeding into an empty channel — avoid re-pinning on top-up runs.
    if pin_first and had == 0 and first_message is not None:
        try:
            await first_message.pin()
        except discord.Forbidden as exc:
            print(f"    [WARN] Cannot pin in #{channel.name}: {exc}", file=sys.stderr)

    return sent, had


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap a Discord test guild for NerpyBot development.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("guild_id", type=int, help="Discord guild (server) ID to set up")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("NerdyPy/config.yaml"),
        help="Path to config.yaml (default: NerdyPy/config.yaml)",
    )
    args = parser.parse_args()

    config = parse_config(args.config)
    token = config.get("bot", {}).get("token")
    if not token:
        print(
            "[ERROR] No bot token found. Set NERPYBOT_TOKEN or add bot.token to config.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = SetupClient(guild_id=args.guild_id)
    asyncio.run(client.start(token))
    if client.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
