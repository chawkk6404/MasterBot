import discord
from discord.ext import commands
import slash_util

from cogs.reaction_roles import Help as RRHelp
from cogs.moderation import Help as MHelp
from cogs.code import Help as CHelp
from cogs.translate import Help as THelp
from cogs.trivia import Help as TrHelp
from cogs.clash_royale import Help as CRHelp

import sys
from async_google_trans_new import __version__ as agtn_version


class HelpAndInfo(slash_util.ApplicationCog):
    def __init__(self, bot):
        super().__init__(bot)
        print('Help and Info cog loaded')

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f'Pong! `{str(round(self.bot.latency * 1000))}ms`')

    @slash_util.slash_command(name='ping', description='Get the bots latency')
    async def _ping(self, ctx):
        await self.ping(ctx)

    @commands.command()
    async def info(self, ctx):
        embed = discord.Embed(title=f'{self.bot.user.name} Info')
        embed.add_field(name='Version Info', value=f'{self.bot.user.name} version {self.bot.__version__}\n'
                                                  f'[Python {sys.version.split(" ")[0]}](https://www.python.org)\n'
                                                  f'[discord.py {discord.__version__}](https://github.com/Rapptz/discord.py)\n'
                                                  f'[async-google-trans-new {agtn_version}](https://github.com/Theelx/async-google-trans-new)\n'
                                                  f'Platform {sys.platform}')
        embed.add_field(name='Stats', value=f'Servers {len(self.bot.guilds)}\nUsers {len(set(self.bot.users))}')
        await ctx.send(embed=embed)

    @slash_util.slash_command(name='info', description='Get info about the bot')
    async def _info(self, ctx):
        await self.info(ctx)

    @commands.group(name='help')
    async def _help(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title=f'{self.bot.user.name} Help Menu')
            embed.add_field(name='Categories',
                            value='`reactions`\n`moderation`\n`welcome`\n`code`\n`translation`\n`trivia`\n`cr`(Clash Royale)')
            embed.add_field(name='Info', value=f'`{self.bot.command_prefix(self.bot, ctx.message)[2]}info`')
            await ctx.send(embed=embed)

    @_help.command()
    async def reactions(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = RRHelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Reaction Role Help',
                              description=help_message)
        await ctx.send(embed=embed)

    @_help.command()
    async def moderation(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = MHelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Moderation Help',
                              description=help_message)
        await ctx.send(embed=embed)

    @_help.command()
    async def code(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = CHelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Code Help',
                              description=help_message)
        await ctx.send(embed=embed)

    @_help.command()
    async def translate(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = THelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Translate Help',
                              description=help_message)
        embed.set_footer(text='This bot uses Google Translate to do this')
        await ctx.send(embed=embed)

    @_help.command()
    async def trivia(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = TrHelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Trivia Help',
                              description=help_message)
        embed.set_footer(text='This bot uses opentdb.com to do this')
        await ctx.send(embed=embed)

    @_help.command()
    async def cr(self, ctx):
        prefix = self.bot.command_prefix(self.bot, ctx.message)[2]
        h = CRHelp(prefix)
        help_message = h.full_help()
        embed = discord.Embed(title='Clash Royale help',
                              description=help_message)
        embed.set_footer(text='This bot uses developer.clashroyale.com to do this')
        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(HelpAndInfo(bot))
