import aiohttp
import discord
import datetime
import utils.format as fmt
from utils.errors import NerpyException
from discord.ext.commands import Cog, command, check, bot_has_permissions, group


class Utility(Cog):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.config = self.bot.config["utility"]

    @command()
    @check(is_botmod)
    @bot_has_permissions(send_messages=True)
    async def uptime(self, ctx):
        """shows bot uptime [bot-moderator]"""
        td = datetime.datetime.utcnow() - self.bot.uptime
        await self.bot.sendc(
            ctx,
            fmt.inline(f"Botuptime: {td.days} Days, {td.seconds // 3600} Hours and {(td.seconds // 60) % 60} Minutes"),
        )

    @command()
    @check(is_botmod)
    async def stop(self, ctx):
        """stop sound playing [bot-moderator]"""
        self.bot.audio.stop(ctx.guild.id)

    @command()
    @check(is_botmod)
    async def leave(self, ctx):
        """bot leaves the channel [bot-moderator]"""
        await self.bot.audio.leave(ctx.guild.id)

    @command()
    @check(is_botmod)
    async def membercount(self, ctx):
        """displays the current membercount of the server [bot-moderator]"""
        await self.bot.sendc(ctx, fmt.inline(f"There are currently {ctx.guild.member_count} members on this discord"))

    @command()
    @bot_has_permissions(embed_links=True, send_messages=True)
    async def weather(self, ctx, *, query: str):
        """outputs weather information"""
        url = (
            f"http://api.openweathermap.org/data/2.5/weather?q={query}&appid={self.config['openweather']}&units=metric"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    err = f"The api-webserver responded with a code: {response.status} - {response.reason}"
                    raise NerpyException(err)
                data = await response.json()

                conditions = []
                for w in data["weather"]:
                    conditions.append(w["main"])

                sunrise = datetime.datetime.fromtimestamp(int(data["sys"]["sunrise"])).strftime("%H:%M")
                sunset = datetime.datetime.fromtimestamp(int(data["sys"]["sunset"])).strftime("%H:%M")

                emb = discord.Embed()
                emb.add_field(
                    name=":earth_africa: " + fmt.bold("location"),
                    value=f"""[{data['name']},
                                    {data['sys']['country']}](https://openweathermap.org/city/{data['id']})""",
                )
                emb.add_field(
                    name=":thermometer: " + fmt.bold("temperature"),
                    value=f"{data['main']['temp']}°C",
                )
                emb.add_field(
                    name=":cloud: " + fmt.bold("condition"),
                    value=str.join(", ", conditions),
                )
                emb.add_field(
                    name=":sweat_drops: " + fmt.bold("humidity"),
                    value=f"{data['main']['humidity']}%",
                )
                emb.add_field(
                    name=":wind_chime: " + fmt.bold("wind"),
                    value=f"{data['wind']['speed']} m/s",
                )
                emb.add_field(
                    name="🔆 " + fmt.bold("min-max"),
                    value=f"{data['main']['temp_min']}°C - {data['main']['temp_max']}°C",
                )
                emb.add_field(name=":city_sunrise: " + fmt.bold("sunrise"), value=f"{sunrise} UTC")
                emb.add_field(name=":city_sunset:  " + fmt.bold("sunset"), value=f"{sunset} UTC")
                emb.set_footer(
                    text="Powered by openweathermap.org",
                    icon_url=f"http://openweathermap.org/img/w/{data['weather'][0]['icon']}.png",
                )

                await self.bot.sendc(ctx, "", emb)


def setup(bot):
    if "utility" in bot.config:
        bot.add_cog(Utility(bot))
    else:
        raise NerpyException("Config not found.")
