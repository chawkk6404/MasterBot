import discord
from discord.ext import commands
from cogs.utils.app_and_cogs import Cog, command
from bot import MasterBot
import aiofiles
from typing import Literal
from cogs.utils.help_utils import HelpSingleton


class Help(metaclass=HelpSingleton):
    def __init__(self, prefix):
        self.prefix = prefix

    def new(self):
        if self.prefix != '/':
            message = f'`{self.prefix}new <version>`: see whats new in a version'
        else:
            message = f'`{self.prefix}whatsnew <version>`: see whats new in a version'
        return message

    def full_help(self):
        return self.new()


class Version(Cog, name='version', help_command=Help):
    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        print('Version cog loaded')

    @commands.command(aliases=['whatsnew'])
    async def new(self, ctx, version):
        path = version.replace('.', '-')
        path += '.txt'
        path = 'version/' + path
        try:
            async with aiofiles.open(path, 'r') as v:
                embed = discord.Embed(title=version,
                                      description=await v.read())
        except FileNotFoundError:
            await ctx.send('That version was not found.')
            return
        await ctx.send(embed=embed)

    @command(name='whatsnew', description='Findout whats new in a version! Starts for 1.4.0')
    async def _new(self, interaction, version: Literal[
        "1.4.0",
        "1.4.1",
        "1.4.2",
        "1.4.3",
        "1.5.0",
        "1.5.1"
    ]):
        path = version.replace('.', '-')
        path += '.txt'
        path = 'version/' + path
        try:
            async with aiofiles.open(path, 'r') as v:
                embed = discord.Embed(title=version,
                                      description=await v.read())
        except FileNotFoundError:
            await interaction.response.send_message('An unexpected error occurred with opening files. Try again later.')
            raise
        await interaction.response.send_message(embed=embed)


async def setup(bot: MasterBot):
    await Version.setup(bot)
