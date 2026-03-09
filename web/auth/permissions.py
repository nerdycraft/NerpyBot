"""Guild permission resolution from Discord permissions integer."""

from __future__ import annotations

# Discord permission flags
ADMINISTRATOR = 0x8
MANAGE_GUILD = 0x20


def resolve_permission_level(permissions: int) -> str:
    """Resolve a Discord permissions integer to a permission level string."""
    if permissions & ADMINISTRATOR:
        return "admin"
    if permissions & MANAGE_GUILD:
        return "mod"
    return "member"


def resolve_guild_permissions(guilds: list[dict]) -> dict[str, dict]:
    """Map guild IDs to permission metadata from Discord guild list.

    Returns only guilds where user has admin/mod level.
    Each value is a dict with keys: level, name, icon.
    """
    result = {}
    for guild in guilds:
        perms = int(guild.get("permissions", 0))
        level = resolve_permission_level(perms)
        if level != "member":
            result[guild["id"]] = {
                "level": level,
                "name": guild.get("name", ""),
                "icon": guild.get("icon"),
            }
    return result
