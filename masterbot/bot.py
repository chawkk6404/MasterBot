"""
The MIT License (MIT)

Copyright (c) 2021-present The Master

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""


import slash_util
import discord
from discord.ext import commands
from time import perf_counter
from typing import Literal, Optional, Callable, Union, Iterable
import logging
import os
from .api_keys import MasterBotAPIKeyManager


class DatabaseFolderNotFound(Exception):
    def __init__(self):
        message = 'create a directory named `databases` for the databases to be created and accessed'
        super().__init__(message)


intents = discord.Intents.default()
intents.members = True


class MasterBot(slash_util.Bot):
    __version__ = '1.0.0b'

    def __init__(self, command_prefix: Optional[Union[str, Iterable, Callable]] = commands.when_mentioned_or('!'),
                 *,
                 cogs: Optional[Iterable[str]] = None,
                 log: Optional[str] = None,
                 api_keys: Optional[MasterBotAPIKeyManager] = MasterBotAPIKeyManager()
                 ):
        super().__init__(command_prefix=command_prefix,
                         intents=intents,
                         help_command=None,
                         activity=discord.Game(f'version {self.__version__}'),
                         strip_after_prefix=True)
        self.start_time = perf_counter()
        self.on_ready_time = None
        self.current_token: Optional[Literal[1, 2]] = None
        self._cogs_to_add = cogs or []
        if log:
            logger = logging.getLogger('discord')
            logger.setLevel(logging.DEBUG)
            handler = logging.FileHandler(filename=log, encoding='utf-8', mode='w')
            handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
            logger.addHandler(handler)
        if not isinstance(api_keys, MasterBotAPIKeyManager) and api_keys is not None:
            raise TypeError(f'`api_keys` expected `MasterBotAPIKeyManager not {api_keys.__class__.__name__!r}')
        self.api_keys: MasterBotAPIKeyManager = api_keys
        if not self.api_keys.weather:
            self._cogs_to_add.remove('masterbot.cogs.weather')
        if not self.api_keys.clash_royale:
            self._cogs_to_add.remove('masterbot.cogs.clash_royale')

    async def on_ready(self):
        print('Logged in as {0} ID: {0.id}'.format(self.user))
        self.on_ready_time = perf_counter()
        print('Time taken to ready up:', round(self.on_ready_time - self.start_time, 1), 'seconds')

    def run(self, token) -> None:
        for cog in self._cogs_to_add:
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

    def custom_oath_url(self, permissions: Optional[discord.Permissions] = None, scopes: Optional[Iterable[str]] = None):
        return discord.utils.oauth_url(self.user.id,
                                       permissions=permissions,
                                       scopes=scopes)