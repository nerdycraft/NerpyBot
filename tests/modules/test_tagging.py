# -*- coding: utf-8 -*-
"""Tests for modules/tagging.py - Tag system commands"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from models.admin import GuildLanguageConfig
from models.tagging import Tag, TagType, TagTypeConverter
from modules.tagging import Tagging
from utils.errors import NerpyValidationError
from utils.strings import load_strings


class TestTagTypeConverter:
    """Tests for the TagTypeConverter command converter."""

    @pytest.fixture
    def converter(self):
        """Create a TagTypeConverter instance."""
        return TagTypeConverter()

    @pytest.fixture
    def mock_ctx(self):
        """Create minimal mock context for converter."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_convert_sound_type(self, converter, mock_ctx):
        """'sound' should convert to TagType.sound.value (0)."""
        result = await converter.convert(mock_ctx, "sound")
        assert result == TagType.sound.value
        assert result == 0

    @pytest.mark.asyncio
    async def test_convert_text_type(self, converter, mock_ctx):
        """'text' should convert to TagType.text.value (1)."""
        result = await converter.convert(mock_ctx, "text")
        assert result == TagType.text.value
        assert result == 1

    @pytest.mark.asyncio
    async def test_convert_url_type(self, converter, mock_ctx):
        """'url' should convert to TagType.url.value (2)."""
        result = await converter.convert(mock_ctx, "url")
        assert result == TagType.url.value
        assert result == 2

    @pytest.mark.asyncio
    async def test_convert_case_insensitive(self, converter, mock_ctx):
        # noinspection GrazieInspection
        """Conversion should be case insensitive."""
        assert await converter.convert(mock_ctx, "SOUND") == TagType.sound.value
        assert await converter.convert(mock_ctx, "Text") == TagType.text.value
        assert await converter.convert(mock_ctx, "URL") == TagType.url.value

    @pytest.mark.asyncio
    async def test_convert_invalid_type_raises(self, converter, mock_ctx):
        """Invalid type should raise NerpyValidationError."""
        with pytest.raises(NerpyValidationError, match="TagType invalid was not found"):
            await converter.convert(mock_ctx, "invalid")

    @pytest.mark.asyncio
    async def test_convert_empty_string_raises(self, converter, mock_ctx):
        """Empty string should raise NerpyValidationError."""
        with pytest.raises(NerpyValidationError):
            await converter.convert(mock_ctx, "")


class TestTagType:
    """Tests for TagType enum."""

    def test_tag_type_values(self):
        """Verify TagType enum values."""
        assert TagType.sound.value == 0
        assert TagType.text.value == 1
        assert TagType.url.value == 2

    def test_tag_type_names(self):
        """Verify TagType can be accessed by name."""
        assert TagType["sound"] == TagType.sound
        assert TagType["text"] == TagType.text
        assert TagType["url"] == TagType.url

    def test_tag_type_from_value(self):
        """Verify TagType can be created from value."""
        assert TagType(0) == TagType.sound
        assert TagType(1) == TagType.text
        assert TagType(2) == TagType.url


class TestVolumeValidation:
    """Tests for volume validation in tagging module."""

    def test_volume_stored_as_integer(self, db_session):
        """Volume should be stored as integer."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.sound.value,
            Author="test",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        retrieved = Tag.get("test", 123, db_session)
        assert isinstance(retrieved.Volume, int)
        assert retrieved.Volume == 100

    def test_volume_default_is_100(self, db_session):
        """Default volume for new tags should be 100."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.sound.value,
            Author="test",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        retrieved = Tag.get("test", 123, db_session)
        assert retrieved.Volume == 100

    def test_volume_can_be_set_to_zero(self, db_session):
        """Volume of 0 should be allowed (muted)."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.sound.value,
            Author="test",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=0,
        )
        db_session.add(tag)
        db_session.commit()

        retrieved = Tag.get("test", 123, db_session)
        assert retrieved.Volume == 0

    def test_volume_can_be_above_100(self, db_session):
        """Volume above 100 should be allowed (amplified)."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.sound.value,
            Author="test",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=200,
        )
        db_session.add(tag)
        db_session.commit()

        retrieved = Tag.get("test", 123, db_session)
        assert retrieved.Volume == 200


