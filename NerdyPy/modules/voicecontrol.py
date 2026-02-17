# -*- coding: utf-8 -*-

from discord import Interaction, app_commands
from discord.ext.commands import Cog

from utils.checks import can_leave_voice, can_stop_playback


@app_commands.guild_only()
class VoiceControl(Cog):
    """commands for controlling bot voice playback"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

    @app_commands.command(name="stop")
    @app_commands.guild_only()
    @app_commands.check(can_stop_playback)
    async def _bot_stop_playing(self, interaction: Interaction):
        """bot stops playing audio [bot-moderator]"""
        self.bot.audio.stop(interaction.guild.id)
        self.bot.audio.clear_buffer(interaction.guild.id)
        await interaction.response.send_message("\U0001f44d", ephemeral=True)

    @app_commands.command(name="leave")
    @app_commands.guild_only()
    @app_commands.check(can_leave_voice)
    async def _bot_leave_channel(self, interaction: Interaction):
        """bot leaves the voice channel [bot-moderator]"""
        await self.bot.audio.leave(interaction.guild.id)
        await interaction.response.send_message("\U0001f44b", ephemeral=True)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(VoiceControl(bot))
