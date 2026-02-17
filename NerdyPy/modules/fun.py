# -*- coding: utf-8 -*-

from random import choice, randint
from typing import Optional

from discord import Interaction, Member, app_commands
from discord.ext.commands import Cog
from utils.errors import NerpyException


@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.guild_only()
class Fun(Cog):
    """HAHA commands so fun, much wow"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

        self.hugs = ["(っ˘̩╭╮˘̩)っ", "(っ´▽｀)っ", "╰(*´︶`*)╯", "(つ≧▽≦)つ", "(づ￣ ³￣)づ"]
        self.ball = [
            "As I see it, yes",
            "It is certain",
            "It is decidedly so",
            "Most likely",
            "Outlook good",
            "Signs point to yes",
            "Without a doubt",
            "Yes",
            "Yes – definitely",
            "You may rely on it",
            "Reply hazy, try again",
            "Ask again later",
            "Better not tell you now",
            "Cannot predict now",
            "Concentrate and ask again",
            "Don't count on it",
            "My reply is no",
            "My sources say no",
            "Outlook not so good",
            "Very doubtful",
        ]
        self.leetdegrees = [
            ["a", "e", "i", "o"],
            ["s", "l", "c", "y", "u", "d"],
            ["k", "g", "t", "z", "f"],
            ["n", "w", "h", "v", "m"],
            ["r", "b", "q", "x"],
            ["j", "p"],
        ]
        self.leetmap = {
            "a": "4",
            "b": "ß",
            "c": "(",
            "d": "Ð",
            "e": "3",
            "f": "ƒ",
            "g": "9",
            "h": "|-|",
            "i": "1",
            "j": "_|",
            "k": "|{",
            "l": "£",
            "m": "|\\/|",
            "n": "|\\|",
            "o": "0",
            "p": "|°",
            "q": "¶",
            "r": "®",
            "s": "$",
            "t": "7",
            "u": "µ",
            "v": "\\/",
            "w": "\\/\\/",
            "x": "(",
            "y": "¥",
            "z": "2",
        }

        self.rotis = {
            1: "Do not talk about /b/",
            2: "Do NOT talk about /b/",
            3: "We are Anonymous",
            4: "Anonymous is legion",
            5: "Anonymous never forgives",
            6: "Anonymous can be a horrible, senseless, uncaring monster",
            7: "Anonymous is still able to deliver",
            8: "There are no real rules about posting",
            9: "There are no real rules about moderation either - enjoy your ban",
            10: "If you enjoy any rival sites - DON'T",
            11: "All your carefully picked arguments can easily be ignored",
            12: "Anything you say can and will be used against you",
            13: "Anything you say can be turned into something else - fixed",
            14: "Do not argue with trolls - it means that they win",
            15: "The harder you try the harder you will fail",
            16: "If you fail in epic proportions, it may just become a winning failure",
            17: "Every win fails eventually",
            18: "Everything that can be labeled can be hated",
            19: "The more you hate it the stronger it gets",
            20: "Nothing is to be taken seriously",
            21: "Original content is original only for a few seconds before getting old",
            22: "Copypasta is made to ruin every last bit of originality",
            23: "Copypasta is made to ruin every last bit of originality",
            24: "Every repost it always a repost of a repost",
            25: "Relation to the original topic decreases with every single post",
            26: "Any topic can easily be turned into something totally unrelated",
            27: "Always question a person's sexual prefrences without any real reason",
            28: "Always question a person's gender - just incase it's really a man",
            29: "In the internet all girls are men and all kids are undercover FBI agents",
            30: "There are no girls on the internet",
            31: "TITS or GTFO - the choice is yours",
            32: "You must have pictures to prove your statements",
            33: "Lurk more - it's never enough",
            34: "There is porn of it, no exceptions",
            35: "If no porn is found at the moment, it will be made",
            36: "There will always be even more fucked up shit than what you just saw",
            37: "You can not divide by zero (just because the calculator says so)",
            38: "No real limits of any kind apply here - not even the sky",
            39: "CAPSLOCK IS CRUISE CONTROL FOR COOL",
            40: "EVEN WITH CRUISE CONTROL YOU STILL HAVE TO STEER",
            41: "Desu isn't funny. Seriously guys. It's worse than Chuck Norris jokes.",
            42: "Nothing is Sacred.",
            43: "The more beautiful and pure a thing is - the more satisfying it is to corrupt it",
            44: "Even one positive comment about Japanese things can make you a weaboo",
            45: "When one sees a lion, one must get into the car.",
            46: "There is always furry porn of it.",
            47: "The pool is always closed.",
            63: "For every given male character, there is a female version of that character; conversely",
        }

    @app_commands.command()
    async def roll(self, interaction: Interaction, dice: int = 6) -> None:
        """
        Rolls random number (between 1 and user choice)

        Parameters
        ----------
        interaction
        dice: int
            anything larger than 1, default is 6
        """
        mention = interaction.user.mention
        if dice > 1:
            n = randint(1, dice)
            await interaction.response.send_message(f"{mention} rolled a d{dice}\n\n:game_die: {n} :game_die:")
        else:
            await interaction.response.send_message(
                f"{mention} rolled a 'AmIRetarded'-dice\n\n:game_die: yes :game_die:"
            )

    @app_commands.command()
    async def choose(self, interaction: Interaction, choices: str) -> None:
        """
        Makes a choice for you.
        Choices need to be seperated by "," and sentences also need to be encased by "".
        """
        choices_list = choices.split(",")
        if len(choices) < 2:
            raise NerpyException("Not enough choices to pick from.")

        mention = interaction.user.mention
        await interaction.response.send_message(
            f"{mention} asked me to choose between: {choices}\n\nI choose {choice(choices_list)}"
        )

    @app_commands.command(name="8ball")
    async def eightball(self, interaction: Interaction, question: str) -> None:
        """
        Ask 8-Ball a question.
        Question must end with a question mark.
        """
        if not question.endswith("?") or question == "?":
            await interaction.response.send_message("That doesn't look like a question.")

        mention = interaction.user.mention
        await interaction.response.send_message(f"{mention} asked me: {question}\n\n{choice(self.ball)}")

    @app_commands.command()
    async def hug(self, interaction: Interaction, user: Member, intensity: Optional[int] = None) -> None:
        """
        Because everyone likes hugs!

        Parameters
        ----------
        interaction
        user: Member
             has to be a valid @user
        intensity: Optional[int]
            The intensity of your hug. 0 to 4 levels, default is random
        """
        name = user.mention
        author = interaction.user.mention
        if intensity is not None:
            if intensity <= 0:
                intensity = 0
            if intensity >= 4:
                intensity = 4

            await interaction.response.send_message(f"{author} {self.hugs[intensity]} {name}")
        else:
            await interaction.response.send_message(f"{author} {choice(self.hugs)} {name}")

    @app_commands.command()
    async def leet(self, interaction: Interaction, intensity: int, text: str) -> None:
        """
        convert text into 1337speak

        Parameters
        ----------
        interaction
        intensity: int
            Set the intensity for the conversion. 5 levels, starting with 1
        text: str
             any text you want to convert
        """
        if intensity > 0:
            if intensity > 5:
                intensity = 5

            valid_chars = self.leetdegrees[0]
            for i in range(1, intensity):
                valid_chars.extend(self.leetdegrees[i])

            leettext = ""
            for c in text:
                if valid_chars.count(c.lower()) > 0:
                    leettext += self.leetmap[c.lower()]
                else:
                    leettext += c

            text = leettext

        await interaction.response.send_message(text)

    @app_commands.command()
    async def roti(self, interaction: Interaction, num: int = None) -> None:
        """
        rules of the internet

        if no <num> is provided, a random rule will display
        """
        if num:
            if num not in self.rotis:
                await interaction.response.send_message("Sorry 4chan pleb, no rules found with this number")
                return
            rule = num
        else:
            rule = choice(list(self.rotis.keys()))
        await interaction.response.send_message(f"Rule {rule}: {self.rotis[rule]}")

    @app_commands.command()
    async def say(self, interaction: Interaction, text: str) -> None:
        """
        makes the bot say what you want :O
        """
        await interaction.response.send_message(text)


async def setup(bot):
    await bot.add_cog(Fun(bot))
