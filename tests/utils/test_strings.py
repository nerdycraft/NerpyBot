# -*- coding: utf-8 -*-
"""Tests for utils/strings.py — localization string lookup."""

import pytest
import yaml

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


class TestGetString:
    def test_fallback_to_english(self, locale_dir):
        strings.load_strings(locale_dir)
        # "farewell" only exists in English
        result = strings.get_string("de", "common.farewell")
        assert result == "Goodbye."

    def test_missing_key_raises(self, locale_dir):
        strings.load_strings(locale_dir)
        with pytest.raises(KeyError):
            strings.get_string("en", "nonexistent.key")

    def test_unknown_language_falls_back_to_english(self, locale_dir):
        strings.load_strings(locale_dir)
        result = strings.get_string("fr", "common.greeting", name="World")
        assert result == "Hello World!"
