import json


async def is_operator(ctx):
    return json.loads(ctx.bot.ops).count(ctx.author.id) > 0


async def is_botmod(ctx):
    if await is_operator(ctx):
        return True
    if ctx.author.guild_permissions.administrator:
        return True
    if ctx.author.roles is not None:
        for role in ctx.author.roles:
            if role.name == ctx.bot.moderator_role:
                return True
    return False


async def is_connected_to_voice(ctx):
    if ctx.author.voice is None:
        await ctx.author.send("I don't know where you are. Please connect to a voice channel.")
        return False
    if not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
        await ctx.author.send("I'm not allowed to join you in your current channel.")
        return False
    return True