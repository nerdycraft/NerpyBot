# -*- coding: utf-8 -*-
"""Tests for models/tagging.py - Tag and TagEntry models"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from models.tagging import Tag, TagEntry, TagType, TagTypeConverter


class TestTagGet:
    """Tests for Tag.get() class method."""

    def test_get_existing_tag(self, db_session):
        """Should return tag by name and guild."""
        # Setup
        tag = Tag(
            GuildId=123,
            Name="test-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Test
        result = Tag.get("test-tag", 123, db_session)

        assert result is not None
        assert result.Name == "test-tag"
        assert result.GuildId == 123

    def test_get_nonexistent_tag_returns_none(self, db_session):
        """Should return None for non-existent tag."""
        result = Tag.get("nonexistent", 123, db_session)
        assert result is None

    def test_get_tag_wrong_guild_returns_none(self, db_session):
        """Should return None when guild doesn't match."""
        tag = Tag(
            GuildId=123,
            Name="test-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Test with different guild
        result = Tag.get("test-tag", 999, db_session)
        assert result is None


class TestTagExists:
    """Tests for Tag.exists() class method."""

    def test_exists_returns_true_for_existing_tag(self, db_session):
        """Should return True when tag exists."""
        tag = Tag(
            GuildId=123,
            Name="existing-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert Tag.exists("existing-tag", 123, db_session) is True

    def test_exists_returns_false_for_nonexistent_tag(self, db_session):
        """Should return False when tag doesn't exist."""
        assert Tag.exists("nonexistent", 123, db_session) is False

    def test_exists_is_guild_scoped(self, db_session):
        """Should only find tags in the specified guild."""
        tag = Tag(
            GuildId=123,
            Name="guild-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert Tag.exists("guild-tag", 123, db_session) is True
        assert Tag.exists("guild-tag", 999, db_session) is False


class TestTagAdd:
    """Tests for Tag.add() class method."""

    def test_add_new_tag(self, db_session):
        """Should add tag to database."""
        tag = Tag(
            GuildId=123,
            Name="new-tag",
            Type=TagType.sound.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )

        Tag.add(tag, db_session)
        db_session.commit()

        # Verify
        result = Tag.get("new-tag", 123, db_session)
        assert result is not None
        assert result.Name == "new-tag"


class TestTagDelete:
    """Tests for Tag.delete() class method."""

    def test_delete_existing_tag(self, db_session):
        """Should remove tag from database."""
        tag = Tag(
            GuildId=123,
            Name="to-delete",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Delete
        Tag.delete("to-delete", 123, db_session)
        db_session.commit()

        # Verify
        assert Tag.get("to-delete", 123, db_session) is None

    def test_delete_cascades_to_entries(self, db_session):
        """Deleting tag should delete its entries too."""
        # Setup tag with entries
        tag = Tag(
            GuildId=123,
            Name="with-entries",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Add entries
        tag.add_entry("Entry 1", db_session)
        tag.add_entry("Entry 2", db_session)
        db_session.commit()

        # Get entry IDs before delete
        entry_ids = [e.Id for e in tag.entries.all()]

        # Delete tag
        Tag.delete("with-entries", 123, db_session)
        db_session.commit()

        # Verify entries are gone
        for entry_id in entry_ids:
            entry = db_session.query(TagEntry).filter(TagEntry.Id == entry_id).first()
            assert entry is None


class TestTagAddEntry:
    """Tests for Tag.add_entry() instance method."""

    def test_add_text_entry(self, db_session):
        """Should add text entry to tag."""
        tag = Tag(
            GuildId=123,
            Name="text-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Add entry
        tag.add_entry("Hello World", db_session)
        db_session.commit()

        # Verify
        entries = tag.entries.all()
        assert len(entries) == 1
        assert entries[0].TextContent == "Hello World"

    def test_add_multiple_entries(self, db_session):
        """Should support multiple entries per tag."""
        tag = Tag(
            GuildId=123,
            Name="multi-entry",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Add multiple entries
        tag.add_entry("Entry 1", db_session)
        tag.add_entry("Entry 2", db_session)
        tag.add_entry("Entry 3", db_session)
        db_session.commit()

        # Verify
        assert tag.entries.count() == 3

    def test_add_entry_with_bytes(self, db_session):
        """Should support binary content for sound tags."""
        tag = Tag(
            GuildId=123,
            Name="sound-tag",
            Type=TagType.sound.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        # Add entry with bytes
        audio_bytes = b"fake audio data"
        tag.add_entry("audio.mp3", db_session, byt=audio_bytes)
        db_session.commit()

        # Verify
        entry = tag.entries.first()
        assert entry.ByteContent == audio_bytes


class TestTagGetRandomEntry:
    """Tests for Tag.get_random_entry() instance method."""

    def test_get_random_returns_entry(self, db_session):
        """Should return one of the tag's entries."""
        tag = Tag(
            GuildId=123,
            Name="random-tag",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        tag.add_entry("Entry A", db_session)
        tag.add_entry("Entry B", db_session)
        tag.add_entry("Entry C", db_session)
        db_session.commit()

        # Test multiple times
        valid_contents = ["Entry A", "Entry B", "Entry C"]
        for _ in range(10):
            entry = tag.get_random_entry()
            assert entry.TextContent in valid_contents

    def test_get_random_single_entry(self, db_session):
        """Should return the only entry when only one exists."""
        tag = Tag(
            GuildId=123,
            Name="single-entry",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        tag.add_entry("Only Entry", db_session)
        db_session.commit()

        entry = tag.get_random_entry()
        assert entry.TextContent == "Only Entry"


class TestTagGetAllFromGuild:
    """Tests for Tag.get_all_from_guild() class method."""

    def test_get_all_returns_guild_tags(self, db_session):
        """Should return all tags for a guild."""
        # Create tags for guild 123
        for name in ["alpha", "beta", "gamma"]:
            tag = Tag(
                GuildId=123,
                Name=name,
                Type=TagType.text.value,
                Author="TestUser",
                CreateDate=datetime.now(UTC),
                Count=0,
                Volume=100,
            )
            db_session.add(tag)
        db_session.commit()

        # Test
        results = Tag.get_all_from_guild(123, db_session)
        assert len(results) == 3

    def test_get_all_excludes_other_guilds(self, db_session):
        """Should only return tags from specified guild."""
        # Tags for different guilds
        for guild_id, name in [(111, "tag1"), (111, "tag2"), (222, "tag3")]:
            tag = Tag(
                GuildId=guild_id,
                Name=name,
                Type=TagType.text.value,
                Author="TestUser",
                CreateDate=datetime.now(UTC),
                Count=0,
                Volume=100,
            )
            db_session.add(tag)
        db_session.commit()

        # Test
        results = Tag.get_all_from_guild(111, db_session)
        assert len(results) == 2

    def test_get_all_ordered_by_name(self, db_session):
        """Results should be ordered by name ascending."""
        # Create in reverse alphabetical order
        for name in ["zebra", "apple", "mango"]:
            tag = Tag(
                GuildId=123,
                Name=name,
                Type=TagType.text.value,
                Author="TestUser",
                CreateDate=datetime.now(UTC),
                Count=0,
                Volume=100,
            )
            db_session.add(tag)
        db_session.commit()

        # Test
        results = Tag.get_all_from_guild(123, db_session)
        names = [t.Name for t in results]
        assert names == ["apple", "mango", "zebra"]


class TestTagStr:
    """Tests for Tag.__str__() method."""

    def test_str_contains_name(self, db_session):
        """String should contain tag name."""
        tag = Tag(
            GuildId=123,
            Name="test-tag-name",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert "test-tag-name" in str(tag)

    def test_str_contains_author(self, db_session):
        """String should contain author."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.text.value,
            Author="SpecificAuthor",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert "SpecificAuthor" in str(tag)

    def test_str_contains_type(self, db_session):
        """String should contain tag type."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.sound.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=0,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert "sound" in str(tag)

    def test_str_contains_hit_count(self, db_session):
        """String should contain hit count."""
        tag = Tag(
            GuildId=123,
            Name="test",
            Type=TagType.text.value,
            Author="TestUser",
            CreateDate=datetime.now(UTC),
            Count=42,
            Volume=100,
        )
        db_session.add(tag)
        db_session.commit()

        assert "42" in str(tag)


class TestTagTypeConverterModel:
    """Additional tests for TagTypeConverter from models."""

    @pytest.fixture
    def converter(self):
        return TagTypeConverter()

    @pytest.fixture
    def mock_ctx(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_all_valid_types_convert(self, converter, mock_ctx):
        """All TagType enum values should be convertible."""
        for tag_type in TagType:
            result = await converter.convert(mock_ctx, tag_type.name)
            assert result == tag_type.value

    @pytest.mark.asyncio
    async def test_mixed_case_conversion(self, converter, mock_ctx):
        """Should handle various case combinations."""
        test_cases = ["SOUND", "Sound", "sOuNd", "TEXT", "text", "URL", "Url"]

        for case in test_cases:
            result = await converter.convert(mock_ctx, case)
            assert result in [t.value for t in TagType]
