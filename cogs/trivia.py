import random
from html import unescape

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils.http import AsyncHTTPClient
from cogs.utils.view import View
from cogs.utils.app_and_cogs import Cog
from bot import MasterBot


class OpenTDBHTTPClient(AsyncHTTPClient):
    def __init__(self, loop):
        super().__init__("https://opentdb.com/", loop=loop, suffix=".php")
        self.token = None

    async def trivia(self, amount=1):
        return await self.request("api", amount=amount, token=self.token)

    async def get_token(self):
        resp = await self.request("api_token", command="request")
        self.token = resp.get("token")


colors = [
    discord.ButtonStyle.green,
    discord.ButtonStyle.red,
    discord.ButtonStyle.blurple,
    discord.ButtonStyle.grey,
]


class TriviaButton(discord.ui.Button["MultipleChoice"]):
    def __init__(self, choice, correct, color):
        self.correct = correct
        super().__init__(style=color, label=choice)

    async def callback(self, interaction: discord.Interaction):
        if self.correct is True:
            self.view.done = True
            await self.view.disable_all(message=interaction.message)

            embed = discord.Embed(
                title=f"{interaction.user.display_name} got it right!",
                description=f"The answer was {self.label}",
            )

            if len(self.view.tries) > 0:
                embed.add_field(
                    name="Wrong guesses",
                    value="\n".join(f"{k}: {v}" for k, v in self.view.tries.items()),
                )

            await interaction.response.send_message(embed=embed)
            self.view.stop()
        else:
            await interaction.response.send_message("Wrong answer.", ephemeral=True)
            self.view.tries[interaction.user.display_name] = self.label


class MultipleChoice(View):
    def __init__(self, correct, incorrect: list):
        self.incorrect = incorrect
        self.choices: list = incorrect + [correct]
        self.choices = [unescape(choice) for choice in self.choices]
        random.shuffle(self.choices)

        self.done = False
        self.tries = {}

        super().__init__(timeout=30)

        for index, choice in enumerate(self.choices):
            answer = False
            if choice == correct:
                answer = True
            self.add_item(TriviaButton(choice, answer, colors[index]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.done:
            self.stop()
            return False

        if interaction.user.display_name in self.tries.keys():
            await interaction.response.send_message(
                "You already tried and failed.", ephemeral=True
            )
            return False
        return True


class Trivia(Cog, name="trivia"):
    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.http = OpenTDBHTTPClient(self.bot.loop)
        print("Trivia cog loaded")

    async def cog_load(self):
        await super().cog_load()
        self.bot.loop.create_task(self.http.get_token())

    @commands.command(description="Play some trivia.")
    @commands.cooldown(1, 3, commands.BucketType.channel)
    async def trivia(self, ctx):
        data = await self.http.trivia()

        if data.get("response_code") != 0:
            await ctx.send("We encountered an unexpected error. Try again later.")
            return
        data = data.get("results")[0]
        question = unescape(data.get("question"))
        embed = discord.Embed(title=question)
        embed.set_footer(text="The difficulty is {}".format(data.get("difficulty")))
        my_view = MultipleChoice(
            data.get("correct_answer"), data.get("incorrect_answers")
        )

        message = await ctx.send(embed=embed, view=my_view)
        message = message or interaction.message

        await my_view.wait()
        if my_view.done is False:
            await my_view.disable_all(message=message)

            embed = discord.Embed(
                title="No one got it right in time.",
                description="The answer was {}".format(
                    unescape(data.get("correct_answer"))
                ),
            )
            embed.add_field(
                name="Wrong guesses",
                value="\n".join(f"{k}: {v}" for k, v in my_view.tries.items())
                or "No guesses",
            )
            await message.reply(embed=embed)

    @trivia.error
    async def error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(error)
        else:
            raise error


async def setup(bot: MasterBot):
    await Trivia.setup(bot)
