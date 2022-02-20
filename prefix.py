import discord
from discord.ext import commands, tasks
from typing import List
import json


async def get_prefix(bot, msg: discord.Message) -> List[str]:
    prefixes = commands.when_mentioned(bot, msg)
    if msg.guild:
        _prefix = bot.prefixes.get(str(msg.guild.id))
        if _prefix is None:
            _prefix = '!'
            bot.prefixes[str(msg.guild.id)] = _prefix
    else:
        _prefix = '!'
    prefixes.append(_prefix)
    return commands.when_mentioned_or(*prefixes)(bot, msg)


class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_prefixes.start()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        del self.bot.prefixes[str(guild.id)]

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx: commands.Context, option):
        if option == 'reset':
            new_prefix = '!'
        else:
            new_prefix = option
        self.bot.prefixes[str(ctx.guild.id)] = new_prefix

    @prefix.error
    async def error(self, ctx, _error):
        if isinstance(_error, commands.MissingPermissions):
            await ctx.send('You need admin perms to change the prefix.')
        else:
            raise _error

    def fetch_prefixes(self):
        with open('databases/prefixes.json', 'r') as p:
            self.bot.prefixes = json.load(p)

    def update_file(self):
        with open('databases/prefixes.json', 'w') as p:
            json.dump(self.bot.prefixes, p)

    @tasks.loop(minutes=9)
    async def update_prefixes(self):
        await self.bot.loop.run_in_executor(None, self.update_file)

    @update_prefixes.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        await self.bot.loop.run_in_executor(None, self.fetch_prefixes)

    @update_prefixes.after_loop
    async def after(self):
        await self.update_prefixes()


