# -*- coding: utf-8 -*-
"""Tests for utils/strings.py — localization string lookup."""

import pytest
import yaml

from models.admin import GuildLanguageConfig
from utils import strings


@pytest.fixture
def locale_dir(tmp_path):
    """Create temporary locale YAML files for testing."""
    en = {
        "common": {"greeting": "Hello {name}!", "farewell": "Goodbye."},
        "admin": {"language": {"set_success": "Language set to {language}."}},
        "templates": {
            "guild": {
                "name": "Guild Membership",
                "questions": ["Question 1?", "Question 2?"],
                "nested": {"deep": "value"},
            }
        },
    }
    de = {
        "common": {"greeting": "Hallo {name}!"},
        "admin": {"language": {"set_success": "Sprache auf {language} gesetzt."}},
        "templates": {
            "guild": {
                "name": "Gildenmitgliedschaft",
                "questions": ["Frage 1?", "Frage 2?"],
            }
        },
    }
    (tmp_path / "lang_en.yaml").write_text(yaml.dump(en))
    (tmp_path / "lang_de.yaml").write_text(yaml.dump(de))
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_strings():
    """Reset module-level state between tests."""
    strings._strings.clear()
    strings._available_languages.clear()
    yield
    strings._strings.clear()
    strings._available_languages.clear()


class TestLoadStrings:
    def test_discovers_language_files(self, locale_dir):
        strings.load_strings(locale_dir)
        assert sorted(strings.available_languages()) == ["de", "en"]

    def test_loads_nested_content(self, locale_dir):
        strings.load_strings(locale_dir)
        assert strings._strings["en"]["common"]["greeting"] == "Hello {name}!"

    def test_ignores_non_lang_files(self, locale_dir):
        (locale_dir / "other.yaml").write_text("foo: bar")
        strings.load_strings(locale_dir)
        assert sorted(strings.available_languages()) == ["de", "en"]


class TestGetString:
    def test_returns_english(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("en", "common.greeting", name="World")
        assert result == "Hello World!"

    def test_returns_german(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("de", "common.greeting", name="Welt")
        assert result == "Hallo Welt!"

    def test_fallback_to_english(self, locale_dir):
        strings.load_strings(locale_dir)
        # "farewell" only exists in English
        result = strings.get_string("de", "common.farewell")
        assert result == "Goodbye."

    def test_missing_key_raises(self, locale_dir):
        strings.load_strings(locale_dir)
        with pytest.raises(KeyError):
            strings.get_string("en", "nonexistent.key")

    def test_format_kwargs(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("en", "admin.language.set_success", language="German")
        assert result == "Language set to German."

    def test_unknown_language_falls_back_to_english(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("fr", "common.greeting", name="World")
        assert result == "Hello World!"

    def test_no_kwargs_returns_raw_string(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("en", "common.farewell")
        assert result == "Goodbye."


class TestGetRaw:
    def test_returns_list(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_raw("en", "templates.guild.questions")
        assert result == ["Question 1?", "Question 2?"]

    def test_returns_dict(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_raw("en", "templates.guild.nested")
        assert result == {"deep": "value"}

    def test_returns_string(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_raw("en", "templates.guild.name")
        assert result == "Guild Membership"

    def test_fallback_to_english(self, locale_dir):
        strings.load_strings(locale_dir)
        # "nested" only exists in English
        result = strings.get_raw("de", "templates.guild.nested")
        assert result == {"deep": "value"}

    def test_missing_key_raises(self, locale_dir):
        strings.load_strings(locale_dir)
        with pytest.raises(KeyError):
            strings.get_raw("en", "nonexistent.key")

    def test_no_format_applied(self, locale_dir):
        strings.load_strings(locale_dir)
        # get_raw returns the raw string without calling .format()
        result = strings.get_raw("en", "common.greeting")
        assert result == "Hello {name}!"

    def test_german_list(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_raw("de", "templates.guild.questions")
        assert result == ["Frage 1?", "Frage 2?"]


class TestGetGuildLanguage:
    def test_default_when_no_config(self, db_session):
        result = strings.get_guild_language(999, db_session)
        assert result == "en"

    def test_returns_configured_language(self, db_session):
        db_session.add(GuildLanguageConfig(GuildId=123, Language="de"))
        db_session.commit()
        result = strings.get_guild_language(123, db_session)
        assert result == "de"


class TestGetLocalizedString:
    def test_combines_guild_language_and_lookup(self, locale_dir, db_session):
        strings.load_strings(locale_dir)
        db_session.add(GuildLanguageConfig(GuildId=123, Language="de"))
        db_session.commit()
        result = strings.get_localized_string(123, "common.greeting", db_session, name="Welt")
        assert result == "Hallo Welt!"

    def test_defaults_to_english(self, locale_dir, db_session):
        strings.load_strings(locale_dir)
        result = strings.get_localized_string(999, "common.greeting", db_session, name="World")
        assert result == "Hello World!"
