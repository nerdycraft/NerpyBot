import discord
import utils.format as fmt
from typing import Optional
from utils.checks import is_botmod
from utils.errors import NerpyException
from discord.app_commands import checks
from discord.ext.commands import GroupCog, hybrid_command, hybrid_group, check, bot_has_permissions


@check(is_botmod)
class Moderation(GroupCog):
    """cog for bot management"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @hybrid_group(aliases=["u"])
    @checks.has_permissions(moderate_members=True)
    async def user(self, ctx):
        """user moderation [bot-moderator]"""
        if ctx.invoked_subcommand is None:
            args = str(ctx.message.clean_content).split(" ")
            if len(args) > 2:
                raise NerpyException("Command not found!")
            elif len(args) <= 1:
                await ctx.send_help(ctx.command)
            else:
                await ctx.send(args[1])

    @user.command(name="info")
    @checks.has_permissions(moderate_members=True)
    async def _get_user_info(self, ctx, member: Optional[discord.Member]):
        """displays information about given user [bot-moderator]"""

        member = member or ctx.author
        created = member.created_at.strftime("%d. %B %Y - %H:%M")
        joined = member.joined_at.strftime("%d. %B %Y - %H:%M")

        emb = discord.Embed(title=member.display_name)
        emb.description = f"original name: {member.name}"
        emb.set_thumbnail(url=member.avatar.url)
        emb.add_field(name="created", value=created)
        emb.add_field(name="joined", value=joined)
        emb.add_field(name="top role", value=member.top_role.name.replace("@", ""))
        rn = []
        for r in member.roles:
            rn.append(r.name.replace("@", ""))

        emb.add_field(name="roles", value=", ".join(rn), inline=False)

        await ctx.send(embed=emb)

    @user.command(name="list")
    @checks.has_permissions(moderate_members=True)
    async def _list_user_info_from_guild(self, ctx):
        """displays a list of all users on your server [bot-moderator]"""
        msg = ""
        for member in ctx.guild.members:
            created = member.created_at.strftime("%d. %b %Y - %H:%M")
            joined = member.joined_at.strftime("%d. %b %Y - %H:%M")
            msg += f"{member.display_name}: [created: {created} | joined: {joined}]\n"

        for page in fmt.pagify(msg, delims=["\n#"], page_length=1990):
            await ctx.send(fmt.box(page))

    @hybrid_command()
    async def history(self, ctx):
        """displays the last 10 received commands since last restart [bot-moderator]"""
        if ctx.guild.id in ctx.bot.last_cmd_cache:
            msg = ""
            for m in ctx.bot.last_cmd_cache[ctx.guild.id]:
                if m.content != "":
                    msg += f"{m.author} - {m.content}\n"

            if msg != "":
                await ctx.send(fmt.box(msg))
                return
        await ctx.send("No recent commands to display.")

    @hybrid_command()
    async def membercount(self, ctx):
        """displays the current membercount of the server [bot-moderator]"""
        await ctx.send(fmt.inline(f"There are currently {ctx.guild.member_count} members on this discord"))


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Moderation(bot))
