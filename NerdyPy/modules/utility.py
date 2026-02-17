# -*- coding: utf-8 -*-

from datetime import UTC, datetime

import utils.format as fmt
from discord import Embed, Interaction, app_commands
from discord.ext.commands import Cog
from openweather.weather import OpenWeather
from utils.errors import NerpyException
from utils.helpers import error_context


@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.guild_only()
class Utility(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.weather_api = OpenWeather(self.bot.config["utility"]["openweather"])

    @app_commands.command(name="ping")
    async def _ping(self, interaction: Interaction):
        """Pong."""
        await interaction.response.send_message("Pong.")

    @app_commands.command(name="uptime")
    async def _uptime(self, interaction: Interaction):
        """shows bot uptime"""
        td = datetime.now(UTC) - self.bot.uptime
        await interaction.response.send_message(
            fmt.inline(f"Uptime: {td.days} Days, {td.seconds // 3600} Hours and {(td.seconds // 60) % 60} Minutes"),
        )

    @app_commands.command(name="weather")
    @app_commands.rename(query="city")
    @app_commands.checks.bot_has_permissions(embed_links=True)
    async def _get_weather(self, interaction: Interaction, *, query: str):
        """outputs weather information"""
        try:
            await interaction.response.defer()

            for umlaut in ["ä", "ö", "ü"]:
                if umlaut in query:
                    await interaction.followup.send("Please use english names only!", ephemeral=True)
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

            await interaction.followup.send(embed=emb)
        except Exception as ex:
            self.bot.log.error(f"{error_context(interaction)}: error while fetching weather: {ex}")
            await interaction.followup.send("An error occurred while fetching the weather information.", ephemeral=True)


async def setup(bot):
    if "utility" in bot.config:
        await bot.add_cog(Utility(bot))
    else:
        raise NerpyException("Config not found.")
