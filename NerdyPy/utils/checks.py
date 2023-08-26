# -*- coding: utf-8 -*-


async def is_connected_to_voice(ctx):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.author.send("I don't know where you are. Please connect to a voice channel.")
        return False
    if not ctx.author.voice.channel.permissions_for(ctx.guild.me).connect:
        await ctx.author.send("I'm not allowed to join you in your current channel.")
        return False
    return True
