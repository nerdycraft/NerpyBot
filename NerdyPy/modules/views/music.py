# -*- coding: utf-8 -*-
"""Now-playing embed builder and interactive view for the music module."""

import discord
from utils.strings import get_string


def _fmt_time(seconds: float) -> str:
    """Format seconds as H:MM:SS."""
    t = int(seconds)
    h, rem = divmod(t, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}"


def build_progress_bar(elapsed: float, total: float, width: int = 16) -> str:
    """Return a two-line code-block progress bar, e.g.:\n```[>---------------]\n0:00:00 / 0:05:00```"""
    if total <= 0:
        return ""
    elapsed = min(elapsed, total)
    ratio = elapsed / total
    filled = int(ratio * width)
    if filled >= width:
        bar = "=" * width
    else:
        bar = "=" * filled + ">" + "-" * (width - filled - 1)
    return f"```\n[{bar}]\n{_fmt_time(elapsed)} / {_fmt_time(total)}\n```"


def build_now_playing_embed(song, elapsed: float, lang: str) -> discord.Embed:
    """Build the now-playing embed for a given song and elapsed time."""
    duration = song.duration or 0
    emb = discord.Embed(
        title=f"\U0001f3b5 {song.title}" if song.title else "\U0001f3b5 Unknown",
        url=song.fetch_data,
        color=discord.Color(0xFF7700),
    )
    desc_lines = []
    if song.artist:
        artist_label = get_string(lang, "music.now_playing.artist")
        desc_lines.append(f"**{artist_label}:** {song.artist}")
    if song.requester is not None:
        req_label = get_string(lang, "music.now_playing.requested_by")
        desc_lines.append(f"**{req_label}:** {song.requester.mention}")
    if desc_lines:
        emb.description = "\n".join(desc_lines)
    progress = build_progress_bar(elapsed, duration)
    if progress:
        emb.add_field(name=get_string(lang, "music.now_playing.progress"), value=progress, inline=False)
    if song.thumbnail:
        emb.set_thumbnail(url=song.thumbnail)
    return emb


class NowPlayingView(discord.ui.View):
    """Interactive controls attached to the now-playing embed."""

    def __init__(self, audio, lang: str = "en"):
        super().__init__(timeout=None)
        self.audio = audio
        self.lang = lang

    def _in_same_channel(self, interaction: discord.Interaction) -> bool:
        bot_vc = interaction.guild.voice_client
        if bot_vc is None:
            return False
        if interaction.user.voice is None:
            return False
        return interaction.user.voice.channel == bot_vc.channel

    async def _reject(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            get_string(self.lang, "music.now_playing.not_in_channel"), ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.HTTPException:
            pass

    @discord.ui.button(label="\u23f8 Pause", style=discord.ButtonStyle.primary, custom_id="music:pause_resume")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._in_same_channel(interaction):
            await self._reject(interaction)
            return
        if self.audio.is_paused(interaction.guild_id):
            self.audio.resume(interaction.guild_id)
            button.label = "\u23f8 Pause"
        else:
            self.audio.pause(interaction.guild_id)
            button.label = "\u25b6 Resume"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="\u23e9 Skip", style=discord.ButtonStyle.primary, custom_id="music:skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._in_same_channel(interaction):
            await self._reject(interaction)
            return
        self.audio.stop(interaction.guild_id)
        await interaction.response.defer()

    @discord.ui.button(label="\u23f9 Stop", style=discord.ButtonStyle.danger, custom_id="music:stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._in_same_channel(interaction):
            await self._reject(interaction)
            return
        self.audio.stop_and_clear(interaction.guild_id)
        msg = self.audio.now_playing_message.pop(interaction.guild_id, None)
        if msg is not None:
            try:
                await msg.delete()
            except discord.NotFound:
                pass
        await interaction.response.defer()

    @discord.ui.button(label="\U0001f4cb Queue", style=discord.ButtonStyle.secondary, custom_id="music:queue")
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.audio.list_queue(interaction.guild_id)
        if not queue:
            await interaction.response.send_message(
                get_string(self.lang, "music.now_playing.queue_empty"), ephemeral=True
            )
            return
        # Cap display to first 10 entries to stay within Discord's 2000-char limit
        shown = queue[:10]
        lines = "\n".join(f"`{i}` {s.title}" for i, s in enumerate(shown, 1))
        if len(queue) > 10:
            lines += f"\n… and {len(queue) - 10} more"
        header = get_string(self.lang, "music.now_playing.queue_header")
        await interaction.response.send_message(f"**{header}**\n{lines}", ephemeral=True)
