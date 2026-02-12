# -*- coding: utf-8 -*-
"""Tests for utils/conversation.py - DM conversation state machine"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from utils.conversation import AnswerType, Conversation, ConversationManager, PreConversation, PrevConvState


class ConcreteConversation(Conversation):
    """Concrete implementation of Conversation for testing."""

    def __init__(self, bot, user, guild):
        super().__init__(bot, user, guild)
        self.state_calls = []

    def create_state_handler(self):
        return {
            "start": self.state_start,
            "middle": self.state_middle,
            "end": self.state_end,
        }

    async def state_start(self):
        self.state_calls.append("start")

    async def state_middle(self):
        self.state_calls.append("middle")

    async def state_end(self):
        self.state_calls.append("end")


class TestConversation:
    """Tests for the Conversation base class."""

    @pytest.fixture
    def conversation(self, mock_bot, mock_user, mock_guild):
        """Create a concrete conversation for testing."""
        return ConcreteConversation(mock_bot, mock_user, mock_guild)

    def test_initial_state_is_first_handler(self, conversation):
        """Initial state should be the first key in state_handler."""
        assert conversation.currentState == "start"

    def test_is_active_initially_true(self, conversation):
        """Conversation should start active."""
        assert conversation.isActive is True

    @pytest.mark.asyncio
    async def test_close_sets_inactive(self, conversation):
        """close() should set isActive to False."""
        await conversation.close()
        assert conversation.isActive is False

    def test_is_conv_message_matches_current(self, conversation):
        """is_conv_message should match current message ID."""
        mock_message = MagicMock()
        mock_message.id = 12345
        conversation.currentMessage = mock_message

        assert conversation.is_conv_message(12345) is True
        assert conversation.is_conv_message(99999) is False

    def test_is_answer_type_exact_match(self, conversation):
        """is_answer_type should match exact type."""
        conversation.answerType = AnswerType.REACTION
        assert conversation.is_answer_type(AnswerType.REACTION) is True
        assert conversation.is_answer_type(AnswerType.TEXT) is False

    def test_is_answer_type_both_matches_all(self, conversation):
        """BOTH answer type should match any type."""
        conversation.answerType = AnswerType.BOTH
        assert conversation.is_answer_type(AnswerType.REACTION) is True
        assert conversation.is_answer_type(AnswerType.TEXT) is True

    @pytest.mark.asyncio
    async def test_repost_state_calls_handler(self, conversation):
        """repost_state should call current state handler."""
        await conversation.repost_state()
        assert "start" in conversation.state_calls

    @pytest.mark.asyncio
    async def test_on_react_changes_state(self, conversation, mock_user):
        """on_react should transition state based on reaction map."""
        # Setup reaction map
        conversation.reactions = {"✅": "middle", "❌": "end"}
        conversation.currentMessage = MagicMock()

        # React with ✅
        await conversation.on_react("✅")

        assert conversation.currentState == "middle"
        assert conversation.currentMessage is None
        assert conversation.lastResponse == "✅"

    @pytest.mark.asyncio
    async def test_on_react_ignores_unmapped_reaction(self, conversation):
        """on_react should ignore reactions not in the map."""
        conversation.reactions = {"✅": "middle"}
        conversation.currentState = "start"

        # React with unmapped emoji
        await conversation.on_react("🚀")

        # State unchanged
        assert conversation.currentState == "start"

    @pytest.mark.asyncio
    async def test_on_message_transitions_state(self, conversation, mock_user):
        """on_message should transition to next state."""
        conversation.nextState = "end"
        conversation.currentMessage = MagicMock()
        conversation.answerHandler = None

        mock_message = MagicMock()
        mock_message.content = "user input"

        await conversation.on_message(mock_message)

        assert conversation.currentState == "end"
        assert conversation.lastResponse == mock_message

    @pytest.mark.asyncio
    async def test_on_message_calls_answer_handler(self, conversation):
        """on_message should call answer handler if set."""
        handler_called = []

        async def handler(msg):
            handler_called.append(msg)
            return True

        conversation.answerHandler = handler
        conversation.nextState = "middle"
        conversation.currentMessage = MagicMock()

        mock_message = MagicMock()
        await conversation.on_message(mock_message)

        assert len(handler_called) == 1
        assert handler_called[0] == mock_message

    @pytest.mark.asyncio
    async def test_on_message_handler_can_reject(self, conversation):
        """answer handler returning False should prevent state change."""

        async def rejecting_handler(msg):
            return False

        conversation.answerHandler = rejecting_handler
        conversation.nextState = "middle"
        conversation.currentState = "start"
        conversation.currentMessage = MagicMock()

        await conversation.on_message(MagicMock())

        # State should remain 'start' due to rejection
        assert conversation.currentState == "start"


class TestConversationSendMethods:
    """Tests for Conversation send methods."""

    @pytest.fixture
    def conversation(self, mock_bot, mock_user, mock_guild):
        return ConcreteConversation(mock_bot, mock_user, mock_guild)

    @pytest.mark.asyncio
    async def test_send_react_sets_answer_type(self, conversation, mock_user):
        """send_react should set answer type to REACTION."""
        mock_embed = MagicMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_user.send = AsyncMock(return_value=mock_message)

        await conversation.send_react(mock_embed, {"✅": "next"})

        assert conversation.answerType == AnswerType.REACTION

    @pytest.mark.asyncio
    async def test_send_react_adds_reactions(self, conversation, mock_user):
        """send_react should add emoji reactions to message."""
        mock_embed = MagicMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_user.send = AsyncMock(return_value=mock_message)

        reactions = {"✅": "yes", "❌": "no"}
        await conversation.send_react(mock_embed, reactions)

        assert mock_message.add_reaction.call_count == 2

    @pytest.mark.asyncio
    async def test_send_msg_sets_answer_type(self, conversation, mock_user):
        """send_msg should set answer type to TEXT."""
        mock_embed = MagicMock()
        mock_user.send = AsyncMock(return_value=MagicMock())

        await conversation.send_msg(mock_embed, "next_state")

        assert conversation.answerType == AnswerType.TEXT
        assert conversation.nextState == "next_state"

    @pytest.mark.asyncio
    async def test_send_both_sets_answer_type(self, conversation, mock_user):
        """send_both should set answer type to BOTH."""
        mock_embed = MagicMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_user.send = AsyncMock(return_value=mock_message)

        await conversation.send_both(mock_embed, "next", None, {"✅": "yes"})

        assert conversation.answerType == AnswerType.BOTH


class TestConversationManager:
    """Tests for the ConversationManager class."""

    @pytest.fixture
    def manager(self, mock_bot):
        """Create a ConversationManager for testing."""
        return ConversationManager(mock_bot)

    @pytest.fixture
    def conversation(self, mock_bot, mock_user, mock_guild):
        """Create a conversation for testing."""
        return ConcreteConversation(mock_bot, mock_user, mock_guild)

    def test_get_user_conversation_returns_none_initially(self, manager, mock_user):
        """Should return None for users without conversations."""
        result = manager.get_user_conversation(mock_user)
        assert result is None

    def test_set_conversation_stores_by_user_id(self, manager, conversation, mock_user):
        """set_conversation should store conversation by user ID."""
        manager.set_conversation(conversation)

        result = manager.get_user_conversation(mock_user)
        assert result is conversation

    @pytest.mark.asyncio
    async def test_init_conversation_new_user(self, manager, conversation, mock_user):
        """init_conversation should store and start conversation for new user."""
        # Mock repost_state to avoid needing full state handler setup
        conversation.repost_state = AsyncMock()

        await manager.init_conversation(conversation)

        # Should be stored
        result = manager.get_user_conversation(mock_user)
        assert result is conversation

        # Should have called repost_state
        conversation.repost_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_conversation_creates_preconversation_when_active(
        self, manager, mock_bot, mock_user, mock_guild
    ):
        """init_conversation should create PreConversation if user has active conv."""
        # Setup existing active conversation
        existing_conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        existing_conv.isActive = True
        manager.set_conversation(existing_conv)

        # Try to init new conversation
        new_conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        new_conv.repost_state = AsyncMock()

        await manager.init_conversation(new_conv)

        # Should have created a PreConversation
        result = manager.get_user_conversation(mock_user)
        assert isinstance(result, PreConversation)

    @pytest.mark.asyncio
    async def test_init_conversation_replaces_inactive(self, manager, mock_bot, mock_user, mock_guild):
        """init_conversation should replace inactive conversation directly."""
        # Setup existing inactive conversation
        existing_conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        existing_conv.isActive = False
        manager.set_conversation(existing_conv)

        # Init new conversation
        new_conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        new_conv.repost_state = AsyncMock()

        await manager.init_conversation(new_conv)

        # Should be the new conversation directly (not PreConversation)
        result = manager.get_user_conversation(mock_user)
        assert result is new_conv


class TestPreConversation:
    """Tests for the PreConversation class."""

    @pytest.fixture
    def prev_conv(self, mock_bot, mock_user, mock_guild):
        """Create previous conversation."""
        conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        conv.repost_state = AsyncMock()
        return conv

    @pytest.fixture
    def next_conv(self, mock_bot, mock_user, mock_guild):
        """Create next conversation."""
        conv = ConcreteConversation(mock_bot, mock_user, mock_guild)
        conv.repost_state = AsyncMock()
        return conv

    @pytest.fixture
    def pre_conv(self, mock_bot, prev_conv, next_conv, mock_user):
        """Create PreConversation for testing."""
        manager = ConversationManager(mock_bot)
        return PreConversation(manager, mock_bot, prev_conv, next_conv, mock_user)

    def test_initial_state_is_init(self, pre_conv):
        """PreConversation should start in INIT state."""
        assert pre_conv.currentState == PrevConvState.INIT

    def test_state_handler_has_required_states(self, pre_conv):
        """Should have handlers for INIT, PREV, and NEXT states."""
        handler = pre_conv.stateHandler
        assert PrevConvState.INIT in handler
        assert PrevConvState.PREV in handler
        assert PrevConvState.NEXT in handler

    @pytest.mark.asyncio
    async def test_prev_conv_state_resumes_previous(self, pre_conv, prev_conv):
        """PREV state should resume previous conversation."""
        await pre_conv.prev_conv()

        # Should have called repost on previous conversation
        prev_conv.repost_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_next_conv_state_starts_new(self, pre_conv, next_conv):
        """NEXT state should start new conversation."""
        await pre_conv.next_conv()

        # Should have called repost on next conversation
        next_conv.repost_state.assert_called_once()


class TestAnswerType:
    """Tests for AnswerType enum."""

    def test_reaction_value(self):
        """REACTION should be 0."""
        assert AnswerType.REACTION.value == 0

    def test_text_value(self):
        """TEXT should be 1."""
        assert AnswerType.TEXT.value == 1

    def test_both_value(self):
        """BOTH should be 2."""
        assert AnswerType.BOTH.value == 2


class TestPrevConvState:
    """Tests for PrevConvState enum."""

    def test_init_value(self):
        """INIT should be 0."""
        assert PrevConvState.INIT.value == 0

    def test_prev_value(self):
        """PREV should be 1."""
        assert PrevConvState.PREV.value == 1

    def test_next_value(self):
        """NEXT should be 2."""
        assert PrevConvState.NEXT.value == 2
