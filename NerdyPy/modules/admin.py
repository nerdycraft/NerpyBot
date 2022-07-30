import discord
from utils.checks import is_operator
from discord.ext.commands import Cog, hybrid_command, check


class Admin(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @hybrid_command(hidden=True)
    @check(is_operator)
    async def shutdown(self, ctx):
        """shutdown the bot nicely (bot owner only)"""
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()
        await self.bot.shutdown()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
