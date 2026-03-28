"""Shared constants used across bot modules and utilities."""

# Modules that are always auto-loaded by the bot and must never be unloaded at runtime.
PROTECTED_MODULES: frozenset[str] = frozenset({"server_admin", "operator"})
