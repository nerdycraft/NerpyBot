"""Twitch notification slash commands (DB-only; reconciler handles EventSub registration)."""

import discord
from discord import Interaction, TextChannel, app_commands
from discord.ext.commands import GroupCog

from models.twitch import TwitchNotifications
from utils.cog import NerpyBotCog
from utils.helpers import send_hidden_message


@app_commands.guild_only()
class TwitchNotificationsCog(NerpyBotCog, GroupCog, group_name="twitch"):
    """Manage Twitch stream notifications for this server."""

    def cog_load(self):
        self.bot.create_all()

    @app_commands.command(name="add", description="Add a Twitch stream notification")
    @app_commands.describe(
        streamer="Twitch login name of the streamer",
        channel="Discord channel to post notifications in",
        message="Custom message (leave empty for default)",
        notify_offline="Also notify when the stream ends",
    )
    async def add(
        self,
        interaction: Interaction,
        streamer: str,
        channel: TextChannel,
        message: str | None = None,
        notify_offline: bool = False,
    ):
        streamer_lower = streamer.lower().strip()
        with self.bot.session_scope() as session:
            existing = TwitchNotifications.get_by_channel_and_streamer(
                interaction.guild_id, channel.id, streamer_lower, session
            )
            if existing:
                await send_hidden_message(
                    interaction,
                    f"A notification for **{streamer_lower}** in {channel.mention} already exists.",
                )
                return
            row = TwitchNotifications(
                GuildId=interaction.guild_id,
                ChannelId=channel.id,
                Streamer=streamer_lower,
                StreamerDisplayName=streamer_lower,
                Message=message or None,
                NotifyOffline=notify_offline,
            )
            session.add(row)
        await send_hidden_message(
            interaction,
            self.bot.get_localized_string(interaction.guild_id, "twitch.add_success", streamer=streamer_lower),
        )

    @app_commands.command(name="remove", description="Remove a Twitch stream notification by ID")
    @app_commands.describe(config_id="The notification ID from /twitch list")
    async def remove(self, interaction: Interaction, config_id: int):
        with self.bot.session_scope() as session:
            row = TwitchNotifications.get_by_id(config_id, session)
            if row is None or row.GuildId != interaction.guild_id:
                await send_hidden_message(
                    interaction,
                    self.bot.get_localized_string(interaction.guild_id, "twitch.remove_not_found"),
                )
                return
            session.delete(row)
        await send_hidden_message(
            interaction,
            self.bot.get_localized_string(interaction.guild_id, "twitch.remove_success"),
        )

    @app_commands.command(name="list", description="List all Twitch stream notifications for this server")
    async def list(self, interaction: Interaction):
        with self.bot.session_scope() as session:
            rows = TwitchNotifications.get_all_by_guild(interaction.guild_id, session)

        if not rows:
            await send_hidden_message(
                interaction,
                self.bot.get_localized_string(interaction.guild_id, "twitch.list_empty"),
            )
            return

        embed = discord.Embed(
            title=self.bot.get_localized_string(interaction.guild_id, "twitch.list_title"),
            color=discord.Color.from_rgb(145, 70, 255),
        )
        for row in rows:
            offline_note = " (offline)" if row.NotifyOffline else ""
            embed.add_field(
                name=f"ID {row.Id}: {row.StreamerDisplayName}{offline_note}",
                value=f"<#{row.ChannelId}>" + (f"\n_{row.Message}_" if row.Message else ""),
                inline=False,
            )
        await send_hidden_message(interaction, embed=embed)


async def setup(bot):
    if "twitch" not in bot.config:
        return
    await bot.add_cog(TwitchNotificationsCog(bot))
