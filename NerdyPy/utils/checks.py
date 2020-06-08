import config


async def is_operator(ctx):
    return config.ops.count(ctx.author.id) > 0


async def is_botmod(ctx):
    if await is_operator(ctx):
        return True
    if ctx.author.roles is not None:
        for role in ctx.author.roles:
            if role.name == config.moderator_role_name:
                return True
    return False
