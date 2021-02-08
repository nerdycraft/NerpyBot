import discord
import utils.format as fmt
from datetime import datetime
from models.guild_prefix import GuildPrefix
from utils.checks import is_botmod
from utils.errors import NerpyException
from utils.database import session_scope
from models.default_channel import DefaultChannel
from discord.ext.commands import Cog, command, group, check


class Management(Cog):
    """cog for bot management"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @group(invoke_without_command=False, aliases=["u"])
    @check(is_botmod)
    async def user(self, ctx):
        """user management"""

    @user.command()
    async def info(self, ctx, user: discord.Member):
        """displays information about given user [bot-moderator]"""
        created = user.created_at.strftime("%d. %B %Y - %H:%M")
        joined = user.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = discord.Embed(title=user.display_name)
        emb.description = f"original name: {user.name}"
        emb.set_thumbnail(url=user.avatar_url)
        emb.add_field(name="created", value=created)
        emb.add_field(name="joined", value=joined)
        emb.add_field(name="top role", value=user.top_role.name.replace("@", ""))
        rn = []
        for r in user.roles:
            rn.append(r.name.replace("@", ""))

        emb.add_field(name="roles", value=", ".join(rn), inline=False)

        await self.bot.sendc(ctx, "", emb=emb)

    @user.command()
    async def list(self, ctx):
        """displays a list of all users on your server"""
        msg = ""
        for member in self.bot.guild.members:
            msg += f"{member.display_name} - created at {member.created_at} - joined at {member.joined_at}\n"

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            await self.bot.sendc(ctx, fmt.box(page, "md"))

    @command()
    @check(is_botmod)
    async def history(self, ctx):
        """displays the last 10 received commands since last restart"""
        if ctx.guild.id in ctx.bot.last_cmd_cache:
            msg = ""
            for m in ctx.bot.last_cmd_cache[ctx.guild.id]:
                msg += f"{m.author} - {m.content}\n"

            await self.bot.sendc(ctx, fmt.box(msg, "md"))

    @group(aliases=["defaultchannel"], invoke_without_command=True)
    @check(is_botmod)
    async def defch(self, ctx):
        """Sets the default response channel for the bot"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @defch.command(name="get")
    async def _defch_get(self, ctx):
        with session_scope() as session:
            def_ch = DefaultChannel.get(ctx.guild.id, session)
            if def_ch is not None:
                channel = self.bot.get_channel(def_ch.ChannelId).mention
                await ctx.send(f"Current default response channel set to: {channel}")
            else:
                await ctx.send("There is currently no default response channel set.")

    @defch.command(name="set")
    async def _defch_set(self, ctx, chan: discord.TextChannel):
        if not chan.permissions_for(chan.guild.me).send_messages:
            raise NerpyException("Missing permission to send message to channel.")

        with session_scope() as session:
            def_ch = DefaultChannel.get(ctx.guild.id, session)
            if def_ch is None:
                def_ch = DefaultChannel(GuildId=ctx.guild.id, CreateDate=datetime.utcnow(), Author=ctx.author.name)
                session.add(def_ch)

            def_ch.ModifiedDate = datetime.utcnow()
            def_ch.ChannelId = chan.id
            session.flush()

        await ctx.send(f"Default response channel set to {chan.mention}.")

    @defch.command(name="remove")
    async def _defch_remove(self, ctx):
        with session_scope() as session:
            def_ch = DefaultChannel.get(ctx.guild.id, session)
            if def_ch is not None:
                session.delete(def_ch)

            session.flush()
        await ctx.send("Default response channel removed.")

    @command()
    @check(is_botmod)
    async def membercount(self, ctx):
        """displays the current membercount of the server [bot-moderator]"""
        await self.bot.sendc(ctx, fmt.inline(f"There are currently {ctx.guild.member_count} members on this discord"))

    @group(invoke_without_command=True)
    @check(is_botmod)
    async def prefix(self, ctx):
        """Sets the prefix for the bot"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command(name="set")
    async def _prefix_set(self, ctx, *, new_pref):
        if " " in new_pref:
            raise NerpyException("Spaces not allowed in prefixes")

        with session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is None:
                pref = GuildPrefix(GuildId=ctx.guild.id, CreateDate=datetime.utcnow(), Author=ctx.author.name)
                session.add(pref)

            pref.ModifiedDate = datetime.utcnow()
            pref.Prefix = new_pref
            session.flush()

        await ctx.send(f"new prefix is now set to '{new_pref}'.")

    @prefix.command(name="delete", aliases=["remove", "rm", "del"])
    async def _prefix_del(self, ctx):
        with session_scope() as session:
            pref = GuildPrefix.get(ctx.guild.id, session)
            if pref is not None:
                session.delete(pref)

            session.flush()
        await ctx.send("Prefix removed.")

    @check(is_botmod)
    async def stop(self, ctx):
        """stop sound playing [bot-moderator]"""
        self.bot.audio.stop(ctx.guild.id)

    @command()
    @check(is_botmod)
    async def leave(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Management(bot))
