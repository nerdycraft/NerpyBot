from enum import Enum

from discord import Embed, Reaction, Message


class AnswerType(Enum):
    REACTION = 0
    TEXT = 1
    BOTH = 2


class Conversation:

    def __init__(self, user):
        self.user = user
        self.bot = None
        self.currentMessage = None
        self.previousState = 0
        self.currentState = 0
        self.answerType = None
        self.nextState = None

    async def initial_message(self):
        pass

    async def on_react(self, reaction: Reaction):
        if self.answerType == AnswerType.REACTION and self.currentMessage.id == reaction.message.id:
            self.previousState = self.currentState
            self.currentState = self.nextState[str(reaction.emoji)]
            self.currentMessage = None
            await self.on_state_change()

    async def on_state_change(self):
        pass

    async def on_message(self, message: Message):
        if self.answerType == AnswerType.TEXT and self.currentMessage.id == message.id:
            self.previousState = self.currentState
            self.currentState = self.nextState
            self.currentMessage = None
            await self.on_answer_received(message)

    async def on_answer_received(self, message: Message):
        pass

    async def send_react(self, embed, reactions):
        self.answerType = AnswerType.REACTION
        self.nextState = reactions
        self.currentMessage = await self.user.send(embed=embed)
        for emoji in reactions.keys():
            await self.currentMessage.add_reaction(emoji)

    async def send_msg(self, embed, next_state):
        self.answerType = AnswerType.TEXT
        self.nextState = next_state
        self.currentMessage = await self.user.send(embed=embed)


class PreConversation(Conversation):

    def __init__(self, conv_man, prev_conv: Conversation, next_conv: Conversation, user):
        super().__init__(user)
        self.convMan = conv_man
        self.prevConv = prev_conv
        self.nextConv = next_conv

    async def initial_message(self):
        emb = Embed(title='PreConversation', description='You already have an active conversation. Do you want to '
                                                         'continue your old conversation (:arrow_backward:) or start '
                                                         'the new one (:arrow_forward:)')

        reactions = {
            '◀': 0,
            '▶': 1
        }

        await self.send_react(emb, reactions)

    async def on_state_change(self):
        if self.currentState == 1:
            self.convMan.set_conversation(self.nextConv)
            await self.nextConv.initial_message()
        else:
            self.convMan.set_conversation(self.prevConv)
            await self.prevConv.on_state_change()


class ConversationManager:
    """Handles all dm conversations"""

    def __init__(self, bot):
        self.bot = bot
        self.conversations = []

    def has_conversation(self, usr):
        if self.get_user_conversation(usr) is None:
            return False
        return True

    def get_user_conversation(self, usr):
        conv = [c for c in self.conversations if c.user.id == usr.id]
        if len(conv) > 0:
            return conv[0]
        return None

    async def init_conversation(self, conv: Conversation):
        conv.bot = self.bot
        prev_conv = self.get_user_conversation(conv.user)
        if prev_conv is not None:
            conv = PreConversation(self, prev_conv, conv, conv.user)
            conv.bot = self.bot

        self.set_conversation(conv)
        await conv.initial_message()

    def set_conversation(self, conv: Conversation):
        orig_conv = self.get_user_conversation(conv.user)
        if orig_conv is not None:
            self.conversations.remove(orig_conv)
        self.conversations.append(conv)
