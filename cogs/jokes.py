import discord
from discord.ext import commands, tasks
from cogs.utils.http import AsyncHTTPClient
from cogs.utils.view import View
import slash_util
import asyncio
from typing import Optional, Union, Tuple, List
from bot import MasterBot
import aiosqlite
from sqlite3 import IntegrityError


class Help:
    def __init__(self, prefix):
        self.prefix = prefix

    def joke_help(self):
        message = f'`{self.prefix}joke [categories]`: Get a joke! Categories are optional. Separate with a space (Slash Commands use select menu). Categories: `Any`, `Misc`,`Programming`, `Dark`, `Pun`, `Spooky`, `Christmas`\n'
        return message

    def blacklist_help(self):
        message = f'`{self.prefix}blacklist [flags]`: Arguments: `nsfw`, `religious`, `political`, `sexist`, `racist`, `explicit`\nExample: `{self.prefix}blacklist nsfw: true racist: false`'
        return message

    def full_help(self):
        help_list = [self.joke_help(), self.blacklist_help()]
        return '\n'.join(help_list)


class BlacklistView(View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.choice = None
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You can't accept or decline. Only the message author can.",
                                                    ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, emoji='\u2705')
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.choice = True
        await self.disable_all(interaction.message)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, emoji='\u274C')
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.choice = False
        await self.disable_all(interaction.message)
        self.stop()


