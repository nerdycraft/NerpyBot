# -*- coding: utf-8 -*-

import asyncio

import discord
from discord import Forbidden, HTTPException, Interaction, Member, NotFound, Role, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import Cog

from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage
from models.rolemanage import RoleMapping
from utils.cache import REACTION_ROLE_CACHE_MISS, cached_autocomplete, invalidate_autocomplete
from utils.checks import is_role_assignable, is_role_below_bot
from utils.cog import NerpyBotCog
from utils.helpers import error_context, notify_error, send_paginated
from utils.permissions import validate_channel_permissions
from utils.strings import get_string


class Roles(NerpyBotCog, Cog):
    """Cog combining delegated role management and reaction-based role assignment."""

    rolemanage = app_commands.Group(
        name="rolemanage",
        description="Delegated role management — lets specific roles assign other roles",
        guild_only=True,
    )
    reactionrole = app_commands.Group(
        name="reactionrole",
        description="Manage reaction-based role assignment",
        guild_only=True,
        default_permissions=discord.Permissions(manage_roles=True),
    )

    # ── rolemanage helpers ────────────────────────────────────────────────────

    # noinspection PyMethodMayBeStatic
    def _has_source_role(self, member, mappings):
        """Check if the member holds any source role from the given mappings."""
        member_role_ids = {r.id for r in member.roles}
        return any(m.SourceRoleId in member_role_ids for m in mappings)

    # ── reactionrole helpers ──────────────────────────────────────────────────

    async def _message_id_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        guild = interaction.guild
        guild_id = guild.id

        def _fetch():
            with self.bot.session_scope() as session:
                return [
                    {
                        "channel_id": msg.ChannelId,
                        "message_id": msg.MessageId,
                        "entry_count": len(msg.entries),
                        "channel_name": None,  # resolved below; None entries are updated in-place to avoid re-fetching within TTL
                    }
                    for msg in ReactionRoleMessage.get_by_guild(guild_id, session)
                ]

        messages = await cached_autocomplete(("rr_msgs", guild_id), _fetch)
        if not messages:
            return []

        # Fill channel names from Discord's internal cache (fast dict lookup).
        for m in messages:
            if m["channel_name"] is None:
                ch = guild.get_channel(m["channel_id"])
                if ch:
                    m["channel_name"] = f"#{ch.name}"

        # For channels still unresolved, fetch in parallel. Mutate cached entries in-place so
        # subsequent calls within the 30s TTL window skip these HTTP round-trips.
        still_missing = [m for m in messages if m["channel_name"] is None]
        if still_missing:

            async def _fetch_channel(cid):
                try:
                    return await guild.fetch_channel(cid)
                except (discord.NotFound, discord.Forbidden):
                    return None

            fetched = await asyncio.gather(*(_fetch_channel(m["channel_id"]) for m in still_missing))
            for m, ch in zip(still_missing, fetched):
                m["channel_name"] = f"#{ch.name}" if ch else "Unknown"

        choices = []
        for rr_msg in messages:
            channel_name = rr_msg["channel_name"] or "Unknown"
            entry_count = rr_msg["entry_count"]
            label = f"{channel_name} \u00b7 {rr_msg['message_id']} ({entry_count} mappings)"
            msg_id_str = str(rr_msg["message_id"])
            if current and current not in msg_id_str and current.lower() not in channel_name.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=msg_id_str))
        return choices[:25]

    def _get_role_for_reaction(self, payload):
        """Look up the role for a given reaction event payload."""
        if not self.bot.guild_cache.is_reaction_role_message(payload.message_id):
            return None

        emoji_str = str(payload.emoji)
        role_id = self.bot.guild_cache.get_reaction_role(payload.message_id, emoji_str)

        if role_id is REACTION_ROLE_CACHE_MISS:
            # Cache not yet warmed — fall back to DB and backfill
            with self.bot.session_scope() as session:
                rr_msg = ReactionRoleMessage.get_by_message(payload.message_id, session)
                if rr_msg is None:
                    return None
                entry = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji_str, session)
                if entry is None:
                    return None
                role_id = entry.RoleId
            self.bot.guild_cache.add_reaction_role_entry(payload.message_id, emoji_str, role_id)
        elif role_id is None:
            return None

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return None

        return guild.get_role(role_id)

    async def _clear_reaction(self, guild, channel_id, message_id, emoji):
        """Remove all reactions of a specific emoji from a message."""
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                return
        try:
            discord_msg = await channel.fetch_message(message_id)
            await discord_msg.clear_reaction(emoji)
        except HTTPException as ex:
            self.bot.log.warning(
                f"[{guild.name} ({guild.id})]: could not clear reaction {emoji} from message {message_id}: {ex}"
            )

    # ── reactionrole event listeners ──────────────────────────────────────────

    @Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None or payload.member is None or payload.member.bot:
            return

        role = self._get_role_for_reaction(payload)
        if role is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        guild_info = f"{guild.name} ({guild.id})" if guild else payload.guild_id
        self.bot.log.debug(f"[{guild_info}] {payload.member}: assigning role {role.name} via reaction")

        try:
            await payload.member.add_roles(role, reason="Reaction role")
        except HTTPException as ex:
            self.bot.log.error(
                f"[{guild_info}] {payload.member} ({payload.member.id}): "
                f"failed to add role {role.name} ({role.id}): {ex}"
            )
            await notify_error(self.bot, f"[{guild_info}] Reaction role add failed", ex)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id is None:
            return

        role = self._get_role_for_reaction(payload)
        if role is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        self.bot.log.debug(f"[{guild.name} ({guild.id})] {member}: removing role {role.name} via reaction")

        try:
            await member.remove_roles(role, reason="Reaction role")
        except HTTPException as ex:
            self.bot.log.error(
                f"[{guild.name} ({guild.id})] {member} ({member.id}): "
                f"failed to remove role {role.name} ({role.id}): {ex}"
            )
            await notify_error(self.bot, f"[{guild.name} ({guild.id})] Reaction role remove failed", ex)

    # ── /rolemanage commands ──────────────────────────────────────────────────

    @rolemanage.command(name="allow")
    @checks.has_permissions(manage_roles=True)
    async def _rolemanage_allow(self, interaction: Interaction, source_role: Role, target_role: Role):
        """Allow a source role to assign a target role. [manage_roles]

        Parameters
        ----------
        interaction
        source_role: discord.Role
            The role whose members can assign the target role
        target_role: discord.Role
            The role that can be assigned
        """
        if not await is_role_assignable(interaction, target_role):
            return
        if not await is_role_below_bot(interaction, target_role):
            return

        lang = self._lang(interaction.guild_id)
        error_msg = None
        with self.bot.session_scope() as session:
            existing = RoleMapping.get(interaction.guild.id, source_role.id, target_role.id, session)
            if existing:
                error_msg = get_string(
                    lang, "rolemanage.allow.already_exists", source=source_role.name, target=target_role.name
                )
            else:
                mapping = RoleMapping(
                    GuildId=interaction.guild.id,
                    SourceRoleId=source_role.id,
                    TargetRoleId=target_role.id,
                )
                session.add(mapping)

        if error_msg:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        await interaction.response.send_message(
            get_string(lang, "rolemanage.allow.success", source=source_role.name, target=target_role.name),
            ephemeral=True,
        )

    @rolemanage.command(name="deny")
    @checks.has_permissions(manage_roles=True)
    async def _rolemanage_deny(self, interaction: Interaction, source_role: Role, target_role: Role):
        """Remove a source-to-target role mapping. [manage_roles]

        Parameters
        ----------
        interaction
        source_role: discord.Role
            The source role
        target_role: discord.Role
            The target role
        """
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            deleted = RoleMapping.delete(interaction.guild.id, source_role.id, target_role.id, session)

        if deleted:
            await interaction.response.send_message(
                get_string(lang, "rolemanage.deny.success", source=source_role.name, target=target_role.name),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(get_string(lang, "rolemanage.deny.not_found"), ephemeral=True)

    @rolemanage.command(name="list")
    @checks.has_permissions(manage_roles=True)
    async def _rolemanage_list(self, interaction: Interaction):
        """List all delegated role mappings for this server. [manage_roles]"""
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_guild(interaction.guild.id, session)
            msg = ""
            for m in mappings:
                source = interaction.guild.get_role(m.SourceRoleId)
                target = interaction.guild.get_role(m.TargetRoleId)
                source_name = source.name if source else f"Unknown ({m.SourceRoleId})"
                target_name = target.name if target else f"Unknown ({m.TargetRoleId})"
                msg += f"> **{source_name}** \u2192 {target_name}\n"

        if not mappings:
            await interaction.response.send_message(get_string(lang, "rolemanage.list.empty"), ephemeral=True)
            return

        await send_paginated(
            interaction, msg, title=get_string(lang, "rolemanage.list.title"), color=0x3498DB, ephemeral=True
        )

    @rolemanage.command(name="assign")
    async def _rolemanage_assign(self, interaction: Interaction, member: Member, role: Role):
        """Assign a role to a member (requires a delegated mapping).

        Parameters
        ----------
        interaction
        member: discord.Member
            The member to assign the role to
        role: discord.Role
            The role to assign
        """
        if not await is_role_assignable(interaction, role):
            return
        if not await is_role_below_bot(interaction, role):
            return

        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(interaction.guild.id, role.id, session)

        if not mappings or not self._has_source_role(interaction.user, mappings):
            await interaction.response.send_message(get_string(lang, "rolemanage.assign.no_permission"), ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message(
                get_string(lang, "rolemanage.assign.already_has", member=member.display_name, role=role.name),
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(role, reason=f"Delegated role assign by {interaction.user}")
        except Forbidden:
            self.bot.log.error(f"{error_context(interaction)}: forbidden assigning {role.name} to {member}")
            await interaction.response.send_message(
                get_string(lang, "rolemanage.assign.forbidden", role=role.name), ephemeral=True
            )
            return
        except HTTPException as ex:
            self.bot.log.error(f"{error_context(interaction)}: failed to assign {role.name} to {member}: {ex}")
            await interaction.response.send_message(
                get_string(lang, "rolemanage.assign.discord_error", status=ex.status), ephemeral=True
            )
            return

        await interaction.response.send_message(
            get_string(lang, "rolemanage.assign.success", role=role.name, member=member.display_name), ephemeral=True
        )

    @rolemanage.command(name="remove")
    async def _rolemanage_remove(self, interaction: Interaction, member: Member, role: Role):
        """Remove a role from a member (requires a delegated mapping).

        Parameters
        ----------
        interaction
        member: discord.Member
            The member to remove the role from
        role: discord.Role
            The role to remove
        """
        if not await is_role_assignable(interaction, role, action="removed from"):
            return
        if not await is_role_below_bot(interaction, role):
            return

        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(interaction.guild.id, role.id, session)

        if not mappings or not self._has_source_role(interaction.user, mappings):
            await interaction.response.send_message(get_string(lang, "rolemanage.remove.no_permission"), ephemeral=True)
            return

        if role not in member.roles:
            await interaction.response.send_message(
                get_string(lang, "rolemanage.remove.does_not_have", member=member.display_name, role=role.name),
                ephemeral=True,
            )
            return

        try:
            await member.remove_roles(role, reason=f"Delegated role remove by {interaction.user}")
        except Forbidden:
            self.bot.log.error(f"{error_context(interaction)}: forbidden removing {role.name} from {member}")
            await interaction.response.send_message(
                get_string(lang, "rolemanage.remove.forbidden", role=role.name), ephemeral=True
            )
            return
        except HTTPException as ex:
            self.bot.log.error(f"{error_context(interaction)}: failed to remove {role.name} from {member}: {ex}")
            await interaction.response.send_message(
                get_string(lang, "rolemanage.remove.discord_error", status=ex.status), ephemeral=True
            )
            return

        await interaction.response.send_message(
            get_string(lang, "rolemanage.remove.success", role=role.name, member=member.display_name), ephemeral=True
        )

    # ── /reactionrole commands ────────────────────────────────────────────────

    @reactionrole.command(name="add")
    @checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(message_id=_message_id_autocomplete)
    async def _reactionrole_add(
        self, interaction: Interaction, channel: TextChannel, message_id: str, emoji: str, role: Role
    ):
        """Add an emoji-to-role mapping on any message.

        Parameters
        ----------
        interaction
        channel: discord.TextChannel
            The channel the message is in
        message_id: str
            The Discord message ID to attach the reaction role to
        emoji: str
            The emoji to react with
        role: discord.Role
            The role to assign when the emoji is used
        """
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return

        if not await is_role_below_bot(interaction, role):
            return

        validate_channel_permissions(
            channel, interaction.guild, "view_channel", "add_reactions", "manage_messages", "read_message_history"
        )

        lang = self._lang(interaction.guild_id)

        try:
            discord_msg = await channel.fetch_message(msg_id)
        except (NotFound, Forbidden) as ex:
            self.bot.log.warning(f"{error_context(interaction)}: fetch_message({msg_id}) in #{channel.name}: {ex}")
            await interaction.response.send_message(
                get_string(lang, "reactionrole.add.message_not_found", message_id=msg_id, channel=channel.mention),
                ephemeral=True,
            )
            return

        error_msg = None
        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                rr_msg = ReactionRoleMessage(
                    GuildId=interaction.guild.id,
                    ChannelId=channel.id,
                    MessageId=msg_id,
                )
                session.add(rr_msg)
                session.flush()

            existing = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji, session)
            if existing is not None:
                error_msg = get_string(lang, "reactionrole.add.already_mapped", emoji=emoji)
            else:
                entry = ReactionRoleEntry(
                    ReactionRoleMessageId=rr_msg.Id,
                    Emoji=emoji,
                    RoleId=role.id,
                )
                session.add(entry)

        if error_msg:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        self.bot.guild_cache.add_reaction_role_message(interaction.guild.id, msg_id)
        self.bot.guild_cache.add_reaction_role_entry(msg_id, emoji, role.id)
        invalidate_autocomplete(("rr_msgs", interaction.guild.id))

        try:
            await discord_msg.add_reaction(emoji)
        except HTTPException as ex:
            self.bot.log.warning(f"{error_context(interaction)}: could not add reaction to message {msg_id}: {ex}")

        await interaction.response.send_message(
            get_string(lang, "reactionrole.add.success", emoji=emoji, role=role.name, message_id=msg_id),
            ephemeral=True,
        )

    @reactionrole.command(name="remove")
    @checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(message_id=_message_id_autocomplete)
    async def _reactionrole_remove(self, interaction: Interaction, message_id: str, emoji: str):
        """Remove an emoji-to-role mapping from a message.

        Parameters
        ----------
        interaction
        message_id: str
            The Discord message ID
        emoji: str
            The emoji mapping to remove
        """
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)
        reply = None
        channel_id = None
        last_entry_removed = False
        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                reply = get_string(lang, "reactionrole.remove.no_config")
            else:
                entry = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji, session)
                if entry is None:
                    reply = get_string(lang, "reactionrole.remove.no_mapping", emoji=emoji)
                else:
                    channel_id = rr_msg.ChannelId
                    session.delete(entry)

                    # clean up the parent if no entries remain
                    if len(rr_msg.entries) == 1:
                        session.delete(rr_msg)
                        last_entry_removed = True

        if reply:
            await interaction.response.send_message(reply, ephemeral=True)
            return

        if last_entry_removed:
            self.bot.guild_cache.remove_reaction_role_message(interaction.guild.id, msg_id)
        else:
            self.bot.guild_cache.remove_reaction_role_entry(msg_id, emoji)
        invalidate_autocomplete(("rr_msgs", interaction.guild.id))

        await self._clear_reaction(interaction.guild, channel_id, msg_id, emoji)
        await interaction.response.send_message(
            get_string(lang, "reactionrole.remove.success", emoji=emoji), ephemeral=True
        )

    @reactionrole.command(name="list")
    @checks.has_permissions(manage_roles=True)
    async def _reactionrole_list(self, interaction: Interaction):
        """List all reaction role configurations for this server."""
        lang = self._lang(interaction.guild_id)
        with self.bot.session_scope() as session:
            messages = ReactionRoleMessage.get_by_guild(interaction.guild.id, session)
            msg = ""
            for rr_msg in messages:
                channel = interaction.guild.get_channel(rr_msg.ChannelId)
                channel_name = channel.mention if channel else f"Unknown ({rr_msg.ChannelId})"
                msg += f"**{channel_name}** \u00b7 `{rr_msg.MessageId}`\n"
                if rr_msg.entries:
                    for entry in rr_msg.entries:
                        role = interaction.guild.get_role(entry.RoleId)
                        role_name = role.name if role else f"Unknown ({entry.RoleId})"
                        msg += f"> {entry.Emoji} \u2192 {role_name}\n"
                else:
                    msg += f"> {get_string(lang, 'reactionrole.list.no_mappings')}\n"
                msg += "\n"

        if not messages:
            await interaction.response.send_message(get_string(lang, "reactionrole.list.empty"), ephemeral=True)
            return

        await send_paginated(
            interaction, msg, title=get_string(lang, "reactionrole.list.title"), color=0x9B59B6, ephemeral=True
        )

    @reactionrole.command(name="clear")
    @checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(message_id=_message_id_autocomplete)
    async def _reactionrole_clear(self, interaction: Interaction, message_id: str):
        """Remove all reaction role mappings from a message.

        Parameters
        ----------
        interaction
        message_id: str
            The Discord message ID to clear all mappings from
        """
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return

        lang = self._lang(interaction.guild_id)
        channel_id = None
        emojis = []
        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                no_config_msg = get_string(lang, "reactionrole.remove.no_config")
            else:
                no_config_msg = None
                channel_id = rr_msg.ChannelId
                emojis = [entry.Emoji for entry in rr_msg.entries]
                ReactionRoleMessage.delete(msg_id, session)

        if no_config_msg:
            await interaction.response.send_message(no_config_msg, ephemeral=True)
            return

        self.bot.guild_cache.remove_reaction_role_message(interaction.guild.id, msg_id)
        invalidate_autocomplete(("rr_msgs", interaction.guild.id))

        await asyncio.gather(
            *[self._clear_reaction(interaction.guild, channel_id, msg_id, emoji) for emoji in emojis],
            return_exceptions=True,
        )

        await interaction.response.send_message(
            get_string(lang, "reactionrole.clear.success", message_id=msg_id), ephemeral=True
        )


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Roles(bot))
