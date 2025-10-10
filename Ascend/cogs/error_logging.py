import discord
from discord.ext import commands
import datetime
import logging
import traceback
import asyncio
import sys
from typing import Optional, Dict, Any
import json

class ErrorLoggingCog(commands.Cog, name="Error Logging"):
    """🚨 Centralized error logging and monitoring system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.error_channel_id = 1425319240038223882
        self.error_counts = {}  # Track error frequency
        self.error_cache = []   # Recent errors cache
        self.max_cache_size = 100

    async def setup_logging(self):
        """Set up enhanced logging configuration"""
        # Create custom logger for the bot
        logger = logging.getLogger('sleepless_radio')
        logger.setLevel(logging.INFO)
        
        # Create file handler for persistent logging
        file_handler = logging.FileHandler('bot_errors.log', encoding='utf-8')
        file_handler.setLevel(logging.ERROR)
        
        # Create console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '[{asctime}] [{levelname}] {name}: {message}',
            style='{',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(detailed_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    @commands.Cog.listener()
    async def on_ready(self):
        """Set up logging when bot is ready"""
        await self.setup_logging()
        print(f"🚨 Error Logging System active - Channel ID: {self.error_channel_id}")

    async def on_command_error(self, ctx, error):
        """Handle command errors and log them - called manually from main.py"""
        try:
            # Get the original error if it's wrapped
            original_error = getattr(error, 'original', error)
            
            # Track error frequency
            error_type = type(original_error).__name__
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            
            # Create error entry
            error_entry = {
                'timestamp': datetime.datetime.now(),
                'error_type': error_type,
                'command': ctx.command.name if ctx.command else 'Unknown',
                'user': str(ctx.author),
                'guild': ctx.guild.name if ctx.guild else 'DM',
                'channel': ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM',
                'message': str(original_error),
                'traceback': traceback.format_exception(type(original_error), original_error, original_error.__traceback__)
            }
            
            # Add to cache
            self.error_cache.append(error_entry)
            if len(self.error_cache) > self.max_cache_size:
                self.error_cache.pop(0)
            
            # Handle different error types
            if isinstance(error, commands.CommandNotFound):
                return  # Ignore command not found errors
            
            elif isinstance(error, commands.MissingPermissions):
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="You don't have the required permissions to use this command.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
                return
            
            elif isinstance(error, commands.BotMissingPermissions):
                embed = discord.Embed(
                    title="❌ Bot Missing Permissions",
                    description=f"I don't have the required permissions: {', '.join(error.missing_permissions)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
                return
            
            elif isinstance(error, commands.CommandOnCooldown):
                embed = discord.Embed(
                    title="⏰ Command on Cooldown",
                    description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=10)
                return
            
            elif isinstance(error, commands.MissingRequiredArgument):
                embed = discord.Embed(
                    title="❌ Missing Argument",
                    description=f"Missing required argument: `{error.param.name}`",
                    color=discord.Color.red()
                )
                if ctx.command:
                    embed.add_field(
                        name="Usage",
                        value=f"`{ctx.prefix}{ctx.command.name} {ctx.command.signature}`",
                        inline=False
                    )
                await ctx.send(embed=embed, delete_after=15)
                return
            
            elif isinstance(error, commands.BadArgument):
                embed = discord.Embed(
                    title="❌ Invalid Argument",
                    description=f"Invalid argument provided: {str(error)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=15)
                return
            
            else:
                # Log serious errors to channel
                await self.log_error_to_channel(error_entry)
                
                # Send generic error message to user
                embed = discord.Embed(
                    title="🚨 An Error Occurred",
                    description="An unexpected error occurred while processing your command. The developers have been notified.",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Error ID",
                    value=f"`{len(self.error_cache)}`",
                    inline=True
                )
                await ctx.send(embed=embed, delete_after=20)

        except Exception as e:
            # Fallback error handling
            print(f"Error in error handler: {e}")
            logging.error(f"Error in error handler: {e}")

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Handle general bot errors"""
        try:
            error_info = sys.exc_info()
            if error_info[0] is None:
                return
            
            error_entry = {
                'timestamp': datetime.datetime.now(),
                'error_type': error_info[0].__name__,
                'event': event,
                'message': str(error_info[1]),
                'traceback': traceback.format_exception(*error_info)
            }
            
            await self.log_error_to_channel(error_entry)
            
        except Exception as e:
            print(f"Error in on_error handler: {e}")
            logging.error(f"Error in on_error handler: {e}")

    async def log_error_to_channel(self, error_entry: Dict[str, Any]):
        """Log error to designated Discord channel"""
        try:
            error_channel = self.bot.get_channel(self.error_channel_id)
            if not error_channel:
                print(f"Error channel {self.error_channel_id} not found!")
                return

            # Create main error embed
            embed = discord.Embed(
                title="🚨 Error Report",
                color=discord.Color.red(),
                timestamp=error_entry['timestamp']
            )
            
            # Add basic error info
            embed.add_field(
                name="Error Type",
                value=f"`{error_entry['error_type']}`",
                inline=True
            )
            
            if 'command' in error_entry:
                embed.add_field(
                    name="Command",
                    value=f"`{error_entry['command']}`",
                    inline=True
                )
            
            if 'event' in error_entry:
                embed.add_field(
                    name="Event",
                    value=f"`{error_entry['event']}`",
                    inline=True
                )
            
            # Add context info
            if 'user' in error_entry:
                embed.add_field(
                    name="User",
                    value=error_entry['user'],
                    inline=True
                )
            
            if 'guild' in error_entry:
                embed.add_field(
                    name="Guild",
                    value=error_entry['guild'],
                    inline=True
                )
            
            if 'channel' in error_entry:
                embed.add_field(
                    name="Channel",
                    value=error_entry['channel'],
                    inline=True
                )
            
            # Add error message
            error_message = error_entry['message'][:1024] if len(error_entry['message']) > 1024 else error_entry['message']
            embed.add_field(
                name="Error Message",
                value=f"```{error_message}```",
                inline=False
            )
            
            # Add error frequency
            error_count = self.error_counts.get(error_entry['error_type'], 1)
            embed.add_field(
                name="Frequency",
                value=f"This error has occurred **{error_count}** time(s)",
                inline=True
            )
            
            # Send main embed
            await error_channel.send(embed=embed)
            
            # Send traceback in a separate message if it exists
            if 'traceback' in error_entry and error_entry['traceback']:
                traceback_text = ''.join(error_entry['traceback'])
                
                # Split traceback if too long
                if len(traceback_text) > 1950:
                    chunks = [traceback_text[i:i+1950] for i in range(0, len(traceback_text), 1950)]
                    for i, chunk in enumerate(chunks):
                        embed = discord.Embed(
                            title=f"📄 Traceback (Part {i+1}/{len(chunks)})",
                            description=f"```python\n{chunk}\n```",
                            color=discord.Color.dark_red()
                        )
                        await error_channel.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="📄 Traceback",
                        description=f"```python\n{traceback_text}\n```",
                        color=discord.Color.dark_red()
                    )
                    await error_channel.send(embed=embed)

        except Exception as e:
            print(f"Failed to log error to channel: {e}")
            logging.error(f"Failed to log error to channel: {e}")

    @commands.hybrid_command(name="error_stats", brief="Show error statistics")
    @commands.has_permissions(manage_guild=True)
    async def error_statistics(self, ctx):
        """📊 Display error statistics and recent errors."""
        try:
            if not self.error_counts and not self.error_cache:
                embed = discord.Embed(
                    title="📊 Error Statistics",
                    description="No errors recorded yet! 🎉",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="📊 Error Statistics",
                description="Bot error analytics and statistics",
                color=discord.Color.orange()
            )
            
            # Error frequency stats
            if self.error_counts:
                sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
                error_text = ""
                for error_type, count in sorted_errors[:10]:
                    error_text += f"• **{error_type}**: {count} times\n"
                
                embed.add_field(
                    name="🔥 Most Common Errors",
                    value=error_text if error_text else "No errors recorded",
                    inline=False
                )
            
            # Recent errors
            if self.error_cache:
                recent_errors = self.error_cache[-5:]  # Last 5 errors
                recent_text = ""
                for i, error in enumerate(reversed(recent_errors)):
                    timestamp = error['timestamp'].strftime("%m/%d %H:%M")
                    command = error.get('command', error.get('event', 'Unknown'))
                    recent_text += f"• `{timestamp}` - **{error['error_type']}** in `{command}`\n"
                
                embed.add_field(
                    name="⏰ Recent Errors",
                    value=recent_text if recent_text else "No recent errors",
                    inline=False
                )
            
            # Statistics summary
            total_errors = sum(self.error_counts.values()) if self.error_counts else 0
            unique_errors = len(self.error_counts) if self.error_counts else 0
            
            embed.add_field(
                name="📈 Summary",
                value=f"• **Total Errors**: {total_errors}\n• **Unique Error Types**: {unique_errors}\n• **Cache Size**: {len(self.error_cache)}",
                inline=False
            )
            
            embed.set_footer(text="Error logging is active and monitoring all bot operations")
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error_to_channel({
                'timestamp': datetime.datetime.now(),
                'error_type': type(e).__name__,
                'command': 'error_stats',
                'message': str(e),
                'traceback': traceback.format_exception(type(e), e, e.__traceback__)
            })
            await ctx.send("❌ Failed to retrieve error statistics.")

    @commands.hybrid_command(name="clear_errors", brief="Clear error cache")
    @commands.has_permissions(administrator=True)
    async def clear_error_cache(self, ctx):
        """🧹 Clear the error cache and reset statistics."""
        try:
            old_count = len(self.error_cache)
            old_types = len(self.error_counts)
            
            self.error_cache.clear()
            self.error_counts.clear()
            
            embed = discord.Embed(
                title="🧹 Error Cache Cleared",
                description="Successfully cleared error statistics and cache.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Cleared Data",
                value=f"• **{old_count}** cached errors\n• **{old_types}** error types\n• All statistics reset",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error_to_channel({
                'timestamp': datetime.datetime.now(),
                'error_type': type(e).__name__,
                'command': 'clear_errors',
                'message': str(e),
                'traceback': traceback.format_exception(type(e), e, e.__traceback__)
            })
            await ctx.send("❌ Failed to clear error cache.")

    @commands.hybrid_command(name="test_error", brief="Test error logging", hidden=True)
    @commands.has_permissions(administrator=True)
    async def test_error_logging(self, ctx):
        """🧪 Test the error logging system."""
        try:
            # Intentionally cause an error for testing
            raise Exception("This is a test error for the logging system!")
            
        except Exception as e:
            # Log the test error
            error_entry = {
                'timestamp': datetime.datetime.now(),
                'error_type': type(e).__name__,
                'command': 'test_error',
                'user': str(ctx.author),
                'guild': ctx.guild.name if ctx.guild else 'DM',
                'channel': ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM',
                'message': str(e),
                'traceback': traceback.format_exception(type(e), e, e.__traceback__)
            }
            
            await self.log_error_to_channel(error_entry)
            
            embed = discord.Embed(
                title="🧪 Test Error Sent",
                description="A test error has been logged to the error channel.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    async def log_custom_error(self, error_message: str, context: Dict[str, Any] = None):
        """Public method for other cogs to log custom errors"""
        try:
            error_entry = {
                'timestamp': datetime.datetime.now(),
                'error_type': 'CustomError',
                'message': error_message,
                'traceback': None
            }
            
            if context:
                error_entry.update(context)
            
            await self.log_error_to_channel(error_entry)
            
        except Exception as e:
            print(f"Failed to log custom error: {e}")
            logging.error(f"Failed to log custom error: {e}")

async def setup(bot):
    await bot.add_cog(ErrorLoggingCog(bot))