# ---------------------------------------------------------------------------
# Localization tests for tagging commands
# ---------------------------------------------------------------------------


@pytest.fixture
def _load_locale_strings():
    load_strings()


@pytest.fixture
def tagging_cog(mock_bot):
    cog = Tagging.__new__(Tagging)
    cog.bot = mock_bot
    cog.queue = {}
    cog.audio = MagicMock()
    cog.audio.stop = MagicMock()
    return cog


@pytest.fixture
def tagging_interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


class TestTagSkipLocale:
    async def test_skip_english(self, _load_locale_strings, tagging_cog, tagging_interaction):
        await Tagging._skip_audio.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "Skipped" in msg

    async def test_skip_german(self, _load_locale_strings, tagging_cog, tagging_interaction, db_session):
        _set_german(db_session)
        await Tagging._skip_audio.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "Übersprungen" in msg


class TestTagQueueDropLocale:
    async def test_drop_english(self, _load_locale_strings, tagging_cog, tagging_interaction):
        await Tagging._drop_queue.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "Queue dropped" in msg

    async def test_drop_german(self, _load_locale_strings, tagging_cog, tagging_interaction, db_session):
        _set_german(db_session)
        await Tagging._drop_queue.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "Warteschlange" in msg


class TestTagCreateLocale:
    async def test_create_already_exists(self, _load_locale_strings, tagging_cog, tagging_interaction, monkeypatch):
        monkeypatch.setattr("modules.tagging.Tag.exists", lambda name, gid, sess: True)

        await Tagging._tag_create.callback(tagging_cog, tagging_interaction, "test", "text", "hello")

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "already exists" in msg

    async def test_create_already_exists_german(
        self, _load_locale_strings, tagging_cog, tagging_interaction, db_session, monkeypatch
    ):
        _set_german(db_session)
        monkeypatch.setattr("modules.tagging.Tag.exists", lambda name, gid, sess: True)

        await Tagging._tag_create.callback(tagging_cog, tagging_interaction, "test", "text", "hello")

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "existiert bereits" in msg


class TestTagVolumeLocale:
    async def test_volume_out_of_range(self, _load_locale_strings, tagging_cog, tagging_interaction):
        await Tagging._tag_volume.callback(tagging_cog, tagging_interaction, "test", 999)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "between 0 and 200" in msg

    async def test_volume_out_of_range_german(self, _load_locale_strings, tagging_cog, tagging_interaction, db_session):
        _set_german(db_session)
        await Tagging._tag_volume.callback(tagging_cog, tagging_interaction, "test", 999)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "zwischen 0 und 200" in msg


class TestTagDeleteLocale:
    async def test_delete_not_found(self, _load_locale_strings, tagging_cog, tagging_interaction, monkeypatch):
        monkeypatch.setattr("modules.tagging.Tag.exists", lambda name, gid, sess: False)

        await Tagging._tag_delete.callback(tagging_cog, tagging_interaction, "missing")

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "doesn't exist" in msg

    async def test_delete_not_found_german(
        self, _load_locale_strings, tagging_cog, tagging_interaction, db_session, monkeypatch
    ):
        _set_german(db_session)
        monkeypatch.setattr("modules.tagging.Tag.exists", lambda name, gid, sess: False)

        await Tagging._tag_delete.callback(tagging_cog, tagging_interaction, "missing")

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "existiert nicht" in msg


class TestTagListLocale:
    async def test_list_empty(self, _load_locale_strings, tagging_cog, tagging_interaction, monkeypatch):
        monkeypatch.setattr("modules.tagging.Tag.get_all_from_guild", lambda gid, sess: [])

        await Tagging._tag_list.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "No tags found" in msg

    async def test_list_empty_german(
        self, _load_locale_strings, tagging_cog, tagging_interaction, db_session, monkeypatch
    ):
        _set_german(db_session)
        monkeypatch.setattr("modules.tagging.Tag.get_all_from_guild", lambda gid, sess: [])

        await Tagging._tag_list.callback(tagging_cog, tagging_interaction)

        msg = tagging_interaction.response.send_message.call_args[0][0]
        assert "Keine Tags gefunden" in msg
