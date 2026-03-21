# -*- coding: utf-8 -*-
"""In-memory guild configuration cache to reduce redundant DB queries."""

import asyncio
import logging
from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError

from cachetools import TTLCache
from discord import app_commands

_log = logging.getLogger(__name__)


@contextmanager
def _open_session(session_factory):
    """Open a SQLAlchemy session and ensure it is closed on exit."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# Sentinel returned by GuildConfigCache.get_reaction_role() when the cache has not been
# warmed yet. Distinguishes "not warmed — fall back to DB" from None ("warmed, no mapping").
REACTION_ROLE_CACHE_MISS = object()


class GuildConfigCache:
    """Lightweight in-memory cache for per-guild configuration that rarely changes.

    Sub-caches:
    - Guild language: lazy (DB on miss), invalidated by ``guild_language_changed`` event
    - Bot moderator role: lazy (DB on miss), invalidated by ``modrole_changed`` event
    - Reaction role message IDs: bulk-loaded on startup, updated on add/remove
    - Reaction role mappings: bulk-loaded on startup, updated on add/remove entry
    - Leave message configs: bulk-loaded on startup, lazy-loaded on cold miss, updated on enable/disable/edit
    """

    def __init__(self):
        self._lang: dict[int, str] = {}
        self._modrole: dict[int, int | None] = {}
        self._rr_message_ids: set[int] = set()  # flat set for O(1) hot-path lookup
        self._rr_by_guild: dict[int, set[int]] = {}  # guild_id -> set[message_id] for eviction
        self._rr_mappings: dict[int, dict[str, int]] = {}
        self._rr_warmed: bool = False
        self._leave_configs: dict[int, tuple[int, str | None] | None] = {}
        self._leave_warmed: bool = False

    @staticmethod
    def _run_warm(session_factory, loader_fn, error_label: str):
        """Run a bulk DB load inside a session.

        Logs and re-raises ``SQLAlchemyError`` so callers stay in degraded mode
        with a clear error entry. Non-SQLAlchemy exceptions (e.g. programming
        errors in ``loader_fn``) propagate uncaught so the real exception type
        is visible.

        Args:
            session_factory: Callable that returns a new SQLAlchemy session.
            loader_fn: ``(session) -> T`` — performs the query and returns data.
            error_label: Prefix used in the error log message.

        Returns:
            Whatever ``loader_fn`` returns.
        """
        with _open_session(session_factory) as session:
            try:
                return loader_fn(session)
            except SQLAlchemyError:
                _log.exception("%s: failed to load from DB — staying in degraded mode", error_label)
                raise

    # ── Language ──────────────────────────────────────────────────────────────

    def get_guild_language(self, guild_id: int, session_factory) -> str:
        """Return the guild's language, loading from DB on first access."""
        if guild_id in self._lang:
            return self._lang[guild_id]

        try:
            with _open_session(session_factory) as session:
                from models.admin import GuildLanguageConfig

                config = GuildLanguageConfig.get(guild_id, session)
                lang = config.Language if config is not None else "en"
        except SQLAlchemyError:
            _log.exception("get_guild_language: DB read failed for guild_id=%d", guild_id)
            raise

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

        try:
            with _open_session(session_factory) as session:
                from models.admin import BotModeratorRole

                entry = BotModeratorRole.get(guild_id, session)
                role_id = entry.RoleId if entry is not None else None
        except SQLAlchemyError:
            _log.exception("get_modrole: DB read failed for guild_id=%d", guild_id)
            raise

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

    def get_reaction_role(self, message_id: int, emoji: str):
        """Return the role ID for the given message + emoji.

        Returns:
            ``REACTION_ROLE_CACHE_MISS`` if the cache has not been warmed yet
                (caller must fall back to DB).
            ``None`` if the cache is warmed but the emoji has no mapping
                (caller should skip the DB query).
            ``int`` role ID if a mapping exists.
        """
        if not self._rr_warmed:
            return REACTION_ROLE_CACHE_MISS
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
        """Remove a single emoji-to-role mapping from a tracked message.

        No-op before warm-up — pre-warm the cache has no mappings to remove.
        """
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
        from models.reactionrole import ReactionRoleMessage

        def _load(session):
            from models.reactionrole import ReactionRoleEntry
            from sqlalchemy import select

            by_guild: dict[int, set[int]] = {}
            all_ids: set[int] = set()
            mappings: dict[int, dict[str, int]] = {}
            for guild_id, msg_id, emoji, role_id in session.execute(
                select(
                    ReactionRoleMessage.GuildId,
                    ReactionRoleMessage.MessageId,
                    ReactionRoleEntry.Emoji,
                    ReactionRoleEntry.RoleId,
                ).outerjoin(ReactionRoleEntry, ReactionRoleEntry.ReactionRoleMessageId == ReactionRoleMessage.Id)
            ).all():
                if msg_id not in all_ids:
                    by_guild.setdefault(guild_id, set()).add(msg_id)
                    all_ids.add(msg_id)
                    mappings[msg_id] = {}
                if emoji is not None:
                    mappings[msg_id][emoji] = role_id
            return by_guild, all_ids, mappings

        self._rr_by_guild, self._rr_message_ids, self._rr_mappings = self._run_warm(
            session_factory, _load, "warm_reaction_roles"
        )
        self._rr_warmed = True

    # ── Leave messages ────────────────────────────────────────────────────────

    def is_leave_message_guild(self, guild_id: int) -> bool:
        """Return True if the guild has leave messages enabled.

        Returns True unconditionally before warm-up completes (conservative).
        """
        if not self._leave_warmed:
            return True
        return guild_id in self._leave_configs

    @staticmethod
    def _query_leave_row(guild_id: int, session):
        """Return the enabled LeaveMessage row for a guild, or None if not found."""
        from models.leavemsg import LeaveMessage
        from sqlalchemy import select

        return session.execute(
            select(LeaveMessage).where(
                LeaveMessage.GuildId == guild_id,
                LeaveMessage.Enabled.is_(True),
            )
        ).scalar_one_or_none()

    def get_leave_config(self, guild_id: int, session_factory) -> tuple[int, str | None] | None:
        """Return ``(channel_id, message_text)`` for the guild's enabled leave message.

        Returns ``None`` when the guild has no enabled leave message.
        Falls back to a direct DB read when the cache has not been warmed yet and populates
        the per-guild entry so subsequent calls are served from memory.

        On ``SQLAlchemyError``, logs the error and returns ``None`` without caching — the
        entry stays absent so the next call retries the DB. Unlike ``get_guild_language``
        and ``get_modrole``, this intentionally swallows the error to keep ``on_member_remove``
        non-fatal; callers must not treat ``None`` as a definitive "no config" when the cache
        is cold.
        """
        if self._leave_warmed or guild_id in self._leave_configs:
            return self._leave_configs.get(guild_id)

        try:
            with _open_session(session_factory) as session:
                row = self._query_leave_row(guild_id, session)
                config = (row.ChannelId, row.Message) if row is not None else None
        except SQLAlchemyError:
            _log.exception("get_leave_config: DB read failed for guild_id=%d — returning None", guild_id)
            return None

        self._leave_configs[guild_id] = config
        return config

    def set_leave_config(self, guild_id: int, channel_id: int, message: str | None) -> None:
        """Upsert the leave message config for a guild."""
        self._leave_configs[guild_id] = (channel_id, message)

    def evict_leave_config(self, guild_id: int) -> None:
        """Remove the leave message config for a guild."""
        self._leave_configs.pop(guild_id, None)

    def reload_leave_config(self, guild_id: int, session_factory) -> None:
        """Force a fresh DB read for a guild's leave config and update the cache.

        Unlike ``get_leave_config``, this bypasses the ``_leave_warmed`` short-circuit
        and always hits the DB. Use after an external mutation (e.g. web dashboard
        enable/disable) so ``is_leave_message_guild`` reflects the new state immediately
        rather than waiting for an eviction-triggered cold miss that would never arrive
        when ``_leave_warmed=True``.

        On ``SQLAlchemyError``, logs the error and falls back to eviction so the next
        ``on_member_remove`` retries the DB read via the cold-miss path.
        """
        try:
            with _open_session(session_factory) as session:
                row = self._query_leave_row(guild_id, session)
        except SQLAlchemyError:
            _log.exception(
                "reload_leave_config: DB read failed for guild_id=%d — evicting so cold-miss retries on next member-remove",
                guild_id,
            )
            self.evict_leave_config(guild_id)
            return

        if row is not None:
            self._leave_configs[guild_id] = (row.ChannelId, row.Message)
        else:
            self.evict_leave_config(guild_id)

    def warm_leave_messages(self, session_factory) -> None:
        """Bulk-load full leave message configs (channel_id, message) for all enabled guilds.

        Idempotent — safe to call again on reconnect.
        """
        from models.leavemsg import LeaveMessage

        def _load(session):
            from sqlalchemy import select

            rows = session.execute(select(LeaveMessage).where(LeaveMessage.Enabled.is_(True))).scalars().all()
            return {row.GuildId: (row.ChannelId, row.Message) for row in rows}

        self._leave_configs = self._run_warm(session_factory, _load, "warm_leave_messages")
        self._leave_warmed = True

    # ── Eviction ──────────────────────────────────────────────────────────────

    def evict_guild(self, guild_id: int) -> None:
        """Remove all cached entries for a guild (called when bot leaves a guild)."""
        self._lang.pop(guild_id, None)
        self._modrole.pop(guild_id, None)
        self.evict_leave_config(guild_id)
        guild_rr = self._rr_by_guild.pop(guild_id, None)
        if guild_rr:
            self._rr_message_ids -= guild_rr
            for msg_id in guild_rr:
                self._rr_mappings.pop(msg_id, None)


