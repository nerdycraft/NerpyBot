# -*- coding: utf-8 -*-

from discord import Interaction, Member, Role, app_commands
from discord.app_commands import checks
from discord.ext.commands import GroupCog

from models.rolemanage import RoleMapping
from utils.checks import is_role_assignable, is_role_below_bot
from utils.helpers import error_context, send_paginated


@app_commands.guild_only()
class RoleManage(GroupCog, group_name="rolemanage"):
    """cog for delegated role management — lets specific roles assign other roles"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot

    def _has_source_role(self, member, mappings):
        """check if the member holds any source role from the given mappings"""
        member_role_ids = {r.id for r in member.roles}
        return any(m.SourceRoleId in member_role_ids for m in mappings)

    @app_commands.command(name="allow")
    @checks.has_permissions(manage_roles=True)
    async def _allow(self, interaction: Interaction, source_role: Role, target_role: Role):
        """allow a source role to assign a target role [manage_roles]

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

        with self.bot.session_scope() as session:
            existing = RoleMapping.get(interaction.guild.id, source_role.id, target_role.id, session)
            if existing:
                await interaction.response.send_message(
                    f"**{source_role.name}** can already assign **{target_role.name}**.", ephemeral=True
                )
                return

            mapping = RoleMapping(
                GuildId=interaction.guild.id,
                SourceRoleId=source_role.id,
                TargetRoleId=target_role.id,
            )
            session.add(mapping)

        await interaction.response.send_message(
            f"**{source_role.name}** can now assign **{target_role.name}**.", ephemeral=True
        )

    @app_commands.command(name="deny")
    @checks.has_permissions(manage_roles=True)
    async def _deny(self, interaction: Interaction, source_role: Role, target_role: Role):
        """remove a source-to-target role mapping [manage_roles]

        Parameters
        ----------
        interaction
        source_role: discord.Role
            The source role
        target_role: discord.Role
            The target role
        """
        with self.bot.session_scope() as session:
            deleted = RoleMapping.delete(interaction.guild.id, source_role.id, target_role.id, session)

        if deleted:
            await interaction.response.send_message(
                f"**{source_role.name}** can no longer assign **{target_role.name}**.", ephemeral=True
            )
        else:
            await interaction.response.send_message("No matching mapping found.", ephemeral=True)

    @app_commands.command(name="list")
    @checks.has_permissions(manage_roles=True)
    async def _list(self, interaction: Interaction):
        """list all delegated role mappings for this server [manage_roles]"""
        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_guild(interaction.guild.id, session)
            if not mappings:
                await interaction.response.send_message("No role mappings configured.", ephemeral=True)
                return

            msg = ""
            for m in mappings:
                source = interaction.guild.get_role(m.SourceRoleId)
                target = interaction.guild.get_role(m.TargetRoleId)
                source_name = source.name if source else f"Unknown ({m.SourceRoleId})"
                target_name = target.name if target else f"Unknown ({m.TargetRoleId})"
                msg += f"> **{source_name}** \u2192 {target_name}\n"

        await send_paginated(
            interaction, msg, title="\U0001f517 Delegated Role Mappings", color=0x3498DB, ephemeral=True
        )

    @app_commands.command(name="assign")
    async def _assign(self, interaction: Interaction, member: Member, role: Role):
        """assign a role to a member (requires a delegated mapping)

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

        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(interaction.guild.id, role.id, session)

        if not mappings or not self._has_source_role(interaction.user, mappings):
            await interaction.response.send_message("You do not have permission to assign that role.", ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message(
                f"**{member.display_name}** already has **{role.name}**.", ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason=f"Delegated role assign by {interaction.user}")
        except Exception as ex:
            self.bot.log.error(f"{error_context(interaction)}: failed to assign role {role.name} to {member}: {ex}")
            await interaction.response.send_message(f"Failed to assign role: {ex}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Assigned **{role.name}** to **{member.display_name}**.", ephemeral=True
        )

    @app_commands.command(name="remove")
    async def _remove(self, interaction: Interaction, member: Member, role: Role):
        """remove a role from a member (requires a delegated mapping)

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

        with self.bot.session_scope() as session:
            mappings = RoleMapping.get_by_target(interaction.guild.id, role.id, session)

        if not mappings or not self._has_source_role(interaction.user, mappings):
            await interaction.response.send_message("You do not have permission to remove that role.", ephemeral=True)
            return

        if role not in member.roles:
            await interaction.response.send_message(
                f"**{member.display_name}** does not have **{role.name}**.", ephemeral=True
            )
            return

        try:
            await member.remove_roles(role, reason=f"Delegated role remove by {interaction.user}")
        except Exception as ex:
            self.bot.log.error(f"{error_context(interaction)}: failed to remove role {role.name} from {member}: {ex}")
            await interaction.response.send_message(f"Failed to remove role: {ex}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Removed **{role.name}** from **{member.display_name}**.", ephemeral=True
        )


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(RoleManage(bot))
