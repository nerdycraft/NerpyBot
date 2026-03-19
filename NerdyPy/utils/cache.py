# -*- coding: utf-8 -*-
"""In-memory guild configuration cache to reduce redundant DB queries."""


class GuildConfigCache:
    """Lightweight in-memory cache for per-guild configuration that rarely changes.

    Sub-caches:
    - Guild language: lazy (DB on miss), invalidated by ``guild_language_changed`` event
    - Bot moderator role: lazy (DB on miss), invalidated by ``modrole_changed`` event
    - Reaction role message IDs: bulk-loaded on startup, updated on add/remove
    - Leave message guild IDs: bulk-loaded on startup, updated on enable/disable
    """

    def __init__(self):
        self._lang: dict[int, str] = {}
        self._modrole: dict[int, int | None] = {}
        self._rr_message_ids: set[int] = set()  # flat set for O(1) hot-path lookup
        self._rr_by_guild: dict[int, set[int]] = {}  # guild_id -> set[message_id] for eviction
        self._rr_warmed: bool = False
        self._leave_guild_ids: set[int] = set()
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

    def add_reaction_role_message(self, guild_id: int, message_id: int) -> None:
        """Register a new reaction role message ID in the cache."""
        self._rr_message_ids.add(message_id)
        self._rr_by_guild.setdefault(guild_id, set()).add(message_id)

    def remove_reaction_role_message(self, guild_id: int, message_id: int) -> None:
        """Remove a reaction role message ID from the cache."""
        self._rr_message_ids.discard(message_id)
        if guild_id in self._rr_by_guild:
            self._rr_by_guild[guild_id].discard(message_id)

    def warm_reaction_roles(self, session_factory) -> None:
        """Bulk-load all reaction role message IDs from the database.

        Idempotent — safe to call again on reconnect.
        """
        session = session_factory()
        try:
            from sqlalchemy import select

            from models.reactionrole import ReactionRoleMessage

            by_guild: dict[int, set[int]] = {}
            all_ids: set[int] = set()
            rows = session.execute(select(ReactionRoleMessage.GuildId, ReactionRoleMessage.MessageId)).all()
            for guild_id, message_id in rows:
                by_guild.setdefault(guild_id, set()).add(message_id)
                all_ids.add(message_id)
        finally:
            session.close()

        self._rr_by_guild = by_guild
        self._rr_message_ids = all_ids
        self._rr_warmed = True

    # ── Leave messages ────────────────────────────────────────────────────────

    def is_leave_message_guild(self, guild_id: int) -> bool:
        """Return True if the guild has leave messages enabled.

        Returns True unconditionally before warm-up completes (conservative).
        """
        if not self._leave_warmed:
            return True
        return guild_id in self._leave_guild_ids

    def set_leave_message_guild(self, guild_id: int, enabled: bool) -> None:
        """Add or remove a guild from the leave-message set."""
        if enabled:
            self._leave_guild_ids.add(guild_id)
        else:
            self._leave_guild_ids.discard(guild_id)

    def warm_leave_messages(self, session_factory) -> None:
        """Bulk-load all guild IDs with enabled leave messages from the database.

        Idempotent — safe to call again on reconnect.
        """
        session = session_factory()
        try:
            from sqlalchemy import select

            from models.leavemsg import LeaveMessage

            ids = set(session.scalars(select(LeaveMessage.GuildId).where(LeaveMessage.Enabled.is_(True))))
        finally:
            session.close()

        self._leave_guild_ids = ids
        self._leave_warmed = True

    # ── Eviction ──────────────────────────────────────────────────────────────

    def evict_guild(self, guild_id: int) -> None:
        """Remove all cached entries for a guild (called when bot leaves a guild)."""
        self._lang.pop(guild_id, None)
        self._modrole.pop(guild_id, None)
        self._leave_guild_ids.discard(guild_id)
        guild_rr = self._rr_by_guild.pop(guild_id, None)
        if guild_rr:
            self._rr_message_ids -= guild_rr
