import os
import json
import logging
from time import sleep
import itertools
import discord
from discord import app_commands
from discord.ext import commands


class CallInServer(commands.Bot):
    def __init__(self, command_prefix):
        logging.basicConfig(level=logging.DEBUG)

        super().__init__(
            command_prefix='!@!',  # deprecated
            intents=discord.Intents().all(),
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="/help"
            ),
        )

        self.remove_command('help')

        self.add_events()
        self.add_commands()

        self.uncallable_roles = {}

    def add_events(self):
        @self.event
        async def on_ready():
            logging.info(f"Logged in as {self.user}.")
            await self.tree.sync()
            if os.path.exists('uncallable_roles.json'):
                self.read_uncallable_roles_json()
            else:
                self.write_uncallable_roles_json()

        @self.event
        async def on_command_error():
                await interaction.response.send_message(
                    'Please use slash commands instead of using the `!@!` prefix.',
                    ephemeral=True
                )

    def add_commands(self):
        @self.tree.command(
                name="help",
                description="Provides information about how to use this bot.",
        )
        async def help_(interaction: discord.Interaction, *, command: str=''):
            """
            Syntax: /help {command}
            Action: shows this message, and a simular message for other commands when provided.
            """
            if command == '':
                await interaction.response.send_message(
                    'this bot can be used to simulate DM-like calls in discord' \
                    + ' servers. it is done by sending messages with a link to' \
                    + ' a voice channel to the users you call.\n' \
                    + 'the avilable commands are:\n'
                    + '\t`help`\n\t`call`\n\t`uncallable`\n\t`recallalbe`'
                    + '\n\t`uncallables`\n\n'
                    + 'to get more information about any command, use: `/help {command}`',
                    ephemeral=True
                )
            elif command == 'help':
                await interaction.response.send_message(
                    'Syntax: `/help {command}`\n'
                    'Action: show a general help message, and a specific message for commands when provided.',
                    ephemeral=True
                )
            elif command == 'call':
                await interaction.response.send_message(
                    'Syntax: `/call {mention1} {mention2} {mention3}...`\n'
                    + 'Action: simulates a call to users and roles.\n\n'
                    + 'Can only call `callable` roles.',
                    ephemeral=True
                )
            elif command == 'uncallable':
                await interaction.response.send_message(
                    'Syntax: `/uncallable {role_mention1} {role_mention3} {role_mention2}...`\n'
                    + 'Action: makes the mentioned roles uncallable.',
                    ephemeral=True
                )
            elif command == 'uncallables':
                await interaction.response.send_message(
                    'Synatx: `/uncallables`\n'
                    + 'Action: sends a list of all uncallables roles in the server.',
                    ephemeral=True
                )
            elif command == 'recallable':
                await interaction.response.send_message(
                    'Syntax: `/recallable {role_mention1} {role_mention3} {role_mention2}...`\n'
                    + 'Action: makes the mentioned roles callable.',
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    'the provided argument is not a valid command',
                    ephemeral=True
                )

        @self.tree.command(
                name="call",
                description="Calls a user/role or a list of users/roles",
        )
        async def call(interaction: discord.Interaction, *, callables: str):
            """
            Syntax: /call {mention1} {mention2} {mention3}...
            Action: simulates a call to users and roles.

            Can only call `callable` roles.
            """
            logging.debug(f"recieved: call: {callables=}.")

            if 'resolved' not in interaction.data.keys():
                await interaction.response.send_message(
                    f"no user/role was provided. use the `/help` command of this bot" \
                    + f" for more information about how to use it.",
                    ephemeral=True
                )
                return

            users_to_call = self.get_pinged_users(interaction, callables)
            users_dm_channels_dict = {
                user: await user.create_dm() for user in users_to_call
            }

            if (
                not interaction.user.voice
            ):  # if the author is not conencted to a voice channel
                await interaction.response.send_message(
                    "You have to be connected to a voice channel"
                        + " to use this command.",
                    ephemeral=True
                )

            else:
                await interaction.response.send_message(
                        "Starting to call.",
                        ephemeral=True
                )
                unavailable_users_messages = await self.send_n_invites(
                    interaction, 5, users_dm_channels_dict
                )
                unavailable_users_message = ""
                for message in unavailable_users_messages:
                    unavailable_users_message += "\n" + message

                await interaction.followup.send(
                    f"Finishing to call.",
                    ephemeral=True
                )
                if unavailable_users_message:
                    await interaction.followup.send(
                        f"Didn't call: {unavailable_users_message}",
                        ephemeral=True
                    )

        @self.tree.command(
                name="uncallable",
                description="Makes the mentioned roles uncallable.",
        )
        @commands.has_permissions(administrator=True)
        async def uncallable(interaction: discord.Interaction, *, role: str):
            """
            Syntax: !@!uncallable {role_mention1} {role_mention3} {role_mention2}...
            Action: makes the mentioned roles uncallable.
            """
            if 'resolved' not in interaction.data.keys():
                await interaction.response.send_message(
                    f"no role was provided. use the `/help` command of this bot" \
                    + f" for more information about how to use it.",
                    ephemeral=True
                )
                return

            if interaction.guild not in self.uncallable_roles:
                self.uncallable_roles[interaction.guild] = []

            mentioned_roles = [discord.utils.get(interaction.guild.roles, id=int(id))
                               for id in interaction.data['resolved']['roles'].keys()]

            for role in mentioned_roles:
                if role not in self.uncallable_roles[interaction.guild]:
                    self.uncallable_roles[interaction.guild].append(role)
                    await interaction.response.send_message(
                        f"The role `{role}` is now not callable",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"The role `{role}` is already not callable",
                        ephemeral=True
                    )

            self.write_uncallable_roles_json()

        @self.tree.command(
                name="recallable",
                description="Makes the mentioned roles callable.",
        )
        @commands.has_permissions(administrator=True)
        async def recallable(interaction: discord.Interaction, *, role: str):
            """
            Syntax: !@!recallable {role_mention1} {role_mention3} {role_mention2}...
            Action: makes the mentioned roles callable.
            """
            if 'resolved' not in interaction.data.keys():
                await interaction.response.send_message(
                    f"no role was provided. use the /help command of this bot" \
                    + f" for more information about how to use it.",
                    ephemeral=True
                )
                return

            if interaction.guild not in self.uncallable_roles:
                self.uncallable_roles[interaction.guild] = []

            mentioned_roles = []
            if 'roles' in interaction.data['resolved'].keys():
                mentioned_roles = [discord.utils.get(interaction.guild.roles, id=int(id))
                                   for id in interaction.data['resolved']['roles'].keys()]

            for role in mentioned_roles:
                if role in self.uncallable_roles[interaction.guild]:
                    self.uncallable_roles[interaction.guild].remove(role)
                    await interaction.response.send_message(
                        f"The role `{role}` is now callable.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"The role `{role}` is already callable.",
                        ephemeral=True
                    )

            self.write_uncallable_roles_json()

        @self.tree.command(
                name="uncallables",
                description="sends a list of all uncallables roles in the server.",
        )
        async def uncallables(interaction: discord.Interaction):
            """
            Synatx: !@!uncallables
            Action: sends a list of all uncallables roles in the server.
            """
            if interaction.guild not in self.uncallable_roles:
                self.uncallable_roles[interaction.guild] = []

            if len(self.uncallable_roles[interaction.guild]) == 0:
                await interaction.response.send_message(
                    "There are no uncallable roles in this server.",
                    ephemeral=True
                )
            elif len(self.uncallable_roles[interaction.guild]) == 1:
                await interaction.response.send_message(
                    "The uncallable role in this server is"
                    + f" `{self.uncallable_roles[interaction.guild][0]}`.",
                    ephemeral=True
                )
            else:
                message = "The uncallable roles in this server are: "
                for role in self.uncallable_roles[interaction.guild]:
                    message += role.mention + ", "
                message = message[:-2] + "."
                await interaction.response.send_message(message, ephemeral=True)

    async def send_n_invites(self, interaction, n, users_dm_channels_dict):
        """Returns messages to display about users that couldn't be called"""
        author_vc = interaction.user.voice.channel
        users_not_to_call = []
        unavilable_user_messages = []
        for _ in range(n):
            for user, channel in list(users_dm_channels_dict.items()):
                if (
                    ((not user.voice) or user.voice.channel != author_vc)
                    and user.status == discord.Status.online
                    and not self.has_uncallable_role(interaction, user)
                ):
                    try:
                        await self.send_dms(interaction, channel)
                    except discord.errors.Forbidden:
                        unavilable_user_messages.append(
                            f"\t{user.mention} because they blocked this bot."
                            + f"🚫"
                        )
                        users_not_to_call.append(user)
                else:
                    if user.status != discord.Status.online:
                        unavilable_user_messages.append(
                            f"\t{user.mention} because their status is"
                            + f" `{user.status}`. ❌"
                        )
                    elif user.voice and user.voice.channel == author_vc:
                        unavilable_user_messages.append(
                            f"\t{user.mention} because they are already"
                            + f" connected. ✅"
                        )
                    elif self.has_uncallable_role(interaction, user):
                        unavilable_user_messages.append(
                            f"\t{user.mention} because they have an"
                            + f" uncallable role. 📵"
                        )
                    users_not_to_call.append(user)

            for user in users_not_to_call:
                users_dm_channels_dict.pop(user)  # stop calling the user
            users_not_to_call = []

            sleep(1)
            if not interaction.user.voice or author_vc != interaction.user.voice.channel:
                return unavilable_user_messages
        return unavilable_user_messages

    async def send_dms(self, interaction, channel):
        invite = await interaction.user.voice.channel.create_invite(
            max_uses=1, max_age=60 * 5, reason="call"
        )
        message_to_send = f"`{interaction.user.display_name}` is calling you on {invite}"
        await channel.send(message_to_send)
        logging.debug(f"sent: {message_to_send}.")

    def get_pinged_users(self, interaction, callables):
        """
        input:
            discord interaction
        output:
            set of all pinged users
        """
        mentioned_users = []
        if 'members' in interaction.data['resolved'].keys():
            mentioned_users = [self.get_user(int(id)) for id in
                               interaction.data['resolved']['members'].keys()]
        mentioned_roles = []
        if 'roles' in interaction.data['resolved'].keys():
            mentioned_roles = [discord.utils.get(interaction.guild.roles, id=int(id))
                               for id in interaction.data['resolved']['roles'].keys()]

        users_by_role = [
            role.members for role in mentioned_roles
        ]  # list of lists of users by role
        role_users = list(
            itertools.chain.from_iterable(users_by_role)
        )  # combine the lists
        pinged_users = set(
            mentioned_users + role_users
        )  # combine and remove duplicates
        return [interaction.guild.get_member(user.id) for user in pinged_users if not user.bot]

    def has_uncallable_role(self, interaction, user):
        if interaction.guild not in self.uncallable_roles:
            self.uncallable_roles[interaction.guild] = []
        for role in self.uncallable_roles[interaction.guild]:
            if role in user.roles:
                return True
        return False

    def write_uncallable_roles_json(self):
        jsonable_uncallable_roles = {}
        for guild, role_list in self.uncallable_roles.items():
            jsonable_uncallable_roles[guild.id] =\
                [role.id for role in role_list]

        with open('uncallable_roles.json', 'w') as file:
            json.dump(jsonable_uncallable_roles, file)

    def read_uncallable_roles_json(self):
        with open('uncallable_roles.json', 'r') as file:
            jsoned_uncallable_roles = json.load(file)

        self.uncallable_roles = {}
        for guild_id, role_id_list in jsoned_uncallable_roles.items():
            guild = self.get_guild(int(guild_id))
            self.uncallable_roles[guild] =\
                [guild.get_role(role_id) for role_id in role_id_list]


if __name__ == "__main__":
    call_in_server_bot = CallInServer("!@!")
    call_in_server_bot.run(os.environ["TOKEN"])

