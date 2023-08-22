# -*- coding: utf-8 -*-

from datetime import datetime

from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import GroupCog, hybrid_command, group

from models.GuildPrefix import GuildPrefix
from models.RoleChecker import RoleChecker


@checks.has_permissions(administrator=True)
class Admin(GroupCog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.settings = {}
        self._role_checker.start()

    def cog_unload(self):
        self._role_checker.cancel()

    @tasks.loop(seconds=5)
    async def _role_checker(self):
        msg = ""
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                self.bot.log.info(guild.name)
                configuration = RoleChecker.get(guild.id, session)
                if configuration.Enabled:
                    for member in guild.members:
                        if len(member.roles) == 1:
                            joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
                            msg += f"{member.display_name}: joined: {joined}\n"

    @_role_checker.before_loop
    async def _role_checker_before_loop(self):
        self.bot.log.info("Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @hybrid_command()
    async def rolechecker(self, ctx, enable: bool):
        """Activates the Role Checker. Kicking optional! [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @group()
    async def prefix(self, ctx):
        """Manage the prefix for the bot [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command(name="get")
    async def _prefix_get(self, ctx):
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
    async def _prefix_set(self, ctx, *, new_pref):
        """Set the prefix to use. [bot-moderator]"""
        if " " in new_pref:
            await ctx.send("Spaces not allowed in prefixes")

        with self.bot.session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is None:
                pref = GuildPrefix(GuildId=ctx.guild.id, CreateDate=datetime.utcnow(), Author=ctx.author.name)
                session.add(pref)

            pref.ModifiedDate = datetime.utcnow()
            pref.Prefix = new_pref

        await ctx.send(f"new prefix is now set to '{new_pref}'.")

    @prefix.command(name="delete", aliases=["remove", "rm", "del"])
    async def _prefix_del(self, ctx):
        """Delete the current prefix. [bot-moderator]"""
        with self.bot.session_scope() as session:
            GuildPrefix.delete(ctx.guild.id, session)
        await ctx.send("Prefix removed.")

    @hybrid_command(name="leave", aliases=["stop"])
    async def _bot_leave_channel(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
