"""bli bla blo"""
from models.default_channel import DefaultChannel
from utils.database import session_scope


async def send(ctx, msg, emb=None):
    with session_scope() as session:
        _ch = DefaultChannel.get(ctx.guild.id, session)
        if _ch is None:
            await ctx.send(msg, embed=emb)
        else:
            chan = ctx.guild.get_channel(_ch.ChannelId)
            if chan is None:
                await ctx.send(msg, embed=emb)
            else:
                await chan.send(msg, embed=emb)
