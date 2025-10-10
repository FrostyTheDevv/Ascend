import discord
from discord.ext import commands
import asyncio
import wavelink
import config
from replit_auth import ReplitAuth
from database import DatabaseManager
import aiosqlite
import time
import os

class Ascend(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.members = True  # For better user management
        
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True
        )
        self.replit_auth = ReplitAuth()
        self.db = DatabaseManager()
        self.start_time = time.time()
        
    async def get_prefix(self, message):
        """Dynamic prefix based on guild settings"""
        if message.guild:
            try:
                guild_data = await self.db.get_guild(message.guild.id)
                if guild_data and 'prefix' in guild_data:
                    prefix = guild_data['prefix']
                    print(f"Debug: Guild {message.guild.id} has prefix: '{prefix}'")
                    # Support no-prefix mode (empty string prefix)
                    if prefix == "":
                        # For no-prefix mode, return both mention and empty string
                        print(f"Debug: No-prefix mode enabled for guild {message.guild.id}")
                        return commands.when_mentioned_or("")(self, message)
                    # Return the custom prefix
                    print(f"Debug: Using custom prefix '{prefix}' for guild {message.guild.id}")
                    return commands.when_mentioned_or(prefix)(self, message)
                else:
                    print(f"Debug: No guild data found for {message.guild.id}, using default prefix")
            except Exception as e:
                print(f"Error getting guild prefix: {e}")
                # Fallback to default prefix
                pass
        # Default to config prefix and mentions
        print(f"Debug: Using default prefix '{config.BOT_PREFIX}'")
        return commands.when_mentioned_or(config.BOT_PREFIX)(self, message)
    
    @commands.command(name='debugprefix', hidden=True)
    async def debug_prefix(self, ctx):
        """Debug command to check prefix settings"""
        if not ctx.guild:
            await ctx.send("This command only works in servers.")
            return
            
        try:
            guild_data = await self.db.get_guild(ctx.guild.id)
            current_prefix = guild_data['prefix'] if guild_data and 'prefix' in guild_data else config.BOT_PREFIX
            
            embed = discord.Embed(
                title="🔍 Prefix Debug Info",
                color=discord.Color.blue()
            )
            embed.add_field(name="Guild ID", value=str(ctx.guild.id), inline=True)
            embed.add_field(name="Guild Data Found", value=str(bool(guild_data)), inline=True)
            embed.add_field(name="Current Prefix", value=f"`{current_prefix}`", inline=True)
            embed.add_field(name="Default Prefix", value=f"`{config.BOT_PREFIX}`", inline=True)
            embed.add_field(name="Message Prefix", value=f"`{ctx.prefix}`", inline=True)
            
            if guild_data:
                embed.add_field(name="Raw Guild Data", value=f"```{guild_data}```", inline=False)
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error checking prefix: {e}")
        
    async def setup_hook(self):
        # Initialize database
        await self.db.initialize_database()
        
        # Load all cogs
        extensions = [
            'cogs.error_logging',    # Load error logging first
            'cogs.music',
            'cogs.music_settings',
            'cogs.audio_commands',
            'cogs.search_discovery',
            'cogs.queue_control',
            'cogs.accounts', 
            'cogs.help',
            'cogs.utility'
        ]
        
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(f'✅ Loaded {extension}')
            except Exception as e:
                print(f'❌ Failed to load {extension}: {e}')
        
        # Setup Lavalink
        try:
            node: wavelink.Node = wavelink.Node(
                identifier='Ascend',
                uri=f'http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}',
                password=config.LAVALINK_PASSWORD
            )
            
            await wavelink.Pool.connect(client=self, nodes=[node])
            print('✅ Lavalink connection initiated')
        except Exception as e:
            print(f'❌ Lavalink connection failed: {e}')
            print('Music commands will be limited without Lavalink')
        
    async def on_ready(self):
        print(f'┌{"─" * 60}┐')
        print(f'│ Ascend Discord Music Bot v2.0 - Free & Open Source  │')
        print(f'├{"─" * 60}┤')
        print(f'│ Bot User: {str(self.user):<47} │')
        if self.user:
            print(f'│ Bot ID: {str(self.user.id):<49} │')
        print(f'│ Servers: {len(self.guilds):<50} │')
        print(f'│ Users: {len(self.users):<52} │')
        print(f'│ Commands: {len(self.commands):<49} │')
        print(f'│ Cogs: {len(self.cogs):<53} │')
        print(f'│ Database: Connected                                  │')
        print(f'│ Lavalink: Connected                                  │')
        print(f'│ Features: Free & Open Source, Full Features        │')
        print(f'└{"─" * 60}┘')
        
        # Note: We removed slash command sync since we're using prefix commands
        print('🎵 Ascend Music Bot v2.0 is ready! 100% free with all features unlocked!')
            
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f'🎵 Lavalink node {payload.node.identifier} is ready!')
    
    async def on_guild_join(self, guild):
        """Handle bot joining a new guild"""
        await self.db.create_guild(
            guild_id=guild.id,
            guild_name=guild.name,
            owner_id=guild.owner_id
        )
        print(f'✅ Joined new guild: {guild.name} ({guild.id})')
        
        # Send welcome message to first available channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🎵 Thank you for adding Ascend!",
                    description="Your music bot is ready to rock!",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="🚀 Quick Start",
                    value="• Use `!help` to see all commands\n• Use `!setup` to configure the bot\n• Use `!play <song>` to start playing music",
                    inline=False
                )
                embed.add_field(
                    name="🎵 Key Features", 
                    value="• User accounts with statistics\n• Custom playlists\n• Spotify integration\n• Modern UI with interactive controls",
                    inline=False
                )
                await channel.send(embed=embed)
                break
    
    async def on_command(self, ctx):
        """Log command usage"""
        if ctx.guild:
            # Ensure user exists in database
            user_data = await self.db.get_user(ctx.author.id)
            if not user_data:
                await self.db.create_user(
                    user_id=ctx.author.id,
                    username=str(ctx.author),
                    display_name=ctx.author.display_name
                )
            
            # Log command usage
            await self.db.log_command_usage(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id,
                command_name=ctx.command.name
            )
            
            # Update user activity
            await self.db.update_user_activity(ctx.author.id)
    
    async def on_command_error(self, ctx, error):
        """Handle command errors gracefully - delegated to error logging cog"""
        # Let the error logging cog handle this
        error_logging_cog = self.get_cog('Error Logging')
        if error_logging_cog:
            await error_logging_cog.on_command_error(ctx, error)
        else:
            # Fallback error handling if error logging cog isn't loaded
            if isinstance(error, commands.CommandNotFound):
                return  # Ignore command not found errors
            
            elif isinstance(error, commands.MissingPermissions):
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="You don't have permission to use this command.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
            
            elif isinstance(error, commands.CommandOnCooldown):
                embed = discord.Embed(
                    title="⏰ Command Cooldown",
                    description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=10)
            
            else:
                embed = discord.Embed(
                    title="❌ An Error Occurred",
                    description="Something went wrong while executing this command.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
                print(f'Command error: {error}')

    async def on_message(self, message):
        """Enhanced message processing for better command reading"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Log all messages for debugging
        if message.guild:
            print(f"💬 Message from {message.author} in {message.guild.name}: {message.content[:50]}")
        
        # Process commands normally - this handles everything
        await self.process_commands(message)

async def main():
    # Install missing dependency if needed
    try:
        import aiosqlite
    except ImportError:
        print('Installing aiosqlite...')
        import subprocess
        subprocess.check_call(['pip', 'install', 'aiosqlite', 'psutil'])
        import aiosqlite
    
    bot = Ascend()
    
    discord_token = config.DISCORD_TOKEN
    if not discord_token:
        discord_token = await bot.replit_auth.get_discord_token()
    
    if not discord_token:
        print('❌ Error: No Discord token found!')
        print('Please set up Discord integration or provide DISCORD_BOT_TOKEN in environment variables.')
        return
    
    async with bot:
        await bot.start(discord_token)

if __name__ == '__main__':
    asyncio.run(main())
