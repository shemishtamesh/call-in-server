import os
import logging
from time import sleep
import itertools
import discord
from discord import app_commands
from discord.ext import commands


class CallInServer(commands.Bot):
    def __init__(self, command_prefix):
        logging.basicConfig(level=logging.DEBUG)

        intents = discord.Intents().all()
        super().__init__(
            command_prefix="!@!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="!@!help"
            ),
        )

        self.uncallable_roles = {}
        self.can_call_everyone = False

        self.add_events()
        self.add_commands()

    def add_events(self):
        @self.event
        async def on_ready():
            logging.info(f"Logged in as {self.user}.")

        @self.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                await ctx.channel.send(
                    "Command not found. You can use `!@!help` to get a list"
                    + " of all available commands."
                )
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.channel.send(
                    "You must supply an argument, you can use `!@!help"
                    + " {command}` to get a discription of the command."
                )
            elif isinstance(error, commands.errors.MissingPermissions):
                await ctx.channel.send("Only administrators can use this command.")
            else:
                raise error

    def add_commands(self):
        @self.command(name="call")
        async def call(ctx: discord.ext.commands.Context, *, msg: str):
            """
            Syntax: !@!call {mention1} {mention2} {mention3}...
            Action: simulates a call.

            Can only call `callable` roles.
            """
            logging.debug(f"recieved: {msg}.")
            users_to_call = self.get_pinged_users(ctx)
            users_dm_channels_dict = {
                user: await user.create_dm() for user in users_to_call
            }

            if (
                not ctx.author.voice
            ):  # if the author is not conencted to a voice channel
                await ctx.channel.send(
                    "You have to be connected to a voice channel"
                    + " to use this command."
                )

            elif not self.can_call_everyone and ctx.message.mention_everyone:
                await ctx.channel.send("`@everyone` and `@here` are not callable.")
            else:
                await ctx.channel.send("Starting call.")
                unavailable_users_messages = await self.send_n_invites(
                    ctx, 5, users_dm_channels_dict
                )
                unavailable_users_message = ""
                for message in unavailable_users_messages:
                    unavailable_users_message += "\n" + message

                await ctx.channel.send("Call finished.")
                if unavailable_users_message:
                    await ctx.channel.send("Didn't call:" + unavailable_users_message)

        @self.command(name="uncallable")
        @commands.has_permissions(administrator=True)
        async def uncallable(ctx: discord.ext.commands.Context, *, msg: str):
            """
            Syntax: !@!uncallable {role_mention1} {role_mention3} {role_mention2}...
            Action: makes the mentioned roles uncallable.
            """
            if ctx.message.mention_everyone:
                if self.can_call_everyone:
                    self.can_call_everyone = False
                    await ctx.send(
                        "The roles `@everyone` and `@here` are now not callable"
                    )
                else:
                    await ctx.send(
                        "The role `@everyone` and `@here` are already not callable"
                    )

            if ctx.guild not in self.uncallable_roles:
                self.uncallable_roles[ctx.guild] = []

            for role in ctx.message.role_mentions:
                if role not in self.uncallable_roles[ctx.guild]:
                    self.uncallable_roles[ctx.guild].append(role)
                    await ctx.send(f"The role `{role}` is now not callable")
                else:
                    await ctx.send(f"The role `{role}` is already not callable")

        @self.command(name="recallable")
        @commands.has_permissions(administrator=True)
        async def recallable(ctx: discord.ext.commands.Context, *, msg: str):
            """
            Syntax: !@!recallable {role_mention1} {role_mention3} {role_mention2}...
            Action: makes the mentioned roles callable.
            """
            if ctx.message.mention_everyone:
                if not self.can_call_everyone:
                    self.can_call_everyone = True
                    await ctx.send("The role `@everyone` and `@here` are now callable")
                else:
                    await ctx.send(
                        "The role `@everyone` and `@here` are now not callable"
                    )

            if ctx.guild not in self.uncallable_roles:
                self.uncallable_roles[ctx.guild] = []

            for role in ctx.message.role_mentions:
                if role in self.uncallable_roles[ctx.guild]:
                    self.uncallable_roles[ctx.guild].remove(role)
                    await ctx.send(f"The role `{role}` is now callable.")
                else:
                    await ctx.send(f"The role `{role}` is already callable.")

        @self.command(name="uncallables")
        async def uncallables(ctx: discord.ext.commands.Context):
            """
            Synatx: !@!uncallables
            Action: sends a list of all uncallables roles in the server.
            """
            if ctx.guild not in self.uncallable_roles:
                self.uncallable_roles[ctx.guild] = []

            if len(self.uncallable_roles[ctx.guild]) == 0:
                await ctx.send("There are no uncallable roles in this server.")
            elif len(self.uncallable_roles[ctx.guild]) == 1:
                await ctx.send(
                    "The uncallable role in this server is"
                    + f" `{self.uncallable_roles[ctx.guild][0]}`."
                )
            else:
                message = "The uncallable roles in this server are: "
                for role in self.uncallable_roles[ctx.guild]:
                    message += role.mention + ", "
                message = message[:-2] + "."
                await ctx.send(message)

    async def send_n_invites(self, ctx, n, users_dm_channels_dict):
        """Returns messages to display about users that couldn't be called"""
        author_vc = ctx.author.voice.channel
        users_not_to_call = []
        unavilable_user_messages = []
        for _ in range(n):
            for user, channel in list(users_dm_channels_dict.items()):
                if (
                    ((not user.voice) or user.voice.channel != author_vc)
                    and user.status == discord.Status.online
                    and not self.has_uncallable_role(ctx, user)
                ):
                    await self.send_dms(ctx, channel)
                else:
                    if user.status != discord.Status.online:
                        unavilable_user_messages.append(
                            f"\t`{user.mention}` because their status is"
                            + f" `{user.status}`. ❌"
                        )
                    elif user.voice and user.voice.channel == author_vc:
                        unavilable_user_messages.append(
                            f"\t`{user.mention}` because they are already"
                            + f"connected. ✅"
                        )
                    elif self.has_uncallable_role(ctx, user):
                        unavilable_user_messages.append(
                            f"\t`{user.mention}` because they have an"
                            + f" uncallable role. 📵"
                        )
                    users_not_to_call.append(user)

            for user in users_not_to_call:
                users_dm_channels_dict.pop(user)  # stop calling the user
            users_not_to_call = []

            sleep(1)
            if not ctx.author.voice or author_vc != ctx.author.voice.channel:
                return unavilable_user_messages
        return unavilable_user_messages

    async def send_dms(self, ctx, channel):
        invite = await ctx.author.voice.channel.create_invite(
            max_uses=1, max_age=60 * 5, reason="call"
        )
        message_to_send = f"{ctx.author.display_name} is calling you on {invite}"
        await channel.send(message_to_send)
        logging.debug(f"sent: {message_to_send}.")

    def get_pinged_users(self, ctx):
        """
        input:
            discord context
        output:
            set of all pinged users
        """
        if self.can_call_everyone and ctx.message.mention_everyone:
            return [
                member
                for member in ctx.guild.members
                if member.status == discord.Status.online and not member.bot
            ]

        user_mentions = ctx.message.mentions
        mentioned_roles = ctx.message.role_mentions

        mentioned_users = [self.get_user(mention.id) for mention in user_mentions]
        users_by_role = [
            role.members for role in mentioned_roles
        ]  # list of lists of users by role
        role_users = list(
            itertools.chain.from_iterable(users_by_role)
        )  # combine the lists
        pinged_users = set(
            mentioned_users + role_users
        )  # combine and remove duplicates
        return [ctx.guild.get_member(user.id) for user in pinged_users if not user.bot]

    def has_uncallable_role(self, ctx, user):
        if ctx.guild not in self.uncallable_roles:
            self.uncallable_roles[ctx.guild] = []
        for role in self.uncallable_roles[ctx.guild]:
            if role in user.roles:
                return True
        return False


if __name__ == "__main__":
    call_in_server_bot = CallInServer("!@!")
    call_in_server_bot.run(os.environ["TOKEN"])
