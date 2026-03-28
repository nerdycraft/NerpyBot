# -*- coding: utf-8 -*-
"""WoW module package: composes character, news, and crafting mixins into a single GroupCog."""

from discord import app_commands
from discord.ext.commands import GroupCog

from modules.wow.characters import WowCharactersMixin
from modules.wow.crafting import WowCraftingMixin
from modules.wow.news import WowNewsMixin
from utils.cog import NerpyBotCog
from utils.errors import NerpyInfraException


@app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
@app_commands.guild_only()
class WorldofWarcraft(WowNewsMixin, WowCraftingMixin, WowCharactersMixin, NerpyBotCog, GroupCog, group_name="wow"):
    """World of Warcraft API"""

    def __init__(self, bot):
        super().__init__(bot)
        self._init_characters(bot)
        self._init_news(bot)
        self._init_crafting(bot)

    async def cog_load(self):
        # Ensure tables exist on existing databases before running migration checks.
        self.bot.create_all()
        self.bot.loop.create_task(self._run_board_migrations())

    def cog_unload(self):
        self._guild_news_loop.cancel()
        self._crafting_cleanup_loop.cancel()


async def setup(bot):
    """adds this module to the bot"""
    if "wow" in bot.config:
        await bot.add_cog(WorldofWarcraft(bot))
    else:
        raise NerpyInfraException("Config not found.")
