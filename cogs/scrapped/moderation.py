import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Union
import asyncio
from motor import motor_asyncio
from pymongo.errors import DuplicateKeyError, OperationFailure
from bot import MasterBot
from cogs.utils.help_utils import HelpSingleton
from cogs.utils.app_and_cogs import Cog, command
import datetime
from cogs.code import EventLoopThread


class Help(metaclass=HelpSingleton):
    def __init__(self, prefix):
        self.prefix = prefix

    def log_help(self):
        message = (
            f"`{self.prefix}log create <channel>`: Make the channel the channel to send all log message to"
            f"`{self.prefix}log remove`: Remove the servers log"
        )
        return message

    def kick_help(self):
        message = f"`{self.prefix}kick <member> [reason]`: Kick a member"
        return message

    def ban_help(self):
        message = f"`{self.prefix}ban <member> [reason]`: Ban a member"
        return message

    def massban_help(self):
        message = f"`{self.prefix}massban <members> [reason]`: Ban many members. Separate each member with a space"
        return message

    def softban_help(self):
        message = f"`{self.prefix}softban <member> [reason]`: Ban a member then unban them. This can be used against hacked accounts"
        return message

    def unban_help(self):
        message = f"`{self.prefix}unban <member> [reason]`: Unban a member"
        return message

    def hackban_help(self):
        message = f"`{self.prefix}hackban <user> [reason]`: Ban a user that is not in the server"
        return message

    def timeout_help(self):
        message = f"`{self.prefix}timeout <member> <minutes> [reason]`: Put a member on timeout. Similar to the old muting"
        return message

    def addrole_help(self):
        message = f"`{self.prefix}addrole <member> <roles>`: Add roles to a member. Separate each role with a space"
        return message

    def removerole_help(self):
        message = f"`{self.prefix}removerole <member> <roles>`: Remove roles from a member. Separate each role with a space"
        return message

    def lock_help(self):
        message = f"`{self.prefix}lock <channels> [roles]`: Lock channels for certain roles or everyone. Roles and channels should be separated by a space"
        return message

    def unlock_help(self):
        message = f"`{self.prefix}unlock <channels> [roles>]`: Unlock channels for certain roles or everyone. Roles and channels should be separated by a space"
        return message

    def clear_help(self):
        message = f"`{self.prefix}clear <argument>`: Clear messages in a channel. Argument can be a user, a role, or a integer"
        return message

    def full_help(self):
        help_list = [
            self.kick_help(),
            self.ban_help(),
            self.massban_help(),
            self.softban_help(),
            self.hackban_help(),
            self.timeout_help(),
            self.addrole_help(),
            self.removerole_help(),
            self.lock_help(),
            self.unlock_help(),
        ]
        return (
            "\n".join(help_list)
            + "\n**Most commands not available with Slash Commands**"
        )


