# -*- coding: utf-8 -*-

import logging
from datetime import UTC, datetime
from typing import Literal, Optional

from discord import Forbidden, HTTPException, Object, Role
from discord import app_commands
from discord.app_commands import CommandSyncFailure, MissingApplicationID, TranslationError
from discord.ext.commands import Cog, Context, Greedy, command, group, hybrid_group
from models.admin import GuildPrefix
from models.botmod import BotModeratorRole
from models.permissions import PermissionSubscriber

from utils.checks import is_admin_or_operator
from utils.errors import NerpyException
from utils.helpers import send_hidden_message
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for


@app_commands.default_permissions(administrator=True)
class Admin(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        """Allow administrators and bot operators to use all admin commands."""
        if await is_admin_or_operator(ctx):
            return True
        raise NerpyException("This command requires administrator permissions or bot operator status.")

    @group()
    async def prefix(self, ctx: Context):
        """Manage the prefix for the bot [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command(name="get")
    async def _prefix_get(self, ctx: Context):
        """Get the prefix currently used. [bot-moderator]"""
        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is not None:
                await send_hidden_message(ctx, f"The current prefix is set to: {pref.Prefix}")
            else:
                await send_hidden_message(
                    ctx, 'There is no custom prefix set. I will respond to Slash Commands or the default prefix "!".'
                )

    @prefix.command(name="set")
    async def _prefix_set(self, ctx: Context, *, new_pref):
        """Set the prefix to use. [bot-moderator]"""
        if " " in new_pref:
            await send_hidden_message(ctx, "Spaces not allowed in prefixes")

        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is None:
                pref = GuildPrefix(GuildId=ctx.guild.id, CreateDate=datetime.now(UTC), Author=ctx.author.name)
                session.add(pref)

            pref.ModifiedDate = datetime.now(UTC)
            pref.Prefix = new_pref

        await send_hidden_message(ctx, f"new prefix is now set to '{new_pref}'.")

    @prefix.command(name="delete", aliases=["remove", "rm", "del"])
    async def _prefix_del(self, ctx: Context):
        """Delete the current prefix. [bot-moderator]"""
        with self.bot.session_scope() as session:
            GuildPrefix.delete(ctx.guild.id, session)
        await send_hidden_message(ctx, "Prefix removed.")

    @hybrid_group()
    async def modrole(self, ctx: Context):
        """Manage the bot-moderator role for this server."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @modrole.command(name="get")
    async def _modrole_get(self, ctx: Context):
        """Show the currently configured bot-moderator role."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(ctx.guild.id, session)
            if entry is not None:
                role = ctx.guild.get_role(entry.RoleId)
                if role is not None:
                    await send_hidden_message(ctx, f"Bot-moderator role: **{role.name}**")
                else:
                    await send_hidden_message(
                        ctx,
                        "A bot-moderator role is configured but the role no longer exists."
                        " Use `modrole delete` to clear it.",
                    )
            else:
                await send_hidden_message(
                    ctx, "No bot-moderator role configured. Falling back to permission-based checks."
                )

    @modrole.command(name="set")
    async def _modrole_set(self, ctx: Context, role: Role):
        """Set the bot-moderator role for this server."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(ctx.guild.id, session)
            if entry is None:
                entry = BotModeratorRole(GuildId=ctx.guild.id)
                session.add(entry)
            entry.RoleId = role.id
        await send_hidden_message(ctx, f"Bot-moderator role set to **{role.name}**.")

    @modrole.command(name="delete", aliases=["remove", "rm", "del"])
    async def _modrole_del(self, ctx: Context):
        """Remove the bot-moderator role configuration."""
        with self.bot.session_scope() as session:
            BotModeratorRole.delete(ctx.guild.id, session)
        await send_hidden_message(ctx, "Bot-moderator role removed.")

    @command(name="sync")
    async def sync(
        self, ctx: Context, guilds: Greedy[Object], spec: Optional[Literal["local", "copy", "clear"]] = None
    ) -> None:
        if not guilds:
            if spec in ("local", "copy", "clear") and ctx.guild is None:
                await send_hidden_message(ctx, f"The `{spec}` option requires a server context.")
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

            await send_hidden_message(
                ctx, f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
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

        await send_hidden_message(ctx, f"Synced the tree to {ret}/{len(guilds)}.")

    @command(name="debug")
    async def _debug(self, ctx: Context) -> None:
        """Toggle debug logging at runtime. [operator]"""
        if ctx.author.id not in self.bot.ops:
            raise NerpyException("This command is restricted to bot operators.")

        logger = logging.getLogger("nerpybot")
        if logger.level == logging.DEBUG:
            logger.setLevel(logging.INFO)
            self.bot.debug = False
            await send_hidden_message(ctx, "Debug logging **disabled** (level: INFO).")
        else:
            logger.setLevel(logging.DEBUG)
            self.bot.debug = True
            await send_hidden_message(ctx, "Debug logging **enabled** (level: DEBUG).")

        self.bot.log.info(f"debug logging toggled to {self.bot.debug} by {ctx.author}")

    @hybrid_group(name="botpermissions", fallback="check")
    async def botpermissions(self, ctx: Context) -> None:
        """Check if the bot has all required permissions in this server."""
        required = required_permissions_for(self.bot.modules)
        missing = check_guild_permissions(ctx.guild, required)
        emb = build_permissions_embed(ctx.guild, missing, self.bot.client_id, required)
        await send_hidden_message(ctx, embed=emb)

    @botpermissions.command(name="subscribe")
    async def _botpermissions_subscribe(self, ctx: Context) -> None:
        """Get DM notifications about missing permissions on bot restart."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(ctx.guild.id, ctx.author.id, session)
            if existing is not None:
                await send_hidden_message(ctx, "You are already subscribed to permission notifications.")
                return
            session.add(PermissionSubscriber(GuildId=ctx.guild.id, UserId=ctx.author.id))
        await send_hidden_message(
            ctx, "Subscribed. You will receive a DM when the bot restarts with missing permissions in this server."
        )

    @botpermissions.command(name="unsubscribe")
    async def _botpermissions_unsubscribe(self, ctx: Context) -> None:
        """Stop receiving DM notifications about missing permissions."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(ctx.guild.id, ctx.author.id, session)
            if existing is None:
                await send_hidden_message(ctx, "You are not subscribed to permission notifications.")
                return
            PermissionSubscriber.delete(ctx.guild.id, ctx.author.id, session)
        await send_hidden_message(ctx, "Unsubscribed from permission notifications for this server.")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
