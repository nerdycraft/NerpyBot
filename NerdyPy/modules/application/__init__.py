# -*- coding: utf-8 -*-
"""Application module — loads the ApplicationManagement cog."""

from modules.application.management import ApplicationManagement


async def setup(bot) -> None:
    await bot.add_cog(ApplicationManagement(bot))
