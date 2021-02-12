from enum import Enum

from discord import Embed, Message


class AnswerType(Enum):
    REACTION = 0
    TEXT = 1
    BOTH = 2


class Conversation:

    def __init__(self, user, guild):
        self.bot = None

        self.user = user
        self.guild = guild

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
        :returns a dictionary of [int/method(str)] to call methods on state changes
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
        self.answerType = AnswerType.REACTION
        self.reactions = reactions
        self.currentMessage = await self.user.send(embed=embed)
        for emoji in reactions.keys():
            await self.currentMessage.add_reaction(emoji)

    async def send_msg(self, embed, next_state, answer_handler=None):
        self.answerType = AnswerType.TEXT
        self.nextState = next_state
        self.answerHandler = answer_handler
        self.currentMessage = await self.user.send(embed=embed)

    async def send_both(self, embed, next_state, answer_handler, reactions):
        self.answerType = AnswerType.BOTH
        self.nextState = next_state
        self.answerHandler = answer_handler
        self.reactions = reactions
        self.currentMessage = await self.user.send(embed=embed)
        for emoji in reactions.keys():
            await self.currentMessage.add_reaction(emoji)


class PrevConvState(Enum):
    INIT = 0
    PREV = 1
    NEXT = 2


class PreConversation(Conversation):

    def __init__(self, conv_man, prev_conv: Conversation, next_conv: Conversation, user):
        super().__init__(user, None)
        self.convMan = conv_man
        self.prevConv = prev_conv
        self.nextConv = next_conv

    def create_state_handler(self):
        return {
            PrevConvState.INIT: self.initial_message,
            PrevConvState.PREV: self.prev_conv,
            PrevConvState.NEXT: self.next_conv
        }

    async def initial_message(self):
        emb = Embed(title='PreConversation', description='You already have an active conversation. Do you want to '
                                                         'continue your old conversation (:arrow_backward:) or start '
                                                         'the new one (:arrow_forward:)')

        reactions = {
            '◀': PrevConvState.PREV,
            '▶': PrevConvState.NEXT
        }

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
        await conv.repost_state()

    def set_conversation(self, conv: Conversation):
        orig_conv = self.get_user_conversation(conv.user)
        if orig_conv is not None:
            self.conversations.remove(orig_conv)
        self.conversations.append(conv)
