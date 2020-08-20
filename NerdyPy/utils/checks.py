import json


async def is_operator(ctx):
    return json.loads(ctx.bot.ops).count(ctx.author.id) > 0


async def is_botmod(ctx):
    if await is_operator(ctx):
        return True
    if ctx.author.roles is not None:
        for role in ctx.author.roles:
            if role.name == ctx.bot.moderator_role:
                return True
    return False
