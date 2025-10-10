#!/usr/bin/env python3
"""
Test script for the new music cog
"""
import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='<', intents=intents)

    async def on_ready(self):
        print(f'✅ Bot logged in as {self.user}')
        print(f'🔗 Connected to {len(self.guilds)} guilds')
        
        # Load the new music cog
        try:
            await self.load_extension('cogs.new_music')
            print('✅ New music cog loaded successfully!')
        except Exception as e:
            print(f'❌ Failed to load new music cog: {e}')

# Run the test
if __name__ == "__main__":
    bot = TestBot()
    
    # Get token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No DISCORD_BOT_TOKEN found in .env file!")
        exit(1)
    
    try:
        asyncio.run(bot.start(token))
    except KeyboardInterrupt:
        print("Bot stopped by user")