# -*- coding: utf-8 -*-

import logging
import re
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from typing import Literal, Optional

from discord import Embed, Forbidden, HTTPException, Interaction, Object, Role, app_commands
from discord.app_commands import CommandSyncFailure, MissingApplicationID, TranslationError
from discord.ext.commands import Cog, Context, Greedy, command, hybrid_command
from models.admin import BotModeratorRole, PermissionSubscriber
from utils.checks import is_admin_or_operator, require_operator
from utils.cog import NerpyBotCog
from utils.errors import NerpyInfraException, NerpyPermissionError
from utils.permissions import build_permissions_embed, check_guild_permissions, required_permissions_for

PROTECTED_MODULES = frozenset({"admin", "voicecontrol"})

_DURATION_MULTIPLIERS = {"m": 60, "h": 3600, "d": 86400}


def _parse_duration(text: str) -> int | None:
    """Parse a human duration string like '30m', '2h', '1d' into seconds."""
    match = re.fullmatch(r"(\d+)\s*([mhd])", text.strip().lower())
    if not match:
        return None
    return int(match.group(1)) * _DURATION_MULTIPLIERS[match.group(2)]


def _format_remaining(seconds: float) -> str:
    """Format seconds into a human-readable string like '1h 23m'."""
    total = int(seconds)
    if total >= 86400:
        days = total // 86400
        hours = (total % 86400) // 3600
        return f"{days}d {hours}h" if hours else f"{days}d"
    if total >= 3600:
        hours = total // 3600
        minutes = (total % 3600) // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    minutes = total // 60
    return f"{minutes}m" if minutes else f"{total}s"


