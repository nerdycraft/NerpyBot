# -*- coding: utf-8 -*-

from enum import Enum

from discord import Embed


class AnswerType(Enum):
    REACTION = 0
    TEXT = 1
    BOTH = 2


class Conversation:
    def __init__(self, bot, user, guild):
        self.bot = bot

        self.user = user
        self.guild = guild

        self.isActive = True

        self.stateHandler = self.create_state_handler()
        self.currentState = list(self.stateHandler.keys())[0]

        self.answerType = None

        self.currentMessage = None
        self.lastResponse = None

        self.nextState = None
        self.reactions = None
        self.answerHandler = None

    def create_state_handler(self):
        """
        Overwrite needed!!!
        all send methods with expected reaction or message answers will refer to this dictionary and call the method.

        Returns
        -------
        dictionary of [uniqueKey/method()] to call methods on state changes
        """
        return {}

    async def repost_state(self):
        await self.stateHandler[self.currentState]()

    def is_conv_message(self, message_id):
        return message_id == self.currentMessage.id

    def is_answer_type(self, answer_type: AnswerType):
        return answer_type == self.answerType or self.answerType == AnswerType.BOTH

    async def on_react(self, reaction):
        if str(reaction) in self.reactions:
            self.currentState = self.reactions[str(reaction)]
            self.currentMessage = None
            self.lastResponse = reaction
            await self.repost_state()

    async def on_message(self, message):
        valid = True
        if self.answerHandler is not None:
            valid = await self.answerHandler(message)
            self.answerHandler = None

        if valid or valid is None:
            self.currentState = self.nextState
            self.currentMessage = None
            self.lastResponse = message

        await self.repost_state()

    async def send_react(self, embed, reactions):
        """
        Send embed with expected reaction response
        :param embed: iscord text embed
        :param reactions: dictionary of emojis and the target state. emojis will be added as reactions.
        """
        self.answerType = AnswerType.REACTION
        self.reactions = reactions
        tmp = self.currentMessage = await self.user.send(embed=embed)
        for emoji in reactions.keys():
            await tmp.add_reaction(emoji)

    async def send_msg(self, embed, next_state, answer_handler=None):
        """
        Send embed with expected text response
        :param embed: discord text embed
        :param next_state: state the conversation will be when answer is received.
        :param answer_handler: separate answer handling -> method(str)
        """
        self.answerType = AnswerType.TEXT
        self.nextState = next_state
        self.answerHandler = answer_handler
        self.currentMessage = await self.user.send(embed=embed)

    async def send_both(self, embed, next_state, answer_handler, reactions):
        """
        Send embed with expected text or reaction response
        :param embed: discord text embed
        :param next_state: state the conversation will be when answer is received.
        :param answer_handler: separate answer handling -> method(str)
        :param reactions: dictionary of emojis and the target state. emojis will be added as reactions.
        """
        self.answerType = AnswerType.BOTH
        self.nextState = next_state
        self.answerHandler = answer_handler
        self.reactions = reactions
        self.currentMessage = await self.user.send(embed=embed)
        for emoji in reactions.keys():
            await self.currentMessage.add_reaction(emoji)

    async def send_ns(self, embed):
        """
        Send embed with no expected response
        :param embed: discord text embed
        """
        await self.user.send(embed=embed)

    async def close(self):
        """closes this conversation"""
        self.isActive = False


class PrevConvState(Enum):
    INIT = 0
    PREV = 1
    NEXT = 2


class PreConversation(Conversation):
    def __init__(self, conv_man, bot, prev_conv: Conversation, next_conv: Conversation, user):
        super().__init__(bot, user, None)
        self.convMan = conv_man
        self.prevConv = prev_conv
        self.nextConv = next_conv

    def create_state_handler(self):
        return {
            PrevConvState.INIT: self.initial_message,
            PrevConvState.PREV: self.prev_conv,
            PrevConvState.NEXT: self.next_conv,
        }

    async def initial_message(self):
        emb = Embed(
            title="PreConversation",
            description="You already have an active conversation. Do you want to "
            "continue your old conversation (:arrow_backward:) or start "
            "the new one (:arrow_forward:)",
        )

        reactions = {"◀": PrevConvState.PREV, "▶": PrevConvState.NEXT}

        await self.send_react(emb, reactions)

    async def prev_conv(self):
        self.convMan.set_conversation(self.prevConv)
        await self.prevConv.repost_state()

    async def next_conv(self):
        self.convMan.set_conversation(self.nextConv)
        await self.nextConv.repost_state()


class ConversationManager:
    """Handles all dm conversations"""

    def __init__(self, bot):
        self.bot = bot
        self.conversations = {}

    def get_user_conversation(self, usr):
        return self.conversations.get(usr.id)

    async def init_conversation(self, conv: Conversation):
        prev_conv = self.get_user_conversation(conv.user)
        if prev_conv is not None and prev_conv.isActive:
            conv = PreConversation(self, self.bot, prev_conv, conv, conv.user)

        self.set_conversation(conv)
        await conv.repost_state()

    def set_conversation(self, conv: Conversation):
        self.conversations[conv.user.id] = conv
