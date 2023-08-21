# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

import discord
import pytimeparse
from discord.ext import tasks
from discord.ext.commands import GroupCog, hybrid_command, check

from models.AutoDelete import AutoDelete
from utils.checks import is_botmod


@check(is_botmod)
class AutoDeleter(GroupCog, group_name="autodeleter"):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self._loop.start()

    def cog_unload(self):
        self._loop.cancel()

    @tasks.loop(hours=4)
    async def _loop(self):
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                configured_channels = AutoDelete.get(guild.id, session)

                for configured_channel in configured_channels:
                    list_before = datetime.utcnow() - timedelta(seconds=configured_channel.DeleteAfter)
                    channel = guild.get_channel(configured_channel.ChannelId)
                    channel.purge(before=list_before)

    @hybrid_command(name="create")
    async def create_autodeleter(self, ctx, *, channel: discord.TextChannel, delete_after: str):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration_exists = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration_exists is not None:
                await ctx.send(
                    "This Channel is already configured for AutoDelete."
                    "Please edit or delete the existing configuration."
                )
            else:
                if ctx.guild.get_channel(channel_id) is not None:
                    delete_in_seconds = pytimeparse.parse(delete_after)

                    deleter = AutoDelete(GuildId=ctx.guild.id, ChannelId=channel_id, DeleteAfter=delete_in_seconds)
                    session.add(deleter)

        await ctx.send(f'AutoDeleter configured for channel "{channel_name}".')

    @hybrid_command(name="delete")
    async def delete_autodeleter(self, ctx, *, channel: discord.TextChannel):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration_exists = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration_exists is not None:
                AutoDelete.delete(ctx.guild.id, channel_id, session)
                await ctx.send(f'Deleted configuration for channel "{channel_name}".')
            else:
                await ctx.send(f'No configuration for channel "{channel_name}" found!')

    @hybrid_command(name="edit")
    async def modify_autodeleter(self, ctx, *, channel: discord.TextChannel, delete_after: str):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration_exists = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration_exists is not None:
                delete_in_seconds = pytimeparse.parse(delete_after)

                configuration_exists.DeleteAfter = delete_in_seconds

                await ctx.send(f'Changed delete threshold to "{delete_after}" in Channel "{channel_name}".')
            else:
                await ctx.send(f'Configuration for channel "{channel_name}" does not exist. Please create one first.')

    @_loop.before_loop
    async def _before_loop(self):
        self.bot.log.info("Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(AutoDeleter(bot))
