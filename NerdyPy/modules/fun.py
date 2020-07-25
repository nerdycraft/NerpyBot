import discord
from random import randint, choice
from utils.errors import NerpyException
from discord.ext.commands import Cog, command, bot_has_permissions


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
            16: "If you fail in epic proportions, it may just become a winning"
            " failure",
            17: "Every win fails eventually",
            18: "Everything that can be labeled can be hated",
            19: "The more you hate it the stronger it gets",
            20: "Nothing is to be taken seriously",
            21: "Original content is original only for a few seconds before getting"
            " old",
            22: "Copypasta is made to ruin every last bit of originality",
            23: "Copypasta is made to ruin every last bit of originality",
            24: "Every repost it always a repost of a repost",
            25: "Relation to the original topic decreases with every single post",
            26: "Any topic can easily be turned into something totally unrelated",
            27: "Always question a person's sexual prefrences without any real reason",
            28: "Always question a person's gender - just incase it's really a man",
            29: "In the internet all girls are men and all kids are undercover FBI"
            " agents",
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
            41: "Desu isn't funny. Seriously guys. It's worse than Chuck Norris"
            " jokes.",
            42: "Nothing is Sacred.",
            43: "The more beautiful and pure a thing is - the more satisfying it is"
            " to corrupt it",
            44: "Even one positive comment about Japanese things can make you a"
            " weaboo",
            45: "When one sees a lion, one must get into the car.",
            46: "There is always furry porn of it.",
            47: "The pool is always closed.",
            63: "For every given male character, there is a female version of that character; "
            "conversely",
        }

    @command()
    @bot_has_permissions(send_messages=True)
    async def roll(self, ctx, dice: int = 6):
        """
        Rolls random number (between 1 and user choice)

        <dice> anything larger than 1, default is 6
        """
        mention = ctx.message.author.mention
        if dice > 1:
            n = randint(1, dice)
            await ctx.send(f"{mention} rolled a d{dice}\n\n:game_die: {n} :game_die:")
        else:
            await ctx.send(
                f"{mention} rolled a 'AmIRetarded'-dice\n\n:game_die: yes :game_die:"
            )

    @command()
    @bot_has_permissions(send_messages=True)
    async def ping(self, ctx):
        """Pong."""
        await ctx.send("Pong.")

    @command()
    @bot_has_permissions(send_messages=True)
    async def choose(self, ctx, *choices):
        """
        Chooses between multiple choices.
        To denote multiple choices, you should use double quotes.
        """
        choices_str = ", ".join(choices)
        if len(choices) < 2:
            raise NerpyException("Not enough choices to pick from.")

        mention = ctx.message.author.mention
        await ctx.send(
            f"{mention} asked me to choose between: {choices_str}\n\nI choose {choice(choices)}"
        )

    @command(name="8ball", aliases=["8b"])
    @bot_has_permissions(send_messages=True)
    async def eightball(self, ctx, *, question: str):
        """
        Ask 8 ball a question
        Question must end with a question mark.
        """
        if not question.endswith("?") or question == "?":
            raise NerpyException("That doesn't look like a question.")

        mention = ctx.message.author.mention
        await ctx.send(f"{mention} asked me: {question}\n\n{choice(self.ball)}`")

    @command(no_pm=True)
    @bot_has_permissions(send_messages=True)
    async def hug(self, ctx, user: discord.Member, intensity: int = 1):
        """
        Because everyone likes hugs!

        <user> has to be a valid @user
        <intensity> 0 to 4 levels default is 1
        """
        name = user.mention
        author = ctx.message.author.mention
        if intensity <= 0:
            intensity = 0
        if intensity >= 4:
            intensity = 4

        await ctx.send(f"{author} {self.hugs[intensity]} {name}")

    @command()
    @bot_has_permissions(send_messages=True)
    async def leet(self, ctx, degree: int, *, text: str):
        """
        convert text into 1337speak

        <degree> 5 levels, starting with 1
        <text> anytext you want to convert
        """
        if degree > 0:
            if degree > 6:
                degree = 6

            valid_chars = self.leetdegrees[0]
            for i in range(1, degree):
                valid_chars.extend(self.leetdegrees[i])

            leettext = ""
            for c in text:
                if valid_chars.count(c.lower()) > 0:
                    leettext += self.leetmap[c.lower()]
                else:
                    leettext += c

            text = leettext

        await ctx.send(text)

    @command()
    async def roti(self, ctx, num: int = None):
        """
        rules of the internet

        if no <num> is provided, a random rule will display
        """
        if num:
            if num not in self.rotis:
                raise NerpyException(
                    "Sorry 4chan pleb, no rules found with this number"
                )
            rule = num
        else:
            rule = choice(list(self.rotis.keys()))
        await ctx.send(f"Rule {rule}: {self.rotis[rule]}")

    @command()
    @bot_has_permissions(send_messages=True)
    async def say(self, ctx, *, text: str):
        """
        makes the bot say what you want :O
        """
        await ctx.send(text)


def setup(bot):
    bot.add_cog(Fun(bot))
