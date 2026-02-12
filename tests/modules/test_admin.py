# -*- coding: utf-8 -*-
"""Tests for modules/admin.py - Administrative commands"""

from datetime import UTC, datetime

import pytest

from models.admin import GuildPrefix
from modules.admin import Admin


@pytest.fixture
def admin_cog(mock_bot):
    """Create an Admin cog instance for testing."""
    return Admin(mock_bot)


class TestPrefixValidation:
    """Tests for prefix validation logic."""

    @pytest.mark.asyncio
    async def test_prefix_with_spaces_rejected(self, admin_cog, mock_context):
        """Prefix containing spaces should be rejected."""
        await admin_cog._prefix_set.callback(admin_cog, mock_context, new_pref="! cmd")

        # Check that rejection message was sent
        mock_context.send.assert_any_call("Spaces not allowed in prefixes")

    @pytest.mark.asyncio
    async def test_prefix_without_spaces_accepted(self, admin_cog, mock_context, db_session):
        """Prefix without spaces should be accepted."""
        await admin_cog._prefix_set.callback(admin_cog, mock_context, new_pref="!")

        # Should confirm the new prefix
        mock_context.send.assert_called_with("new prefix is now set to '!'.")


class TestPrefixGet:
    """Tests for the prefix get command."""

    @pytest.mark.asyncio
    async def test_get_existing_prefix(self, admin_cog, mock_context, db_session, mock_guild):
        """Should return the custom prefix if one exists."""
        # Setup: Create a prefix in the database
        prefix = GuildPrefix(
            GuildId=mock_guild.id,
            Prefix=">>",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
        )
        db_session.add(prefix)
        db_session.commit()

        await admin_cog._prefix_get.callback(admin_cog, mock_context)

        call_args = mock_context.send.call_args[0][0]
        assert ">>" in call_args

    @pytest.mark.asyncio
    async def test_get_no_prefix_returns_default_message(self, admin_cog, mock_context):
        """Should indicate no custom prefix when none exists."""
        await admin_cog._prefix_get.callback(admin_cog, mock_context)

        call_args = mock_context.send.call_args[0][0]
        assert "no custom prefix" in call_args.lower()
        assert "!" in call_args  # mentions default prefix


class TestPrefixSet:
    """Tests for the prefix set command."""

    @pytest.mark.asyncio
    async def test_set_new_prefix(self, admin_cog, mock_context, db_session, mock_guild):
        """Should create new prefix entry when none exists."""
        await admin_cog._prefix_set.callback(admin_cog, mock_context, new_pref=">>")

        # Verify in database
        prefix = GuildPrefix.get(mock_guild.id, db_session)
        assert prefix is not None
        assert prefix.Prefix == ">>"

    @pytest.mark.asyncio
    async def test_update_existing_prefix(self, admin_cog, mock_context, db_session, mock_guild):
        """Should update existing prefix."""
        # Setup: Create initial prefix
        prefix = GuildPrefix(
            GuildId=mock_guild.id,
            Prefix="!",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
        )
        db_session.add(prefix)
        db_session.commit()

        # Update prefix
        await admin_cog._prefix_set.callback(admin_cog, mock_context, new_pref="??")

        # Verify update
        updated = GuildPrefix.get(mock_guild.id, db_session)
        assert updated.Prefix == "??"
        assert updated.ModifiedDate is not None


class TestPrefixDelete:
    """Tests for the prefix delete command."""

    @pytest.mark.asyncio
    async def test_delete_existing_prefix(self, admin_cog, mock_context, db_session, mock_guild):
        """Should remove existing prefix from database."""
        # Setup: Create a prefix
        prefix = GuildPrefix(
            GuildId=mock_guild.id,
            Prefix=">>",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
        )
        db_session.add(prefix)
        db_session.commit()

        await admin_cog._prefix_del.callback(admin_cog, mock_context)

        # Verify deletion
        assert GuildPrefix.get(mock_guild.id, db_session) is None
        mock_context.send.assert_called_with("Prefix removed.")