@app_commands.default_permissions(administrator=True)
class Admin(NerpyBotCog, Cog):
    """cog for administrative usage"""

    modrole = app_commands.Group(
        name="modrole", description="Manage the bot-moderator role for this server", guild_only=True
    )
    botpermissions = app_commands.Group(name="botpermissions", description="Check bot permissions", guild_only=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Allow administrators and bot operators to use all admin slash commands."""
        if interaction.command and interaction.command.name == "ping":
            return True
        if await is_admin_or_operator(interaction):
            return True
        raise app_commands.CheckFailure("This command requires administrator permissions or bot operator status.")

    async def cog_check(self, ctx: Context) -> bool:
        """Allow operators to use DM prefix commands (sync, debug, uptime)."""
        if ctx.command and ctx.command.name == "ping":
            return True
        if ctx.author.id in self.bot.ops:
            return True
        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        raise NerpyPermissionError("This command requires administrator permissions or bot operator status.")

    @modrole.command(name="get")
    async def _modrole_get(self, interaction: Interaction):
        """Show the currently configured bot-moderator role."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is not None:
                role = interaction.guild.get_role(entry.RoleId)
                if role is not None:
                    await interaction.response.send_message(f"Bot-moderator role: **{role.name}**", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "A bot-moderator role is configured but the role no longer exists."
                        " Use `/admin modrole delete` to clear it.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    "No bot-moderator role configured. Falling back to permission-based checks.", ephemeral=True
                )

    @modrole.command(name="set")
    async def _modrole_set(self, interaction: Interaction, role: Role):
        """Set the bot-moderator role for this server."""
        with self.bot.session_scope() as session:
            entry = BotModeratorRole.get(interaction.guild.id, session)
            if entry is None:
                entry = BotModeratorRole(GuildId=interaction.guild.id)
                session.add(entry)
            entry.RoleId = role.id
        await interaction.response.send_message(f"Bot-moderator role set to **{role.name}**.", ephemeral=True)

    @modrole.command(name="delete")
    async def _modrole_del(self, interaction: Interaction):
        """Remove the bot-moderator role configuration."""
        with self.bot.session_scope() as session:
            BotModeratorRole.delete(interaction.guild.id, session)
        await interaction.response.send_message("Bot-moderator role removed.", ephemeral=True)

    @botpermissions.command(name="check")
    async def _botpermissions_check(self, interaction: Interaction) -> None:
        """Check if the bot has all required permissions in this server."""
        required = required_permissions_for(self.bot.modules)
        missing = check_guild_permissions(interaction.guild, required)
        emb = build_permissions_embed(interaction.guild, missing, self.bot.client_id, required)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @botpermissions.command(name="subscribe")
    async def _botpermissions_subscribe(self, interaction: Interaction) -> None:
        """Get DM notifications about missing permissions on bot restart."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(interaction.guild.id, interaction.user.id, session)
            if existing is not None:
                await interaction.response.send_message(
                    "You are already subscribed to permission notifications.", ephemeral=True
                )
                return
            session.add(PermissionSubscriber(GuildId=interaction.guild.id, UserId=interaction.user.id))
        await interaction.response.send_message(
            "Subscribed. You will receive a DM when the bot restarts with missing permissions in this server.",
            ephemeral=True,
        )

    @botpermissions.command(name="unsubscribe")
    async def _botpermissions_unsubscribe(self, interaction: Interaction) -> None:
        """Stop receiving DM notifications about missing permissions."""
        with self.bot.session_scope() as session:
            existing = PermissionSubscriber.get(interaction.guild.id, interaction.user.id, session)
            if existing is None:
                await interaction.response.send_message(
                    "You are not subscribed to permission notifications.", ephemeral=True
                )
                return
            PermissionSubscriber.delete(interaction.guild.id, interaction.user.id, session)
        await interaction.response.send_message(
            "Unsubscribed from permission notifications for this server.", ephemeral=True
        )

    @hybrid_command(name="ping")
    async def ping(self, ctx: Context):
        """Pong."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"\U0001f3d3 Pong! **{latency}ms**")

    @command(name="help")
    async def _help(self, ctx: Context, *, name: str = None) -> None:
        """Show available operator commands, or details for a specific one. [operator]"""
        require_operator(ctx)

        if name is not None:
            cmd = self.bot.get_command(name.lower())
            if cmd is None or not cmd.help or "[operator]" not in cmd.help:
                await ctx.send(f"Unknown operator command `{name}`. Use `!help` to list all.")
                return
            detail = cmd.help.replace("[operator]", "").strip()
            await ctx.send(f"**`!{cmd.qualified_name}`**\n{detail}")
            return

        lines = ["\U0001f4cb **Operator Commands**\n"]
        for cmd in sorted(self.bot.commands, key=lambda c: c.qualified_name):
            if cmd.help and "[operator]" in cmd.help:
                desc = cmd.short_doc.replace("[operator]", "").strip().rstrip(".")
                lines.append(f"`!{cmd.qualified_name}` — {desc}")
        lines.append("\nUse `!help <command>` for details.")

        await ctx.send("\n".join(lines))

    @command(name="sync")
    async def sync(
        self, ctx: Context, guilds: Greedy[Object], spec: Optional[Literal["local", "copy", "clear"]] = None
    ) -> None:
        """Sync commands globally or to a specific guild. [operator]

        Usage:
          `!sync`                — Sync globally
          `!sync <guild_id> ...` — Sync to specific guild(s)
          `!sync local`          — Sync current guild's commands
          `!sync copy`           — Copy global commands to current guild
          `!sync clear`          — Clear commands from current guild"""
        if not guilds:
            if spec in ("local", "copy", "clear") and ctx.guild is None:
                await ctx.send(f"The `{spec}` option requires a server context.")
                return
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
                raise NerpyInfraException("Could not sync commands to Discord API.")
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @command(name="uptime")
    async def _uptime(self, ctx: Context) -> None:
        """Shows bot uptime and version. [operator]"""
        require_operator(ctx)

        td = datetime.now(UTC) - self.bot.uptime
        bot_version = pkg_version("NerpyBot")
        hours = td.seconds // 3600
        minutes = (td.seconds // 60) % 60

        emb = Embed(
            description=f"**{td.days}**d · **{hours}**h · **{minutes}**m",
            color=0x5865F2,
        )
        emb.set_author(name=f"NerpyBot v{bot_version}")
        await ctx.send(embed=emb)

    @command(name="debug")
    async def _debug(self, ctx: Context) -> None:
        """Toggle debug logging at runtime. [operator]"""
        require_operator(ctx)

        logger = logging.getLogger("nerpybot")
        if logger.level == logging.DEBUG:
            logger.setLevel(logging.INFO)
            self.bot.debug = False
            await ctx.send("Debug logging **disabled** (level: INFO).")
        else:
            logger.setLevel(logging.DEBUG)
            self.bot.debug = True
            await ctx.send("Debug logging **enabled** (level: DEBUG).")

        self.bot.log.info(f"debug logging toggled to {self.bot.debug} by {ctx.author}")

    @command(name="errors")
    async def _errors(self, ctx: Context, action: str = "status", *, arg: str = None) -> None:
        """Manage error notifications. [operator]

        Subcommands:
          `status`         — Show current throttle & suppression state (default)
          `suppress <dur>` — Suppress all error DMs (e.g. `30m`, `2h`, `1d`)
          `resume`         — Cancel suppression and resume notifications"""
        require_operator(ctx)

        action = action.lower()

        if action == "status":
            status = self.bot.error_throttle.get_status()

            if status["is_suppressed"]:
                remaining = _format_remaining(status["suppressed_remaining"])
                header = f"🔇 Error notifications suppressed for {remaining} remaining"
            else:
                header = "🔔 Error notifications active"

            window_m = status["throttle_window"] // 60
            lines = [header, f"📊 Throttle ({window_m}m window):"]

            if not status["buckets"]:
                lines.append("  No errors tracked yet.")
            else:
                for key, info in status["buckets"].items():
                    ago = _format_remaining(info["last_notified_ago"])
                    entry = f"  • {key} — last {ago} ago"
                    if info["suppressed_count"]:
                        entry += f" ({info['suppressed_count']} suppressed)"
                    lines.append(entry)

            await ctx.send("\n".join(lines))

        elif action == "suppress":
            if not arg:
                await ctx.send("Usage: `!errors suppress <duration>` (e.g. 30m, 2h, 1d)")
                return
            seconds = _parse_duration(arg)
            if seconds is None:
                await ctx.send("Invalid duration. Use `<number><m|h|d>`, e.g. `30m`, `2h`, `1d`.")
                return
            self.bot.error_throttle.suppress(seconds)
            await ctx.send(f"🔇 Error notifications suppressed for {_format_remaining(seconds)}.")

        elif action == "resume":
            if not self.bot.error_throttle.is_suppressed:
                await ctx.send("🔔 Error notifications are already active (nothing to resume).")
                return
            self.bot.error_throttle.resume()
            await ctx.send("🔔 Error notifications resumed.")

        else:
            await ctx.send(f"Unknown action `{action}`. Use `!help errors` for usage.")

    @command(name="disable")
    async def _disable(self, ctx: Context, *, module: str) -> None:
        """Disable a module at runtime. [operator]

        Disables all slash commands in a module. Users will see an ephemeral
        "disabled for maintenance" message. Protected: `admin`, `voicecontrol`.

        Usage: `!disable <module>` (e.g. `!disable wow`)"""
        require_operator(ctx)

        module = module.lower()
        if f"modules.{module}" not in self.bot.extensions:
            await ctx.send(f"Unknown or not loaded module `{module}`.")
            return
        if module in PROTECTED_MODULES:
            await ctx.send(f"Cannot disable `{module}` — it is a protected module.")
            return
        if module in self.bot.disabled_modules:
            await ctx.send(f"`{module}` is already disabled.")
            return

        self.bot.disabled_modules.add(module)
        self.bot.log.warning(f"Module {module} disabled by {ctx.author}")
        await ctx.send(
            f"\U0001f512 Module **{module}** disabled. All its commands will respond with a maintenance message."
        )

    @command(name="enable")
    async def _enable(self, ctx: Context, *, module: str = None) -> None:
        """Re-enable a disabled module, or all if none specified. [operator]

        Usage:
          `!enable <module>` — Re-enable a specific module
          `!enable`          — Re-enable all disabled modules at once"""
        require_operator(ctx)

        if module is None:
            if not self.bot.disabled_modules:
                await ctx.send("No modules are currently disabled.")
                return
            names = ", ".join(f"`{m}`" for m in sorted(self.bot.disabled_modules))
            self.bot.disabled_modules.clear()
            self.bot.log.warning(f"All modules re-enabled by {ctx.author}")
            await ctx.send(f"\U0001f513 All modules re-enabled: {names}")
            return

        module = module.lower()
        if module not in self.bot.disabled_modules:
            await ctx.send(f"`{module}` is not disabled.")
            return

        self.bot.disabled_modules.discard(module)
        self.bot.log.warning(f"Module {module} re-enabled by {ctx.author}")
        await ctx.send(f"\U0001f513 Module **{module}** re-enabled.")

    @command(name="disabled")
    async def _disabled(self, ctx: Context) -> None:
        """List currently disabled modules. [operator]"""
        require_operator(ctx)

        if not self.bot.disabled_modules:
            await ctx.send("\u2705 All modules are enabled.")
            return

        names = ", ".join(f"`{m}`" for m in sorted(self.bot.disabled_modules))
        await ctx.send(f"\U0001f512 Disabled modules: {names}")


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Admin(bot))