# ── Autocomplete TTL cache ─────────────────────────────────────────────────────

# Shared cache for autocomplete handlers. Key: (cache_key_prefix, entity_id).
# Short TTL (30s) reduces DB hits during rapid typing while keeping results fresh.
_autocomplete_cache: TTLCache = TTLCache(maxsize=500, ttl=30)


async def cached_autocomplete(key: tuple, fetcher):
    """Return cached autocomplete results, calling fetcher() on miss.

    Args:
        key: A hashable tuple uniquely identifying the query (e.g. ("tags", guild_id)).
        fetcher: Zero-argument callable that opens a DB session and returns a list.
            Run in a thread pool on cache miss to avoid blocking the event loop.

    Returns:
        The cached or freshly fetched list.

    Error handling:
        ``SQLAlchemyError`` is caught, logged, and returns ``[]`` without caching
        so the next keystroke retries. Non-DB exceptions (programming errors,
        unexpected import failures) propagate uncaught so they surface immediately
        rather than silently returning empty results on every keystroke.
    """
    if key in _autocomplete_cache:
        return _autocomplete_cache[key]
    # No lock: two concurrent keystrokes for the same key can both miss and fire parallel DB
    # fetches. Both write the same result, so this is benign — Discord's 3s autocomplete
    # window makes true simultaneity rare, and the TTL window suppresses all subsequent hits.
    try:
        result = await asyncio.to_thread(fetcher)
    except SQLAlchemyError:
        _log.exception("cached_autocomplete: fetcher for key %r raised an error", key)
        return []
    _autocomplete_cache[key] = result
    return result


def invalidate_autocomplete(key: tuple) -> None:
    """Evict a single key from the autocomplete cache.

    Call after mutations that change the result set (e.g. adding/removing a reaction role
    message), so the next autocomplete call fetches fresh data rather than serving stale
    labels for up to 30 seconds.
    """
    _autocomplete_cache.pop(key, None)


def build_name_choices(names: list[str], current: str) -> list[app_commands.Choice[str]]:
    """Filter a list of names by the current autocomplete input and return up to 25 choices.

    Companion to ``cached_autocomplete`` for the common case where the cache stores
    plain name strings and Discord choices have name == value.
    """
    return [app_commands.Choice(name=n[:100], value=n[:100]) for n in names if current.lower() in n.lower()][:25]
