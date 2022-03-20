import asyncio
from concurrent.futures import TimeoutError
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Union
import re
import os as __os__
import sys as __sys__
from bot import MasterBot
from cogs.utils.help_utils import HelpSingleton
import aiofiles
import builtins
import io
from cogs.utils.cog import Cog, command
import threading


class Help(metaclass=HelpSingleton):
    def __init__(self, prefix):
        self.prefix = prefix

    def eval_help(self):
        message = f'`{self.prefix}eval <code>`: Code in python with the discord bot! (Command may not work). (Certain words will cause the code to not run to protect our system. [Click here for more](https://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html))'
        return message

    def canrun_help(self):
        message = f'`{self.prefix}canrun [user] <command>`: User is optional. Check if you or the user can run the command.'
        return message

    def search_help(self):
        message = f'`{self.prefix}search <regex> <text>`: Use regular expressions `re.search()`. Example: `!search [a-z][0-9][A-Z] a0Z`'
        return message

    def match_help(self):
        message = f'`{self.prefix}match <regex> <text>`: Use regular expressions `re.match()`. Same as `search` but full match.'
        return message

    def code_help(self):
        message = f'`{self.prefix}code <file> [lines]`: Get some code from the bot.'
        return message

    def created_help(self):
        message = f'`{self.prefix}created <snowflake>`: Snowflake can be a user or a made up ID. Get the time a snowflake was create at.'
        return message

    def full_help(self):
        help_list = [self.eval_help(), self.canrun_help(), self.search_help(), self.match_help(), self.code_help(), self.created_help()]
        return '\n'.join(help_list)


