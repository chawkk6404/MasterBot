# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import random
from datetime import time
from typing import Literal
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
from english_words import english_words_lower_set
import enchant

from bot import MasterBot
from cogs.utils.view import View, smart_send
from cogs.utils.app_and_cogs import Cog


words = [word for word in english_words_lower_set if len(word) == 5 and "'" not in word]


Num = Literal[1, 2, 3]


class TicTacToeButton(discord.ui.Button["TicTacToeView"]):
    emojis = {0: "❌", 1: "⭕"}

    def __init__(self, x, y):
        self.x, self.y = x, y
        super().__init__(style=discord.ButtonStyle.grey, row=y, label="\u0020")

    async def callback(self, interaction: discord.Interaction):
        self.label = self.emojis[self.view.turn]

        for child in self.view.children:
            if (child.x, child.y) == (self.x, self.y):  # type: ignore
                self.disabled = True

                break
        if self.view.turn == 0:
            self.view.x.append((self.x, self.y))
            player = "x"
        else:
            self.view.o.append((self.x, self.y))
            player = "o"

        finished = False
        moves = getattr(self.view, player)

        for combo in self.view.diags:
            if all([c in moves for c in combo]):
                print(combo)
                finished = True
                self.view.winner = self.view.users[self.view.turn]
                child: TicTacToeButton
                for child in self.view.children:
                    if (child.x, child.y) in combo:
                        child.style = discord.ButtonStyle.green
                break

        if not finished:
            counter_x = {0: 0, 1: 0, 2: 0}
            counter_y = {0: 0, 1: 0, 2: 0}
            for x, y in moves:
                counter_x[x] += 1
                counter_y[y] += 1
            for k, v in counter_x.items():
                if v == 3:
                    finished = True
                    self.view.winner = self.view.users[self.view.turn]
                    for child in self.view.children:
                        if child.x == k:
                            child.style = discord.ButtonStyle.green
                    break
            if not finished:
                for k, v in counter_y.items():
                    if v == 3:
                        finished = True
                        self.view.winner = self.view.users[self.view.turn]
                        for child in self.view.children:
                            if child.y == k:
                                child.style = discord.ButtonStyle.green
                        break

        await interaction.message.edit(view=self.view)

        if finished:
            await self.view.disable_all(interaction.message)
            self.view.stop()
        if all(c.disabled for c in self.view.children):  # type: ignore
            self.view.winner = 0
            self.view.stop()
        self.view.turn = 1 if self.view.turn == 0 else 0


class TicTacToeView(View):
    diags: list[list[tuple[Num, Num]]] = [  # each must be hardcoded sadly
        [(0, 0), (1, 1), (2, 2)],
        [(0, 0), (2, 2), (1, 1)],
        [(1, 1), (0, 0), (2, 2)],
        [(1, 1), (2, 2), (0, 0)],
        [(2, 2), (0, 0), (1, 1)],
        [(2, 2), (1, 1), (0, 0)],
        [(2, 0), (1, 1), (0, 2)],
        [(2, 0), (0, 2), (1, 1)],
        [(1, 1), (2, 0), (0, 2)],
        [(1, 1), (0, 2), (2, 0)],
        [(0, 2), (1, 1), (2, 0)],
        [(0, 2), (2, 0), (1, 1)],
    ]

    def __init__(self, user1, user2):
        self.users = [user1.id, user2.id]
        self.turn = 0
        self.winner = None
        self.x = []
        self.o = []
        super().__init__()
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.users[self.turn] == interaction.user.id:
            return True
        if interaction.user.id in self.users:
            await smart_send(interaction, "Wait for your turn", ephemeral=True)
        await smart_send(interaction, "You are not in this tic tac toe game")
        return False


