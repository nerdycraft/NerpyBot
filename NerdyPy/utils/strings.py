# -*- coding: utf-8 -*-
"""Localized string lookup — loads YAML templates and resolves per-guild language."""

from pathlib import Path

import yaml
from models.admin import GuildLanguageConfig

# Module-level state, populated by load_strings()
_strings: dict[str, dict] = {}
_available_languages: list[str] = []


def load_strings(locales_dir: Path | None = None) -> None:
    """Scan locales directory for lang_*.yaml files and load them into memory.

    Args:
        locales_dir: Path to the locales directory. Defaults to NerdyPy/locales/.
    """
    if locales_dir is None:
        locales_dir = Path(__file__).parent.parent / "locales"

    _strings.clear()
    _available_languages.clear()

    for path in sorted(locales_dir.glob("lang_*.yaml")):
        lang_code = path.stem.removeprefix("lang_")
        with open(path, encoding="utf-8") as f:
            _strings[lang_code] = yaml.safe_load(f) or {}
        _available_languages.append(lang_code)


def available_languages() -> list[str]:
    """Return the list of discovered language codes."""
    return list(_available_languages)


def _traverse(data: dict, key: str) -> str | None:
    """Traverse a nested dict by dot-separated key. Returns None if not found."""
    parts = key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, str) else None


_SENTINEL = object()


def _traverse_raw(data: dict, key: str):
    """Traverse a nested dict by dot-separated key. Returns any leaf type."""
    parts = key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _SENTINEL
        current = current[part]
    return current


def get_string(lang: str, key: str, **kwargs) -> str:
    """Look up a localized string by dot-notation key with English fallback.

    Args:
        lang: Language code (e.g. "de").
        key: Dot-notation key (e.g. "admin.language.set_success").
        **kwargs: Format arguments for the string template.

    Returns:
        The formatted string.

    Raises:
        KeyError: If the key is missing from both the target language and English.
    """
    # Try target language
    if lang in _strings:
        result = _traverse(_strings[lang], key)
        if result is not None:
            return result.format(**kwargs) if kwargs else result

    # Fallback to English
    if "en" in _strings:
        result = _traverse(_strings["en"], key)
        if result is not None:
            return result.format(**kwargs) if kwargs else result

    raise KeyError(f"Missing localization key: {key}")


def get_raw(lang: str, key: str):
    """Look up any YAML value by dot-notation key with English fallback.

    Unlike ``get_string``, this returns the raw value (list, dict, string, etc.)
    without calling ``.format()``.

    Raises:
        KeyError: If the key is missing from both the target language and English.
    """
    if lang in _strings:
        result = _traverse_raw(_strings[lang], key)
        if result is not _SENTINEL:
            return result

    if "en" in _strings:
        result = _traverse_raw(_strings["en"], key)
        if result is not _SENTINEL:
            return result

    raise KeyError(f"Missing localization key: {key}")


def get_guild_language(guild_id: int, session) -> str:
    """Get the configured language for a guild, defaulting to 'en'."""
    config = GuildLanguageConfig.get(guild_id, session)
    return config.Language if config is not None else "en"


def get_localized_string(guild_id: int, key: str, session, **kwargs) -> str:
    """Convenience: resolve guild language, then look up and format a string."""
    lang = get_guild_language(guild_id, session)
    return get_string(lang, key, **kwargs)
