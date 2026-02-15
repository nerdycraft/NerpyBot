# -*- coding: utf-8 -*-

from discord.ext.commands import Cog, Context, check, hybrid_command

from utils.checks import can_leave_voice, can_stop_playback
from utils.helpers import send_hidden_message


class VoiceControl(Cog):
    """commands for controlling bot voice playback"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

    @hybrid_command(name="stop")
    @check(can_stop_playback)
    async def _bot_stop_playing(self, ctx: Context):
        """bot stops playing audio [bot-moderator]"""
        self.bot.audio.stop(ctx.guild.id)
        self.bot.audio.clear_buffer(ctx.guild.id)
        if ctx.interaction is not None:
            await send_hidden_message(ctx, "\U0001f44d")

    @hybrid_command(name="leave")
    @check(can_leave_voice)
    async def _bot_leave_channel(self, ctx: Context):
        """bot leaves the voice channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)
        if ctx.interaction is not None:
            await send_hidden_message(ctx, "\U0001f44b")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(VoiceControl(bot))