class RockPaperScissorsButton(discord.ui.Button["RockPaperScissors"]):
    def __init__(self, name, emoji):
        self.name = name
        super().__init__(label=name, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        if self.view.p1 == interaction.user:
            self.view.value1 = self.name
        else:
            self.view.value2 = self.name

        if self.view.p2 is None:
            self.view.value2 = random.choice(
                [name for name, emoji in self.view.options]
            )
            await self.view.disable_all(interaction.message)
            self.view.stop()
            return

        if self.view.value1 and self.view.value2:
            await self.view.disable_all(interaction.message)
            self.view.stop()


class RockPaperScissors(View):
    options = (("Rock", "🪨"), ("Paper", "📜"), ("Scissors", "✂"))

    def __init__(self, p1: discord.User, p2: discord.User | None = None):
        self.p1 = p1
        self.p2 = p2
        self.value1 = None
        self.value2 = None
        super().__init__()
        for name, emoji in self.options:
            self.add_item(RockPaperScissorsButton(name, emoji))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in (self.p1, self.p2):
            await interaction.response.send_message("You are not in this game.")
            return False

        else:
            if interaction.user == self.p1 and self.value1:
                await interaction.response.send_message(
                    f"You already selected {self.value1}"
                )
            elif interaction.user == self.p2 and self.value2:
                await interaction.response.send_message(
                    f"You already selected {self.value2}"
                )
            else:
                return True
        return False

    def get_value(self, player: discord.User):
        if player == self.p1:
            return self.value1
        elif player == self.p2:
            return self.value2
        return None


class Games(Cog, name="games"):
    word = random.choice(words)
    font = ImageFont.truetype("arial.ttf", 15)

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.done: list[int] = []
        self.new_word.start()
        self.d = enchant.Dict("en_US")
        print("Games cog loaded")

    @tasks.loop(time=time(0, 0, 0))
    async def new_word(self):
        self.__class__.word = random.choice(words)
        self.done.clear()

    @commands.command(description="Play tic tac toe against someone.")
    @commands.guild_only()
    async def tictactoe(self, ctx, *, member: discord.Member):
        view = TicTacToeView(ctx.author, member)
        embed = discord.Embed(
            title=f"{ctx.author.display_name} vs {member.display_name}"
        )
        embed.set_footer(text="You have 3 minutes.")

        msg = await ctx.send(member.mention, embed=embed, view=view)
        await view.wait()

        if view.winner:
            winner = ctx.guild.get_member(view.winner)
            await msg.reply(f"The winner is {winner.display_name}!")
            return

        if view.winner == 0:
            await msg.reply("You tied. You both suck.")
        await msg.reply("You couldn't finish in time.")

    @tictactoe.error
    async def error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("You only can do this in a server.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("I couldn't find that member")
        elif isinstance(error, commands.MissingRequiredArgument):
            o_msg = await ctx.reply("Mention a user to play against.")
            try:
                msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
                    timeout=30,
                )
            except asyncio.TimeoutError:
                await o_msg.reply("You didn't respond in time.")
                return
            try:
                member = await commands.MemberConverter().convert(ctx, msg.content)
            except commands.MemberNotFound:
                await ctx.send("sadly I couldn't find that member")
                return
            await self.tictactoe(ctx, member=member)

    @app_commands.command(
        name="tictactoe", description="Challenge a user to Tic Tac Toe!"
    )
    @app_commands.describe(member="The member to challenge.")
    async def _tictactoe(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        view = TicTacToeView(interaction.user, member)
        embed = discord.Embed(
            title=f"{interaction.user.display_name} vs {member.display_name}"
        )
        embed.set_footer(text="You have 3 minutes.")

        await interaction.response.send_message(embed=embed, view=view)
        await interaction.followup.send(member.mention)
        await view.wait()

        if view.winner:
            winner = interaction.guild.get_member(view.winner)
            await interaction.followup.send(f"The winner is {winner.display_name}!")
            return

        if view.winner == 0:
            await interaction.followup.send("You tied. You both suck.")
            return

        await interaction.followup.send("You couldn't finish in time.")

    @commands.command(
        aliases=["rps", "rockpaperscissors"], description="Play rock paper scissors!"
    )
    async def rock_paper_scissors(
        self, ctx: commands.Context, member: discord.Member = None
    ):
        view = RockPaperScissors(ctx.author, member)
        member = member or ctx.me

        embed = discord.Embed(
            title=f"{ctx.author.display_name} vs {member.display_name}"
        )
        msg = await ctx.send(member.mention, embed=embed, view=view)
        await view.wait()

        winner = None
        v1 = view.value1
        v2 = view.value2
        if v1 == "Rock":
            if v2 == "Scissors":
                winner = ctx.author
            elif v2 == "Paper":
                winner = member
        elif v1 == "Paper":
            if v2 == "Scissors":
                winner = member
            elif v2 == "Rock":
                winner = ctx.author
        else:
            if v2 == "Rock":
                winner = member
            elif v2 == "Paper":
                winner = ctx.author

        if winner is None:
            await msg.reply("Tie. They both picked the same thing LOL.")
            return
        loser = ctx.author if winner is not ctx.author else member
        embed = discord.Embed(
            title=f"The winner is {winner.display_name}!",
            description=f"{view.get_value(winner)} beats {view.get_value(loser)}",
        )
        await msg.reply(embed=embed)

    @app_commands.command(
        name="rockpaperscissors", description="Play a quick game of rock paper scissors"
    )
    @app_commands.describe(member="If you want you can challenge a member")
    async def _rock_paper_scissors(self, interaction, member: discord.Member = None):
        view = RockPaperScissors(interaction.user, member)
        member = member or interaction.guild.me

        embed = discord.Embed(
            title=f"{interaction.user.display_name} vs {member.display_name}"
        )
        await interaction.response.send(member.mention, embed=embed, view=view)
        await view.wait()

        winner = None
        v1 = view.value1
        v2 = view.value2
        if v1 == "Rock":
            if v2 == "Scissors":
                winner = interaction.user
            elif v2 == "Paper":
                winner = member
        elif v1 == "Paper":
            if v2 == "Scissors":
                winner = member
            elif v2 == "Rock":
                winner = interaction.user
        else:
            if v2 == "Rock":
                winner = member
            elif v2 == "Paper":
                winner = interaction.user

        if winner is None:
            await interaction.followup.send("Tie. They both picked the same thing LOL.")
            return

        loser = interaction.user if winner is not interaction.user else member
        embed = discord.Embed(
            title=f"The winner is {winner.display_name}!",
            description=f"{view.get_value(winner)} beats {view.get_value(loser)}",  # type: ignore
        )  # type: ignore
        await interaction.followup.send(embed=embed)

    @staticmethod
    def convert(seconds):
        seconds = seconds % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60

        return "%d:%02d:%02d" % (hour, minutes, seconds)

    @commands.command(description="Play the popular game Wordle from New York Times")
    async def wordle(self, ctx):
        if (
            ctx.author.id in self.done
        ):  # id is used so `User` and `Member` are treated the same
            next_word = self.new_word.next_iteration - discord.utils.utcnow()
            await ctx.reply(
                f"You've already done it. A new word comes in {self.convert(next_word.total_seconds())}"
            )
            return

        background = Image.new(mode="RGB", size=(185, 220), color="white")
        results = {}

        attempt = 1
        y = 17

        success = False
        word = self.__class__.word

        sent = await ctx.send(
            "Type a 5 letter word to guess.",
        )
        check = lambda m: len(m.content) == 5 and m.author == ctx.author

        while attempt < 7:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=600)
            except asyncio.TimeoutError:
                await sent.reply("Try guessing a bit faster next time.")
                return

            content = msg.content.lower()

            if not self.d.check(content):
                await msg.reply("I don't think that's a real word.")
                continue

            for index, letter in enumerate(content):
                if letter == word[index]:
                    results[index] = (letter, "green")
                elif letter in word:
                    results[index] = (letter, "#FFD700")
                else:
                    results[index] = (letter, "gray")

            x = 10

            for letter, color in results.values():
                background.paste(Image.new("RGB", size=(25, 25), color=color), (x, y))
                x += 35

            img = ImageDraw.Draw(background)
            x = 18.5

            for letter, _ in results.values():
                img.text((x, y + 4), letter.upper(), font=self.font)
                x += 35

            with BytesIO() as image_binary:
                background.save(image_binary, "PNG")
                image_binary.seek(0)
                file = discord.File(image_binary, "image.png")
            await msg.reply(file=file, mention_author=False)

            if content == word:
                success = True
                break

            attempt += 1
            y += 29

        if not success:
            await sent.reply(f"You didn't guess it. The word is ||{word}||")
            return

        await sent.reply(f"It took you {attempt} tries.")

    @app_commands.command(
        name="wordle", description="Play the popular game wordle. (Not created by us)"
    )
    async def _wordle(self, interaction):
        if (
            interaction.user.id in self.done
        ):  # id is used so `User` and `Member` are treated the same
            next_word = self.new_word.next_iteration - discord.utils.utcnow()
            await interaction.response.send_message(
                f"You've already done it. A new word comes in {self.convert(next_word.total_seconds())}"
            )
            return

        background = await asyncio.to_thread(
            Image.new(mode="RGB", size=(185, 200), color="white")
        )
        results = {}

        attempt = 1
        y = 17

        success = False

        await interaction.response.send_message(
            "Type a 5 letter word to guess.",
        )
        check = lambda m: len(m.content) == 5 and m.author == interaction.user

        while attempt < 7:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=600)
            except asyncio.TimeoutError:
                await interaction.followup.send("Try guessing a bit faster next time.")
                return

            content = msg.content.lower()

            if content not in english_words_lower_set:
                await msg.reply("I don't think that's a real word.")
                continue

            for index, letter in enumerate(content):
                if letter == self.word[index]:
                    results[index] = (letter, "green")
                elif letter in self.word:
                    results[index] = (letter, "#FFD700")
                else:
                    results[index] = (letter, "gray")

            x = 10

            for letter, color in results.values():
                await asyncio.to_thread(
                    background.paste(
                        Image.new("RGB", size=(25, 25), color=color), (x, y)
                    )
                )
                x += 35

            img = ImageDraw.Draw(background)
            x = 18.5

            for letter, _ in results.values():
                img.text((x, y + 4), letter.upper(), font=self.font)
                x += 35

            with BytesIO() as image_binary:
                await asyncio.to_thread(background.save(image_binary, "PNG"))
                image_binary.seek(0)
                file = discord.File(image_binary, "image.png")
            await interaction.followup.send(file=file)

            if content == self.word:
                success = True
                break

            attempt += 1
            y += 29

        if not success:
            await interaction.followup.send(
                f"You didn't guess it. The word is ||{self.word}||"
            )
            return

        await interaction.followup.send(f"It took you {attempt} tries.")


async def setup(bot: MasterBot):
    await Games.setup(bot)
