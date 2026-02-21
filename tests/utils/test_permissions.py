# -*- coding: utf-8 -*-

from unittest.mock import MagicMock

import pytest

from utils.errors import NerpyPermissionError
from utils.permissions import validate_channel_permissions


def _make_channel(*, view_channel=True, send_messages=True, manage_messages=True, embed_links=True):
    """Build a mock TextChannel whose permissions_for() returns the given flags."""
    perms = MagicMock()
    perms.view_channel = view_channel
    perms.send_messages = send_messages
    perms.manage_messages = manage_messages
    perms.embed_links = embed_links

    channel = MagicMock()
    channel.permissions_for.return_value = perms
    channel.mention = "#test-channel"
    return channel


def _make_guild():
    guild = MagicMock()
    guild.me = MagicMock()
    return guild


def test_validate_passes_when_all_permissions_present():
    channel = _make_channel(view_channel=True, send_messages=True)
    guild = _make_guild()
    # Should not raise
    validate_channel_permissions(channel, guild, "view_channel", "send_messages")


def test_validate_raises_when_permission_missing():
    channel = _make_channel(send_messages=False)
    guild = _make_guild()
    with pytest.raises(NerpyPermissionError, match="send_messages"):
        validate_channel_permissions(channel, guild, "view_channel", "send_messages")


def test_validate_raises_lists_all_missing():
    channel = _make_channel(view_channel=False, send_messages=False)
    guild = _make_guild()
    with pytest.raises(NerpyPermissionError, match="view_channel") as exc_info:
        validate_channel_permissions(channel, guild, "view_channel", "send_messages")
    assert "send_messages" in str(exc_info.value)


def test_validate_uses_channel_permissions_for():
    channel = _make_channel()
    guild = _make_guild()
    validate_channel_permissions(channel, guild, "send_messages")
    channel.permissions_for.assert_called_once_with(guild.me)
