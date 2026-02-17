# -*- coding: utf-8 -*-

from datetime import UTC, datetime, timedelta
from typing import Optional

import humanize
from discord import Interaction, TextChannel, app_commands
from discord.ext import tasks
from discord.ext.commands import GroupCog
from models.reminder import ReminderMessage
from utils.helpers import notify_error, send_paginated
from utils.permissions import validate_channel_permissions


@app_commands.guild_only()
class Reminder(GroupCog, group_name="reminder"):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self._reminder_loop.start()

    def cog_unload(self):
        self._reminder_loop.cancel()

    @tasks.loop(seconds=30)
    async def _reminder_loop(self):
        self.bot.log.debug("Start Reminder Loop!")
        try:
            with self.bot.session_scope() as session:
                for guild in self.bot.guilds:
                    self.bot.log.debug(f"Checking reminders for guild {guild.name} ({guild.id})")
                    messages = ReminderMessage.get_all_by_guild(guild.id, session)
                    self.bot.log.debug(f"Found {len(messages)} reminder(s) for guild {guild.name} ({guild.id})")

                    for msg in messages:
                        if msg.LastSend.astimezone(UTC) + timedelta(minutes=msg.Minutes) < datetime.now(UTC):
                            chan = guild.get_channel(msg.ChannelId)
                            if chan is None:
                                session.delete(msg)
                            else:
                                await chan.send(msg.Message)
                                if msg.Repeat < 1:
                                    session.delete(msg)
                                else:
                                    msg.LastSend = datetime.now(UTC)
                                    msg.Count += 1
        except Exception as ex:
            self.bot.log.error(f"Reminder loop: {ex}")
            await notify_error(self.bot, "Reminder background loop", ex)
        self.bot.log.debug("Stop Reminder Loop!")

    @app_commands.command(name="create")
    async def _reminder_create(
        self, interaction: Interaction, channel: Optional[TextChannel], minutes: int, repeat: bool, message: str
    ):
        """
        creates a message which gets send after a certain time
        """
        channel_id = interaction.channel.id
        channel_name = interaction.channel.name

        if channel:
            channel_id = channel.id
            channel_name = channel.name

        target = channel or interaction.channel
        validate_channel_permissions(target, interaction.guild, "view_channel", "send_messages")

        with self.bot.session_scope() as session:
            msg = ReminderMessage(
                GuildId=interaction.guild.id,
                ChannelId=channel_id,
                ChannelName=channel_name,
                Author=str(interaction.user),
                CreateDate=datetime.now(UTC),
                LastSend=datetime.now(UTC),
                Minutes=minutes,
                Message=message,
                Repeat=repeat,
                Count=0,
            )
            session.add(msg)
        await interaction.response.send_message("Message created.", ephemeral=True)

    @app_commands.command(name="list")
    async def _reminder_list(self, interaction: Interaction):
        """
        list all current reminder messages
        """
        with self.bot.session_scope() as session:
            msgs = ReminderMessage.get_all_by_guild(interaction.guild.id, session)
            if not msgs:
                await interaction.response.send_message("No reminders set.", ephemeral=True)
                return

            to_send = ""
            for msg in msgs:
                next_send = humanize.naturaltime(
                    msg.LastSend + timedelta(minutes=float(msg.Minutes)), when=datetime.now(UTC)
                )
                to_send += f"**#{msg.Id}** \u2014 #{msg.ChannelName}\n"
                to_send += f"> {msg.Message}\n"
                to_send += f"*{msg.Author} \u00b7 Next: {next_send} \u00b7 Hits: {msg.Count}*\n\n"

            await send_paginated(interaction, to_send, title="\u23f0 Reminders", color=0xF39C12, ephemeral=True)

    @app_commands.command(name="delete")
    async def _reminder_delete(self, interaction: Interaction, reminder_id: int):
        """
        deletes a reminder message
        """
        with self.bot.session_scope() as session:
            ReminderMessage.delete(reminder_id, interaction.guild.id, session)
        await interaction.response.send_message("Message deleted.", ephemeral=True)

    @_reminder_loop.before_loop
    async def _reminder_before_loop(self):
        self.bot.log.info("Reminder: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Reminder(bot))
