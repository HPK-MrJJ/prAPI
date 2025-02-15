import discord
from redbot.core import commands, Config, checks
from discord.ext import tasks  # ✅ Correct
import aiohttp
import random
import xml.etree.ElementTree as ET
from discord import Embed
import time
import csv
import os
from datetime import datetime
import asyncio
from datetime import datetime, timedelta


class NexusExchange(commands.Cog):
    """A Master Currency Exchange Cog for The Wellspring"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(None, identifier=345678654456, force_registration=True)
        self.config.register_guild(
            daily_channel = None,
            daily_time = "12:00",  # Default time to noon
            master_currency_name="wellcoin",
            exchange_rates={}, 
            xp_per_message=5,  # XP per message
            coins_per_message=1,  # WellCoins per valid message
            message_cooldown=10,  # Cooldown in seconds to prevent farming
            blacklisted_channels=[],  # List of channel IDs where WellCoins are NOT earned# {"currency_name": {"config_id": int, "rate": float}}
            min_message_length=20,  # Minimum message length to earn rewards

        )
        
        self.config.register_user(master_balance=0, xp=0, last_message_time=0, linked_nations=[])

            # Lootbox configuration
        self.config.register_global(
            season=[3,4],
            categories=["common", "uncommon", "rare", "ultra-rare", "epic"],
            useragent="",
            nationName="",
            password="",
        )
        self.daily_task.start()  # Start the daily loop

    def cog_unload(self):
        self.daily_task.cancel()


    @tasks.loop(hours=1)
    async def daily_task(self):
        now = datetime.utcnow().strftime("%H")  # Get current time in HH:MM format
        guilds = await self.config.all_guilds()
        for guild_id, data in guilds.items():
            if data["daily_channel"] and data["daily_time"] == now:
                channel = self.bot.get_channel(data["daily_channel"])
                if channel:
                    try:
                        #daily Loop stuff 
                        await channel.send("This is your daily message!")
                        ad_text = self.get_random_ad()
                        if ad_text:
                            try:
                                await channel.send(ad_text)

                    
                            #end of daily Loops stuff
                            except discord.Forbidden:
                                print(f"Missing permissions to send messages in {channel.id}")
    

    async def fetch_wa_data(self,hall):
        """Fetches WA voting data from NationStates API"""
        url = f"https://www.nationstates.net/cgi-bin/api.cgi?wa={hall}&q=resolution+voters"
        headers = {"User-Agent": "9006, NexusExhange"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return None
                return await response.text()

    async def get_9006_vote(self, xml_data):
        """Parses XML and finds how nation '9006' voted"""
        root = ET.fromstring(xml_data)

        votes_for = {n.text.lower() for n in root.findall(".//VOTES_FOR/N")}
        votes_against = {n.text.lower() for n in root.findall(".//VOTES_AGAINST/N")}

        if "9006" in votes_for:
            return "for"
        elif "9006" in votes_against:
            return "against"
        return None  # 9006 hasn't voted
    
    async def reward_users(self, user_votes, vote_9006_council1, vote_9006_council2):
        """Rewards users who voted the same as '9006' in either or both councils"""
        all_users = await self.config.all_users()

        for user_id, data in all_users.items():
            linked_nations = data.get("linked_nations", [])
            if not linked_nations:
                continue  # Skip users with no linked nations

            matching_council_1 = False
            matching_council_2 = False

            for nation in linked_nations:
                nation = nation.lower()
                if vote_9006_council1 and nation in user_votes["council1"]:
                    matching_council_1 = True
                if vote_9006_council2 and nation in user_votes["council2"]:
                    matching_council_2 = True

            # Reward based on how many councils match
            if matching_council_1 and matching_council_2:
                reward = 20  # Matching both votes
            elif matching_council_1 or matching_council_2:
                reward = 10  # Matching in one council
            else:
                reward = 0  # No match, no reward

            if reward > 0:
                new_balance = data["master_balance"] + reward
                await self.config.user_from_id(user_id).master_balance.set(new_balance)

    @commands.command()
    @commands.admin_or_permissions(manage_guild=True)
    async def reward_voters(self, ctx):
        """Check votes and reward users who voted the same as '9006' in either WA Council"""
        await ctx.send("Fetching WA vote data for both councils...")

        # Fetch data for both WA councils
        xml_data_council1 = await self.fetch_wa_data(1)
        xml_data_council2 = await self.fetch_wa_data(2)

        # Determine 9006's votes
        vote_9006_council1 = await self.get_9006_vote(xml_data_council1)
        vote_9006_council2 = await self.get_9006_vote(xml_data_council2)

        # If 9006 hasn't voted in either council, no rewards
        if not vote_9006_council1 and not vote_9006_council2:
            await ctx.send("Nation '9006' has not voted in either council. No rewards given.")
            return

        # Parse votes from each council
        user_votes = {"council1": set(), "council2": set()}

        if xml_data_council1 and vote_9006_council1:
            root = ET.fromstring(xml_data_council1)
            user_votes["council1"] = {n.text.lower() for n in root.findall(f".//VOTES_{vote_9006_council1.upper()}/N")}

        if xml_data_council2 and vote_9006_council2:
            root = ET.fromstring(xml_data_council2)
            user_votes["council2"] = {n.text.lower() for n in root.findall(f".//VOTES_{vote_9006_council2.upper()}/N")}

        # Reward users
        await self.reward_users(user_votes, vote_9006_council1, vote_9006_council2)

        await ctx.send(f"Users who voted the same as **9006** have been rewarded! (10 for one match, 20 for both)")
        
        

    @commands.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def set_daily_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where the daily message will be sent."""
        await self.config.guild(ctx.guild).daily_channel.set(channel.id)
        await ctx.send(f"Daily message channel set to {channel.mention}.")

    @commands.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def set_daily_time(self, ctx, time: str):
        """Set the daily message time (HH:MM format, UTC)."""
        try:
            datetime.strptime(time, "%H")  # Validate time format
            await self.config.guild(ctx.guild).daily_time.set(time)
            await ctx.send(f"Daily message time set to **{time} UTC**.")
        except ValueError:
            await ctx.send("Invalid time format. Use HH (24-hour UTC).")
                        
    @commands.group(name="shop")
    async def shop(self, ctx):
        """Master command for the shop."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="🛒 Shop Inventory", color=discord.Color.blue())
            
            embed.add_field(name="Loot box", value=f"💰 `10 Coins`\n📜", inline=False)

            await ctx.send(embed=embed)

    @shop.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def set_nation(self, ctx, *, nationname: str):
        """Set the nation name for the loot box prizes."""
        await self.config.nationName.set(nationname)
        await ctx.send(f"Nation Name set to {nationname}")

    @shop.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def set_password(self, ctx, *, password: str):
        """Set the password for the loot box prizes."""
        await self.config.password.set(password)
        await ctx.send("Password has been set successfully.")

    @shop.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def useragent(self, ctx, *, useragent: str):
        """Set the User-Agent header for the requests."""
        await self.config.useragent.set(useragent)
        await ctx.send(f"User-Agent set to {useragent}")

    @shop.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def season(self, ctx, *seasons: str):
        """Set the season to filter cards."""
        seasons = [season for season in seasons]
        await self.config.season.set(seasons)
        await ctx.send(f"Season's set to {seasons}")

    @shop.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def categories(self, ctx, *categories: str):
        """Set the categories to filter cards."""
        categories = [category for category in categories]
        await self.config.categories.set(categories)
        await ctx.send(f"Categories set to {', '.join(categories)}")

    @shop.command()
    @commands.admin()
    @commands.cooldown(1, 60, commands.BucketType.default)  # 1 use per 60 seconds
    async def buy_lootbox(self, ctx, *recipient: str):
        """Open a loot box and fetch a random card for the specified nation."""
        await ctx.send("You bought a lootbox woot woot!")


            # Fetch the user's current WellCoin balance
        user_balance = await self.config.user(ctx.author).master_balance()
    
        # Check if the user has at least 10 WellCoins
        lootbox_cost = 10
        if user_balance < lootbox_cost:
            await ctx.send(f"❌ You need at least `{lootbox_cost}` WellCoins to buy a lootbox. Your balance: `{user_balance}` WellCoins.")
            return

        if len(recipient) < 1:
            await ctx.send("Make sure to put your nation in after openlootbox")
            return


        recipient =  "_".join(recipient)
        season = await self.config.season()
        nationname = await self.config.nationName()
        categories = ["common","uncommon", "rare", "ultra-rare","epic"]
        useragent = await self.config.useragent()

        headers = {"User-Agent": useragent}
        password = await self.config.password()

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"https://www.nationstates.net/cgi-bin/api.cgi?q=cards+deck;nationname={nationname}"
            ) as response:
                if response.status != 200:
                    await ctx.send(f"Failed to fetch data from NationStates API. {response.status}")
                    await ctx.send(response.text)

                    return

                data = await response.text()
                cards = self.parse_cards(data, season, categories)

                if not cards:
                    await ctx.send(data[:1000])
                    await ctx.send(
                        f"No cards found for season {season} in categories {', '.join(categories)}"
                    )
                    return

                random_card = random.choice(cards)

                # Fetch card details
                async with session.get(
                    f"https://www.nationstates.net/cgi-bin/api.cgi?q=card+info;cardid={random_card['id']};season={random_card['season']}"
                ) as card_info_response:
                    if card_info_response.status != 200:
                        await ctx.send("Failed to fetch card details from NationStates API.")
                        return

                    card_info_data = await card_info_response.text()
                    card_info = self.parse_card_info(card_info_data)

                    embed_color = self.get_embed_color(random_card['category'])
                    embed = Embed(title="Loot Box Opened!", description="You received a card!", color=embed_color)
                    embed.add_field(name="Card Name", value=card_info['name'], inline=True)
                    embed.add_field(name="Card ID", value=random_card['id'], inline=True)
                    embed.add_field(name="Season", value=random_card['season'], inline=True)
                    embed.add_field(name="Market Value", value=card_info['market_value'], inline=True)

                # Prepare the gift
                prepare_data = {
                    "nation": nationname,
                    "c": "giftcard",
                    "cardid": random_card['id'],
                    "season": random_card['season'],
                    "to": recipient,
                    "mode": "prepare"
                }
                prepare_headers = {
                    "User-Agent": useragent,
                    "X-Password": password
                }

                async with session.post("https://www.nationstates.net/cgi-bin/api.cgi", data=prepare_data, headers=prepare_headers) as prepare_response:
                    if prepare_response.status != 200:
                        if prepare_response.status == 409 or 403:
                            await ctx.send(prepare_response.text)
                            await ctx.send("No loot boxes ready! Give me a minute or so to wrap one up for you.")
                            return       
                        await ctx.send(prepare_response.text)
                        await ctx.send("Failed to prepare the gift.")
                        return

                    prepare_response_data = await prepare_response.text()
                    token = self.parse_token(prepare_response_data)
                    x_pin = prepare_response.headers.get("X-Pin")

                    if not token or not x_pin:
                        await ctx.send(prepare_response_data)
                        await ctx.send("Failed to retrieve the token or X-Pin for gift execution.")
                        return

                    # Execute the gift
                    execute_data = {
                        "nation": nationname,
                        "c": "giftcard",
                        "cardid": random_card['id'],
                        "season": random_card['season'],
                        "to": recipient,
                        "mode": "execute",
                        "token": token
                    }
                    execute_headers = {
                        "User-Agent": useragent,
                        "X-Pin": x_pin
                    }

                    async with session.post("https://www.nationstates.net/cgi-bin/api.cgi", data=execute_data, headers=execute_headers) as execute_response:
                        if execute_response.status == 200:
                            await ctx.send(embed=embed)
                         # Deduct the cost from the user's balance
                            await self.config.user(ctx.author).master_balance.set(user_balance - lootbox_cost)
                        
                            # Confirm purchase
                            await ctx.send(f"✅ You bought a lootbox for `{lootbox_cost}` WellCoins! Your new balance: `{user_balance - lootbox_cost}` WellCoins.")
                        else:
                            await ctx.send("Failed to execute the gift.")


    @shop.command()
    @commands.admin()
    @commands.cooldown(1, 60, commands.BucketType.default)  # 1 use per 60 seconds
    async def buy_card_request(self, ctx, id, *recipient: str):
        """Open a loot box and fetch a random card for the specified nation."""

        if len(recipient) < 1:
            await ctx.send("Make sure to put your nation in at the end.")
            return
            
        if not id:
            await ctx.send("Please tell me the ID of the card you want ``shop buy_card_request 1 9003``")
            return
            
            # Fetch the user's current WellCoin balance
        user_balance = await self.config.user(ctx.author).master_balance()
    
        # Check if the user has at least 10 WellCoins
        lootbox_cost = 500
        if user_balance < lootbox_cost:
            await ctx.send(f"❌ You need at least `{lootbox_cost}` WellCoins to buy a card request. Your balance: `{user_balance}` WellCoins.")
            return

        await ctx.send("You bought a card request woot woot!")
        
        recipient =  "_".join(recipient)
        season = 4
        nationname = await self.config.nationName()
        categories = ["common","uncommon", "rare", "ultra-rare","epic"]
        useragent = await self.config.useragent()

        headers = {"User-Agent": useragent}
        password = await self.config.password()

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"https://www.nationstates.net/cgi-bin/api.cgi?q=card+info+owners;cardid={id};season=4"
            ) as response:
                if response.status != 200:
                    await ctx.send(f"Failed to fetch data from NationStates API. {response.status}")
                    await ctx.send(response.text)
                    return

                data = await response.text()
                if "<owner>9006</owner>" not in data.lower():
                    await ctx.send("Sorry you can only request cards that 9006 owns in season 4 at this time!")
                    return
                    
                if "<category>legendary</category>" in data.lower():
                    await ctx.send("Sorry Legendary cards must be specialy requested from 9006 please ask him directly")
                    return

        
                card_info_data = await response.text()
                card_info = self.parse_card_info(card_info_data)

                embed = Embed(title="Loot Box Opened!", description="You received a card!", color=0xFFFF00)
                embed.add_field(name="Card Name", value=card_info['name'], inline=True)
                embed.add_field(name="Card ID", value=id, inline=True)
                embed.add_field(name="Season", value=4, inline=True)
                embed.add_field(name="Market Value", value=card_info['market_value'], inline=True)

                # Prepare the gift
                prepare_data = {
                    "nation": nationname,
                    "c": "giftcard",
                    "cardid": id,
                    "season": 4,
                    "to": recipient,
                    "mode": "prepare"
                }
                prepare_headers = {
                    "User-Agent": useragent,
                    "X-Password": password
                }

                async with session.post("https://www.nationstates.net/cgi-bin/api.cgi", data=prepare_data, headers=prepare_headers) as prepare_response:
                    if prepare_response.status != 200:
                        if prepare_response.status == 409 or 403:
                            await ctx.send(prepare_response.text)
                            await ctx.send("No loot boxes ready! Give me a minute or so to wrap one up for you.")
                            return       
                        await ctx.send(prepare_response.text)
                        await ctx.send("Failed to prepare the gift.")
                        return

                    prepare_response_data = await prepare_response.text()
                    token = self.parse_token(prepare_response_data)
                    x_pin = prepare_response.headers.get("X-Pin")

                    if not token or not x_pin:
                        await ctx.send(prepare_response_data)
                        await ctx.send("Failed to retrieve the token or X-Pin for gift execution.")
                        return

                    # Execute the gift
                    execute_data = {
                        "nation": nationname,
                        "c": "giftcard",
                        "cardid": id,
                        "season": 4,
                        "to": recipient,
                        "mode": "execute",
                        "token": token
                    }
                    execute_headers = {
                        "User-Agent": useragent,
                        "X-Pin": x_pin
                    }

                    async with session.post("https://www.nationstates.net/cgi-bin/api.cgi", data=execute_data, headers=execute_headers) as execute_response:
                        if execute_response.status == 200:
                            await ctx.send(embed=embed)
                         # Deduct the cost from the user's balance
                            await self.config.user(ctx.author).master_balance.set(user_balance - lootbox_cost)
                        
                            # Confirm purchase
                            await ctx.send(f"✅ You bought card ID {id} for `{lootbox_cost}` WellCoins! Your new balance: `{user_balance - lootbox_cost}` WellCoins.")
                        else:
                            await ctx.send(execute_response.text)
                            await ctx.send("Failed to execute the gift.")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def add_to_currency(self, ctx, user: discord.Member, currency_name: str, amount: int):
        """Add a certain amount of a mini-currency to a user's balance."""
        currency_name = currency_name.lower().replace(" ", "_")
        exchange_rates = await self.config.guild(ctx.guild).exchange_rates()

        if currency_name not in exchange_rates:
            await ctx.send("This currency does not exist.")
            return

        config_id = exchange_rates[currency_name]["config_id"]
        mini_currency_config = Config.get_conf(None, identifier=config_id, force_registration=True)
        
        # Retrieve user's current balance
        user_balance = await mini_currency_config.user(user).get_raw(currency_name, default=0)
        new_balance = user_balance + amount

        # Update balance
        await mini_currency_config.user(user).set_raw(currency_name, value=new_balance)

        await ctx.send(f"Added `{amount}` `{currency_name}` to {user.mention}. New balance: `{new_balance}`.")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def add_currency(self, ctx, currency_name: str, config_id: int, rate: float):
        """Add a new mini-currency with its config ID and exchange rate."""
        currency_name = currency_name.lower().replace(" ","_")
        async with self.config.guild(ctx.guild).exchange_rates() as exchange_rates:
            exchange_rates[currency_name] = {"config_id": config_id, "rate": rate}
        await ctx.send(f"Added `{currency_name}` with exchange rate `{rate}` from config `{config_id}`.")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def remove_currency(self, ctx, currency_name: str):
        """Remove a mini-currency from the exchange list."""
        currency_name = currency_name.lower().replace(" ","_")
        async with self.config.guild(ctx.guild).exchange_rates() as exchange_rates:
            if currency_name not in exchange_rates:
                await ctx.send("This currency does not exist.")
                return
            del exchange_rates[currency_name]
        await ctx.send(f"Removed `{currency_name}` from the exchange list.")

    @commands.guild_only()
    @commands.command()
    async def exchange(self, ctx, currency_name: str, amount: int):
        """Convert a mini-currency into WellCoins."""
        currency_name = currency_name.lower().replace(" ","_")
        exchange_rates = await self.config.guild(ctx.guild).exchange_rates()
        
        if currency_name not in exchange_rates:
            await ctx.send("This currency is not available for exchange.")
            return

        config_id = exchange_rates[currency_name]["config_id"]
        rate = exchange_rates[currency_name]["rate"]
        mini_currency_config = Config.get_conf(None, identifier=config_id)
        user_balance = await mini_currency_config.user(ctx.author).get_raw(currency_name, default=0)

        if user_balance < amount:
            await ctx.send("You do not have enough of this currency.")
            return

        new_wellspring_coins = int(amount * rate)
        
        # Deduct from mini-currency
        await mini_currency_config.user(ctx.author).set_raw(currency_name, value=user_balance - amount)
        
        # Add to master currency
        master_balance = await self.config.user(ctx.author).master_balance()
        await self.config.user(ctx.author).master_balance.set(master_balance + new_wellspring_coins)
        
        await ctx.send(f"Exchanged `{amount}` `{currency_name}` for `{new_wellspring_coins}` WellCoins!")

    @commands.guild_only()
    @commands.command()
    async def balance(self, ctx, currency_name: str = None):
        """Check your balance of WellCoins or a specific mini-currency."""
        if currency_name is None:
            balance = await self.config.user(ctx.author).master_balance()
            await ctx.send(f"You have `{balance}` WellCoins.")
        else:
            currency_name = currency_name.lower().replace(" ","_")
            exchange_rates = await self.config.guild(ctx.guild).exchange_rates()

            if currency_name not in exchange_rates:
                await ctx.send("This currency does not exist.")
                return

            config_id = exchange_rates[currency_name]["config_id"]
            mini_currency_config = Config.get_conf(None, identifier=config_id, force_registration=True)
            user_balance = await mini_currency_config.user(ctx.author).get_raw(currency_name, default=0)

            await ctx.send(f"You have `{user_balance}` `{currency_name}`.")

    @commands.guild_only()
    @commands.command()
    async def rates(self, ctx):
        """View current exchange rates."""
        exchange_rates = await self.config.guild(ctx.guild).exchange_rates()
        if not exchange_rates:
            await ctx.send("No currencies have been added yet.")
            return
        
        embed = discord.Embed(title="Exchange Rates", color=discord.Color.blue())
        for currency, data in exchange_rates.items():
            embed.add_field(name=currency, value=f"Rate: 1 {currency} will get you `{data['rate']}` Wellcoins (Config: `{data['config_id']}`)", inline=False)
        
        embed.add_field(name="How to get the various currencies", value="**Gold** Comes from Hunger Games! Join us every Saturday\n\n**Credits** come from recruiting, if you are instread in joining our recruiting force please reach out to 9006! ", inline=False)
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def set_rate(self, ctx, currency_name: str, rate: float):
        """Change the exchange rate for a mini-currency."""
        currency_name = currency_name.lower().replace(" ","_")
        async with self.config.guild(ctx.guild).exchange_rates() as exchange_rates:
            if currency_name not in exchange_rates:
                await ctx.send("That currency does not exist.")
                return
            exchange_rates[currency_name]["rate"] = rate
        await ctx.send(f"Updated `{currency_name}` exchange rate to `{rate}`.")

    @commands.guild_only()
    @commands.command()
    async def debug_currency(self, ctx, currency_name: str):
        """Dump everything related to a given currency's config."""
        currency_name = currency_name.lower().replace(" ", "_")
        
        # Check if the currency exists
        exchange_rates = await self.config.guild(ctx.guild).exchange_rates()
        if currency_name not in exchange_rates:
            await ctx.send(f"Currency `{currency_name}` does not exist.")
            return
    
        # Retrieve the correct config_id
        config_id = exchange_rates[currency_name]["config_id"]
        mini_currency_config = Config.get_conf(None, identifier=config_id, force_registration=True)
    
        # Retrieve all stored data in this Config space
        try:
            all_data = await mini_currency_config.all()
            all_user_data = await mini_currency_config.all_users()
            all_member_data = await mini_currency_config.all_members()
        except Exception as e:
            await ctx.send(f"Error retrieving data: {e}")
            return
    
        # Format the data for debugging
        embed = discord.Embed(title=f"Debugging `{currency_name}`", color=discord.Color.red())
        embed.add_field(name="Stored Config ID", value=f"`{config_id}`", inline=False)
        
        if all_data:
            embed.add_field(name="Global Config Data", value=f"```{str(all_data)[:1000]}```", inline=False)
        else:
            embed.add_field(name="Global Config Data", value="No data found.", inline=False)
    
        if all_user_data:
            embed.add_field(name="User-Level Data", value=f"```{str(all_user_data)[:1000]}```", inline=False)
        else:
            embed.add_field(name="User-Level Data", value="No user data found.", inline=False)
    
        if all_member_data:
            embed.add_field(name="Member-Level Data", value=f"```{str(all_member_data)[:1000]}```", inline=False)
        else:
            embed.add_field(name="Member-Level Data", value="No member data found.", inline=False)
    
        await ctx.send(embed=embed)


    def parse_cards(self, xml_data, season, categories):
        root = ET.fromstring(xml_data)
        cards = []
        for card in root.findall(".//CARD"):
            card_season = int(card.find("SEASON").text)
            card_category = card.find("CATEGORY").text
            if str(card_season) in str(season) and card_category in categories:
                card_id = card.find("CARDID").text
                cards.append(
                    {"id": card_id, "season": card_season, "category": card_category}
                )
        return cards

    def parse_card_info(self, xml_data):
        root = ET.fromstring(xml_data)
        return {
            "name": root.find("NAME").text,
            "market_value": root.find("MARKET_VALUE").text
        }

    def parse_token(self, xml_data):
        root = ET.fromstring(xml_data)
        token = root.find("SUCCESS")
        return token.text if token is not None else None

    def get_embed_color(self, category):
        colors = {
            "COMMON": 0x808080,       # Grey
            "UNCOMMON": 0x00FF00,     # Green
            "RARE": 0x0000FF,         # Blue
            "ULTRA-RARE": 0x800080,   # Purple
            "EPIC": 0xFFA500,         # Orange
            "LEGENDARY": 0xFFFF00     # Yellow
        }
        return colors.get(category.upper(), 0xFFFFFF)  # Default to white if not found

    @commands.guild_only()
    @commands.command(name="richest")
    async def richest(self, ctx):
        """Display the top 3 richest users in WellCoins."""
        
        # Get all user balances
        all_users = await self.config.all_users()
        
        # Extract users and balances
        balances = [(ctx.guild.get_member(user_id), data.get("master_balance", 0)) for user_id, data in all_users.items()]
        
        # Filter out users who are not in the server (None values)
        balances = [(user, balance) for user, balance in balances if user is not None]
        
        # Sort users by balance in descending order
        top_users = sorted(balances, key=lambda x: x[1], reverse=True)[:3]
        
        # Create an embed to display results
        embed = discord.Embed(title="🏆 Top 3 Richest Users 🏆", color=discord.Color.gold())
        
        if not top_users:
            embed.description = "No users have any WellCoins yet."
        else:
            for rank, (user, balance) in enumerate(top_users, start=1):
                embed.add_field(name=f"#{rank} {user.display_name}", value=f"💰 `{balance}` WellCoins", inline=False)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Reward users for chatting."""
        if message.author.bot or not message.guild:
            return  # Ignore bot messages and DMs

        if message.guild.id != 1098644885797609492:
            return  # Ignore messages from other servers

        if len(message.content.strip()) < await self.config.guild(message.guild).min_message_length():
            return  # Ignore low-effort messages
        
        
        user = message.author
        guild = message.guild
        channel = message.channel
        # Fetch config settings
        xp_per_message = await self.config.guild(guild).xp_per_message()
        coins_per_message = await self.config.guild(guild).coins_per_message()
        cooldown_time = await self.config.guild(guild).message_cooldown()
        blacklisted_channels = await self.config.guild(guild).blacklisted_channels()
        

        # Check cooldown
        last_message_time = await self.config.user(user).last_message_time()
        current_time = datetime.utcnow().timestamp()
        
        if current_time - last_message_time < cooldown_time:
            return  # On cooldown, no rewards
        
        # Grant XP (always given)
        user_xp = await self.config.user(user).xp()
        await self.config.user(user).xp.set(user_xp + xp_per_message)

        
        # Grant WellCoins if the channel is NOT blacklisted
        if channel.id not in blacklisted_channels:
            user_balance = await self.config.user(user).master_balance()
            await self.config.user(user).master_balance.set(user_balance + coins_per_message)
            # 10% chance to add a green check mark reaction
            if random.random() < 0.10:
                await message.add_reaction("💰")          
            # Update last message time
            await self.config.user(user).last_message_time.set(current_time)
    
    @commands.guild_only()
    @commands.admin()
    @commands.group()
    async def chatrewards(self, ctx):
        """Manage chat-based rewards."""
        pass
    
    @chatrewards.command()
    async def setxp(self, ctx, xp: int):
        """Set the amount of XP gained per message."""
        await self.config.guild(ctx.guild).xp_per_message.set(xp)
        await ctx.send(f"XP per message set to {xp}.")
    
    @chatrewards.command()
    async def setcoins(self, ctx, coins: int):
        """Set the amount of WellCoins gained per valid message."""
        await self.config.guild(ctx.guild).coins_per_message.set(coins)
        await ctx.send(f"WellCoins per message set to {coins}.")
    
    @chatrewards.command()
    async def setcooldown(self, ctx, seconds: int):
        """Set the cooldown time in seconds before users can earn again."""
        await self.config.guild(ctx.guild).message_cooldown.set(seconds)
        await ctx.send(f"Message reward cooldown set to {seconds} seconds.")
    
    @chatrewards.command()
    async def blacklist(self, ctx, channel: discord.TextChannel):
        """Blacklist a channel from earning WellCoins."""
        async with self.config.guild(ctx.guild).blacklisted_channels() as blacklisted_channels:
            if channel.id not in blacklisted_channels:
                blacklisted_channels.append(channel.id)
                await ctx.send(f"{channel.mention} has been blacklisted from earning WellCoins.")
            else:
                await ctx.send(f"{channel.mention} is already blacklisted.")
    
    @chatrewards.command()
    async def unblacklist(self, ctx, channel: discord.TextChannel):
        """Remove a channel from the blacklist."""
        async with self.config.guild(ctx.guild).blacklisted_channels() as blacklisted_channels:
            if channel.id in blacklisted_channels:
                blacklisted_channels.remove(channel.id)
                await ctx.send(f"{channel.mention} has been removed from the blacklist.")
            else:
                await ctx.send(f"{channel.mention} is not blacklisted.")
    
    @chatrewards.command()
    async def viewsettings(self, ctx):
        """View current chat reward settings."""
        settings = await self.config.guild(ctx.guild).all()
        embed = discord.Embed(title="Chat Reward Settings", color=discord.Color.blue())
        embed.add_field(name="XP per Message", value=f"{settings['xp_per_message']}")
        embed.add_field(name="WellCoins per Message", value=f"{settings['coins_per_message']}")
        embed.add_field(name="Cooldown Time", value=f"{settings['message_cooldown']} seconds")
        embed.add_field(name="Blacklisted Channels", value=f"{', '.join([f'<#{cid}>' for cid in settings['blacklisted_channels']])}" if settings['blacklisted_channels'] else "None")
        await ctx.send(embed=embed)
    
    @chatrewards.command()
    async def setminlength(self, ctx, length: int):
        """Set the minimum message length required to earn rewards."""
        await self.config.guild(ctx.guild).min_message_length.set(length)
        await ctx.send(f"Minimum message length set to {length} characters.")

    @commands.command()
    async def linknation(self, ctx, nation_name: str):
        """Link your NationStates nation to your Discord account."""
        verify_url = f"https://www.nationstates.net/page=verify_login"
        await ctx.send(f"To verify your NationStates nation, visit {verify_url} and copy the code in the box.")
        await ctx.send(f"Then, DM me the following command to complete verification: `!verifynation <nation_name> <code>` \n For example `!verifynation {nation_name} FWIXlb2dPZCHm1rq-4isM94FkCJ4RGPUXcjrMjFHsIc`")
    
    @commands.command()
    async def verifynation(self, ctx, nation_name: str, code: str):
        """Verify the NationStates nation using the provided verification code."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://www.nationstates.net/cgi-bin/api.cgi?a=verify&nation={nation_name}&checksum={code}") as response:
                result = await response.text()
                
                if result.strip() == "1":
                    async with self.config.user(ctx.author).linked_nations() as nations:
                        if nation_name not in nations:
                            nations.append(nation_name)
                        await ctx.send(f"✅ Successfully linked your NationStates nation: **{nation_name}**")
                else:
                    await ctx.send("❌ Verification failed. Make sure you entered the correct code and try again.")
    
    @commands.command()
    async def mynation(self, ctx, user: discord.Member = None):
        """Check which NationStates nation is linked to a Discord user."""
        user = user or ctx.author
        nations = await self.config.user(user).linked_nations()
        if nations:
            nation_list = "\n".join(nations)
            await ctx.send(f"🌍 {user.display_name}'s linked NationStates nations is: **{nation_list}**")
        else:
            await ctx.send(f"❌ {user.display_name} has not linked a NationStates nation yet.")
    
    
    @commands.command()
    async def unlinknation(self, ctx, nation_name: str):
        """Unlink a specific NationStates nation from your Discord account."""
        async with self.config.user(ctx.author).linked_nations() as nations:
            if nation_name in nations:
                nations.remove(nation_name)
                await ctx.send(f"✅ Successfully unlinked the NationStates nation: **{nation_name}**")
            else:
                await ctx.send(f"❌ You do not have **{nation_name}** linked to your account.")

    @commands.guild_only()
    @commands.command()
    async def pay(self, ctx, recipient: discord.Member, amount: int):
        """Transfer WellCoins to another player."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than zero.")
            return

        sender_balance = await self.config.user(ctx.author).master_balance()
        if sender_balance < amount:
            await ctx.send(f"❌ You do not have enough WellCoins to complete this transaction. You only have {sender_balance} WellCoins")
            return

        recipient_balance = await self.config.user(recipient).master_balance()
        await self.config.user(ctx.author).master_balance.set(sender_balance - amount)
        await self.config.user(recipient).master_balance.set(recipient_balance + amount)

        await ctx.send(f"✅ {ctx.author.mention} has sent `{amount}` WellCoins to {recipient.mention}!")


    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def govpay(self, ctx, user: discord.Member, amount: int):
        """The government distributes WellCoins to a user."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than zero.")
            return

        user_balance = await self.config.user(user).master_balance()
        await self.config.user(user).master_balance.set(user_balance + amount)
        await ctx.send(f"🏛️ Gob The great has issued `{amount}` WellCoins to {user.mention}!")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def fine(self, ctx, user: discord.Member, amount: int):
        """Fine a user a specific amount of WellCoins."""
        if amount <= 0:
            await ctx.send("❌ Fine amount must be greater than zero.")
            return

        user_balance = await self.config.user(user).master_balance()
        if user_balance < amount:
            await ctx.send(f"❌ {user.mention} does not have enough WellCoins to pay the fine of `{amount}`.")
            return

        await self.config.user(user).master_balance.set(user_balance - amount)
        await ctx.send(f"🚨 {user.mention} has been fined `{amount}` WellCoins by Gob on behalf the goverment!")
    
    @commands.command()
    async def migrate_nations(self, ctx):
        """Migrate old linked_nation data to linked_nations."""
        all_users = await self.config.all_users()
        migrated_count = 0
        
        for user_id, data in all_users.items():
            if "linked_nation" in data and data["linked_nation"]:
                async with self.config.user_from_id(user_id).linked_nations() as nations:
                    if data["linked_nation"] not in nations:
                        nations.append(data["linked_nation"])
                await self.config.user_from_id(user_id).linked_nation.clear()
                migrated_count += 1
        
        await ctx.send(f"✅ Migration complete! {migrated_count} users had their nations migrated.")

    def get_random_ad(self):
        """Fetches a random text file from the ad folder and returns its content."""
        if not os.path.exists(self.ads_folder):
            return "No ad folder found."

        files = [f for f in os.listdir(self.ads_folder) if f.endswith(".txt")]
        if not files:
            return "No ad files found."

        chosen_file = random.choice(files)
        with open(os.path.join(self.ads_folder, chosen_file), "r", encoding="utf-8") as f:
            return f.read()



