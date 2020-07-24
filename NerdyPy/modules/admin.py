import asyncio
import discord
import utils.checks as checks
from discord.ext.commands import Cog, command, check


class Admin(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @command(hidden=True)
    @check(checks.is_operator)
    async def shutdown(self, ctx):
        """shutdown the bot nicely (bot owner only)"""
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete()
        await self.bot.shutdown()


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Admin(bot))
