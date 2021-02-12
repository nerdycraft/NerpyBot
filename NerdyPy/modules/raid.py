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
        await self.bot.convMan.init_conversation(RaidConversation(ctx.author, ctx.guild))


class RaidPlanerState(Enum):
    MAIN = 0
    CT_NAME = 1
    CT_DESCRIPTION = 2
    CT_ENCOUNTER_ADD = 4
    CT_PREVIEW = 50
    USE_TEMPLATE = 3
    CLOSE = 999


class RaidConversation(Conversation):

    def __init__(self, user, guild):
        super().__init__(user, guild)
        self.templateName = ""
        self.templateDesc = ""

    def create_state_handler(self):
        return {
            RaidPlanerState.MAIN: self.initial_message,
            RaidPlanerState.CT_NAME: self.create_template_name,
            RaidPlanerState.CT_DESCRIPTION: self.create_template_desc,
            RaidPlanerState.CT_PREVIEW: self.create_template_preview,
            RaidPlanerState.USE_TEMPLATE: self.use_template,
            RaidPlanerState.CLOSE: self.close
        }

    async def initial_message(self):
        emb = Embed(title='RaidPlaner',
                    description=''
                                '<:check:809765339230896128> Use existing  template\n'
                                '<:add:809765525629698088> create a new template'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.USE_TEMPLATE,
            '<:add:809765525629698088>': RaidPlanerState.CT_NAME,
            '<:cancel:809790666930126888>': RaidPlanerState.CLOSE,
        }

        await self.send_react(emb, reactions)

    async def create_template_name(self):
        emb = Embed(title='RaidPlaner',
                    description='To create a new template you first need to give it a name:'
                    )

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN,
        }
        await self.send_both(emb, RaidPlanerState.CT_DESCRIPTION, self.set_template_name, reactions)

    async def set_template_name(self, answer):
        if len(answer) > 10:
            emb = Embed(title='RaidPlaner',
                        description='Name can not be longer than 10 characters'
                        )
            await self.send_ns(emb)
            return False
        self.templateName = answer

    async def create_template_desc(self):
        emb = Embed(title='RaidPlaner',
                    description='Now write a few lines to describe your event.'
                    )

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN,
        }
        await self.send_both(emb, RaidPlanerState.CT_PREVIEW, self.set_template_desc, reactions)

    async def set_template_desc(self, answer):
        self.templateDesc = answer

    async def create_template_preview(self):
        emb = Embed(title=self.templateName,
                    description=self.templateDesc
                    )

        await self.send_ns(embed=emb)
        emb = Embed(title='RaidPlaner',
                    description='Above you can see the preview. Looking good eh?'
                    )

        reactions = {
            '👍': RaidPlanerState.MAIN,
        }
        await self.send_react(emb, reactions)

    async def use_template(self):
        emb = Embed(title='RaidPlaner', description='use_template PoC message (send text to continue)')
        await self.send_msg(emb, RaidPlanerState.MAIN)


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Raid(bot))