class CategorySelect(discord.ui.Select):
    def __init__(self, author, view):
        self._view = view
        self.author = author
        options = [
            discord.SelectOption(label='Any'),
            discord.SelectOption(label='Misc'),
            discord.SelectOption(label='Programming'),
            discord.SelectOption(label='Dark'),
            discord.SelectOption(label='Pun'),
            discord.SelectOption(label='Spooky'),
            discord.SelectOption(label='Christmas')
        ]
        super().__init__(placeholder='Categories',
                         min_values=1,
                         max_values=7,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("Only the person that used the command can use this.",
                                                           ephemeral=True)
        for child in self._view.children:
            child.disabled = True
        await interaction.message.edit(view=self._view)
        self._view.stop()


class CategoryView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.item = self.add_item(CategorySelect(author, self))


class BlacklistFlags(commands.FlagConverter):
    nsfw: Optional[str] = None
    religious: Optional[str] = None
    political: Optional[str] = None
    sexist: Optional[str] = None
    racist: Optional[str] = None
    explicit: Optional[str] = None


class SlashFlagObject:
    def __init__(self, **options):
        for k, v in options.items():
            setattr(self, k, v)


class JokeAPIHTTPClient(AsyncHTTPClient):
    def __init__(self):
        super().__init__('https://v2.jokeapi.dev/joke/')

    async def get_joke(self, categories=None, blacklist_flags=None):
        categories = categories or ['Any']
        if len(categories) == 0:
            categories = ['Any']
        if blacklist_flags:
            return await self.request(','.join(categories), blacklistFlags=','.join(blacklist_flags))
        return await self.request(','.join(categories))


def decode_sql_bool(data: Tuple[int]) -> List[bool]:
    converted = []
    for num in data:
        if num == 1:
            converted.append(True)
        else:
            converted.append(False)
    return converted


class Jokes(slash_util.ApplicationCog):
    default_options = {'nsfw': True, 'religious': True, 'political': True, 'sexist': True, 'racist': True,
                            'explicit': True}

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.db = None
        self.blacklist = {}
        self.update_db.start()
        self.http = JokeAPIHTTPClient()
        self.used_jokes = [12345]  # 12345 is so the while loop starts
        self.categories = ["any", "misc", "programming", "dark", "pun", "spooky", "christmas"]
        print('Jokes cog loaded')

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
            async with self.db.execute(f"""SELECT nsfw, religious, political, sexist, racist, explicit FROM blacklist
                                        WHERE id = {guild.id}""") as cursor:
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
                await self.db.execute(f"""INSERT INTO blacklist VALUES ({guild.id},
                {self.blacklist[guild.id]['nsfw']},
                {self.blacklist[guild.id]['religious']},
                {self.blacklist[guild.id]['political']},
                {self.blacklist[guild.id]['sexist']},
                {self.blacklist[guild.id]['racist']},
                {self.blacklist[guild.id]['explicit']});""")
            except IntegrityError:
                await self.db.execute(f"""UPDATE blacklist
                SET nsfw = {self.blacklist[guild.id]['nsfw']},
                    religious = {self.blacklist[guild.id]['religious']},
                    political = {self.blacklist[guild.id]['political']},
                    sexist = {self.blacklist[guild.id]['sexist']},
                    racist = {self.blacklist[guild.id]['racist']},
                    explicit = {self.blacklist[guild.id]['explicit']}
                    WHERE id = {guild.id};""")
        await self.db.commit()

    @update_db.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        self.db = await aiosqlite.connect('cogs/databases/joke_blacklist.db')
        await self.db.execute("""CREATE TABLE IF NOT EXISTS blacklist (
                                        id INTEGER PRIMARY KEY,
                                        nsfw BOOLEAN,
                                        religious BOOLEAN,
                                        political BOOLEAN,
                                        sexist BOOLEAN,
                                        racist BOOLEAN,
                                        explicit BOOLEAN
                                    );""")
        await self.db.commit()
        await self.fetch_blacklist()

    @update_db.after_loop
    async def after(self):
        await asyncio.sleep(0)
        await self.update_db()

    @commands.command()
    async def joke(self, ctx, *categories):
        for category in categories:
            if category.lower() not in self.categories:
                return await ctx.send(f"That isn't a category! The categories are `{'`, `'.join(self.categories)}`.")
        blacklist = self.blacklist.get(ctx.guild.id)
        if blacklist:
            blacklist_flags = [k for k, v in blacklist.items() if not v]
        else:
            blacklist_flags = None
        joke_id = 12345
        data = {}  # to make pycharm stop complaining
        while joke_id in self.used_jokes:
            data: dict = await self.http.get_joke(categories, blacklist_flags)
            joke_id = data.get('id')
        if data.get('error') is True:
            await ctx.send(data)
            return await ctx.send('An unexpected error occurred :( Try again later.')
        if data.get('type') == 'twopart':
            embed = discord.Embed(title=data.get('setup'))
            embed.set_footer(text=f'Category: {data.get("category")}')
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            embed2 = discord.Embed(title=data.get('delivery'))
            await msg.reply(embed=embed2)
        elif data.get('type') == 'single':
            embed = discord.Embed(title=data.get('joke'))
            embed.set_footer(text=f'Category: {data.get("category")}')
            await ctx.send(embed=embed)
        self.used_jokes.append(joke_id)

    @slash_util.slash_command(name='joke', description='Let me tell you a joke!')
    async def _joke(self, ctx: slash_util.Context):
        embed = discord.Embed(title='Select a Category')
        view = CategoryView(ctx.author)
        await ctx.send(embed=embed, view=view)
        await view.wait()
        categories = view.item.values
        if len(categories) > 1 and 'Any' in categories:
            return await ctx.send(f'{ctx.author.mention} You cannot select **Any** and other categories.')
        if len(categories) == 0:
            return await ctx.send("You didn't select anything =(")
        await self.joke(ctx, *categories)

    @commands.command(name='blacklist')
    async def _blacklist(self, ctx, *, flags: Union[BlacklistFlags, SlashFlagObject]):
        for k, v in vars(flags).items():
            if v is None:
                guild = self.blacklist.get(ctx.guild.id)
                if guild:
                    setattr(flags, k, guild.get(k))
                else:
                    if k in ('religious', 'sexist', 'racist'):
                        setattr(flags, k, False)
                    else:
                        setattr(flags, k, True)
            else:
                new = v.capitalize()
                if new == 'True':
                    new = True
                elif new == 'False':
                    new = False
                setattr(flags, k, new)
        options = vars(flags)
        embed = discord.Embed(title='New Joke Blacklist Settings',
                              description='**True = Turned on**\n' + '\n'.join(f'{k}: {v}' for k, v in options.items()))
        embed.set_footer(text='Choose an option')
        view = BlacklistView(ctx.author)
        msg = await ctx.send(embed=embed, view=view)
        secondary = False
        if options.get('nsfw') is True:
            await asyncio.sleep(1)
            nsfw_embed = discord.Embed(
                title='By having NSFW jokes turned on, you agree that all users are mature enough to handle them')
            await msg.reply(embed=nsfw_embed)
            secondary = True
        if options.get('religious') is True:
            await asyncio.sleep(1)
            religious_embed = discord.Embed(
                title='By having Religious jokes turned on, you agree that users may take offense from some jokes')
            await msg.reply(embed=religious_embed)
            secondary = True
        if options.get('political') is True:
            await asyncio.sleep(1)
            political_embed = discord.Embed(
                title='By having Political jokes turned on, you agree that users may have conflicting political views and may take offense')
            await msg.reply(embed=political_embed)
            secondary = True
        if options.get('sexist') is True:
            await asyncio.sleep(1)
            sexist_embed = discord.Embed(
                title='By having Sexist jokes turned on, you agree that users may take offense from some jokes')
            await ctx.send(embed=sexist_embed)
            secondary = True
        if options.get('racist') is True:
            await asyncio.sleep(1)
            racist_embed = discord.Embed(
                title='By having Racist jokes turned on, you agree that users may take offense from some jokes')
            await msg.reply(embed=racist_embed)
            secondary = True
        if options.get('explicit') is True:
            await asyncio.sleep(1)
            explicit_embed = discord.Embed(
                title='By having Explicit turned on, you agree that all users are mature enough to handle them')
            await msg.reply(embed=explicit_embed)
            secondary = True
        if secondary is True:
            await asyncio.sleep(1)
            alert_bed = discord.Embed(
                title='We are not responsible for any jokes that make any users or goups, feel discomfort or feel offended.')
            await ctx.send(embed=alert_bed)
        await view.wait()
        if view.choice is None:
            await msg.reply(embed=discord.Embed(title='Cancelled'))
            await view.disable_all(msg)
        elif view.choice is True:
            await msg.reply(embed=discord.Embed(title='New settings confirmed!'))
        elif view.choice is False:
            await msg.reply(embed=discord.Embed(title='New settings cancelled.'))
        self.blacklist[ctx.guild.id] = options

    @_blacklist.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need administrator perms to run this!!")
        else:
            raise error

    @slash_util.slash_command(name='blacklist', description='Turn off some possible jokes.')
    @slash_util.describe(nsfw='NSFW jokes',
                         religious='Religious jokes',
                         political='Political jokes',
                         sexist='Sexist jokes',
                         racist='Racist jokes',
                         explicit='Explicit jokes')
    async def __blacklist(self,
                          ctx: slash_util.Context,
                          nsfw: str = None,
                          religious: str = None,
                          political: str = None,
                          sexist: str = None,
                          racist: str = None,
                          explicit: str = None):

        if not ctx.author.guild_permissions.administrator:
            return await ctx.send('You need admin perms to run this!!')
        flags = SlashFlagObject(nsfw=nsfw,
                                religious=religious,
                                political=political,
                                sexist=sexist,
                                racist=racist,
                                explicit=explicit)
        await self._blacklist(ctx, flags=flags)


def setup(bot: MasterBot):
    bot.add_cog(Jokes(bot))
