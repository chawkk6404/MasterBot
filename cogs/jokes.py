import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
from aiosqlite import IntegrityError

from cogs.utils.http import AsyncHTTPClient
from cogs.utils.view import View
from bot import MasterBot
from static_embeds import (
    joke_category_embed,
    nsfw_embed,
    religious_embed,
    political_embed,
    sexist_embed,
    racist_embed,
    explicit_embed,
    alert_bed,
    confirm_bed,
    cancel_bed,
)
from cogs.utils.app_and_cogs import Cog, QuickObject


class BlacklistView(View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.choice = None
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You can't accept or decline. Only the message author can.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="\u2705")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.choice = True
        await self.disable_all(interaction.message)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="\u274C")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = False
        await self.disable_all(interaction.message)
        self.stop()


class CategorySelect(discord.ui.Select):
    def __init__(self):

        options = [
            discord.SelectOption(label="Any"),
            discord.SelectOption(label="Misc"),
            discord.SelectOption(label="Programming"),
            discord.SelectOption(label="Dark"),
            discord.SelectOption(label="Pun"),
            discord.SelectOption(label="Spooky"),
            discord.SelectOption(label="Christmas"),
        ]
        super().__init__(
            placeholder="Categories", min_values=1, max_values=7, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.disable_all(interaction.message)
        self.view.stop()


class CategoryView(View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.item = self.add_item(CategorySelect())
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the person that used the command can use this.", ephemeral=True
            )
            return False
        return True


class BlacklistFlags(commands.FlagConverter):
    nsfw: Optional[str] = None
    religious: Optional[str] = None
    political: Optional[str] = None
    sexist: Optional[str] = None
    racist: Optional[str] = None
    explicit: Optional[str] = None


class JokeAPIHTTPClient(AsyncHTTPClient):
    def __init__(self, loop):
        super().__init__("https://v2.jokeapi.dev/joke/", loop=loop)

    async def get_joke(self, categories=None, blacklist_flags=None):
        categories = categories or ["Any"]
        if len(categories) == 0:
            categories = ["Any"]
        if blacklist_flags:

            return await self.request(
                ",".join(categories), blacklistFlags=",".join(blacklist_flags)
            )
        return await self.request(",".join(categories))


def decode_sql_bool(data: tuple | list) -> list[bool]:
    return [True if num == 1 else False for num in data]


class Jokes(Cog, name="jokes"):
    # hybrid commands don't work here because *arguments and flag arguments.
    default_options = {
        "nsfw": True,
        "religious": True,
        "political": True,
        "sexist": True,
        "racist": True,
        "explicit": True,
    }
    categories = ["any", "misc", "programming", "dark", "pun", "spooky", "christmas"]

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.db = None
        self.blacklist = {}
        self.http = JokeAPIHTTPClient(self.bot.loop)
        self.used_jokes: set = {12345}  # 12345 is so the while loop starts
        print("Jokes cog loaded")

    async def cog_load(self):
        await super().cog_load()
        self.update_db.start()

    async def cog_unload(self):
        await super().cog_unload()
        self.update_db.cancel()

    async def cog_command_error(self, ctx, error):
        error: commands.CommandError  # showing as `Exception` for some reason

        if not ctx.command:
            return
        if isinstance(error, commands.MissingPermissions):
            return
        else:
            await self.bot.on_command_error(ctx, error)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if guild.id not in self.blacklist.keys():
            self.blacklist[guild.id] = self.default_options

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if guild.id in self.blacklist.keys():
            del self.blacklist[guild.id]

    async def fetch_blacklist(self):
        for guild in self.bot.guilds:
            async with self.db.execute(
                f"""SELECT nsfw, religious, political, sexist, racist, explicit FROM blacklist
                                        WHERE id = {guild.id}"""
            ) as cursor:
                data = await cursor.fetchone()
            data = decode_sql_bool(data)
            converted_dict = {}

            for num, key in enumerate(self.default_options.keys()):
                converted_dict[key] = data[num]
            self.blacklist[guild.id] = converted_dict

    @tasks.loop(minutes=3)
    async def update_db(self):
        for guild in self.bot.guilds:
            if guild.id not in self.blacklist:
                self.blacklist[guild.id] = self.default_options
            try:
                await self.db.execute(
                    f"""INSERT INTO blacklist VALUES ({guild.id},
                {self.blacklist[guild.id]['nsfw']},
                {self.blacklist[guild.id]['religious']},
                {self.blacklist[guild.id]['political']},
                {self.blacklist[guild.id]['sexist']},
                {self.blacklist[guild.id]['racist']},
                {self.blacklist[guild.id]['explicit']});"""
                )
            except IntegrityError:
                await self.db.execute(
                    f"""UPDATE blacklist
                SET nsfw = {self.blacklist[guild.id]['nsfw']},
                    religious = {self.blacklist[guild.id]['religious']},
                    political = {self.blacklist[guild.id]['political']},
                    sexist = {self.blacklist[guild.id]['sexist']},
                    racist = {self.blacklist[guild.id]['racist']},
                    explicit = {self.blacklist[guild.id]['explicit']}
                    WHERE id = {guild.id};"""
                )
        await self.db.commit()

    @update_db.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        self.db = await aiosqlite.connect("cogs/databases/joke_blacklist.db")
        await self.db.execute(
            """CREATE TABLE IF NOT EXISTS blacklist (
                                        id INTEGER PRIMARY KEY,
                                        nsfw BOOLEAN,
                                        religious BOOLEAN,
                                        political BOOLEAN,
                                        sexist BOOLEAN,
                                        racist BOOLEAN,
                                        explicit BOOLEAN
                                    );"""
        )
        await self.db.commit()
        await self.fetch_blacklist()

    @update_db.after_loop
    async def after(self):
        await asyncio.sleep(0)
        await self.update_db()
        await self.db.close()

    @commands.command(description="Let me tell you a joke.")
    async def joke(self, ctx, *categories):
        for category in categories:
            if category.lower() not in self.categories:
                await ctx.send(
                    f"That isn't a category! The categories are `{'`, `'.join(self.categories)}`."
                )
                return

        blacklist = self.blacklist.get(ctx.guild.id)
        if blacklist:
            blacklist_flags = [k for k, v in blacklist.items() if not v]
        else:
            blacklist_flags = None

        joke_id = 12345
        data = {}  # to make pycharm stop complaining

        while joke_id in self.used_jokes:
            data: dict = await self.http.get_joke(categories, blacklist_flags)
            joke_id = data.get("id")

        if data.get("error") is True:
            await ctx.send(data)
            await ctx.send("An unexpected error occurred :( Try again later.")
            return

        if data.get("type") == "twopart":
            embed = discord.Embed(title=data.get("setup"))
            embed.set_footer(text=f'Category: {data.get("category")}')
            msg = await ctx.send(embed=embed)

            await asyncio.sleep(5)
            embed2 = discord.Embed(title=data.get("delivery"))
            await msg.reply(embed=embed2)

        elif data.get("type") == "single":
            embed = discord.Embed(title=data.get("joke"))
            embed.set_footer(text=f'Category: {data.get("category")}')
            await ctx.send(embed=embed)

        self.used_jokes.add(joke_id)

    @app_commands.command(name="joke", description="Let me tell you a joke!")
    async def _joke(self, interaction: discord.Interaction):
        view = CategoryView(interaction.user)
        await interaction.response.send_message(embed=joke_category_embed, view=view)
        await view.wait()

        categories = view.item.values
        if len(categories) > 1 and "Any" in categories:
            await interaction.followup.send(
                f"{interaction.user.mention} You cannot select **Any** and other categories."
            )
            return

        if len(categories) == 0:
            await interaction.followup.send("You didn't select anything =(")
        for category in categories:
            if category.lower() not in self.categories:
                await interaction.followup.send(
                    f"That isn't a category! The categories are `{'`, `'.join(self.categories)}`."
                )
                return

        blacklist = self.blacklist.get(interaction.guild.id)
        if blacklist:
            blacklist_flags = [k for k, v in blacklist.items() if not v]
        else:
            blacklist_flags = None

        joke_id = 12345
        data = {}  # to make pycharm stop complaining

        while joke_id in self.used_jokes:
            data: dict = await self.http.get_joke(categories, blacklist_flags)
            joke_id = data.get("id")

        if data.get("error") is True:
            await interaction.followup.send(
                "An unexpected error occurred :( Try again later."
            )
            return

        if data.get("type") == "twopart":
            embed = discord.Embed(title=data.get("setup"))
            embed.set_footer(text=f'Category: {data.get("category")}')
            msg = await interaction.followup.send(embed=embed)

            await asyncio.sleep(5)
            embed2 = discord.Embed(title=data.get("delivery"))
            await msg.reply(embed=embed2)

        elif data.get("type") == "single":
            embed = discord.Embed(title=data.get("joke"))
            embed.set_footer(text=f'Category: {data.get("category")}')
            await interaction.followup.send(embed=embed)

        self.used_jokes.add(joke_id)

    @commands.command(name="blacklist", description="Make some jokes not allowed.")
    @commands.has_permissions(administrator=True)
    async def _blacklist(self, ctx, *, flags: BlacklistFlags):
        for k, v in vars(flags).items():
            if v is None:
                guild = self.blacklist.get(ctx.guild.id)
                if guild:
                    setattr(flags, k, guild.get(k))
                else:
                    if k in ("religious", "sexist", "racist"):
                        setattr(flags, k, False)
                    else:
                        setattr(flags, k, True)
            else:
                new = v.capitalize()
                if new == "True":
                    new = True
                elif new == "False":
                    new = False
                setattr(flags, k, new)

        options = vars(flags)
        embed = discord.Embed(
            title="New Joke Blacklist Settings",
            description="**True = Turned on**\n"
            + "\n".join(f"{k}: {v}" for k, v in options.items()),
        )
        embed.set_footer(text="Choose an option")
        view = BlacklistView(ctx.author)
        msg = await ctx.send(embed=embed, view=view)
        secondary = False

        if options.get("nsfw") is True:
            await asyncio.sleep(0.25)
            await msg.reply(embed=nsfw_embed)
            secondary = True

        if options.get("religious") is True:
            await asyncio.sleep(0.25)
            await msg.reply(embed=religious_embed)
            secondary = True

        if options.get("political") is True:
            await asyncio.sleep(0.25)
            await msg.reply(embed=political_embed)
            secondary = True
        if options.get("sexist") is True:
            await asyncio.sleep(0.25)
            await ctx.send(embed=sexist_embed)
            secondary = True

        if options.get("racist") is True:
            await asyncio.sleep(0.25)
            await msg.reply(embed=racist_embed)
            secondary = True

        if options.get("explicit") is True:
            await asyncio.sleep(0.25)
            await msg.reply(embed=explicit_embed)
            secondary = True

        if secondary is True:
            await asyncio.sleep(0.25)
            await ctx.send(embed=alert_bed)
        await view.wait()

        if view.choice is None:
            await msg.reply(embed=discord.Embed(title="Cancelled"))
            await view.disable_all(msg)

        elif view.choice is True:
            await msg.reply(emebed=confirm_bed)

        elif view.choice is False:
            await msg.reply(embed=cancel_bed)

        self.blacklist[ctx.guild.id] = options

    @_blacklist.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need administrator perms to run this!!")
        else:
            raise error

    @app_commands.command(name="blacklist", description="Turn off some possible jokes.")
    @app_commands.describe(
        nsfw="NSFW jokes",
        religious="Religious jokes",
        political="Political jokes",
        sexist="Sexist jokes",
        racist="Racist jokes",
        explicit="Explicit jokes",
    )
    @app_commands.default_permissions(administrator=True)
    async def __blacklist(
        self,
        interaction: discord.Interaction,
        nsfw: str = None,
        religious: str = None,
        political: str = None,
        sexist: str = None,
        racist: str = None,
        explicit: str = None,
    ):
        ctx = await commands.Context.from_interaction(interaction)
        flags = QuickObject(
            nsfw=nsfw,
            religious=religious,
            political=political,
            sexist=sexist,
            racist=racist,
            explicit=explicit,
        )
        await self._blacklist(ctx, flags=flags)  # type: ignore


async def setup(bot: MasterBot):
    await Jokes.setup(bot)
