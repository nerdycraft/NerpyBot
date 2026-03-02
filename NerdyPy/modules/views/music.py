# -*- coding: utf-8 -*-
"""Now-playing embed builder and interactive view for the music module."""

import discord
from utils.strings import get_string


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

    @discord.ui.button(emoji="\u23ef\ufe0f", style=discord.ButtonStyle.primary, custom_id="music:pause_resume")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._in_same_channel(interaction):
            await self._reject(interaction)
            return
        if self.audio.is_paused(interaction.guild_id):
            self.audio.resume(interaction.guild_id)
        else:
            self.audio.pause(interaction.guild_id)
        await interaction.response.defer()

    @discord.ui.button(emoji="\u23ed\ufe0f", style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._in_same_channel(interaction):
            await self._reject(interaction)
            return
        self.audio.stop(interaction.guild_id)
        await interaction.response.defer()

    @discord.ui.button(emoji="\u23f9\ufe0f", style=discord.ButtonStyle.danger, custom_id="music:stop")
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

    @discord.ui.button(emoji="\U0001f4cb", style=discord.ButtonStyle.secondary, custom_id="music:queue")
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
