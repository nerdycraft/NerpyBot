# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, timezone, time
from typing import Optional

import humanize
import pytimeparse
from discord.app_commands import checks
from discord.ext import tasks
from discord.ext.commands import GroupCog, hybrid_command, group

from models.GuildPrefix import GuildPrefix
from models.RoleChecker import RoleChecker

utc = timezone.utc
# If no tzinfo is given then UTC is assumed.
loop_run_time = time(hour=12, minute=30, tzinfo=utc)


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

    @tasks.loop(time=loop_run_time)
    async def _role_checker(self):
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                configuration = RoleChecker.get(guild.id, session)
                if configuration is None:
                    continue
                if configuration.Enabled and configuration.KickAfter > 0:
                    self.bot.log.info(f"Checking for member without role in {guild.name}.")
                    for member in guild.members:
                        if len(member.roles) == 1:
                            kick_reminder = datetime.utcnow() - timedelta(seconds=(configuration.KickAfter / 2))
                            kick_reminder = kick_reminder.replace(tzinfo=timezone.utc)
                            kick_after = datetime.utcnow() - timedelta(seconds=configuration.KickAfter)
                            kick_after = kick_after.replace(tzinfo=timezone.utc)

                            if member.joined_at < kick_after:
                                self.bot.log.debug(f"Kick member {member.display_name}!")
                                await member.kick()
                            elif member.joined_at < kick_reminder:
                                if configuration.ReminderMessage is not None:
                                    await member.send(configuration.ReminderMessage)
                                else:
                                    await member.send(
                                        f"You have not selected a role on {guild.name}. "
                                        f"Please choose a role until {humanize.naturaldate(kick_after)}."
                                    )

    @_role_checker.before_loop
    async def _role_checker_before_loop(self):
        self.bot.log.info("Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    @hybrid_command()
    async def rolechecker(self, ctx, enable: bool, kick_after: str, kick_reminder_message: Optional[str]):
        """Activates the Role Checker. [bot-moderator]"""
        with self.bot.session_scope() as session:
            configuration = RoleChecker.get(ctx.guild.id, session)
            if kick_after is not None:
                kick_time = pytimeparse.parse(kick_after)
            else:
                await ctx.send("You need to specify when I should kick someone!")
                return
            if configuration is not None:
                configuration.KickAfter = kick_time
                configuration.Enabled = enable
                configuration.ReminderMessage = kick_reminder_message
            else:
                rolechecker = RoleChecker(
                    GuildId=ctx.guild.id,
                    KickAfter=kick_time,
                    Enabled=enable,
                    ReminderMessage=kick_reminder_message,
                )
                session.add(rolechecker)

        await ctx.send("RoleChecker configured for this server.")

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
