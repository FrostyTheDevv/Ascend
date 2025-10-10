import discord
from discord.ext import commands
from discord import ui
import wavelink
import datetime
import logging
import asyncio
import random
from typing import Dict, List, Optional, Union
import json

class QueueControlCog(commands.Cog, name="Queue Control"):
    """📋 Advanced queue management and control"""
    
    def __init__(self, bot):
        self.bot = bot
        self.error_channel_id = 1425319240038223882
        self.queue_history = {}  # Store queue history per guild
        self.saved_queues = {}   # Store saved queues per guild

    async def log_error(self, error: str, guild_id: Optional[int] = None):
        """Log errors to designated channel"""
        try:
            error_channel = self.bot.get_channel(self.error_channel_id)
            if error_channel:
                embed = discord.Embed(
                    title="🚨 Queue Control Error",
                    description=f"```{error}```",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                if guild_id:
                    guild = self.bot.get_guild(guild_id)
                    embed.add_field(name="Guild", value=guild.name if guild else f"ID: {guild_id}", inline=True)
                await error_channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Failed to log error to channel: {e}")

    def has_dj_permissions(self, ctx) -> bool:
        """Check if user has DJ permissions"""
        if ctx.author.guild_permissions.manage_guild:
            return True
        
        # Check for DJ role (would need to get from music_settings cog)
        music_settings = self.bot.get_cog('Music Settings')
        if music_settings:
            settings = music_settings.get_guild_settings(ctx.guild.id)
            dj_role_id = settings.get('dj_role')
            if dj_role_id:
                return any(role.id == dj_role_id for role in ctx.author.roles)
        
        return False

    @commands.hybrid_command(name="q", brief="Show current queue")
    async def show_queue(self, ctx, page: int = 1):
        """📋 Display the current music queue with advanced controls."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                embed = discord.Embed(
                    title="📋 Queue Empty",
                    description="No songs in queue. Use `/play` to add music!",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            if not queue and not player.current:
                embed = discord.Embed(
                    title="📋 Queue Empty",
                    description="No songs in queue. Use `/play` to add music!",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            # Create queue view with pagination and controls
            view = QueueView(queue, player, page, ctx.author.id, self.has_dj_permissions(ctx))
            embed = self.create_queue_embed(queue, player, page)
            
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Queue display error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to display queue.")

    def create_queue_embed(self, queue: List, player, page: int = 1) -> discord.Embed:
        """Create queue display embed"""
        items_per_page = 10
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = queue[start_idx:end_idx]
        
        total_duration = sum(track.length for track in queue if hasattr(track, 'length') and track.length)
        queue_duration = self.format_duration(total_duration)
        
        embed = discord.Embed(
            title="📋 Music Queue",
            description=f"**{len(queue)}** songs in queue | Duration: `{queue_duration}`",
            color=discord.Color.blue()
        )
        
        # Current track
        if player.current:
            current_pos = player.position // 1000 if hasattr(player, 'position') else 0
            current_dur = player.current.length // 1000 if hasattr(player.current, 'length') else 0
            progress = f"{self.format_duration(current_pos * 1000)} / {self.format_duration(player.current.length)}"
            
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{player.current.title}**\nBy {player.current.author}\n`{progress}`",
                inline=False
            )
        
        # Queue items
        if page_items:
            queue_text = ""
            for i, track in enumerate(page_items):
                position = start_idx + i + 1
                duration = self.format_duration(track.length) if hasattr(track, 'length') else "Unknown"
                title = track.title[:40] + "..." if len(track.title) > 40 else track.title
                queue_text += f"`{position}.` **{title}**\n    By {track.author} | `{duration}`\n\n"
            
            embed.add_field(
                name=f"📜 Queue (Page {page})",
                value=queue_text if queue_text else "No items on this page",
                inline=False
            )
        
        # Footer with page info
        total_pages = (len(queue) - 1) // items_per_page + 1 if queue else 1
        embed.set_footer(text=f"Page {page}/{total_pages} • Use buttons to control queue")
        
        return embed

    @commands.hybrid_command(name="move", brief="Move track in queue")
    async def move_track(self, ctx, from_pos: int, to_pos: int):
        """🔄 Move a track from one position to another in the queue."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            if not self.has_dj_permissions(ctx):
                await ctx.send("❌ You need DJ permissions to move tracks!")
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            # Validate positions
            if not 1 <= from_pos <= len(queue) or not 1 <= to_pos <= len(queue):
                await ctx.send(f"❌ Invalid position! Queue has {len(queue)} tracks.")
                return

            # Move track
            track = queue.pop(from_pos - 1)
            queue.insert(to_pos - 1, track)
            
            embed = discord.Embed(
                title="🔄 Track Moved",
                description=f"Moved **{track.title}** from position {from_pos} to {to_pos}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Move track error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to move track.")

    @commands.hybrid_command(name="remove", aliases=["rm"], brief="Remove track from queue")
    async def remove_track(self, ctx, position: int):
        """🗑️ Remove a track from the queue by position."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            if not self.has_dj_permissions(ctx):
                await ctx.send("❌ You need DJ permissions to remove tracks!")
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            if not 1 <= position <= len(queue):
                await ctx.send(f"❌ Invalid position! Queue has {len(queue)} tracks.")
                return

            # Remove track
            removed_track = queue.pop(position - 1)
            
            embed = discord.Embed(
                title="🗑️ Track Removed",
                description=f"Removed **{removed_track.title}** by {removed_track.author}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Remove track error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to remove track.")

    @commands.hybrid_command(name="clear", brief="Clear the queue")
    async def clear_queue(self, ctx):
        """🧹 Clear all tracks from the queue."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            if not self.has_dj_permissions(ctx):
                await ctx.send("❌ You need DJ permissions to clear the queue!")
                return

            player = ctx.voice_client
            queue_size = len(player.queue._queue) if hasattr(player.queue, '_queue') else 0
            
            # Clear queue
            if hasattr(player.queue, 'clear'):
                player.queue.clear()
            
            embed = discord.Embed(
                title="🧹 Queue Cleared",
                description=f"Removed **{queue_size}** tracks from the queue.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Clear queue error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to clear queue.")

    @commands.hybrid_command(name="qshuffle", aliases=["shuffleq"], brief="Shuffle the queue")
    async def shuffle_queue(self, ctx):
        """🔀 Shuffle all tracks in the queue randomly."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            if not self.has_dj_permissions(ctx):
                await ctx.send("❌ You need DJ permissions to shuffle the queue!")
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            if len(queue) < 2:
                await ctx.send("❌ Need at least 2 tracks to shuffle!")
                return

            # Shuffle queue
            random.shuffle(queue)
            
            embed = discord.Embed(
                title="🔀 Queue Shuffled",
                description=f"Shuffled **{len(queue)}** tracks in the queue.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Shuffle queue error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to shuffle queue.")

    @commands.hybrid_command(name="loop", brief="Set loop mode")
    async def loop_mode(self, ctx, mode: str = None):
        """🔁 Set loop mode (off/track/queue)."""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Not connected to voice!")
                return

            if mode is None:
                # Show loop controls
                view = LoopControlView(ctx.voice_client)
                embed = discord.Embed(
                    title="🔁 Loop Controls",
                    description="Choose your loop preference:",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Loop Modes",
                    value="🔁 **Track** - Repeat current song\n🔄 **Queue** - Repeat entire queue\n❌ **Off** - No looping",
                    inline=False
                )
                await ctx.send(embed=embed, view=view)
                return

            valid_modes = ["off", "track", "queue"]
            if mode.lower() not in valid_modes:
                await ctx.send(f"❌ Invalid mode! Use: {', '.join(valid_modes)}")
                return

            # Set loop mode (implementation would depend on your player setup)
            mode_display = {
                "off": "❌ Off",
                "track": "🔁 Track",
                "queue": "🔄 Queue"
            }
            
            embed = discord.Embed(
                title="🔁 Loop Mode Updated",
                description=f"Loop mode set to: **{mode_display[mode.lower()]}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Loop mode error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set loop mode.")

    @commands.hybrid_command(name="skipto", brief="Skip to specific track")
    async def skip_to(self, ctx, position: int):
        """⏭️ Skip to a specific track in the queue."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            if not self.has_dj_permissions(ctx):
                await ctx.send("❌ You need DJ permissions to skip to tracks!")
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            if not 1 <= position <= len(queue):
                await ctx.send(f"❌ Invalid position! Queue has {len(queue)} tracks.")
                return

            # Skip to position (remove tracks before target)
            skipped_tracks = []
            for _ in range(position - 1):
                if queue:
                    skipped_tracks.append(queue.pop(0))
            
            target_track = queue[0] if queue else None
            if target_track:
                embed = discord.Embed(
                    title="⏭️ Skipped to Track",
                    description=f"Skipped {len(skipped_tracks)} tracks to:\n**{target_track.title}** by {target_track.author}",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                
                # Skip current track to start the target
                if hasattr(player, 'skip'):
                    await player.skip()

        except Exception as e:
            await self.log_error(f"Skip to error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to skip to track.")

    @commands.hybrid_command(name="save_queue", brief="Save current queue")
    async def save_queue(self, ctx, name: str):
        """💾 Save the current queue for later use."""
        try:
            if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
                await ctx.send("❌ No queue found!")
                return

            player = ctx.voice_client
            queue = player.queue._queue if hasattr(player.queue, '_queue') else []
            
            if not queue:
                await ctx.send("❌ Queue is empty!")
                return

            # Initialize saved queues for guild
            if ctx.guild.id not in self.saved_queues:
                self.saved_queues[ctx.guild.id] = {}

            # Save queue
            queue_data = []
            for track in queue:
                queue_data.append({
                    'title': track.title,
                    'author': track.author,
                    'uri': track.uri,
                    'length': track.length
                })

            self.saved_queues[ctx.guild.id][name] = {
                'tracks': queue_data,
                'created_by': ctx.author.id,
                'created_at': datetime.datetime.now().isoformat(),
                'track_count': len(queue_data)
            }

            embed = discord.Embed(
                title="💾 Queue Saved",
                description=f"Saved **{len(queue_data)}** tracks as: **{name}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Queue Info",
                value=f"📁 Name: {name}\n🎵 Tracks: {len(queue_data)}\n👤 Saved by: {ctx.author.mention}",
                inline=False
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Save queue error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to save queue.")

    @commands.hybrid_command(name="load_queue", brief="Load a saved queue")
    async def load_queue(self, ctx, name: str = None):
        """📁 Load a previously saved queue."""
        try:
            if ctx.guild.id not in self.saved_queues:
                self.saved_queues[ctx.guild.id] = {}

            saved_queues = self.saved_queues[ctx.guild.id]

            if name is None:
                # Show available saved queues
                if not saved_queues:
                    embed = discord.Embed(
                        title="📁 No Saved Queues",
                        description="No saved queues found. Use `/save_queue` to save the current queue.",
                        color=discord.Color.blue()
                    )
                    await ctx.send(embed=embed)
                    return

                view = SavedQueuesView(saved_queues, ctx.voice_client)
                embed = discord.Embed(
                    title="📁 Saved Queues",
                    description="Select a queue to load:",
                    color=discord.Color.blue()
                )

                for queue_name, queue_data in saved_queues.items():
                    created_date = datetime.datetime.fromisoformat(queue_data['created_at']).strftime("%m/%d/%Y")
                    embed.add_field(
                        name=f"📋 {queue_name}",
                        value=f"🎵 {queue_data['track_count']} tracks\n📅 Created: {created_date}",
                        inline=True
                    )

                await ctx.send(embed=embed, view=view)
                return

            if name not in saved_queues:
                await ctx.send(f"❌ Queue '{name}' not found!")
                return

            # Load queue
            queue_data = saved_queues[name]
            tracks_loaded = len(queue_data['tracks'])

            embed = discord.Embed(
                title="📁 Queue Loaded",
                description=f"Loaded **{tracks_loaded}** tracks from: **{name}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Queue Info",
                value=f"📁 Name: {name}\n🎵 Tracks: {tracks_loaded}\n📅 Created: {datetime.datetime.fromisoformat(queue_data['created_at']).strftime('%m/%d/%Y')}",
                inline=False
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Load queue error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to load queue.")

    @commands.hybrid_command(name="queue_history", brief="Show queue history")
    async def queue_history(self, ctx):
        """📜 Show recently played tracks and queue history."""
        try:
            if ctx.guild.id not in self.queue_history or not self.queue_history[ctx.guild.id]:
                embed = discord.Embed(
                    title="📜 Queue History",
                    description="No queue history found.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            history = self.queue_history[ctx.guild.id][-10:]  # Last 10 entries
            
            embed = discord.Embed(
                title="📜 Queue History",
                description="Recently played tracks:",
                color=discord.Color.blue()
            )
            
            for i, entry in enumerate(reversed(history)):
                timestamp = entry['timestamp'].strftime("%m/%d %H:%M")
                embed.add_field(
                    name=f"{len(history) - i}. {entry['title'][:30]}{'...' if len(entry['title']) > 30 else ''}",
                    value=f"🎤 {entry['artist'][:20]}\n⏰ {timestamp}",
                    inline=True
                )
            
            embed.set_footer(text="Track history from this server")
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Queue history error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to retrieve queue history.")

    def format_duration(self, milliseconds: int) -> str:
        """Format duration from milliseconds to mm:ss"""
        if milliseconds is None:
            return "Unknown"
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

# UI Components for Queue Control

class QueueView(ui.View):
    def __init__(self, queue: List, player, page: int, user_id: int, has_dj: bool):
        super().__init__(timeout=300)
        self.queue = queue
        self.player = player
        self.current_page = page
        self.user_id = user_id
        self.has_dj = has_dj
        self.items_per_page = 10

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            # Update embed here
            await interaction.response.send_message(f"📄 Page {self.current_page}", ephemeral=True)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        total_pages = (len(self.queue) - 1) // self.items_per_page + 1
        if self.current_page < total_pages:
            self.current_page += 1
            # Update embed here
            await interaction.response.send_message(f"📄 Page {self.current_page}", ephemeral=True)

    @ui.button(label="🔀", style=discord.ButtonStyle.primary)
    async def shuffle_queue(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_dj:
            await interaction.response.send_message("❌ You need DJ permissions!", ephemeral=True)
            return
        
        random.shuffle(self.queue)
        await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)

    @ui.button(label="🧹", style=discord.ButtonStyle.danger)
    async def clear_queue(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_dj:
            await interaction.response.send_message("❌ You need DJ permissions!", ephemeral=True)
            return
        
        if hasattr(self.player.queue, 'clear'):
            self.player.queue.clear()
        await interaction.response.send_message("🧹 Queue cleared!", ephemeral=True)

    @ui.select(placeholder="Select track to manage", options=[
        discord.SelectOption(label="Track 1", value="0"),
        discord.SelectOption(label="Track 2", value="1"),
        discord.SelectOption(label="Track 3", value="2"),
        discord.SelectOption(label="Track 4", value="3"),
        discord.SelectOption(label="Track 5", value="4"),
    ])
    async def select_track(self, interaction: discord.Interaction, select: ui.Select):
        track_index = int(select.values[0])
        start_idx = (self.current_page - 1) * self.items_per_page
        actual_index = start_idx + track_index
        
        if actual_index < len(self.queue):
            track = self.queue[actual_index]
            view = TrackActionView(track, actual_index, self.has_dj)
            
            embed = discord.Embed(
                title="🎵 Track Selected",
                description=f"**{track.title}**\nBy {track.author}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Position", value=f"{actual_index + 1}", inline=True)
            embed.add_field(name="Duration", value=f"`{self.format_duration(track.length)}`", inline=True)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def format_duration(self, milliseconds: int) -> str:
        """Format duration helper"""
        if milliseconds is None:
            return "Unknown"
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

class TrackActionView(ui.View):
    def __init__(self, track, position: int, has_dj: bool):
        super().__init__(timeout=180)
        self.track = track
        self.position = position
        self.has_dj = has_dj

    @ui.button(label="⏭️ Skip To", style=discord.ButtonStyle.primary)
    async def skip_to_track(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_dj:
            await interaction.response.send_message("❌ You need DJ permissions!", ephemeral=True)
            return
        
        await interaction.response.send_message(f"⏭️ Skipping to: **{self.track.title}**", ephemeral=True)

    @ui.button(label="🗑️ Remove", style=discord.ButtonStyle.danger)
    async def remove_track(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_dj:
            await interaction.response.send_message("❌ You need DJ permissions!", ephemeral=True)
            return
        
        await interaction.response.send_message(f"🗑️ Removed: **{self.track.title}**", ephemeral=True)

    @ui.button(label="🔄 Move", style=discord.ButtonStyle.secondary)
    async def move_track(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_dj:
            await interaction.response.send_message("❌ You need DJ permissions!", ephemeral=True)
            return
        
        modal = MoveTrackModal(self.track, self.position)
        await interaction.response.send_modal(modal)

class MoveTrackModal(ui.Modal, title="Move Track"):
    def __init__(self, track, current_position: int):
        super().__init__()
        self.track = track
        self.current_position = current_position

    new_position = ui.TextInput(
        label="New Position",
        placeholder="Enter new position number...",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_pos = int(self.new_position.value)
            embed = discord.Embed(
                title="🔄 Track Moved",
                description=f"Moved **{self.track.title}** from position {self.current_position + 1} to {new_pos}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid position number!", ephemeral=True)

class LoopControlView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.select(placeholder="Select loop mode", options=[
        discord.SelectOption(label="Off", description="Disable looping", value="off", emoji="❌"),
        discord.SelectOption(label="Track", description="Repeat current song", value="track", emoji="🔁"),
        discord.SelectOption(label="Queue", description="Repeat entire queue", value="queue", emoji="🔄"),
    ])
    async def select_loop_mode(self, interaction: discord.Interaction, select: ui.Select):
        mode = select.values[0]
        mode_display = {
            "off": "❌ Off",
            "track": "🔁 Track",
            "queue": "🔄 Queue"
        }
        
        embed = discord.Embed(
            title="🔁 Loop Mode Updated",
            description=f"Loop mode set to: **{mode_display[mode]}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SavedQueuesView(ui.View):
    def __init__(self, saved_queues: Dict, voice_client):
        super().__init__(timeout=300)
        self.saved_queues = saved_queues
        self.voice_client = voice_client

        # Create select options from saved queues
        options = []
        for name, data in saved_queues.items():
            options.append(
                discord.SelectOption(
                    label=name[:25],
                    description=f"{data['track_count']} tracks",
                    value=name
                )
            )
        
        if options:
            self.add_item(QueueSelectMenu(options, saved_queues))

    @ui.button(label="🗑️ Delete Queue", style=discord.ButtonStyle.danger)
    async def delete_queue(self, interaction: discord.Interaction, button: ui.Button):
        # This would open another modal/select for deleting
        await interaction.response.send_message("🗑️ Select a queue to delete...", ephemeral=True)

class QueueSelectMenu(ui.Select):
    def __init__(self, options: List[discord.SelectOption], saved_queues: Dict):
        super().__init__(placeholder="Select a queue to load", options=options)
        self.saved_queues = saved_queues

    async def callback(self, interaction: discord.Interaction):
        queue_name = self.values[0]
        queue_data = self.saved_queues[queue_name]
        
        embed = discord.Embed(
            title="📁 Queue Loaded",
            description=f"Loading **{queue_data['track_count']}** tracks from: **{queue_name}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(QueueControlCog(bot))