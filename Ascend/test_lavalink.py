#!/usr/bin/env python3
"""
Simple Lavalink connection test for Wavelink v4
"""
import asyncio
import os
import discord
import wavelink
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TestBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Bot logged in as {self.user}')
        
        # Test Lavalink connection
        await self.test_lavalink_connection()

    async def test_lavalink_connection(self):
        try:
            print("=" * 60)
            print("🔗 LAVALINK CONNECTION TEST")
            print("=" * 60)
            
            # Get configuration
            lavalink_uri = os.getenv('LAVALINK_URI', 'https://sleeplessll.replit.app:5000')
            lavalink_password = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
            
            print(f"📍 URI: {lavalink_uri}")
            print(f"🔑 Password: {'*' * len(lavalink_password)}")
            
            # Create node
            print("🔧 Creating Wavelink node...")
            node = wavelink.Node(
                uri=lavalink_uri,
                password=lavalink_password,
                identifier="TestNode"
            )
            
            print(f"✅ Node created: {node.identifier}")
            
            # Connect to pool
            print("📡 Connecting to Wavelink pool...")
            await wavelink.Pool.connect(client=self, nodes=[node])
            
            print(f"📊 Connection completed!")
            print(f"🔍 Active nodes: {len(wavelink.Pool.nodes)}")
            print(f"🔍 Node identifiers: {list(wavelink.Pool.nodes.keys())}")
            
            # Test node retrieval
            test_node = wavelink.Pool.get_node("TestNode")
            if test_node:
                print("✅ SUCCESS! Node retrieval works!")
                print(f"   📍 Node URI: {test_node.uri}")
                print(f"   🏷️  Node ID: {test_node.identifier}")
                print("=" * 60)
            else:
                print("❌ FAILED! Could not retrieve node")
                print("=" * 60)
                
        except Exception as e:
            print("❌ CONNECTION FAILED!")
            print(f"💥 Error: {e}")
            print("=" * 60)
        
        # Close the bot
        await self.close()

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
        print("Test interrupted by user")