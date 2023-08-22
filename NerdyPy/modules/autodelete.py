# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

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

    @tasks.loop(minutes=5)
    async def _loop(self):
        with self.bot.session_scope() as session:
            for guild in self.bot.guilds:
                configurations = AutoDelete.get(guild.id, session)

                for configuration in configurations:
                    if configuration.DeleteOlderThan is None:
                        list_before = None
                    else:
                        list_before = datetime.utcnow() - timedelta(seconds=configuration.DeleteOlderThan)
                    list_before = list_before.replace(tzinfo=timezone.utc)
                    channel = guild.get_channel(configuration.ChannelId)
                    messages = [message async for message in channel.history(before=list_before, oldest_first=True)]

                    while len(messages) > configuration.KeepMessages:
                        message = messages.pop()
                        if not configuration.DeletePinnedMessage and message.pinned:
                            continue
                        self.bot.log.info(f"Delete message {message.id}, created at {message.created_at}.")
                        await message.delete()

    @hybrid_command(name="create")
    async def create_autodeleter(
        self,
        ctx,
        *,
        channel: discord.TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                await ctx.send(
                    "This Channel is already configured for AutoDelete."
                    "Please edit or delete the existing configuration."
                )
            else:
                if ctx.guild.get_channel(channel_id) is not None:
                    if delete_older_than is None:
                        configuration.DeleteOlderThan = delete_older_than
                    else:
                        delete_in_seconds = pytimeparse.parse(delete_older_than)

                    deleter = AutoDelete(
                        GuildId=ctx.guild.id,
                        ChannelId=channel_id,
                        KeepMessages=keep_messages,
                        DeleteOlderThan=delete_in_seconds,
                        DeletePinnedMessage=delete_pinned_message,
                    )
                    session.add(deleter)

        await ctx.send(f'AutoDeleter configured for channel "{channel_name}".')

    @hybrid_command(name="delete")
    async def delete_autodeleter(self, ctx, *, channel: discord.TextChannel):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                AutoDelete.delete(ctx.guild.id, channel_id, session)
                await ctx.send(f'Deleted configuration for channel "{channel_name}".')
            else:
                await ctx.send(f'No configuration for channel "{channel_name}" found!')

    @hybrid_command(name="edit")
    async def modify_autodeleter(
        self,
        ctx,
        *,
        channel: discord.TextChannel,
        delete_older_than: Optional[Union[str | None]],
        keep_messages: Optional[Union[int | None]],
        delete_pinned_message: bool,
    ):
        channel_id = channel.id
        channel_name = channel.name

        with self.bot.session_scope() as session:
            configuration = AutoDelete.get_by_channel(ctx.guild.id, channel_id, session)
            if configuration is not None:
                if delete_older_than is None:
                    configuration.DeleteOlderThan = delete_older_than
                else:
                    delete_in_seconds = pytimeparse.parse(delete_older_than)
                    configuration.DeleteOlderThan = delete_in_seconds
                configuration.KeepMessages = keep_messages
                configuration.DeletePinnedMessage = delete_pinned_message

                await ctx.send(f'Updated configuration for channel "{channel_name}".')
            else:
                await ctx.send(f'Configuration for channel "{channel_name}" does not exist. Please create one first.')

    @_loop.before_loop
    async def _before_loop(self):
        self.bot.log.info("Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(AutoDeleter(bot))
