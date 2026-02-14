# -*- coding: utf-8 -*-

from discord import Member, Role
from discord.app_commands import checks
from discord.ext.commands import Cog, Context, hybrid_group

from models.rolemanage import RoleMapping
from utils.format import box
from utils.helpers import empty_subcommand, error_context, send_hidden_message


class RoleManage(Cog):
    """cog for delegated role management — lets specific roles assign other roles"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

    def _has_source_role(self, member, mappings):
        """check if the member holds any source role from the given mappings"""
        member_role_ids = {r.id for r in member.roles}
        return any(m.SourceRoleId in member_role_ids for m in mappings)

    @hybrid_group(name="rolemanage", aliases=["rm"])
    async def _rolemanage(self, ctx: Context):
        """manage delegated role assignments"""
        await empty_subcommand(ctx)

    @_rolemanage.command(name="allow")
    @checks.has_permissions(manage_roles=True)
    async def _allow(self, ctx: Context, source_role: Role, target_role: Role):
        """allow a source role to assign a target role [manage_roles]

        Parameters
        ----------
        ctx
        source_role: discord.Role
            The role whose members can assign the target role
        target_role: discord.Role
            The role that can be assigned
        """
        if target_role.managed:
            await send_hidden_message(
                ctx, f"**{target_role.name}** is an integration role and cannot be assigned to members."
            )
            return

        if target_role >= ctx.guild.me.top_role:
            await send_hidden_message(
                ctx, f"I cannot manage **{target_role.name}** — it is at or above my highest role."
            )
            return

        with self.bot.session_scope() as session:
            existing = RoleMapping.get(ctx.guild.id, source_role.id, target_role.id, session)
            if existing:
                await send_hidden_message(ctx, f"**{source_role.name}** can already assign **{target_role.name}**.")
                return

            mapping = RoleMapping(
                GuildId=ctx.guild.id,
                SourceRoleId=source_role.id,
                TargetRoleId=target_role.id,
            )
            session.add(mapping)

        await send_hidden_message(ctx, f"**{source_role.name}** can now assign **{target_role.name}**.")

    @_rolemanage.command(name="deny")
    @checks.has_permissions(manage_roles=True)
    async def _deny(self, ctx: Context, source_role: Role, target_role: Role):
        """remove a source-to-target role mapping [manage_roles]

        Parameters
        ----------
        ctx
        source_role: discord.Role
            The source role
        target_role: discord.Role
            The target role
        """
        with self.bot.session_scope() as session:
            deleted = RoleMapping.delete(ctx.guild.id, source_role.id, target_role.id, session)

        if deleted:
            await send_hidden_message(ctx, f"**{source_role.name}** can no longer assign **{target_role.name}**.")
        else:
            await send_hidden_message(ctx, "No matching mapping found.")

    @_rolemanage.command(name="list")
    @checks.has_permissions(manage_roles=True)
    async def _list(self, ctx: Context):
        """list all delegated role mappings for this server [manage_roles]"""
        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_guild(ctx.guild.id, session)
            if not mappings:
                await send_hidden_message(ctx, "No role mappings configured.")
                return

            lines = ["==== Delegated Role Mappings ====\n"]
            for m in mappings:
                source = ctx.guild.get_role(m.SourceRoleId)
                target = ctx.guild.get_role(m.TargetRoleId)
                source_name = source.name if source else f"Unknown ({m.SourceRoleId})"
                target_name = target.name if target else f"Unknown ({m.TargetRoleId})"
                lines.append(f"  {source_name} -> {target_name}")

        await send_hidden_message(ctx, box("\n".join(lines)))

    @_rolemanage.command(name="assign")
    async def _assign(self, ctx: Context, member: Member, role: Role):
        """assign a role to a member (requires a delegated mapping)

        Parameters
        ----------
        ctx
        member: discord.Member
            The member to assign the role to
        role: discord.Role
            The role to assign
        """
        if role.managed:
            await send_hidden_message(ctx, f"**{role.name}** is an integration role and cannot be assigned to members.")
            return

        if role >= ctx.guild.me.top_role:
            await send_hidden_message(ctx, f"I cannot manage **{role.name}** — it is at or above my highest role.")
            return

        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(ctx.guild.id, role.id, session)

        if not mappings or not self._has_source_role(ctx.author, mappings):
            await send_hidden_message(ctx, "You do not have permission to assign that role.")
            return

        if role in member.roles:
            await send_hidden_message(ctx, f"**{member.display_name}** already has **{role.name}**.")
            return

        try:
            await member.add_roles(role, reason=f"Delegated role assign by {ctx.author}")
        except Exception as ex:
            self.bot.log.error(f"{error_context(ctx)}: failed to assign role {role.name} to {member}: {ex}")
            await send_hidden_message(ctx, f"Failed to assign role: {ex}")
            return

        await send_hidden_message(ctx, f"Assigned **{role.name}** to **{member.display_name}**.")

    @_rolemanage.command(name="remove")
    async def _remove(self, ctx: Context, member: Member, role: Role):
        """remove a role from a member (requires a delegated mapping)

        Parameters
        ----------
        ctx
        member: discord.Member
            The member to remove the role from
        role: discord.Role
            The role to remove
        """
        if role.managed:
            await send_hidden_message(
                ctx, f"**{role.name}** is an integration role and cannot be removed from members."
            )
            return

        if role >= ctx.guild.me.top_role:
            await send_hidden_message(ctx, f"I cannot manage **{role.name}** — it is at or above my highest role.")
            return

        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(ctx.guild.id, role.id, session)

        if not mappings or not self._has_source_role(ctx.author, mappings):
            await send_hidden_message(ctx, "You do not have permission to remove that role.")
            return

        if role not in member.roles:
            await send_hidden_message(ctx, f"**{member.display_name}** does not have **{role.name}**.")
            return

        try:
            await member.remove_roles(role, reason=f"Delegated role remove by {ctx.author}")
        except Exception as ex:
            self.bot.log.error(f"{error_context(ctx)}: failed to remove role {role.name} from {member}: {ex}")
            await send_hidden_message(ctx, f"Failed to remove role: {ex}")
            return

        await send_hidden_message(ctx, f"Removed **{role.name}** from **{member.display_name}**.")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(RoleManage(bot))
