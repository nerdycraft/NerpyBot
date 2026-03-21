# -*- coding: utf-8 -*-
"""In-memory guild configuration cache to reduce redundant DB queries."""

import logging

from cachetools import TTLCache
from discord import app_commands

_log = logging.getLogger(__name__)


class GuildConfigCache:
    """Lightweight in-memory cache for per-guild configuration that rarely changes.

    Sub-caches:
    - Guild language: lazy (DB on miss), invalidated by ``guild_language_changed`` event
    - Bot moderator role: lazy (DB on miss), invalidated by ``modrole_changed`` event
    - Reaction role message IDs: bulk-loaded on startup, updated on add/remove
    - Reaction role mappings: bulk-loaded on startup, updated on add/remove entry
    - Leave message guild IDs: bulk-loaded on startup, updated on enable/disable
    - Leave message configs: bulk-loaded on startup, updated on enable/disable/edit
    """

    def __init__(self):
        self._lang: dict[int, str] = {}
        self._modrole: dict[int, int | None] = {}
        self._rr_message_ids: set[int] = set()  # flat set for O(1) hot-path lookup
        self._rr_by_guild: dict[int, set[int]] = {}  # guild_id -> set[message_id] for eviction
        self._rr_mappings: dict[int, dict[str, int]] = {}
        self._rr_warmed: bool = False
        self._leave_configs: dict[int, tuple[int, str | None]] = {}
        self._leave_warmed: bool = False

    # ── Language ──────────────────────────────────────────────────────────────

    def get_guild_language(self, guild_id: int, session_factory) -> str:
        """Return the guild's language, loading from DB on first access."""
        if guild_id in self._lang:
            return self._lang[guild_id]

        session = session_factory()
        try:
            from models.admin import GuildLanguageConfig

            config = GuildLanguageConfig.get(guild_id, session)
            lang = config.Language if config is not None else "en"
        finally:
            session.close()

        self._lang[guild_id] = lang
        return lang

    def set_guild_language(self, guild_id: int, lang: str) -> None:
        """Update the cached language for a guild."""
        self._lang[guild_id] = lang

    # ── Moderator role ────────────────────────────────────────────────────────

    def get_modrole(self, guild_id: int, session_factory) -> int | None:
        """Return the guild's bot-moderator role ID, loading from DB on first access."""
        if guild_id in self._modrole:
            return self._modrole[guild_id]

        session = session_factory()
        try:
            from models.admin import BotModeratorRole

            entry = BotModeratorRole.get(guild_id, session)
            role_id = entry.RoleId if entry is not None else None
        finally:
            session.close()

        self._modrole[guild_id] = role_id
        return role_id

    def set_modrole(self, guild_id: int, role_id: int | None) -> None:
        """Update or clear the cached modrole for a guild."""
        self._modrole[guild_id] = role_id

    def delete_modrole(self, guild_id: int) -> None:
        """Remove the modrole entry for a guild."""
        self._modrole.pop(guild_id, None)

    # ── Reaction roles ────────────────────────────────────────────────────────

    def is_reaction_role_message(self, message_id: int) -> bool:
        """Return True if the message has reaction roles configured.

        Returns True unconditionally before warm-up completes (conservative: always
        falls through to the DB query so no reactions are missed).
        """
        if not self._rr_warmed:
            return True
        return message_id in self._rr_message_ids

    def get_reaction_role(self, message_id: int, emoji: str) -> int | None:
        """Return the role ID for the given message + emoji, or None if not mapped.

        Returns None before warm-up completes (callers must fall back to DB).
        """
        if not self._rr_warmed:
            return None
        return self._rr_mappings.get(message_id, {}).get(emoji)

    def add_reaction_role_message(self, guild_id: int, message_id: int) -> None:
        """Register a new reaction role message ID in the cache."""
        self._rr_message_ids.add(message_id)
        self._rr_by_guild.setdefault(guild_id, set()).add(message_id)

    def add_reaction_role_entry(self, message_id: int, emoji: str, role_id: int) -> None:
        """Add an emoji-to-role mapping for a tracked message.

        No-op before warm-up — the full mapping is loaded by warm_reaction_roles().
        """
        if not self._rr_warmed:
            return
        self._rr_mappings.setdefault(message_id, {})[emoji] = role_id

    def remove_reaction_role_entry(self, message_id: int, emoji: str) -> None:
        """Remove a single emoji-to-role mapping from a tracked message."""
        if message_id in self._rr_mappings:
            self._rr_mappings[message_id].pop(emoji, None)

    def remove_reaction_role_message(self, guild_id: int, message_id: int) -> None:
        """Remove a reaction role message and all its mappings from the cache."""
        self._rr_message_ids.discard(message_id)
        self._rr_mappings.pop(message_id, None)
        if guild_id in self._rr_by_guild:
            self._rr_by_guild[guild_id].discard(message_id)

    def warm_reaction_roles(self, session_factory) -> None:
        """Bulk-load all reaction role message IDs and emoji mappings from the database.

        Idempotent — safe to call again on reconnect.
        """
        session = session_factory()
        try:
            from models.reactionrole import ReactionRoleMessage

            by_guild: dict[int, set[int]] = {}
            all_ids: set[int] = set()
            mappings: dict[int, dict[str, int]] = {}
            # entries uses lazy="joined", so this single query fetches everything
            messages = session.query(ReactionRoleMessage).all()
            for msg in messages:
                by_guild.setdefault(msg.GuildId, set()).add(msg.MessageId)
                all_ids.add(msg.MessageId)
                mappings[msg.MessageId] = {entry.Emoji: entry.RoleId for entry in msg.entries}
        except Exception:
            _log.exception("warm_reaction_roles: failed to load from DB — staying in degraded mode")
            raise
        finally:
            session.close()

        self._rr_by_guild = by_guild
        self._rr_message_ids = all_ids
        self._rr_mappings = mappings
        self._rr_warmed = True

    # ── Leave messages ────────────────────────────────────────────────────────

    def is_leave_message_guild(self, guild_id: int) -> bool:
        """Return True if the guild has leave messages enabled.

        Returns True unconditionally before warm-up completes (conservative).
        """
        if not self._leave_warmed:
            return True
        return guild_id in self._leave_configs

    def get_leave_config(self, guild_id: int, session_factory) -> tuple[int, str | None] | None:
        """Return (channel_id, message_text) for the guild's enabled leave message, or None.

        Falls back to a direct DB read when the cache has not been warmed yet, matching
        the lazy-load pattern used by ``get_guild_language`` and ``get_modrole``.
        """
        if self._leave_warmed:
            return self._leave_configs.get(guild_id)

        session = session_factory()
        try:
            from models.leavemsg import LeaveMessage

            row = (
                session.query(LeaveMessage)
                .filter(
                    LeaveMessage.GuildId == guild_id,
                    LeaveMessage.Enabled.is_(True),
                )
                .first()
            )
            return (row.ChannelId, row.Message) if row is not None else None
        finally:
            session.close()

    def set_leave_message_guild(
        self,
        guild_id: int,
        enabled: bool,
        channel_id: int | None = None,
        message: str | None = None,
    ) -> None:
        """Add or remove a guild from the leave-message config cache.

        When ``enabled=True``, ``channel_id`` must be provided; passing ``None`` raises
        ``ValueError`` to surface caller bugs early.
        When ``enabled=False``, the guild is evicted regardless of channel_id.
        """
        if enabled:
            if channel_id is None:
                raise ValueError(
                    f"set_leave_message_guild: channel_id is required when enabled=True (guild_id={guild_id})"
                )
            self._leave_configs[guild_id] = (channel_id, message)
        else:
            self._leave_configs.pop(guild_id, None)

    def warm_leave_messages(self, session_factory) -> None:
        """Bulk-load all guild IDs with enabled leave messages from the database.

        Idempotent — safe to call again on reconnect.
        """
        session = session_factory()
        try:
            from models.leavemsg import LeaveMessage

            rows = session.query(LeaveMessage).filter(LeaveMessage.Enabled.is_(True)).all()
            configs = {row.GuildId: (row.ChannelId, row.Message) for row in rows}
        except Exception:
            _log.exception("warm_leave_messages: failed to load from DB — staying in degraded mode")
            raise
        finally:
            session.close()

        self._leave_configs = configs
        self._leave_warmed = True

    # ── Eviction ──────────────────────────────────────────────────────────────

    def evict_guild(self, guild_id: int) -> None:
        """Remove all cached entries for a guild (called when bot leaves a guild)."""
        self._lang.pop(guild_id, None)
        self._modrole.pop(guild_id, None)
        self._leave_configs.pop(guild_id, None)
        guild_rr = self._rr_by_guild.pop(guild_id, None)
        if guild_rr:
            self._rr_message_ids -= guild_rr
            for msg_id in guild_rr:
                self._rr_mappings.pop(msg_id, None)


# ── Autocomplete TTL cache ─────────────────────────────────────────────────────

# Shared cache for autocomplete handlers. Key: (cache_key_prefix, entity_id).
# Short TTL (30s) reduces DB hits during rapid typing while keeping results fresh.
_autocomplete_cache: TTLCache = TTLCache(maxsize=500, ttl=30)


def cached_autocomplete(key: tuple, fetcher):
    """Return cached autocomplete results, calling fetcher() on miss.

    Args:
        key: A hashable tuple uniquely identifying the query (e.g. ("tags", guild_id)).
        fetcher: Zero-argument callable that opens a DB session and returns a list.

    Returns:
        The cached or freshly fetched list.
    """
    if key in _autocomplete_cache:
        return _autocomplete_cache[key]
    result = fetcher()
    _autocomplete_cache[key] = result
    return result


def build_name_choices(names: list[str], current: str) -> list[app_commands.Choice[str]]:
    """Filter a list of names by the current autocomplete input and return up to 25 choices.

    Companion to ``cached_autocomplete`` for the common case where the cache stores
    plain name strings and Discord choices have name == value.
    """
    return [app_commands.Choice(name=n[:100], value=n) for n in names if current.lower() in n.lower()][:25]
