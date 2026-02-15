# -*- coding: utf-8 -*-

from discord import Role, TextChannel, app_commands
from discord.app_commands import checks
from discord.ext.commands import Cog, Context, MissingPermissions, hybrid_group

from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage

from utils.format import box
from utils.helpers import empty_subcommand, error_context, notify_error, send_hidden_message


@app_commands.default_permissions(manage_roles=True)
class ReactionRole(Cog):
    """cog for managing reaction-based role assignment"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        """Enforce manage_roles permission for prefix commands."""
        if ctx.interaction is not None:
            return True
        if ctx.author.guild_permissions.manage_roles:
            return True
        raise MissingPermissions(["manage_roles"])

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
        except Exception as ex:
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
        except Exception as ex:
            self.bot.log.error(
                f"[{guild.name} ({guild.id})] {member} ({member.id}): "
                f"failed to remove role {role.name} ({role.id}): {ex}"
            )
            await notify_error(self.bot, f"[{guild.name} ({guild.id})] Reaction role remove failed", ex)

    def _get_role_for_reaction(self, payload):
        """looks up the role for a given reaction event payload"""
        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(payload.message_id, session)
            if rr_msg is None:
                return None

            emoji_str = str(payload.emoji)
            entry = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji_str, session)
            if entry is None:
                return None

            role_id = entry.RoleId

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return None

        return guild.get_role(role_id)

    async def _clear_reaction(self, guild, channel_id, message_id, emoji):
        """removes all reactions of a specific emoji from a message"""
        channel = guild.get_channel(channel_id)
        if channel is None:
            return
        try:
            discord_msg = await channel.fetch_message(message_id)
            await discord_msg.clear_reaction(emoji)
        except Exception as ex:
            self.bot.log.warning(
                f"[{guild.name} ({guild.id})]: could not clear reaction {emoji} from message {message_id}: {ex}"
            )

    @hybrid_group(name="reactionrole", aliases=["rr"])
    @checks.has_permissions(manage_roles=True)
    async def _reactionrole(self, ctx: Context):
        """manage reaction role assignments [bot-moderator]"""
        await empty_subcommand(ctx)

    @_reactionrole.command(name="add")
    @checks.has_permissions(manage_roles=True)
    async def _add(self, ctx: Context, channel: TextChannel, message_id: str, emoji: str, role: Role):
        """add an emoji-to-role mapping on any message

        Parameters
        ----------
        ctx
        channel: discord.TextChannel
            The channel the message is in
        message_id: str
            The Discord message ID to attach the reaction role to
        emoji: str
            The emoji to react with
        role: discord.Role
            The role to assign when the emoji is used
        """
        msg_id = int(message_id)

        if role >= ctx.guild.me.top_role:
            await send_hidden_message(ctx, f"I cannot assign **{role.name}** — it is at or above my highest role.")
            return

        try:
            discord_msg = await channel.fetch_message(msg_id)
        except Exception:
            await send_hidden_message(ctx, f"Could not find message `{msg_id}` in {channel.mention}.")
            return

        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                rr_msg = ReactionRoleMessage(
                    GuildId=ctx.guild.id,
                    ChannelId=channel.id,
                    MessageId=msg_id,
                )
                session.add(rr_msg)
                session.flush()

            existing = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji, session)
            if existing is not None:
                await send_hidden_message(ctx, f"Emoji {emoji} is already mapped on that message.")
                return

            entry = ReactionRoleEntry(
                ReactionRoleMessageId=rr_msg.Id,
                Emoji=emoji,
                RoleId=role.id,
            )
            session.add(entry)

        try:
            await discord_msg.add_reaction(emoji)
        except Exception as ex:
            self.bot.log.warning(f"{error_context(ctx)}: could not add reaction to message {msg_id}: {ex}")

        await send_hidden_message(ctx, f"Mapped {emoji} to **{role.name}** on message `{msg_id}`.")

    @_reactionrole.command(name="remove")
    @checks.has_permissions(manage_roles=True)
    async def _remove(self, ctx: Context, message_id: str, emoji: str):
        """remove an emoji-to-role mapping from a message

        Parameters
        ----------
        ctx
        message_id: str
            The Discord message ID
        emoji: str
            The emoji mapping to remove
        """
        msg_id = int(message_id)

        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                await send_hidden_message(ctx, "No reaction role config found for that message.")
                return

            entry = ReactionRoleEntry.get_by_message_and_emoji(rr_msg.Id, emoji, session)
            if entry is None:
                await send_hidden_message(ctx, f"No mapping for {emoji} found on that message.")
                return

            channel_id = rr_msg.ChannelId
            session.delete(entry)

            # clean up the parent if no entries remain
            remaining = [e for e in rr_msg.entries if e.Id != entry.Id]
            if not remaining:
                session.delete(rr_msg)

        await self._clear_reaction(ctx.guild, channel_id, msg_id, emoji)
        await send_hidden_message(ctx, f"Removed mapping for {emoji}.")

    @_reactionrole.command(name="list")
    @checks.has_permissions(manage_roles=True)
    async def _list(self, ctx: Context):
        """list all reaction role configurations for this server"""
        with self.bot.session_scope() as session:
            messages = ReactionRoleMessage.get_by_guild(ctx.guild.id, session)
            if not messages:
                await send_hidden_message(ctx, "No reaction roles configured.")
                return

            msg = "==== Reaction Roles ====\n"
            for rr_msg in messages:
                channel = ctx.guild.get_channel(rr_msg.ChannelId)
                channel_name = channel.name if channel else f"Unknown ({rr_msg.ChannelId})"
                msg += f"\n--- #{channel_name} / {rr_msg.MessageId} ---\n"
                if rr_msg.entries:
                    for entry in rr_msg.entries:
                        role = ctx.guild.get_role(entry.RoleId)
                        role_name = role.name if role else f"Unknown ({entry.RoleId})"
                        msg += f"  {entry.Emoji} -> {role_name}\n"
                else:
                    msg += "  (no mappings)\n"

        await send_hidden_message(ctx, box(msg))

    @_reactionrole.command(name="clear")
    @checks.has_permissions(manage_roles=True)
    async def _clear(self, ctx: Context, message_id: str):
        """remove all reaction role mappings from a message

        Parameters
        ----------
        ctx
        message_id: str
            The Discord message ID to clear all mappings from
        """
        msg_id = int(message_id)

        with self.bot.session_scope() as session:
            rr_msg = ReactionRoleMessage.get_by_message(msg_id, session)
            if rr_msg is None:
                await send_hidden_message(ctx, "No reaction role config found for that message.")
                return

            channel_id = rr_msg.ChannelId
            emojis = [entry.Emoji for entry in rr_msg.entries]
            ReactionRoleMessage.delete(msg_id, session)

        for emoji in emojis:
            await self._clear_reaction(ctx.guild, channel_id, msg_id, emoji)

        await send_hidden_message(ctx, f"Cleared all reaction role mappings from message `{msg_id}`.")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(ReactionRole(bot))
