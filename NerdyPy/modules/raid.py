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

    def create_state_handler(self):
        return {
            RaidPlanerState.MAIN: self.initial_message,
            RaidPlanerState.CREATE_TEMPLATE: self.create_template,
            RaidPlanerState.USE_TEMPLATE: self.use_template
        }

    async def initial_message(self, answer):
        emb = Embed(title='RaidPlaner', description='Test message please ignore.')
        reactions = {
            '<:oof:809539203813605387>': RaidPlanerState.USE_TEMPLATE,
            '🍉': RaidPlanerState.CREATE_TEMPLATE
        }

        await self.send_react(emb, reactions)

    async def create_template(self, answer):
        emb = Embed(title='RaidPlaner', description='state 1')
        await self.send_msg(emb, RaidPlanerState.MAIN)

    async def use_template(self, answer):
        emb = Embed(title='RaidPlaner', description='state 2')
        await self.send_msg(emb, RaidPlanerState.MAIN)


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Raid(bot))
