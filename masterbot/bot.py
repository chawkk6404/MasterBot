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
