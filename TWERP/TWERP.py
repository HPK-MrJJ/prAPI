import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
import aiohttp


class CharacterSelectView(discord.ui.View):
    def __init__(self, cog, characters, interaction):
        super().__init__(timeout=180)  # View timeout after 180 seconds
        self.add_item(CharacterSelect(cog, characters, interaction))


class CharacterSelect(discord.ui.Select):
    def __init__(self, cog, characters, interaction):
        self.cog = cog
        self.interaction = interaction
        options = [
            discord.SelectOption(label=char_name, value=char_name)
            for char_name in characters.keys()
        ]
        super().__init__(placeholder="Select a character...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        """Trigger the modal after a character is selected."""
        try:
            character_name = self.values[0]  # Get selected character
            characters = await self.cog.config.user(interaction.user).characters()
            character_info = characters[character_name]
            webhook = await self.cog._get_webhook(interaction.channel)

            if webhook:
                modal = TWERPModal(self.cog, character_name, webhook, interaction, character_info)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message("Failed to retrieve or create a webhook.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)


class TWERPModal(discord.ui.Modal, title="Enter your message here"):
    def __init__(self, cog, character_name, webhook, interaction, character_info):
        super().__init__(title=f"Enter your message here")
        self.cog = cog
        self.character_name = character_name
        self.webhook = webhook
        self.interaction = interaction
        self.character_info = character_info

        self.message = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.paragraph,  # Multiline text area
            placeholder="Enter your message here...",
            required=True,
            max_length=2000  # Discord limit for message length
        )
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        """Send the message via the webhook when the modal is submitted."""
        try:
            async with aiohttp.ClientSession() as session:
                webhook_url = self.webhook.url
                combined_name = f"{self.character_info['name']} ({interaction.user.name})"
                json_data = {
                    "content": self.message.value,
                    "username": combined_name,
                    "avatar_url": self.character_info["pfp_url"],
                    "allowed_mentions": {
                        "parse": ["users"]  # Prevent @everyone and @here pings
                    }
                }
                await session.post(webhook_url, json=json_data)
            await interaction.response.defer()  # Close the modal
        except discord.errors.InteractionResponded:
            pass
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)


class TWERP(commands.Cog):
    """A cog that allows users to create characters, delete them, and send messages as characters using webhooks."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=23456789648)

        self._init_config()

    def _init_config(self):
        if not hasattr(self.config.GUILD, "allowed_channels"):
            self.config.register_guild(allowed_channels=[])
        if not hasattr(self.config.USER, "credits"):
            self.config.register_user(credits=0)
        if not hasattr(self.config.USER, "completed_personal_projects"):
            self.config.register_user(completed_personal_projects={})
        if not hasattr(self.config.USER, "characters"):
            self.config.register_user(characters={})
        if not hasattr(self.config.GUILD, "NPCS"):
            self.config.register_guild(NPCS={})

    async def cog_load(self):
        """This method is called when the cog is loaded, and it ensures that all slash commands are synced."""
        await bot.tree.sync()
        commands_to_add = [
            self.create_character, self.delete_character, self.select_character,
            self.create_npc, self.delete_npc, self.select_npc
        ]

        # Check if commands already exist and avoid re-adding them
        for cmd in commands_to_add:
            if self.bot.tree.get_command(cmd.name) is None:
                self.bot.tree.add_command(cmd)

        # Sync the commands globally
        await self.bot.tree.sync()
        print("All slash commands synced.")

    async def cog_unload(self):
        """Cleanup logic when the cog is unloaded, to remove slash commands."""
        commands_to_remove = [
            self.create_character, self.delete_character, self.select_character,
            self.create_npc, self.delete_npc, self.select_npc
        ]

        # Remove the commands when the cog is unloaded
        for cmd in commands_to_remove:
            if self.bot.tree.get_command(cmd.name):
                self.bot.tree.remove_command(cmd.name)


            # Autocomplete Function for Character Names
    async def character_name_autocomplete(self, interaction: discord.Interaction, current: str):
            """Autocomplete function to provide character names."""
            characters = await self.config.user(interaction.user).characters()
            if not characters:
                return []
            
            # Return matching character names based on the user's input (current)
            return [
                discord.app_commands.Choice(name=char_name, value=char_name)
                for char_name in characters.keys() if current.lower() in char_name.lower()
            ]

    async def NPC_name_autocomplete(self, interaction: discord.Interaction, current: str):
            """Autocomplete function to provide NPC names."""
            NPCS = await self.config.guild(interaction.guild).NPCS()
            if not NPCS:
                return []
            
            # Return matching character names based on the user's input (current)
            return [
                discord.app_commands.Choice(name=char_name, value=char_name)
                for char_name in NPCS.keys() if current.lower() in char_name.lower()
            ]

    # Create Character Slash Command
    @discord.app_commands.command(name="createcharacter", description="Create a character with a name and profile picture URL.")
    async def create_character(self, interaction: discord.Interaction, name: str, pfp_url: str):
        """Create a new character with a custom name and profile picture."""
        try:
            characters = await self.config.user(interaction.user).characters()
            if characters is None:
                characters = {}

            if len(characters) >= 2:
                await interaction.response.send_message("You already have 2 characters! Delete one before creating a new one.", ephemeral=True)
                return

            characters[name] = {
                "pfp_url": pfp_url,
                "name": name
            }

            await self.config.user(interaction.user).characters.set(characters)
            await interaction.response.send_message(f"Character {name} created with profile picture!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    # Create Character Slash Command
    @discord.app_commands.command(name="create_npc", description="Create a NPC with a name and profile picture URL.")
    async def create_npc(self, interaction: discord.Interaction, name: str, pfp_url: str):
        """Create a new character with a custom name and profile picture."""
        try:
            NPCS = await self.config.guild(interaction.guild).NPCS()
            if NPCS is None:
                NPCS = {}

            if len(NPCS) >= 25:
                await interaction.response.send_message("You already have 25 NPCs! Delete one before creating a new one.", ephemeral=True)
                return

            NPCS[name] = {
                "pfp_url": pfp_url,
                "name": name
            }

            await self.config.guild.NPCS.set(NPCS)
            await interaction.response.send_message(f"NPC {name} created with profile picture!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    # Delete Character Slash Command
    @discord.app_commands.command(name="deletecharacter", description="Delete one of your characters.")
    @discord.app_commands.autocomplete(name=character_name_autocomplete)
    async def delete_character(self, interaction: discord.Interaction, name: str):
        """Delete one of your characters."""
        try:
            characters = await self.config.user(interaction.user).characters()

            if name not in characters:
                await interaction.response.send_message(f"Character {name} not found.", ephemeral=True)
                return

            del characters[name]
            await self.config.user(interaction.user).characters.set(characters)
            await interaction.response.send_message(f"Character {name} deleted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    # Delete Character Slash Command
    @discord.app_commands.command(name="delete_npc", description="Delete a NPCs.")
    @discord.app_commands.autocomplete(name=NPC_name_autocomplete)
    async def delete_npc(self, interaction: discord.Interaction, name: str):
        """Delete one of your characters."""
        try:
            NPCS = await self.config.guild(interaction.guild).NPCS()

            if name not in NPCS:
                await interaction.response.send_message(f"NPC {name} not found.", ephemeral=True)
                return

            del NPCS[name]
            await self.config.guild.NPCS.set(NPCS)
            await interaction.response.send_message(f"NPC {name} deleted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)


    # Select Character Slash Command with Autocomplete
    @discord.app_commands.command(name="speak", description="Select a character and speak as that character.")
    @discord.app_commands.autocomplete(character=character_name_autocomplete)
    async def select_character(self, interaction: discord.Interaction, character: str, message: str = None):
        """Speak as one of your characters."""
        try:
            characters = await self.config.user(interaction.user).characters()

            # No characters found
            if not characters:
                await interaction.response.send_message("You don't have any characters created.", ephemeral=True)
                return

            # Ensure the selected character is valid
            if character not in characters:
                await interaction.response.send_message(f"Character `{character}` not found.", ephemeral=True)
                return

            character_info = characters[character]
            webhook = await self._get_webhook(interaction.channel)
            if webhook:
                if message is None:
                    modal = TWERPModal(self, character, webhook, interaction, character_info)
                    await interaction.response.send_modal(modal)
                else:
                    await self.send_as_character(interaction, character, character_info, message, webhook)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    # Select Character Slash Command with Autocomplete
    @discord.app_commands.command(name="speak_npc", description="Select a NPC and speak as that NPC.")
    @discord.app_commands.autocomplete(character=NPC_name_autocomplete)
    async def select_npc(self, interaction: discord.Interaction, character: str, message: str = None):
        """Speak as a NPC."""
        try:
            NPCS = await self.config.guild(interaction.guild).NPCS()

            # No characters found
            if not NPCS:
                await interaction.response.send_message("You don't have any NPCS created.", ephemeral=True)
                return

            # Ensure the selected character is valid
            if character not in NPCS:
                await interaction.response.send_message(f"NPC `{character}` not found.", ephemeral=True)
                return

            character_info = NPCS[character]
            webhook = await self._get_webhook(interaction.channel)
            if webhook:
                if message is None:
                    modal = TWERPModal(self, character, webhook, interaction, character_info)
                    await interaction.response.send_modal(modal)
                else:
                    await self.send_as_character(interaction, character, character_info, message, webhook)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    async def send_as_character(self, interaction, character_name, character_info, message, webhook):
        """Helper function to send a message as a character using the webhook."""
        try:
            async with aiohttp.ClientSession() as session:
                webhook_url = webhook.url
                combined_name = f"{character_info['name']} ({interaction.user.name})"
                json_data = {
                    "content": message,
                    "username": combined_name,
                    "avatar_url": character_info["pfp_url"],
                    "allowed_mentions": {
                        "parse": ["users"]  # Prevent @everyone and @here pings
                    }
                }
                await session.post(webhook_url, json=json_data)
    
            # Properly acknowledge the interaction to prevent the "thinking" state
            await interaction.response.send_message(f"Message sent as {character_name}!", ephemeral=True)
    
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)


    async def _get_webhook(self, channel: discord.TextChannel):
        """Creates or retrieves a webhook for the channel."""
        try:
            webhooks = await channel.webhooks()
            bot_webhook = discord.utils.get(webhooks, name="CharacterWebhook")

            if not bot_webhook:
                try:
                    bot_webhook = await channel.create_webhook(name="CharacterWebhook")
                except discord.Forbidden:
                    return None

            return bot_webhook
        except Exception as e:
            return None