class Moderation(Cog, help_command=Help, name="moderation"):
    """Will be changed to cache instead of db call in v2 or earlier
    UPDATE: COG IS DEPRECATED"""

    def __init__(self, bot: MasterBot):
        super().__init__(bot)
        self.client = None
        self.log = None
        print("Moderation cog loaded")

    async def cog_load(self):
        # last update ever
        await super().cog_load()

        async def blocker():
            self.client = motor_asyncio.AsyncIOMotorClient(self.bot.moderation_mongo)
            self.log = self.client["moderation"]["channels"]

        async with EventLoopThread() as thr:
            self.bot.loop.run_in_executor(None, thr.run_coro, blocker())

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            await self.log.delete_many({"_id": str(guild.id)})
        except OperationFailure:
            pass

    async def cog_command_error(self, ctx, error):
        error: commands.CommandError  # showing as `Exception` for some reason

        if ctx.command is None:
            return
        if isinstance(error, commands.errors.MissingPermissions):
            return
        elif isinstance(error, commands.errors.BotMissingPermissions):
            embed = discord.Embed(
                title=str(error), description="Give those permissions to me"
            )
            await ctx.send(embed=embed)
            return
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            if not ctx.command.has_error_handler():
                await ctx.send(str(error))
                return
        else:
            if not ctx.command.has_error_handler():
                await self.bot.on_command_error(ctx, error)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def log(self, ctx, option, channel: discord.TextChannel = None):
        if option == "remove":
            await self.log.delete_many({"_id": str(ctx.guild.id)})
            await ctx.send("Done!")
        if option == "create":
            if channel is None:
                return await ctx.send(
                    "You didn't give me a channel or I couldn't find the channel =("
                )
            if channel.guild != ctx.guild:
                return await ctx.send("The channel must be in this server.")
            try:
                await channel.send("Log will be sent here.")
            except discord.errors.Forbidden:
                return await ctx.send("I can't send message in that channel. =(")
            try:
                await self.log.insert_one(
                    {"_id": str(ctx.guild.id), "channel": str(channel.id)}
                )
            except DuplicateKeyError:
                await self.log.update_one(
                    {"_id": str(ctx.guild.id)}, {"$set": {"channel": str(channel.id)}}
                )
            await ctx.send(f"Log message will be sent in {channel.mention}")

    @log.error
    async def error(self, ctx, error):
        if isinstance(error, commands.ChannelNotFound):
            await ctx.send("I couldn't find that channel. I wonder why..")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.top_role.position <= member.top_role.position:
            return await ctx.send(
                "I can't let you do that. Your top role is lower or equal to theirs in the hierarchy."
            )
        await member.kick(reason=reason)
        await ctx.send(f"{member} got kicked.")
        if ctx.guild.id in self.log.keys():
            embed = discord.Embed(
                title=f"{member} was kicked by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await ctx.send(embed=embed)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{member} was kicked by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @kick.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).kick_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Member not found?")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        member: discord.Member,
        delete_after: Optional[int] = 1,
        *,
        reason=None,
    ):
        if ctx.author.top_role.position <= member.top_role.position:
            return await ctx.send(
                "I can't let you do that. Your top role is lower or equal to theirs in the hierarchy."
            )
        if delete_after < 1 or delete_after > 7:
            return await ctx.send("Delete After Days must be from 1-7")
        await member.ban(reason=reason, delete_message_days=delete_after)  # type: ignore
        await ctx.send(f"{member} got banned.")
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{member} was banned by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @ban.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).ban_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Member not found?")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def massban(
        self, ctx, members: commands.Greedy[discord.Member], *, reason=None
    ):
        for member in members:
            if ctx.author.top_role.position <= member.top_role.position:
                return await ctx.send(
                    f"I can't let you ban {member}. Your top role is lower or equal to theirs in the hierarchy."
                )
        embed = discord.Embed(title="This may take a while", description="Sit tight")
        await ctx.send(embed=embed)
        for member in members:
            member.ban(reason=reason)
            await asyncio.sleep(1)
        await ctx.reply("The members got banned =)")
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"The following members were banned by {ctx.author}",
                description="{0}\n{1}".format(
                    "\n".join(members), reason or "Reason not provided"
                ),
            )  # type: ignore
            await channel.send(embed=embed)

    @massban.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).massban_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Member(s) not found?")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def softban(self, ctx, member: discord.Member, *, reason=None):
        if ctx.author.top_role.position <= member.top_role.position:
            return await ctx.send(
                "I can't let you do that. Your top role is lower or equal to theirs in the hierarchy."
            )
        await member.ban(reason=reason)
        await ctx.guild.unban(member, reason=reason)
        await ctx.send("Ok done.")
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{member} was softbanned by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @softban.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).softban_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Member not found?")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason=None):
        await ctx.guild.unban(user, reason=reason)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{user} was unbanned by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @unban.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).unban_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("User does not exist apparently.")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def hackban(self, ctx, user: discord.User, *, reason=None):
        await ctx.guild.ban(user, reason=reason)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{user} was hackbanned by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @hackban.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).hackban_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("User does not exist apparently.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(
        self, ctx, member: discord.Member, minutes: int = None, *, reason: str = None
    ):
        if ctx.author.top_role.position <= member.top_role.position:
            await ctx.send(
                "I can't let you do that. Your top role is lower or equal to theirs in the hierarchy."
            )
            return
        if minutes:
            if minutes > 40320:
                await ctx.send("You can't timeout for 28 days or more sadly.")
                return
            timed_out_until = discord.utils.utcnow() + datetime.timedelta(
                minutes=minutes
            )
            await ctx.send(
                f"{member.display_name} got a timeout! I'll let them back in {minutes} minutes."
            )
            message = "was put on timeout by"
        else:
            timed_out_until = None
            await ctx.send(f"{member.display_name} was removed from timeout.")
            message = "was removed from timeout by"
        await member.edit(timed_out_until=timed_out_until, reason=reason)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{member} {message} by {ctx.author}",
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @command(name="timeout", description="Put a user on timeout!")
    @app_commands.describe(
        member="The member",
        minutes="The time. If not provided then will removed timeout",
        reason="Optional reason",
    )
    async def _timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = None,
    ) -> None:
        if interaction.user.guild_permissions.moderate_members:
            if interaction.user.top_role.position <= member.top_role.position:
                await interaction.response.send_message(
                    "I can't let you do that. Your top role is lower or equal to theirs in the hierarchy."
                )
                return
            if minutes > 40320:
                await interaction.response.send_message(
                    "You can't timeout for 28 days or more sadly."
                )
                return
            timed_out_until = datetime.timedelta(minutes=minutes)
            await member.timeout(timed_out_until, reason=reason)
            await interaction.response.send_message(
                f"{member} got a timeout! I'll let them back in {minutes} minutes."
            )
            log = await self.log.find_one({"_id": str(interaction.guild.id)})
            if log:
                channel = self.bot.get_channel(int(log.get("channel")))
                embed = discord.Embed(
                    title=f"{member} was put on timeout by {interaction.user}",
                    description=reason or "Reason not provided",
                    timestamp=discord.utils.utcnow(),
                )
                await channel.send(embed=embed)
        await interaction.response.send_message("You can't use this")

    @timeout.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).timeout_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("I didn't find the member.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def mute(self, ctx):
        await ctx.send(
            f"This command has been removed because of the timeout feature. Try {ctx.clean_prefix}timeout instead"
        )

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def addrole(
        self,
        ctx,
        member: discord.Member,
        roles: commands.Greedy[discord.Role],
        *,
        reason=None,
    ):
        for role in roles:
            if role.position >= ctx.guild.me.top_role.position:
                embed = discord.Embed(title="The role(s) must be below my top role =|")
                return await ctx.send(embed=embed)
            if ctx.author.top_role.position <= role.position:
                embed = discord.Embed(title="The role(s) must be below ur role")
                return await ctx.send(embed=embed, delete_after=10)
        await member.add_roles(*roles, reason=reason)
        await ctx.send(
            "{} added to {}!".format(",".join([role.name for role in roles]), member)
        )
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title="{} added {} to {}".format(
                    ctx.author, ", ".join([role.name for role in roles]), member
                ),
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @addrole.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).addrole_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("I didn't find the member.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def removerole(
        self,
        ctx,
        member: discord.Member,
        roles: commands.Greedy[discord.Role],
        *,
        reason=None,
    ):
        for role in roles:
            if role.position >= ctx.guild.me.top_role.position:
                embed = discord.Embed(title="The role(s) must be below my top role =|")
                return await ctx.send(embed=embed)
            if ctx.author.top_role.position <= role.position:
                embed = discord.Embed(title="The role(s) must be below ur role")
                return await ctx.send(embed=embed, delete_after=10)
        await member.add_roles(*roles, reason=reason)
        await member.remove_roles(*roles, reason=reason)
        await ctx.send(
            "{} removed from {} =(".format(
                ", ".join([role.mention for role in roles]), member
            )
        )
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title="{} removed {} from {}".format(
                    ctx.author, ", ".join([role for role in roles]), member
                ),
                description=reason or "Reason not provided",
                timestamp=ctx.message.created_at,
            )
            await channel.send(embed=embed)

    @removerole.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).removerole_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("I didn't find the member.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(
        self,
        ctx,
        channels: commands.Greedy[discord.TextChannel] = None,
        roles: commands.Greedy[discord.Role] = None,
    ):
        channels = channels or [ctx.channel]
        roles = roles or [ctx.guild.default_role]
        for role in roles:
            if role.position >= ctx.guild.me.top_role:
                embed = discord.Embed(title="The role(s) must be below my top role =|")
                return await ctx.send(embed=embed, delete_after=10)
        for role in roles:
            overwrite = ctx.channel.overwrites_for(role)
            overwrite.send_messages = False
            for channel in channels:
                await channel.set_permissions(role, overwrite=overwrite)
        embed = discord.Embed(
            title="The following channels have been locked for {} by {}".format(
                ", ".join([role.name for role in roles]), ctx.author
            ),
            description=", ".join([channel.mention for channel in channels]),
            timestamp=ctx.message.created_at,
        )
        await ctx.send(embed=embed)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            await channel.send(embed=embed)

    @lock.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).lock_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send("That role doesn't exist.")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send("That channel doesn't exist.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(
        self,
        ctx,
        channels: commands.Greedy[discord.TextChannel] = None,
        roles: commands.Greedy[discord.Role] = None,
    ):
        channels = channels or [ctx.channel]
        roles = roles or [ctx.guild.default_role]
        for role in roles:
            if role.position >= ctx.guild.me.top_role:
                embed = discord.Embed(title="The role(s) must be below my top role =|")
                return await ctx.send(embed=embed, delete_after=10)
        for role in roles:
            overwrite = ctx.channel.overwrites_for(role)
            overwrite.send_messages = True
            for channel in channels:
                await channel.set_permissions(role, overwrite=overwrite)
        embed = discord.Embed(
            title="The following channels have been unlocked for {} by {}".format(
                ", ".join([role.name for role in roles]), ctx.author
            ),
            description=", ".join([channel.mention for channel in channels]),
            timestamp=ctx.message.created_at,
        )
        await ctx.send(embed=embed)
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            await channel.send(embed=embed)

    @unlock.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).unlock_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send("That role doesn't exist.")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send("That channel doesn't exist.")

    @commands.command(aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def clear(
        self,
        ctx: commands.Context,
        arg: Optional[Union[discord.Member, discord.Role, discord.TextChannel]],
        limit: int = 100,
    ):
        await ctx.message.delete()
        if arg is None:
            check = lambda m: True
        else:
            check = lambda m: m.id == arg.id
        await ctx.channel.purge(check=check, limit=limit)
        await ctx.send(f"Done! That was fun! Cleared {limit} messages!")
        if arg is not None:
            await ctx.send(f"Messages deleted from {arg.name} {arg.__class__.__name__}")
        log = await self.log.find_one({"_id": str(ctx.guild.id)})
        if log:
            channel = self.bot.get_channel(int(log.get("channel")))
            embed = discord.Embed(
                title=f"{ctx.author} cleared messages some messages",
                description=arg.mention,
            )
            await channel.send(embed=embed)

    @clear.error
    async def error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="You missed a argument stupid.",
                description=Help(ctx.prefix).clear_help(),
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="I need to rest.",
                description="Try again in {:.1f} seconds".format(error.retry_after),
            )
            await ctx.send(embed=embed)
        elif isinstance(
            error,
            (commands.RoleNotFound, commands.MemberNotFound, commands.ChannelNotFound),
        ):
            await ctx.send("I couldn't find that channel or member or role.")


async def setup(bot: MasterBot):
    await Moderation.setup(bot)
