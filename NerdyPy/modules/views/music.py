# -*- coding: utf-8 -*-
"""Now-playing embed builder and interactive view for the music module."""

import discord


def build_progress_bar(elapsed: float, total: float, width: int = 20) -> str:
    """Return a progress bar string, e.g. `[=====>-----] 2:30 / 5:00`."""
    if total <= 0:
        return ""
    elapsed = min(elapsed, total)
    ratio = elapsed / total
    filled = int(ratio * width)
    if filled >= width:
        bar = "=" * width
    else:
        bar = "=" * filled + ">" + "-" * (width - filled - 1)
    elapsed_str = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
    total_str = f"{int(total // 60)}:{int(total % 60):02d}"
    return f"`[{bar}] {elapsed_str} / {total_str}`"


def build_now_playing_embed(song, elapsed: float, lang: str) -> discord.Embed:
    """Build the now-playing embed for a given song and elapsed time."""
    from utils.strings import get_string

    duration = song.duration or 0
    emb = discord.Embed(
        title=get_string(lang, "music.now_playing.title"),
        description=f"[{song.title}]({song.fetch_data})" if song.title else song.fetch_data,
        color=discord.Color(0x0099FF),
    )
    progress = build_progress_bar(elapsed, duration)
    if progress:
        emb.add_field(name="\u200b", value=progress, inline=False)
    if song.requester is not None:
        emb.set_footer(text=get_string(lang, "music.now_playing.requested_by", user=song.requester.display_name))
    if hasattr(song, "_thumbnail") and song._thumbnail:
        emb.set_thumbnail(url=song._thumbnail)
    return emb
