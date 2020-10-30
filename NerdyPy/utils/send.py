"""bli bla blo"""
from models.default_channel import DefaultChannel
from utils.database import session_scope


async def send(ctx, msg):
    with session_scope() as session:
        _ch = DefaultChannel.get(ctx.guild.id, session)
        if _ch is None:
            await ctx.send(msg)
        else:
            chan = ctx.guild.get_channel(_ch.ChannelId)
            if chan is None:
                await ctx.send(msg)
            else:
                await chan.send(msg)


async def send_embed(ctx, msg):
    with session_scope() as session:
        _ch = DefaultChannel.get(ctx.guild.id, session)
        if _ch is None:
            await ctx.send(embed=msg)
        else:
            chan = ctx.guild.get_channel(_ch.ChannelId)
            if chan is None:
                await ctx.send(embed=msg)
            else:
                await chan.send(embed=msg)
