# -*- coding: utf-8 -*-

import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext.commands import Cog, hybrid_command, bot_has_permissions

import utils.format as fmt
from utils.errors import NerpyException


@bot_has_permissions(send_messages=True)
class Utility(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.weather_api_key = self.bot.config.get("utility", "openweather")

    @hybrid_command()
    @bot_has_permissions(send_messages=True)
    async def ping(self, ctx):
        """Pong."""
        await ctx.send("Pong.")

    @hybrid_command(hidden=True)
    async def uptime(self, ctx):
        """shows bot uptime"""
        td = datetime.datetime.utcnow() - self.bot.uptime
        await ctx.send(
            fmt.inline(f"Uptime: {td.days} Days, {td.seconds // 3600} Hours and {(td.seconds // 60) % 60} Minutes"),
        )

    @hybrid_command()
    @app_commands.rename(query="city")
    @bot_has_permissions(embed_links=True)
    async def weather(self, ctx, *, query: str):
        """outputs weather information"""
        location_url = f"http://api.openweathermap.org/geo/1.0/direct?q={query}&appid={self.weather_api_key}"

        for umlaut in ["ä", "ö", "ü"]:
            if umlaut in query:
                ctx.send("Please use english names only!")
                return

        async with aiohttp.ClientSession() as session:
            async with session.get(location_url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                location = await response.json()

        if location is None:
            return

        lat = location[0].get("lat")
        lon = location[0].get("lon")
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={self.weather_api_key}&units=metric"

        async with aiohttp.ClientSession() as session:
            async with session.get(weather_url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                weather = await response.json()

        conditions = []
        for w in weather.get("weather", dict()):
            conditions.append(w.get("main"))

        sunrise = datetime.datetime.fromtimestamp(int(weather.get("sys", dict()).get("sunrise"))).strftime("%H:%M")
        sunset = datetime.datetime.fromtimestamp(int(weather.get("sys", dict()).get("sunset"))).strftime("%H:%M")

        emb = discord.Embed()
        emb.add_field(
            name=f':earth_africa: {fmt.bold("location")}',
            value=f"""[{weather.get("name")},
                            {weather.get("sys", dict()).get("country")}](https://openweathermap.org/city/{weather.get("id")})""",
        )
        emb.add_field(
            name=f':thermometer: {fmt.bold("temperature")}',
            value=f"{weather['main']['temp']}°C",
        )
        emb.add_field(
            name=f':cloud: {fmt.bold("condition")}',
            value=str.join(", ", conditions),
        )
        emb.add_field(
            name=f':sweat_drops: {fmt.bold("humidity")}',
            value=f"{weather['main']['humidity']}%",
        )
        emb.add_field(
            name=f':wind_chime: {fmt.bold("wind")}',
            value=f"{weather['wind']['speed']} m/s",
        )
        emb.add_field(
            name=f'🔆 {fmt.bold("min-max")}',
            value=f"{weather['main']['temp_min']}°C - {weather['main']['temp_max']}°C",
        )
        emb.add_field(name=f':city_sunrise: {fmt.bold("sunrise")}', value=f"{sunrise} UTC")
        emb.add_field(name=f':city_sunset:  {fmt.bold("sunset")}', value=f"{sunset} UTC")
        emb.set_footer(
            text="Powered by openweathermap.org",
            icon_url=f'http://openweathermap.org/img/w/{weather.get("weather", list())[0].get("icon")}.png',
        )

        await ctx.send(embed=emb)


async def setup(bot):
    if "utility" in bot.config:
        await bot.add_cog(Utility(bot))
    else:
        raise NerpyException("Config not found.")
