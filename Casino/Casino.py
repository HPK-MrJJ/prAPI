import random
import discord
from redbot.core import commands, Config, checks
import asyncio


class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(None, identifier=345678654456, force_registration=True)

    async def get_balance(self, user: discord.Member):
        return await self.config.user(user).master_balance()

    async def update_balance(self, user: discord.Member, amount: int):
        balance = await self.get_balance(user)
        new_balance = max(0, balance + amount)  # Prevent negative balance
        await self.config.user(user).master_balance.set(new_balance)
        return new_balance

    @commands.command()
    @commands.admin_or_permissions(administrator=True)
    async def coinflip(self, ctx, bet: int, call_it=None):
        """Flip a coin and win or lose your bet (House Edge: 52% loss, 48% win)"""
        balance = await self.get_balance(ctx.author)
        if bet <= 0 or bet > balance:
            return await ctx.send("Invalid bet amount.")
        
        outcome = random.choices(["win", "lose"], weights=[48, 52])[0]
        if outcome == "win":
            winnings = bet
            new_balance = await self.update_balance(ctx.author, winnings)
            await ctx.send(f"You won! Your new balance is {new_balance} WellCoins.")
        else:
            new_balance = await self.update_balance(ctx.author, -bet)
            await ctx.send(f"You lost! Your new balance is {new_balance} WellCoins.")

    @commands.command()
    @commands.admin_or_permissions(administrator=True)
    async def dice(self, ctx, bet: int):
        """Roll a dice against the house (House rolls 1-6, Player rolls 1-5)"""
        balance = await self.get_balance(ctx.author)
        if bet <= 0 or bet > balance:
            return await ctx.send("Invalid bet amount.")
        
        player_roll = random.randint(1, 6)
        house_roll = random.choices([1, 2, 3, 4, 5, 6], weights=[5, 10, 15, 20, 25, 30])[0]
        
        if player_roll > house_roll:
            winnings = bet
            new_balance = await self.update_balance(ctx.author, winnings)
            await ctx.send(f"You rolled {player_roll}, house rolled {house_roll}. You win! New balance: {new_balance} WellCoins.")
        else:
            new_balance = await self.update_balance(ctx.author, -bet)
            await ctx.send(f"You rolled {player_roll}, house rolled {house_roll}. You lose! New balance: {new_balance} WellCoins.")

    @commands.command()
    @commands.admin_or_permissions(administrator=True)
    async def slots(self, ctx, bet: int):
        """Play a 3x3 slot machine with emojis and live message updates."""
        balance = await self.get_balance(ctx.author)
        if bet <= 0 or bet > balance:
            return await ctx.send("Invalid bet amount.")
        
        emojis = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "🌸"]
        weighted_emojis = ["🍒"] * 10 + ["🍋"] * 12 + ["🍊"] * 15 + ["🍉"] * 18 + ["⭐"] * 20 + ["💎"] * 20 + ["🌸"] * 5
        
        message = await ctx.send("🎰 Rolling the slots... 🎰")
        
        # Generate the initial 3x3 grid
        grid = [[random.choice(weighted_emojis) for _ in range(3)] for _ in range(3)]
        
        # Simulate rolling effect by editing the message
        for _ in range(3):
            temp_grid = [[random.choice(emojis) for _ in range(3)] for _ in range(3)]
            display = "\n".join([" | ".join(row) for row in temp_grid])
            await message.edit(content=f"{display}\n🎰 Rolling... 🎰")
            await asyncio.sleep(0.3)
        
        display = "\n".join([" | ".join(row) for row in grid])
        payout = 0
        flat_grid = [emoji for row in grid for emoji in row]
        result_text = "You lost! 😢"
        
        if flat_grid.count("🍒") >= 2:
            payout = bet * 2
            result_text = "Two or more cherries! 🍒 You win 2x your bet!"
        if any(row.count(row[0]) == 3 for row in grid) or any(col.count(col[0]) == 3 for col in zip(*grid)):
            payout = max(payout, bet * 5)
            result_text = "Three of a kind in a row or column! 🎉 You win 5x your bet!"
        if flat_grid.count("🌸") == 3:
            payout = bet * 25
            result_text = "JACKPOT! 🌸🌸🌸 You hit the cherry blossoms jackpot!"
        
        if payout == 0:
            payout = -bet  # House edge ensured
        
        new_balance = await self.update_balance(ctx.author, payout)
        await message.edit(content=f"{display}\n{result_text} New balance: {new_balance} WellCoins.")

    @commands.command()
    @commands.admin_or_permissions(administrator=True)
    async def roulette(self, ctx, bet: int, choice: str):
        """Play roulette (Red/Black = 2x, Number (0-36) = 35x)"""
        balance = await self.get_balance(ctx.author)
        if bet <= 0 or bet > balance:
            return await ctx.send("Invalid bet amount.")
        
        result = random.randint(0, 36)
        color = "red" if result % 2 == 0 else "black"
        payout = 0
        
        if choice.lower() in ["red", "black"]:
            if choice.lower() == color:
                payout = bet * 2
        elif choice.isdigit() and 0 <= int(choice) <= 36:
            if int(choice) == result:
                payout = bet * 35
        
        if payout > 0:
            new_balance = await self.update_balance(ctx.author, payout)
            await ctx.send(f"Roulette landed on {result} ({color}). You won {payout} WellCoins! New balance: {new_balance}")
        else:
            new_balance = await self.update_balance(ctx.author, -bet)
            await ctx.send(f"Roulette landed on {result} ({color}). You lost! New balance: {new_balance} WellCoins.")
