from __future__ import annotations

import slash_util
import discord
from discord.ext import commands
from time import perf_counter
from typing import Optional, Iterable
import os
from prefix import Prefix,  get_prefix


class DatabaseFolderNotFound(Exception):
    def __init__(self):
        message = 'create a directory named `databases` for the databases to be created and accessed'
        super().__init__(message)


class MissingConfigValue(Exception):
    def __init__(self, value):
        super().__init__(f'config value {value} is missing in config.json')


intents = discord.Intents.default()
intents.members = True


"""
https://azure.microsoft.com/en-us/free/virtual-machines/search/?OCID=AID2200277_SEM_93fccfc30f331d38359eadd231eb7f93:G:s&ef_id=93fccfc30f331d38359eadd231eb7f93:G:s&msclkid=93fccfc30f331d38359eadd231eb7f93
"""


class MasterBot(slash_util.Bot):
    __version__ = '1.0.0rc'

    def __init__(self, cr_api_key, weather_api_key):
        super().__init__(command_prefix=get_prefix,
                         intents=intents,
                         help_command=None,
                         activity=discord.Game(f'version {self.__version__}'),
                         strip_after_prefix=True)
        self.add_cog(Prefix(self))
        self.start_time = perf_counter()
        self.on_ready_time = None
        self.clash_royale = cr_api_key
        self.weather = weather_api_key
        self.prefixes = {}
        self.prefixes_db = None

    async def on_ready(self):
        print('Logged in as {0} ID: {0.id}'.format(self.user))
        self.on_ready_time = perf_counter()
        print('Time taken to ready up:', round(self.on_ready_time - self.start_time, 1), 'seconds')

    async def on_command_error(self, context: commands.Context, exception: commands.errors.CommandError) -> None:
        if isinstance(exception, commands.CheckFailure):
            return

    def run(self, token) -> None:
        cogs = [
            'cogs.clash_royale',
            'cogs.code',
            'cogs.help_info',
            'cogs.jokes',
            'cogs.moderation',
            'cogs.reaction_roles',
            'cogs.translate',
            'cogs.trivia',
            'cogs.weather',
            'cogs.webhook',
            'cogs.forms',
        ]
        for cog in cogs:
            self.load_extension(cog)
        if 'databases' not in os.listdir():
            raise DatabaseFolderNotFound()
        super().run(token)

    def restart(self):
        """Reloads all extensions and clears the cache"""
        extensions = list(self.extensions).copy()
        for ext in extensions:
            self.reload_extension(ext)
        self.clear()

    @property
    def oath_url(self):
        permissions = discord.Permissions(manage_roles=True,
                                          manage_channels=True,
                                          kick_members=True,
                                          ban_members=True,
                                          manage_webhooks=True,
                                          moderate_members=True,
                                          send_messages=True,
                                          add_reactions=True)
        scopes = ('bot', 'applications.commands')
        return discord.utils.oauth_url(self.user.id,
                                       permissions=permissions,
                                       scopes=scopes)

    def custom_oath_url(self, permissions: Optional[discord.Permissions] = None,
                        scopes: Optional[Iterable[str]] = None):
        return discord.utils.oauth_url(self.user.id,
                                       permissions=permissions,
                                       scopes=scopes)