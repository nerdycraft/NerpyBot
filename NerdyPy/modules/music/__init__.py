# modules/music/__init__.py
"""Music module — loads playback and playlist cogs."""

from modules.music.playback import MusicPlayback
from modules.music.playlist import MusicPlaylist


async def setup(bot) -> None:
    await bot.add_cog(MusicPlayback(bot))
    await bot.add_cog(MusicPlaylist(bot))
