from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord import app_commands

if TYPE_CHECKING:
    from bot import MasterBot


class Cog(commands.Cog):
    def __init__(self, bot: MasterBot):
        self.bot = bot

    async def cog_load(self):
        if hasattr(self, "http"):
            await self.http.create()

    async def cog_unload(self):
        if hasattr(self, "http"):
            await self.http.close()

    @classmethod
    async def setup(cls, bot: MasterBot):
        self = cls(bot)
        await bot.add_cog(self)


class NoPrivateMessage(app_commands.CheckFailure):
    def __init__(self, message=None):
        self.message = message or "This command can only be used in a server."
        super().__init__(message)


class QuickObject:
    def __init__(self, **attrs):
        self.__attrs = attrs

        for k, v in attrs.items():
            setattr(self, k, v)

    def __str__(self):
        # need to turn into message command flags for flag parser
        return " ".join(
            f"{k}: {v}" for k, v in self.__attrs.items() if v not in (None, "")
        )


def hybrid_has_permissions(**perms):
    async def predicate(ctx: commands.Context):
        return await commands.has_permissions(**perms).predicate(ctx)

    async def inner(func):
        func = app_commands.default_permissions(**perms)
        func = commands.check(predicate)(func)
        return func

    return inner
