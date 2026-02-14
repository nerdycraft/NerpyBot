# -*- coding: utf-8 -*-

from datetime import UTC, datetime

import utils.format as fmt
from discord import Embed, app_commands
from discord.ext.commands import Cog, Context, bot_has_permissions, hybrid_command
from openweather.weather import OpenWeather
from utils.errors import NerpyException
from utils.helpers import error_context, send_hidden_message


@bot_has_permissions(send_messages=True)
class Utility(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.weather_api = OpenWeather(self.bot.config["utility"]["openweather"])

    @hybrid_command(name="ping", hidden=True)
    @bot_has_permissions(send_messages=True)
    async def _ping(self, ctx: Context):
        """Pong."""
        await ctx.send("Pong.")

    @hybrid_command(name="uptime", hidden=True)
    async def _uptime(self, ctx: Context):
        """shows bot uptime"""
        td = datetime.now(UTC) - self.bot.uptime
        await ctx.send(
            fmt.inline(f"Uptime: {td.days} Days, {td.seconds // 3600} Hours and {(td.seconds // 60) % 60} Minutes"),
        )

    @hybrid_command(name="weather")
    @app_commands.rename(query="city")
    @bot_has_permissions(embed_links=True)
    async def _get_weather(self, ctx: Context, *, query: str):
        """outputs weather information"""
        try:
            async with ctx.typing():
                for umlaut in ["ä", "ö", "ü"]:
                    if umlaut in query:
                        await send_hidden_message(ctx, "Please use english names only!")
                        return

                weather = self.weather_api.get_weather(city=query)

                conditions = []
                for w in weather.get("weather", dict()):
                    conditions.append(w.get("main"))

                sunrise = datetime.fromtimestamp(int(weather.get("sys", dict()).get("sunrise"))).strftime("%H:%M")
                sunset = datetime.fromtimestamp(int(weather.get("sys", dict()).get("sunset"))).strftime("%H:%M")

                emb = Embed()
                emb.add_field(
                    name=f":earth_africa: {fmt.bold('location')}",
                    value=f"""[{weather.get("name")},
                    {weather.get("sys", dict()).get("country")}](https://openweathermap.org/city/{weather.get("id")})""",
                )
                temp = self.weather_api.convert_temperature(weather["main"]["temp"])
                emb.add_field(
                    name=f":thermometer: {fmt.bold('temperature')}",
                    value=f"{temp:.2f}°C",
                )
                emb.add_field(
                    name=f":cloud: {fmt.bold('condition')}",
                    value=str.join(", ", conditions),
                )
                emb.add_field(
                    name=f":sweat_drops: {fmt.bold('humidity')}",
                    value=f"{weather['main']['humidity']}%",
                )
                emb.add_field(
                    name=f":wind_chime: {fmt.bold('wind')}",
                    value=f"{weather['wind']['speed']} m/s",
                )
                temp_min = self.weather_api.convert_temperature(weather["main"]["temp_min"])
                temp_max = self.weather_api.convert_temperature(weather["main"]["temp_max"])
                emb.add_field(
                    name=f"🔆 {fmt.bold('min-max')}",
                    value=f"{temp_min:.2f}°C - {temp_max:.2f}°C",
                )
                emb.add_field(name=f":city_sunrise: {fmt.bold('sunrise')}", value=f"{sunrise} UTC")
                emb.add_field(name=f":city_sunset:  {fmt.bold('sunset')}", value=f"{sunset} UTC")
                emb.set_footer(
                    text="Powered by openweathermap.org",
                    icon_url=f"https://openweathermap.org/img/w/{weather.get('weather', list())[0].get('icon')}.png",
                )

                await ctx.send(embed=emb)
        except Exception as ex:
            self.bot.log.error(f"{error_context(ctx)}: error while fetching weather: {ex}")
            await send_hidden_message(ctx, "An error occurred while fetching the weather information.")


async def setup(bot):
    if "utility" in bot.config:
        await bot.add_cog(Utility(bot))
    else:
        raise NerpyException("Config not found.")
