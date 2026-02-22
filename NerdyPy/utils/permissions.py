# -*- coding: utf-8 -*-

"""
Per-module bot permission requirements and guild-level audit helpers.
"""

from discord import Embed, Guild, Permissions, TextChannel

from utils.errors import NerpyPermissionError

# Maps module name → set of Permissions flag names the bot needs at runtime.
# User-level checks (has_permissions) are NOT included — only bot actions.
# Implicit permissions (view_channel, use_application_commands, etc.) are in _core.
REQUIRED_PERMISSIONS: dict[str, set[str]] = {
    # Core bot (always active) — basic visibility, slash commands, prefix-command cleanup
    "_core": {
        "view_channel",
        "send_messages",
        "send_messages_in_threads",
        "manage_messages",
        "read_message_history",
        "use_application_commands",
        "use_external_emojis",
        "use_external_stickers",
    },
    "admin": set(),
    "application": {"send_messages", "embed_links", "create_public_threads"},
    "league": {"send_messages"},
    "leavemsg": {"send_messages"},
    "moderation": {"send_messages", "kick_members", "manage_messages", "read_message_history"},
    "music": {"send_messages", "embed_links", "connect", "speak", "add_reactions", "read_message_history"},
    "reactionrole": {
        "send_messages",
        "manage_roles",
        "add_reactions",
        "manage_messages",
        "read_message_history",
    },
    "rolemanage": {"send_messages", "manage_roles"},
    "reminder": {"send_messages"},
    "tagging": {"send_messages", "connect", "speak", "add_reactions", "read_message_history"},
    "voicecontrol": {"send_messages", "connect", "speak"},
    "wow": {"send_messages", "embed_links"},
}


def required_permissions_for(modules: list[str]) -> Permissions:
    """Compute the combined Permissions object for a list of enabled modules."""
    flags: set[str] = set(REQUIRED_PERMISSIONS.get("_core", set()))
    for mod in modules:
        flags |= REQUIRED_PERMISSIONS.get(mod, set())

    return Permissions(**{f: True for f in flags})


def check_guild_permissions(guild: Guild, required: Permissions) -> list[str]:
    """Return a list of permission flag names the bot is missing in *guild*."""
    bot_perms = guild.me.guild_permissions
    missing = []
    for perm, needed in required:
        if needed and not getattr(bot_perms, perm):
            missing.append(perm)
    return missing


def build_permissions_embed(guild: Guild, missing: list[str], client_id: int, required: Permissions) -> Embed:
    """Build a Discord Embed reporting missing permissions."""
    if missing:
        colour = 0xFF4444
        desc = "**Missing permissions:**\n" + "\n".join(f"- `{p}`" for p in missing)
    else:
        colour = 0x44FF44
        desc = "All required permissions are granted."

    emb = Embed(title=f"Permission check — {guild.name}", description=desc, color=colour)

    invite_perms = required.value
    invite_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={client_id}&permissions={invite_perms}&scope=bot%20applications.commands"
    )
    emb.add_field(name="Invite link (with correct permissions)", value=f"[Re-invite]({invite_url})", inline=False)
    return emb


def validate_channel_permissions(channel: TextChannel, guild: Guild, *perms: str) -> None:
    """Raise NerpyPermissionError if the bot lacks any of *perms* in *channel*.

    Uses channel.permissions_for(guild.me) which resolves guild-level
    permissions plus channel-specific overrides into effective permissions.
    """
    resolved = channel.permissions_for(guild.me)
    missing = [p for p in perms if not getattr(resolved, p, False)]
    if missing:
        formatted = ", ".join(f"`{p}`" for p in missing)
        raise NerpyPermissionError(f"I need the following permissions in {channel.mention}: {formatted}")
