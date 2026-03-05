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
        return "admin"
    return "member"


def resolve_guild_permissions(guilds: list[dict]) -> dict[str, str]:
    """Map guild IDs to permission levels from Discord guild list.

    Returns only guilds where user has admin/mod level.
    """
    result = {}
    for guild in guilds:
        perms = int(guild.get("permissions", 0))
        level = resolve_permission_level(perms)
        if level != "member":
            result[guild["id"]] = level
    return result
