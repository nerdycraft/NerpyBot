# -*- coding: utf-8 -*-
"""Tests for models/tagging.py - Tag and TagEntry models"""

from datetime import UTC, datetime

from models.tagging import Tag, TagEntry, TagType


class TestTagGetAllFromGuild:
    """Tests for Tag.get_all_from_guild() class method."""

    def test_get_all_returns_guild_tags(self, db_session):
        """Should return all tags for a guild."""
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

        results = Tag.get_all_from_guild(123, db_session)
        assert len(results) == 3

    def test_get_all_excludes_other_guilds(self, db_session):
        """Should only return tags from specified guild."""
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

        results = Tag.get_all_from_guild(111, db_session)
        assert len(results) == 2

    def test_get_all_ordered_by_name(self, db_session):
        """Results should be ordered by name ascending."""
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

        results = Tag.get_all_from_guild(123, db_session)
        names = [t.Name for t in results]
        assert names == ["apple", "mango", "zebra"]


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


class TestTagDelete:
    """Tests for cascade delete behaviour."""

    def test_delete_cascades_to_entries(self, db_session):
        """Deleting tag should delete its entries too."""
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

        tag.add_entry("Entry 1", db_session)
        tag.add_entry("Entry 2", db_session)
        db_session.commit()

        entry_ids = [e.Id for e in tag.entries.all()]

        Tag.delete("with-entries", 123, db_session)
        db_session.commit()

        for entry_id in entry_ids:
            entry = db_session.query(TagEntry).filter(TagEntry.Id == entry_id).first()
            assert entry is None
