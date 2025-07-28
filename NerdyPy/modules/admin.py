# -*- coding: utf-8 -*-

from datetime import datetime, UTC
from typing import Optional, Literal

from discord import Object, HTTPException, Forbidden
from discord.app_commands import checks, CommandSyncFailure, MissingApplicationID, TranslationError
from discord.ext.commands import Cog, group, Context, command, guild_only, Greedy

from models.admin import GuildPrefix
from utils.errors import NerpyException


@checks.has_permissions(administrator=True)
class Admin(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

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
                await ctx.send(f"The current prefix is set to: {pref.Prefix}")
            else:
                await ctx.send(
                    'There is no custom prefix set. I will respond to Slash Commands or the default prefix "!".'
                )

    @prefix.command(name="set")
    async def _prefix_set(self, ctx: Context, *, new_pref):
        """Set the prefix to use. [bot-moderator]"""
        if " " in new_pref:
            await ctx.send("Spaces not allowed in prefixes")

        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is None:
                pref = GuildPrefix(GuildId=ctx.guild.id, CreateDate=datetime.now(UTC), Author=ctx.author.name)
                session.add(pref)

            pref.ModifiedDate = datetime.now(UTC)
            pref.Prefix = new_pref

        await ctx.send(f"new prefix is now set to '{new_pref}'.")

    @prefix.command(name="delete", aliases=["remove", "rm", "del"])
    async def _prefix_del(self, ctx: Context):
        """Delete the current prefix. [bot-moderator]"""
        with self.bot.session_scope() as session:
            GuildPrefix.delete(ctx.guild.id, session)
        await ctx.send("Prefix removed.")

    @command(name="sync")
    @guild_only()
    async def sync(
        self, ctx: Context, guilds: Greedy[Object], spec: Optional[Literal["local", "copy", "clear"]] = None
    ) -> None:
        if not guilds:
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


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
