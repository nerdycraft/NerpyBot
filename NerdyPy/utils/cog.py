# -*- coding: utf-8 -*-


class NerpyBotCog:
    """Base mixin for NerpyBot cogs — sets ``self.bot`` and logs module load."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        bot.log.info(f"loaded {self.__module__}")

    def _lang(self, guild_id: int | None) -> str:
        """Return the configured language for the given guild, defaulting to 'en'.

        Uses the in-memory cache; loads from DB on first access per guild.
        """
        return self.bot.get_guild_language(guild_id)