class EventLoopThread(threading.Thread):
    def __init__(self, *args, loop: asyncio.AbstractEventLoop = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = loop or asyncio.new_event_loop()
        self.running = False

    def run(self):
        self.running = True
        self.loop.run_forever()

    def run_coro(self, coro, timeout: Optional[int] = None):
        return asyncio.run_coroutine_threadsafe(coro, loop=self.loop).result(timeout=timeout)

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.join()
        self.running = False

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# print to the string io instead of the console only locally


async def aexec(code, string_io: io.StringIO):
    # https://stackoverflow.com/questions/44859165/async-exec-in-python
    # Make an async function with the code and `exec` it

    def string_io_print(*args, **kwargs):
        kwargs['file'] = string_io
        print(*args, **kwargs)

    _globals = vars(builtins).copy()
    _globals['print'] = string_io_print

    exec(

        f'async def __ex(): ' +
        ''.join(f'\n {l}' for l in code.split('\n')),
        _globals,
        locals()
    )
    # Get `__ex` from local variables, call it and return the result
    return await locals()['__ex']()


class CodeBlock:
    """Credits to Rapptz the creator of RoboDanny"""
    missing_error = 'Missing code block. Please use the following markdown\n\\`\\`\\`py\ncode here\n\\`\\`\\`'

    def __init__(self, argument):
        try:
            block, code = argument.split('\n', 1)
        except ValueError:
            raise commands.BadArgument(self.missing_error)

        if not block.startswith('```') and not code.endswith('```'):
            raise commands.BadArgument(self.missing_error)
        self.source = code.rstrip('`').replace('```', '')


class SlashCodeBlock:
    def __init__(self, argument):
        self.source = argument


class Code(Cog, help_command=Help, name='code'):
    """
    Many of the commands are owner only
    """
    forbidden_imports = ['os', 'sys', 'subprocess', 'setuptools', 'distutils', 'threading', 'multiprocessing', 'Cython']
    forbidden_words = ['ctx', '__os__', '__sys__', 'self', 'open(', 'sys']

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        print('Code cog loaded')

    async def cog_command_error(self, ctx: commands.Context, error):
        error: commands.CommandError

        if not ctx.command:
            return
        if ctx.command.has_error_handler():
            return
        if isinstance(error, (commands.MissingPermissions, commands.MissingRequiredArgument, commands.NotOwner)):
            return
        else:
            if not ctx.command.has_error_handler():
                await self.bot.on_command_error(ctx, error)

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command(name='eval')
    async def _eval(self, ctx, *, code: Union[CodeBlock, SlashCodeBlock]):
        """
        This command will need lots of working on.
        """
        async with ctx.typing():
            if len(code.source.split('\n')) > 300:
                await ctx.send("You can't eval over 300 lines.")
                return
            if any([word in code.source for word in self.forbidden_words]):
                await ctx.send('Your code has a word that would be risky to eval.')
                return
            if any([f'import {word}' in code.source or f'__import__("{word}")' in code.source or f"__import__('{word}')" in code.source for word in self.forbidden_imports]):
                await ctx.send("You can't import that.")
                return

            temp_out = io.StringIO()
    
            try:
                try:
                    async with EventLoopThread() as thr:
                        await self.bot.loop.run_in_executor(None, thr.run_coro, aexec(code.source, temp_out), 60)
                        # to prevent blocking event loop if they use time.sleep etc
                except TimeoutError:
                    await ctx.reply('Your code took too long to run.')
                    return
            except Exception as e:
                await ctx.reply(f'Your code raised an exception\n```\n{e.__class__.__name__}: {e}\n```')
                return

            value = temp_out.getvalue()

            value = value or 'No output'
            await ctx.reply(f'```\n{value}\n```')

            temp_out.close()

    @_eval.error
    async def error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            if await self.bot.is_owner(ctx.author):
                await ctx.reinvoke()
                return
            await ctx.send('Patience. Wait {:.1f} seconds'.format(error.retry_after))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
        else:
            await ctx.send('Command raised an exception\n```\n{}\n```'.format(error))

    @commands.command()
    async def canrun(self, ctx, user: Optional[discord.User], *, acommand):
        command: Union[commands.Command, commands.Group] = self.bot.all_commands.get(acommand)
        if command is None:
            embed = discord.Embed(title=f'Command `{acommand}` not found.')
            await ctx.send(embed=embed)
            return
        ctx.author = user or ctx.author
        await command.can_run(ctx)
        await ctx.send(f'{user} can run this command!')

    @canrun.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title='Your too weak!',
                                  description=str(error))
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(title='Missing something',
                                  description=f'`{self.bot.command_prefix}canrun [user] <command>`')
            await ctx.send(embed=embed)
        elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            await ctx.send("I couldn't find that person =(")
        else:
            raise error

    @commands.command()
    async def search(self, ctx, regex, *, text):
        returned = re.search(regex, text)
        await ctx.send(str(returned))

    @command(name='search', description='Use regex to search text')
    @app_commands.describe(regex='The regular expression', text='The text to search.')
    async def _search(self, interaction, regex: str, text: str):
        returned = re.search(regex, text)
        await interaction.response.send_message(str(returned))

    @commands.command()
    async def match(self, ctx, regex, *, text):
        returned = re.fullmatch(regex, text)
        await ctx.send(str(returned))

    @command(name='match', description='Use regex to match text')
    @app_commands.describe(regex='The regular expression', text='The text to match.')
    async def _match(self, interaction, regex: str, text: str):
        returned = re.match(regex, text)
        await interaction.response.send_message(str(returned))

    @commands.command()
    @commands.is_owner()
    async def logger(self, ctx, last=5):
        with aiofiles.open('logs/discord.log', 'r') as l:
            log = await l.read()
        log = log.split('\n')
        log.reverse()
        full = [log[i] for i in range(1, last)]
        legnth = [i for i in range(len(log)-last, len(log))]
        lined = '\n'.join(f'Line {legnth[i]}: {full[i]}' for i in range(len(full)))
        await ctx.send('```\n{}\n```'.format(lined))

    @commands.command(name='os')
    @commands.is_owner()
    async def _os(self, ctx, *, what):
        await self.bot.loop.run_in_executor(None, __os__.system, what)

    @commands.command()
    @commands.is_owner()
    async def close(self, ctx):
        await ctx.send('Closing. Bye bye!')
        await self.bot.close()
        __sys__.exit()

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, *exts):
        for ext in exts:
            await self.bot.reload_extension(f'cogs.{ext}')
        await ctx.send(f'Extensions reloaded: {", ".join(exts)}')

    @commands.command()
    async def load(self, ctx, *exts):
        for ext in exts:
            await self.bot.load_extension(f'cogs.{ext}')
        await ctx.send(f'Extensions loaded: {", ".join(exts)}')

    @commands.command()
    async def unload(self, ctx, *exts):
        for ext in exts:
            await self.bot.unload_extension(f'cogs.{ext}')
        await ctx.send(f'Extensions unloaded: {", ".join(exts)}')

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        """Nearly a full restart. Just without restarting the connection."""
        await ctx.send('Ok!')
        try:
            self.bot.restart()
        except Exception as exc:
            await ctx.send(f'An Error!?\n```\n{exc}\n```')

    @commands.group()
    async def git(self, ctx):
        pass

    @git.command()
    @commands.is_owner()
    async def add(self, ctx, path):
        await self.bot.loop.run_in_executor(None, __os__.system, 'git add {}'.format(path))
        await ctx.send('Files in {} were added to the next commit.'.format(path))

    @git.command()
    @commands.is_owner()
    async def commit(self, ctx, *, message):
        await self.bot.loop.run_in_executor(None, __os__.system, 'git commit -m "{}"'.format(message))
        await ctx.send('Changes have been committed with the messageg {}'.format(message))

    @git.command()
    @commands.is_owner()
    async def push(self, ctx, force=False):
        command = 'git push'
        if force == 'force':
            command += ' -f'
        await self.bot.loop.run_in_executor(None, __os__.system, command)
        await ctx.send('Files pushed. Force push = {}.'.format(force == 'force'))

    @commands.command(name='code')
    async def _code(self, ctx, file_path, lines=None):
        if lines is None:
            pass
        elif '-' in lines:
            lines = [int(line) for line in lines.split('-')]
        else:
            lines = int(lines)
        try:
            async with aiofiles.open(file_path, 'r') as file:
                content = (await file.read()).split('\n')
        except FileNotFoundError:
            await ctx.send("I couldn't find that file.")
            return
        if isinstance(lines, list):
            content = '\n'.join(content[lines[0]+1:lines[1]+1])
        elif lines is None:
            content = '\n'.join(content)
        else:
            content = content[lines]
        content = content.replace('`', r'\`')
        try:
            embed = discord.Embed(title=f'Code for {file_path}',
                                  description=f'```py\n{content}\n```')
            await ctx.send(embed=embed)
        except discord.HTTPException:
            await ctx.send('Too much to send.')

    @_code.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('You forgot "{}"'.format(error.param))
        else:
            raise error

    @command(name='eval', description='Run a Python file')
    async def __eval(self, interaction: discord.Interaction, file: discord.Attachment):
        if not file.filename.endswith('.py'):
            await interaction.response.send_message('It must be a `python` file.')
            return
        code = await file.read()
        code = SlashCodeBlock(code.decode('utf-8'))
        if len(code.source.split('\n')) > 300:
            await interaction.response.send_message("You can't eval over 300 lines.")
            return
        if any([word in code.source for word in self.forbidden_words]):
            await interaction.response.send_message('Your code has a word that would be risky to eval.')
            return
        if any([
                   f'import {word}' in code.source or f'__import__("{word}")' in code.source or f"__import__('{word}')" in code.source
                   for word in self.forbidden_imports]):
            await interaction.response.send_message("You can't import that.")
            return

        await interaction.response.defer(thinking=True)

        temp_out = io.StringIO()

        try:
            try:
                async with EventLoopThread() as thr:
                    await self.bot.loop.run_in_executor(None, thr.run_coro, aexec(code.source, temp_out), 60)
                    # to prevent blocking event loop if they use time.sleep etc
            except TimeoutError:
                await interaction.followup.send('Your code took too long to run.')
                return
        except Exception as e:
            await interaction.followup.send(f'Your code raised an exception\n```\n{e.__class__.__name__!r}: {e}\n```')
            return

        value = temp_out.getvalue()
        value = value or 'No output'
        await interaction.followup.send(f'```\n{value}\n```')

        temp_out.close()

    @commands.command()
    async def sync(self, ctx, guild: bool = None):
        if guild:
            guild = self.bot.test_guild
        data = await self.bot.tree.sync(guild=guild)
        await ctx.send(data)

    @commands.command()
    async def created(self, ctx, user: Union[discord.User, int]):
        user = user.id if isinstance(user, discord.User) else user
        created_at = discord.utils.snowflake_time(user)
        timestamp = discord.utils.format_dt(created_at, 'R')
        await ctx.reply(timestamp, mention_author=False)

    @created.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('You need to give me a `user` or `id`')
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"I couldn't make that into a user or id")
        else:
            raise error

    @command(name='created', description='See when a discord user or snowflake was created at')
    @app_commands.describe(user='A discord user', snowflake='A discord ID')
    async def _created(self, interaction, user: discord.User = None, snowflake: int = None):
        if not user and not snowflake:
            await interaction.response.send_message('You must give a user or snowflake', ephemeral=True)
        if not snowflake:
            snowflake = user.id

        created_at = discord.utils.snowflake_time(snowflake)
        timestamp = discord.utils.format_dt(created_at, 'R')
        await interaction.response.send_message(timestamp)

    @commands.command()
    async def binaryint(self, ctx, integer: int):
        await ctx.send(f'{integer:b}')

    @commands.command(aliases=['hexadecimal'])
    async def hexint(self, ctx, integer: int):
        await ctx.send(str(hex(integer)))

    @commands.command(aliases=['octal'])
    async def octint(self, ctx, integer: int):
        await ctx.send(str(oct(integer)))

    @binaryint.error
    @hexint.error
    @octint.error
    async def error(self, ctx, error):
        await ctx.send(str(error))

    @commands.command(name='setup')
    @commands.is_owner()
    async def _setup(self, ctx):
        lines = """
from setuptools import setup
from Cython.Build import cythonize
  
setup(ext_modules=cythonize('cogs/utils/math_extensions.pyx'), zip_safe=False)
        """

        # creating a new file
        async with aiofiles.open('setup.py', 'w') as cy_setup:
            await cy_setup.write(lines)
        try:
            __os__.system(' python setup.py build_ext --inplace')
        except Exception as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        finally:
            try:
                __os__.remove('setup.py')
            except FileNotFoundError:
                pass


async def setup(bot: MasterBot):
    await Code.setup(bot)
