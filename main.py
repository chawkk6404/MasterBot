import discord
from discord.ext import commands
import slash_util

from time import perf_counter
import logging
import requests


__version__ = '1.0.0a'


# logging
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


# two tokens for my two bots
TOKEN1 = 'OTI0MDM1ODc4ODk1MTEyMjUz.YcYteQ.JFJ5PrKgDX8lvQE-p5bQWKGFBBs'
TOKEN2 = 'ODc4MDM1MDY3OTc5NTYzMDY5.YR7T4Q.oD3Gk9-jNwpYOje5Iz9C8ZN-Xhc'

intents = discord.Intents.default()
intents.members = True

bot = slash_util.Bot(command_prefix=commands.when_mentioned_or('!'),
                     intents=intents,
                     help_command=None,
                     activity=discord.Game(f'version {__version__}'),
                     strip_after_prefix=True)
bot.__version__ = __version__
bot.start_time = perf_counter()


cogs = ['cogs.reaction_roles',
        'cogs.moderation',
        'cogs.code',
        'cogs.translate',
        'cogs.trivia',
        'cogs.help_info',
        'cogs.clash_royale',
        'cogs.jokes',
        'cogs.auto',
        'cogs.webhook']

if __name__ == '__main__':
    for cog in cogs:
        bot.load_extension(cog)


@bot.event
async def on_ready():
    print('Logged in as {0} ID: {0.id}'.format(bot.user))


@bot.listen('on_ready')
async def time():
    bot.on_ready_time = perf_counter()
    print('Time taken to ready up:', round(bot.on_ready_time - bot.start_time, 1), 'seconds')


bot.run(TOKEN1)
