# -*- coding: utf-8 -*-

import logging
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from typing import Literal, Optional

from discord import Embed, Forbidden, HTTPException, Interaction, Object, Role
from discord import app_commands
from discord.app_commands import CommandSyncFailure, MissingApplicationID, TranslationError
from discord.ext.commands import Cog, Context, Greedy, command, hybrid_command
from models.botmod import BotModeratorRole
from models.permissions import PermissionSubscriber

from utils.checks import is_admin_or_operator, require_operator
from utils.errors import NerpyException
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for


@app_commands.default_permissions(administrator=True)
class Admin(Cog):
    """cog for administrative usage"""

    modrole = app_commands.Group(
        name="modrole", description="Manage the bot-moderator role for this server", guild_only=True
    )
    botpermissions = app_commands.Group(name="botpermissions", description="Check bot permissions", guild_only=True)

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Allow administrators and bot operators to use all admin slash commands."""
        if interaction.command and interaction.command.name == "ping":
            return True
        if await is_admin_or_operator(interaction):
            return True
        raise app_commands.CheckFailure("This command requires administrator permissions or bot operator status.")

    async def cog_check(self, ctx: Context) -> bool:
        """Allow operators to use DM prefix commands (sync, debug, uptime)."""
        if ctx.command and ctx.command.name == "ping":
            return True
        if ctx.author.id in self.bot.ops:
            return True
        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        raise NerpyException("This command requires administrator permissions or bot operator status.")

    @modrole.command(name="get")
    async def _modrole_get(self, interaction: Interaction):
        """Show the currently configured bot-moderator role."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is not None:
                role = interaction.guild.get_role(entry.RoleId)
                if role is not None:
                    await interaction.response.send_message(f"Bot-moderator role: **{role.name}**", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "A bot-moderator role is configured but the role no longer exists."
                        " Use `/admin modrole delete` to clear it.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    "No bot-moderator role configured. Falling back to permission-based checks.", ephemeral=True
                )

    @modrole.command(name="set")
    async def _modrole_set(self, interaction: Interaction, role: Role):
        """Set the bot-moderator role for this server."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is None:
                entry = BotModeratorRole(GuildId=interaction.guild.id)
                session.add(entry)
            entry.RoleId = role.id
        await interaction.response.send_message(f"Bot-moderator role set to **{role.name}**.", ephemeral=True)

    @modrole.command(name="delete")
    async def _modrole_del(self, interaction: Interaction):
        """Remove the bot-moderator role configuration."""
        with self.bot.session_scope() as session:
            BotModeratorRole.delete(interaction.guild.id, session)
        await interaction.response.send_message("Bot-moderator role removed.", ephemeral=True)

    @botpermissions.command(name="check")
    async def _botpermissions_check(self, interaction: Interaction) -> None:
        """Check if the bot has all required permissions in this server."""
        required = required_permissions_for(self.bot.modules)
        missing = check_guild_permissions(interaction.guild, required)
        emb = build_permissions_embed(interaction.guild, missing, self.bot.client_id, required)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @botpermissions.command(name="subscribe")
    async def _botpermissions_subscribe(self, interaction: Interaction) -> None:
        """Get DM notifications about missing permissions on bot restart."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(interaction.guild.id, interaction.user.id, session)
            if existing is not None:
                await interaction.response.send_message(
                    "You are already subscribed to permission notifications.", ephemeral=True
                )
                return
            session.add(PermissionSubscriber(GuildId=interaction.guild.id, UserId=interaction.user.id))
        await interaction.response.send_message(
            "Subscribed. You will receive a DM when the bot restarts with missing permissions in this server.",
            ephemeral=True,
        )

    @botpermissions.command(name="unsubscribe")
    async def _botpermissions_unsubscribe(self, interaction: Interaction) -> None:
        """Stop receiving DM notifications about missing permissions."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(interaction.guild.id, interaction.user.id, session)
            if existing is None:
                await interaction.response.send_message(
                    "You are not subscribed to permission notifications.", ephemeral=True
                )
                return
            PermissionSubscriber.delete(interaction.guild.id, interaction.user.id, session)
        await interaction.response.send_message(
            "Unsubscribed from permission notifications for this server.", ephemeral=True
        )

    @hybrid_command(name="ping")
    @app_commands.default_permissions()
    async def ping(self, ctx: Context):
        """Pong."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"\U0001f3d3 Pong! **{latency}ms**")

    @command(name="sync")
    async def sync(
        self, ctx: Context, guilds: Greedy[Object], spec: Optional[Literal["local", "copy", "clear"]] = None
    ) -> None:
        """Sync commands globally or to a specific guild. [operator]"""
        if not guilds:
            if spec in ("local", "copy", "clear") and ctx.guild is None:
                await ctx.send(f"The `{spec}` option requires a server context.")
                return
            if spec == "local":
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "copy":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "clear":
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await self.bot.tree.sync()

            await ctx.send(f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}")
            return

        ret = 0
        for guild in guilds:
            try:
                await self.bot.tree.sync(guild=guild)
            except HTTPException:
                pass
            except (CommandSyncFailure, Forbidden, MissingApplicationID, TranslationError) as ex:
                self.bot.log.debug(ex)
                raise NerpyException("Could not sync commands to Discord API.")
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @command(name="uptime")
    async def _uptime(self, ctx: Context) -> None:
        """Shows bot uptime and version. [operator]"""
        require_operator(ctx)

        td = datetime.now(UTC) - self.bot.uptime
        bot_version = pkg_version("NerpyBot")
        hours = td.seconds // 3600
        minutes = (td.seconds // 60) % 60

        emb = Embed(
            description=f"**{td.days}**d · **{hours}**h · **{minutes}**m",
            color=0x5865F2,
        )
        emb.set_author(name=f"NerpyBot v{bot_version}")
        await ctx.send(embed=emb)

    @command(name="debug")
    async def _debug(self, ctx: Context) -> None:
        """Toggle debug logging at runtime. [operator]"""
        require_operator(ctx)

        logger = logging.getLogger("nerpybot")
        if logger.level == logging.DEBUG:
            logger.setLevel(logging.INFO)
            self.bot.debug = False
            await ctx.send("Debug logging **disabled** (level: INFO).")
        else:
            logger.setLevel(logging.DEBUG)
            self.bot.debug = True
            await ctx.send("Debug logging **enabled** (level: DEBUG).")

        self.bot.log.info(f"debug logging toggled to {self.bot.debug} by {ctx.author}")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
