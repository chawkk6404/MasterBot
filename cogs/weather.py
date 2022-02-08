import discord
from discord.ext import commands, tasks
from cogs.utils.http import AsyncHTTPClient
from bot import MasterBot
import slash_util
from typing import Optional
import aiosqlite
from sqlite3 import IntegrityError


class FlagUnits(commands.FlagConverter):
    speed: Optional[str] = None
    temp: Optional[str] = None


class WeatherAPIHTTPClient(AsyncHTTPClient):
    def __init__(self):
        super().__init__('http://api.weatherapi.com/v1/')
        self.api_key = '77aaea92eeeb4a1d80b41211220602'

    async def request(self, route, json=True, **params):
        return await super().request(route=route,
                                     json=json,
                                     key=self.api_key,
                                     **params)

    async def current(self, location):
        return await self.request('current.json', q=location, aqi='yes')


class Weather(slash_util.ApplicationCog):
    metric = {'temp': 'C', 'speed': 'kph'}
    customary = {'temp': 'F', 'speed': 'mph'}

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.http = WeatherAPIHTTPClient()
        self.temp_units = {}
        self.speed_units = {}
        self.db = None
        self.update_db.start()
        print('Weather cog loaded')

    async def fetch_units(self):
        for guild in self.bot.guilds:
            cursor = await self.db.execute(f"""SELECT temp, speed FROM units
                                        WHERE id = {guild.id}""")
            temp, speed = await cursor.fetchone()
            self.temp_units[guild.id] = temp
            self.speed_units[guild.id] = speed

    @tasks.loop(minutes=4)
    async def update_db(self):
        for guild in self.bot.guilds:
            if guild not in self.temp_units:
                self.temp_units[guild.id] = self.metric['temp']
            if guild not in self.speed_units:
                self.speed_units[guild.id] = self.metric['speed']
            try:
                await self.db.execute(f"""INSERT INTO units VALUES ({guild.id},
                '{self.temp_units[guild.id]}',
                '{self.speed_units[guild.id]}')""")
            except IntegrityError:
                await self.db.execute(f"""UPDATE units
                SET temp = '{self.temp_units[guild.id]}', speed = '{self.speed_units[guild.id]}'
                WHERE id = {guild.id};""")
        await self.db.commit()

    @update_db.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        self.db = await aiosqlite.connect('cogs/databases/units.db')
        await self.db.execute("""CREATE TABLE IF NOT EXISTS units (
                                        id INTEGER PRIMARY KEY,
                                        temp TEXT,
                                        speed TEXT
                                    );""")
        await self.db.commit()
        await self.fetch_units()

    @update_db.after_loop
    async def after(self):
        await self.update_db()

    @commands.command()
    async def units(self, ctx, *, flags: FlagUnits):
        if not flags.temp and not flags.speed:
            return await ctx.send(f'You forgot the flag arguments. `{ctx.prefix}units <flags_args>`. **Args:**\n`temp` `C` or `F`\n`speed` `mph` or `kph``')
        if flags.temp:
            if flags.temp.upper() in ('C', 'F'):
                self.temp_units[ctx.guild.id] = flags.temp.upper()
            else:
                return await ctx.send('Temp can only be **c** or **f**')
        if flags.speed:
            if flags.speed.lower() in ('mph', 'kph'):
                self.speed_units[ctx.guild.id] = flags.speed.lower()
            else:
                return await ctx.send('Speed can only be **kph** or **mph**')
        await ctx.send(f'New settings! Temp: `{self.temp_units[ctx.guild.id]}` Speed: `{self.speed_units[ctx.guild.id]}`')

    @commands.command()
    async def current(self, ctx, *, location):
        data = await self.http.current(location)
        embed = discord.Embed(title=f'{data.get("location").get("name")}, {data.get("location").get("region")}, {data.get("location").get("country")}',
                              timestamp=ctx.message.created_at)

        await ctx.send(embed=embed)


def setup(bot: MasterBot):
    bot.add_cog(Weather(bot))