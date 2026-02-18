# -*- coding: utf-8 -*-
"""Tests for utils.checks — Interaction-based check functions."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.checks import (
    _is_bot_moderator,
    _reject,
    can_leave_voice,
    can_stop_playback,
    is_admin_or_operator,
    is_connected_to_voice,
)
from utils.errors import SilentCheckFailure


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_interaction(db_session):
    """Create a mock discord.Interaction with all attributes checks rely on."""
    interaction = MagicMock()

    # interaction.user (a Member in a guild context)
    user = MagicMock()
    user.id = 100
    user.voice = MagicMock()
    user.voice.channel = MagicMock()
    user.guild_permissions = MagicMock()
    user.guild_permissions.administrator = False
    user.guild_permissions.mute_members = False
    user.guild_permissions.manage_channels = False
    user.roles = []
    interaction.user = user

    # interaction.guild
    guild = MagicMock()
    guild.id = 900
    guild.voice_client = None  # bot not in voice by default
    guild.me = MagicMock()
    interaction.guild = guild

    # interaction.response
    response = MagicMock()
    response.send_message = AsyncMock()
    response.is_done = MagicMock(return_value=False)
    interaction.response = response

    # interaction.followup
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    # interaction.client (the bot)
    client = MagicMock()
    client.ops = []

    @contextmanager
    def session_scope():
        yield db_session

    client.session_scope = session_scope
    interaction.client = client

    return interaction


# ---------------------------------------------------------------------------
# _reject
# ---------------------------------------------------------------------------


class TestReject:
    async def test_sends_ephemeral_when_response_not_done(self, mock_interaction):
        with pytest.raises(SilentCheckFailure):
            await _reject(mock_interaction, "nope")

        mock_interaction.response.send_message.assert_awaited_once_with("nope", ephemeral=True)
        mock_interaction.followup.send.assert_not_awaited()

    async def test_uses_followup_when_response_already_done(self, mock_interaction):
        mock_interaction.response.is_done.return_value = True

        with pytest.raises(SilentCheckFailure):
            await _reject(mock_interaction, "too late")

        mock_interaction.followup.send.assert_awaited_once_with("too late", ephemeral=True)
        mock_interaction.response.send_message.assert_not_awaited()

    async def test_exception_message_matches(self, mock_interaction):
        with pytest.raises(SilentCheckFailure, match="custom msg"):
            await _reject(mock_interaction, "custom msg")


# ---------------------------------------------------------------------------
# is_admin_or_operator
# ---------------------------------------------------------------------------


class TestIsAdminOrOperator:
    async def test_returns_true_for_operator(self, mock_interaction):
        mock_interaction.client.ops = [100]
        assert await is_admin_or_operator(mock_interaction) is True

    async def test_returns_true_for_guild_admin(self, mock_interaction):
        mock_interaction.user.guild_permissions.administrator = True
        assert await is_admin_or_operator(mock_interaction) is True

    async def test_returns_false_for_regular_user(self, mock_interaction):
        assert await is_admin_or_operator(mock_interaction) is False

    async def test_returns_false_when_no_guild(self, mock_interaction):
        mock_interaction.guild = None
        assert await is_admin_or_operator(mock_interaction) is False

    async def test_operator_takes_priority_over_guild_check(self, mock_interaction):
        """Operator check happens first, so it works even without a guild."""
        mock_interaction.guild = None
        mock_interaction.client.ops = [100]
        assert await is_admin_or_operator(mock_interaction) is True


# ---------------------------------------------------------------------------
# _is_bot_moderator
# ---------------------------------------------------------------------------


class TestIsBotModerator:
    async def test_returns_true_for_mute_members_perm(self, mock_interaction):
        mock_interaction.user.guild_permissions.mute_members = True
        assert await _is_bot_moderator(mock_interaction) is True

    async def test_returns_true_for_manage_channels_perm(self, mock_interaction):
        mock_interaction.user.guild_permissions.manage_channels = True
        assert await _is_bot_moderator(mock_interaction) is True

    async def test_returns_true_for_admin_perm(self, mock_interaction):
        mock_interaction.user.guild_permissions.administrator = True
        assert await _is_bot_moderator(mock_interaction) is True

    async def test_returns_true_for_operator(self, mock_interaction):
        mock_interaction.client.ops = [100]
        assert await _is_bot_moderator(mock_interaction) is True

    async def test_returns_true_for_configured_role(self, mock_interaction, db_session):
        from models.botmod import BotModeratorRole

        entry = BotModeratorRole(GuildId=900, RoleId=42)
        db_session.add(entry)
        db_session.commit()

        role = MagicMock()
        role.id = 42
        mock_interaction.user.roles = [role]

        assert await _is_bot_moderator(mock_interaction) is True

    async def test_returns_false_for_wrong_configured_role(self, mock_interaction, db_session):
        from models.botmod import BotModeratorRole

        entry = BotModeratorRole(GuildId=900, RoleId=42)
        db_session.add(entry)
        db_session.commit()

        role = MagicMock()
        role.id = 99
        mock_interaction.user.roles = [role]

        assert await _is_bot_moderator(mock_interaction) is False

    async def test_returns_false_for_regular_user(self, mock_interaction):
        assert await _is_bot_moderator(mock_interaction) is False

    async def test_returns_false_when_no_botmod_entry(self, mock_interaction):
        """No BotModeratorRole configured for this guild — should return False."""
        mock_interaction.user.roles = [MagicMock(id=42)]
        assert await _is_bot_moderator(mock_interaction) is False


# ---------------------------------------------------------------------------
# is_connected_to_voice
# ---------------------------------------------------------------------------


class TestIsConnectedToVoice:
    async def test_returns_true_when_user_in_voice_with_perms(self, mock_interaction):
        perms = MagicMock()
        perms.connect = True
        perms.speak = True
        mock_interaction.user.voice.channel.permissions_for.return_value = perms
        assert await is_connected_to_voice(mock_interaction) is True

    async def test_rejects_when_user_not_in_voice(self, mock_interaction):
        mock_interaction.user.voice = None
        with pytest.raises(SilentCheckFailure, match="connect to a voice channel"):
            await is_connected_to_voice(mock_interaction)
        mock_interaction.response.send_message.assert_awaited_once()

    async def test_rejects_when_voice_channel_is_none(self, mock_interaction):
        mock_interaction.user.voice.channel = None
        with pytest.raises(SilentCheckFailure, match="connect to a voice channel"):
            await is_connected_to_voice(mock_interaction)

    async def test_rejects_when_bot_cannot_connect(self, mock_interaction):
        perms = MagicMock()
        perms.connect = False
        perms.speak = True
        mock_interaction.user.voice.channel.permissions_for.return_value = perms
        with pytest.raises(SilentCheckFailure, match="not allowed to join"):
            await is_connected_to_voice(mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "not allowed to join" in msg

    async def test_rejects_when_bot_cannot_speak(self, mock_interaction):
        perms = MagicMock()
        perms.connect = True
        perms.speak = False
        mock_interaction.user.voice.channel.permissions_for.return_value = perms
        with pytest.raises(SilentCheckFailure, match="permission to speak"):
            await is_connected_to_voice(mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "permission to speak" in msg


# ---------------------------------------------------------------------------
# can_stop_playback
# ---------------------------------------------------------------------------


class TestCanStopPlayback:
    async def test_rejects_when_nothing_playing(self, mock_interaction):
        mock_interaction.guild.voice_client = None
        with pytest.raises(SilentCheckFailure, match="Nothing is playing"):
            await can_stop_playback(mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "Nothing is playing" in msg

    async def test_allows_moderator_from_anywhere(self, mock_interaction):
        bot_voice = MagicMock()
        bot_voice.channel = MagicMock()
        mock_interaction.guild.voice_client = bot_voice
        mock_interaction.user.guild_permissions.administrator = True
        assert await can_stop_playback(mock_interaction) is True

    async def test_allows_user_in_same_channel(self, mock_interaction):
        voice_channel = MagicMock()
        bot_voice = MagicMock()
        bot_voice.channel = voice_channel
        mock_interaction.guild.voice_client = bot_voice
        mock_interaction.user.voice.channel = voice_channel
        assert await can_stop_playback(mock_interaction) is True

    async def test_rejects_user_not_in_voice(self, mock_interaction):
        bot_voice = MagicMock()
        bot_voice.channel = MagicMock()
        mock_interaction.guild.voice_client = bot_voice
        mock_interaction.user.voice = None
        with pytest.raises(SilentCheckFailure, match="be in a voice channel"):
            await can_stop_playback(mock_interaction)

    async def test_rejects_user_in_different_channel(self, mock_interaction):
        bot_voice = MagicMock()
        bot_voice.channel = MagicMock()
        mock_interaction.guild.voice_client = bot_voice
        mock_interaction.user.voice.channel = MagicMock()  # different channel
        with pytest.raises(SilentCheckFailure, match="same voice channel"):
            await can_stop_playback(mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "same voice channel" in msg

    async def test_rejects_user_with_voice_channel_none(self, mock_interaction):
        bot_voice = MagicMock()
        bot_voice.channel = MagicMock()
        mock_interaction.guild.voice_client = bot_voice
        mock_interaction.user.voice.channel = None
        with pytest.raises(SilentCheckFailure, match="be in a voice channel"):
            await can_stop_playback(mock_interaction)


# ---------------------------------------------------------------------------
# can_leave_voice
# ---------------------------------------------------------------------------


class TestCanLeaveVoice:
    async def test_allows_moderator(self, mock_interaction):
        mock_interaction.user.guild_permissions.mute_members = True
        assert await can_leave_voice(mock_interaction) is True

    async def test_allows_operator(self, mock_interaction):
        mock_interaction.client.ops = [100]
        assert await can_leave_voice(mock_interaction) is True

    async def test_allows_admin(self, mock_interaction):
        mock_interaction.user.guild_permissions.administrator = True
        assert await can_leave_voice(mock_interaction) is True

    async def test_rejects_regular_user(self, mock_interaction):
        with pytest.raises(SilentCheckFailure, match="[Mm]oderators"):
            await can_leave_voice(mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "moderators" in msg.lower()
