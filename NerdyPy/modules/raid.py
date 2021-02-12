from enum import Enum

from discord import Embed
from discord.ext.commands import Cog, command

from utils.conversation import Conversation


class Raid(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @command()
    async def raidplaner(self, ctx):
        """sound and text tags"""
        await self.bot.convMan.init_conversation(RaidConversation(ctx.author))


class RaidPlanerState(Enum):
    MAIN = 0
    CREATE_TEMPLATE = 1
    USE_TEMPLATE = 2


class RaidConversation(Conversation):

    async def initial_message(self):
        emb = Embed(title='RaidPlaner', description='Test message please ignore.')
        reactions = {
            '<:oof:809539203813605387>': RaidPlanerState.USE_TEMPLATE,
            '🍉': RaidPlanerState.CREATE_TEMPLATE
        }

        await self.send_react(emb, reactions)

    async def on_state_change(self):
        switcher = {
            RaidPlanerState.MAIN: self.on_state_0,
            RaidPlanerState.CREATE_TEMPLATE: self.on_state_1,
            RaidPlanerState.USE_TEMPLATE: self.on_state_2
        }
        await switcher.get(self.currentState)()

    async def on_state_0(self):
        await self.user.send('state 0')

    async def on_state_1(self):
        await self.user.send('state 1')

    async def on_state_2(self):
        await self.user.send('state 2')


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Raid(bot))
