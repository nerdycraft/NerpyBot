# modules/music/__init__.py
"""Music module — loads playback and playlist cogs."""


async def setup(bot) -> None:
    # Deferred to avoid circular import: bot.py imports modules.music.audio directly,
    # which triggers this __init__; top-level imports here would form a cycle through
    # utils.checks -> bot before NerpyBot is defined.
    from modules.music.playback import MusicPlayback
    from modules.music.playlist import MusicPlaylist

    await bot.add_cog(MusicPlayback(bot))
    await bot.add_cog(MusicPlaylist(bot))
