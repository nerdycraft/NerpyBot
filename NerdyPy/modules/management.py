from datetime import datetime

import discord
import utils.format as fmt
from models.default_channel import DefaultChannel

from utils.checks import is_botmod
from discord.ext.commands import Cog, command, group, check

from utils.database import session_scope
from utils.send import send


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

        await send(ctx, "", emb)

    @user.command()
    async def list(self, ctx):
        """displays a list of all users on your server"""
        msg = ""
        for member in self.bot.guild.members:
            msg += f"{member.display_name} - created at {member.created_at} - joined at {member.joined_at}\n"

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            await send(fmt.box(page, "md"))

    @command(pass_context=True)
    @check(is_botmod)
    async def history(self, ctx):
        """displays the last 10 received commands since last restart"""
        if ctx.guild.id in ctx.bot.last_cmd_cache:
            msg = ""
            for m in ctx.bot.last_cmd_cache[ctx.guild.id]:
                msg += f"{m.author} - {m.content}\n"

            await send(fmt.box(msg, "md"))

    @command(pass_context=True, aliases=["defch"])
    @check(is_botmod)
    async def defaultchannel(self, ctx, chan: discord.TextChannel):
        """Sets the default response channel for the bot"""
        with session_scope() as session:
            def_ch = DefaultChannel.get(ctx.guild.id, session)
            if def_ch is None:
                def_ch = DefaultChannel(GuildId=ctx.guild.id, CreateDate=datetime.utcnow(), Author=ctx.author.name)
                session.add(def_ch)

            def_ch.ModifiedDate = datetime.utcnow()
            def_ch.ChannelId = chan.id
            session.flush()


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(Management(bot))
