# -*- coding: utf-8 -*-


class NerpyBotCog:
    """Base mixin for NerpyBot cogs — sets ``self.bot`` and logs module load."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        bot.log.info(f"loaded {self.__module__}")
