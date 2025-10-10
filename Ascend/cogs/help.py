import discord
from discord.ext import commands
from discord import ui
import datetime
from typing import Dict, List, Optional
from database import DatabaseManager

# Advanced Help Components for Categories

class MusicHelpView(ui.View):
    def __init__(self, bot, prefix: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix
        self.current_page = "overview"

    @ui.select(placeholder="🎵 Select Music Category", options=[
        discord.SelectOption(label="🏠 Overview", value="overview", description="Music system overview", emoji="🏠"),
        discord.SelectOption(label="▶️ Playback", value="playback", description="Play, pause, skip commands", emoji="▶️"),
        discord.SelectOption(label="📋 Queue", value="queue", description="Queue management commands", emoji="📋"),
        discord.SelectOption(label="🎛️ Audio", value="audio", description="Volume, equalizer, effects", emoji="🎛️"),
        discord.SelectOption(label="🔍 Search", value="search", description="Search and discovery", emoji="🔍"),
        discord.SelectOption(label="🟢 Spotify", value="spotify", description="Spotify integration", emoji="🟢"),
        discord.SelectOption(label="⚙️ Settings", value="settings", description="Music preferences", emoji="⚙️"),
    ], row=0)
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        self.current_page = select.values[0]
        embed = self.create_embed(select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="🎮", label="Try Commands", style=discord.ButtonStyle.primary, row=1)
    async def try_commands(self, interaction: discord.Interaction, button: ui.Button):
        modal = QuickCommandModal(self.prefix, "music")
        await interaction.response.send_modal(modal)

    @ui.button(emoji="🎵", label="Quick Play", style=discord.ButtonStyle.green, row=1)
    async def quick_play(self, interaction: discord.Interaction, button: ui.Button):
        modal = QuickPlayModal(self.prefix)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="📊", label="Music Stats", style=discord.ButtonStyle.secondary, row=1)
    async def music_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📊 Music System Statistics",
            color=discord.Color.green()
        )
        
        # Get music stats
        total_commands = 14  # Music commands count
        embed.add_field(
            name="🎵 Music Commands",
            value=f"**Total Commands:** {total_commands}\n**Platforms:** YouTube, Spotify, SoundCloud\n**Audio Quality:** Up to 320kbps",
            inline=True
        )
        
        embed.add_field(
            name="🎛️ Audio Features",
            value="**Equalizer:** 15-band professional\n**Effects:** Reverb, Bass Boost, Distortion\n**Volume:** 0-200% range",
            inline=True
        )
        
        embed.add_field(
            name="📋 Queue Features",
            value="**Max Queue:** Unlimited\n**Modes:** Normal, Shuffle, Loop\n**Autoplay:** Smart recommendations",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji="🆘", label="Get Help", style=discord.ButtonStyle.secondary, row=1)
    async def get_help(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🆘 Need Help with Music?",
            description="Get assistance with music commands and features",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📖 Quick Help",
            value=f"• `{self.prefix}help <command>` - Detailed command help\n• `{self.prefix}status` - Check Lavalink connection\n• `{self.prefix}about` - Bot information",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Support Links",
            value="[Support Server](https://discord.gg/zCdWpTNN6Y) • [Documentation](https://ascend-docs.replit.app/) • [GitHub](https://github.com/FrostyTheDevv/Ascend)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji="🏠", label="Main Help", style=discord.ButtonStyle.secondary, row=2)
    async def main_help(self, interaction: discord.Interaction, button: ui.Button):
        # Return to main help
        from cogs.help import HelpCog
        help_cog = self.bot.get_cog('HelpCog')
        if help_cog:
            await help_cog.help_command(interaction, command_or_category=None)

    def create_embed(self, category: str):
        if category == "overview":
            embed = discord.Embed(
                title="🎵 Music System - Complete Overview",
                description="**Professional music bot with multi-platform support and advanced audio features**",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🚀 Quick Start",
                value=f"```1. Join a voice channel\n2. {self.prefix}play <song name>\n3. {self.prefix}queue to see playlist\n4. Use buttons to control playback```",
                inline=False
            )
            
            embed.add_field(
                name="🌟 Key Features",
                value="• **Multi-Platform:** YouTube, Spotify, SoundCloud\n• **High Quality:** Up to 320kbps audio\n• **Smart Queue:** Unlimited with autoplay\n• **Advanced Audio:** 15-band EQ, effects\n• **Interactive Controls:** Modern button interface",
                inline=False
            )
            
            embed.add_field(
                name="📱 Supported Platforms",
                value=f"🎥 **YouTube** - Videos and playlists\n🎧 **Spotify** - Tracks and playlists (requires linking)\n☁️ **SoundCloud** - Tracks and sets\n🔗 **Direct Links** - MP3, MP4, and more",
                inline=False
            )
            
        elif category == "playback":
            embed = discord.Embed(
                title="▶️ Playback Controls",
                description="Control music playback with these essential commands",
                color=discord.Color.green()
            )
            
            commands = [
                (f"{self.prefix}play <song>", "Play music from any platform"),
                (f"{self.prefix}pause", "Pause current track"),
                (f"{self.prefix}resume", "Resume paused track"),
                (f"{self.prefix}skip", "Skip to next track"),
                (f"{self.prefix}stop", "Stop and clear queue"),
                (f"{self.prefix}disconnect", "Leave voice channel"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        elif category == "queue":
            embed = discord.Embed(
                title="📋 Queue Management",
                description="Manage your music queue with advanced features",
                color=discord.Color.orange()
            )
            
            commands = [
                (f"{self.prefix}queue", "View current queue with controls"),
                (f"{self.prefix}move <from> <to>", "Move track to new position"),
                (f"{self.prefix}remove <number>", "Remove track from queue"),
                (f"{self.prefix}clear", "Clear entire queue"),
                (f"{self.prefix}shuffle", "Shuffle queue tracks"),
                (f"{self.prefix}loop <mode>", "Set loop mode (off/track/queue)"),
                (f"{self.prefix}skipto <position>", "Skip to specific track"),
                (f"{self.prefix}save_queue <name>", "Save current queue"),
                (f"{self.prefix}load_queue <name>", "Load saved queue"),
                (f"{self.prefix}queue_history", "View recent tracks"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        elif category == "audio":
            embed = discord.Embed(
                title="🎛️ Audio Controls",
                description="Professional audio controls and effects",
                color=discord.Color.purple()
            )
            
            commands = [
                (f"{self.prefix}volume <0-200>", "Set playback volume with controls"),
                (f"{self.prefix}bassboost <level>", "Bass enhancement (off/low/medium/high)"),
                (f"{self.prefix}speed <rate>", "Playback speed (0.5x - 2.0x)"),
                (f"{self.prefix}pitch <semitones>", "Pitch adjustment (-12 to +12)"),
                (f"{self.prefix}distortion <level>", "Apply distortion effect"),
                (f"{self.prefix}reverb <room>", "Add reverb effect"),
                (f"{self.prefix}nightcore", "Apply nightcore effect"),
                (f"{self.prefix}vaporwave", "Apply vaporwave effect"),
                (f"{self.prefix}reset_audio", "Reset all audio effects"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        elif category == "search":
            embed = discord.Embed(
                title="🔍 Search & Discovery",
                description="Find and discover music across platforms",
                color=discord.Color.gold()
            )
            
            commands = [
                (f"{self.prefix}search <query>", "Multi-platform music search"),
                (f"{self.prefix}trending <platform>", "Show trending music"),
                (f"{self.prefix}recommend <seed>", "Get music recommendations"),
                (f"{self.prefix}genres <genre>", "Explore music by genre"),
                (f"{self.prefix}history", "View search history"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        elif category == "spotify":
            embed = discord.Embed(
                title="🟢 Spotify Integration",
                description="Connect and control your Spotify account",
                color=discord.Color.green()
            )
            
            commands = [
                (f"{self.prefix}spotify link", "Link your Spotify account"),
                (f"{self.prefix}spotify unlink", "Unlink Spotify account"),
                (f"{self.prefix}spotify status", "Check connection status"),
                (f"{self.prefix}spotify device", "Use bot as Spotify device"),
                (f"{self.prefix}spotify play <track>", "Play from Spotify"),
                (f"{self.prefix}spotify pause", "Pause Spotify playback"),
                (f"{self.prefix}spotify skip", "Skip Spotify track"),
                (f"{self.prefix}spotify previous", "Previous Spotify track"),
                (f"{self.prefix}spotify playlists", "View your playlists"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        elif category == "settings":
            embed = discord.Embed(
                title="⚙️ Music Settings",
                description="Customize your music experience",
                color=discord.Color.dark_blue()
            )
            
            commands = [
                (f"{self.prefix}autoplay", "Toggle smart autoplay"),
                (f"{self.prefix}djrole <role>", "Set DJ role permissions"),
                (f"{self.prefix}maxvolume <limit>", "Set volume limits"),
                (f"{self.prefix}musicchannel", "Restrict to channels"),
                (f"{self.prefix}247", "Toggle 24/7 mode"),
                (f"{self.prefix}quality <level>", "Set audio quality"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
        
        embed.set_footer(text=f"Use the dropdown above to explore different categories • Prefix: {self.prefix}")
        return embed


class AccountHelpView(ui.View):
    def __init__(self, bot, prefix: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix

    @ui.select(placeholder="👤 Select Account Feature", options=[
        discord.SelectOption(label="🏠 Overview", value="overview", description="Account system overview", emoji="🏠"),
        discord.SelectOption(label="👤 Profile", value="profile", description="User profiles and stats", emoji="👤"),
        discord.SelectOption(label="⚙️ Settings", value="settings", description="Account preferences", emoji="⚙️"),
        discord.SelectOption(label="📊 Statistics", value="statistics", description="Your music stats", emoji="📊"),
        discord.SelectOption(label="🎧 Spotify", value="spotify", description="Spotify integration", emoji="🎧"),
    ], row=0)
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        embed = self.create_account_embed(select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="📝", label="Create Account", style=discord.ButtonStyle.primary, row=1)
    async def create_account(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📝 Create Your Account",
            description=f"Use `{self.prefix}signup` to create your free Ascend account!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="✨ Account Benefits",
            value="• Personal music statistics\n• Custom preferences\n• Spotify integration\n• Playlist management\n• History tracking",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji="👤", label="View Profile", style=discord.ButtonStyle.secondary, row=1)
    async def view_profile(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="👤 Profile Information",
            description=f"Use `{self.prefix}profile` to view your account details",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_account_embed(self, category: str):
        if category == "overview":
            embed = discord.Embed(
                title="👤 Account System Overview",
                description="**Personalized music experience with statistics and preferences**",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🚀 Getting Started",
                value=f"```{self.prefix}signup - Create account\n{self.prefix}profile - View profile\n{self.prefix}settings - Preferences```",
                inline=False
            )
            
        elif category == "profile":
            embed = discord.Embed(
                title="👤 User Profiles",
                description="View and manage user profiles",
                color=discord.Color.green()
            )
            
            commands = [
                (f"{self.prefix}profile", "View your profile"),
                (f"{self.prefix}profile @user", "View someone's profile"),
                (f"{self.prefix}edit bio <text>", "Update your bio"),
                (f"{self.prefix}avatar <url>", "Set profile picture"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
                
        # Add other categories...
        
        embed.set_footer(text=f"Account features are 100% free • Prefix: {self.prefix}")
        return embed


class UtilityHelpView(ui.View):
    def __init__(self, bot, prefix: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix

    @ui.select(placeholder="🔧 Select Utility Category", options=[
        discord.SelectOption(label="🏠 Overview", value="overview", description="Utility commands overview", emoji="🏠"),
        discord.SelectOption(label="ℹ️ Information", value="info", description="Bot and server info", emoji="ℹ️"),
        discord.SelectOption(label="⚙️ Configuration", value="config", description="Setup commands", emoji="⚙️"),
        discord.SelectOption(label="🔗 Links", value="links", description="Support and links", emoji="🔗"),
    ], row=0)
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        embed = self.create_utility_embed(select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)

    def create_utility_embed(self, category: str):
        if category == "overview":
            embed = discord.Embed(
                title="🔧 Utility Commands Overview",
                description="**Helpful tools and bot information commands**",
                color=discord.Color.blue()
            )
            
            commands = [
                (f"{self.prefix}about", "Bot information and stats"),
                (f"{self.prefix}ping", "Check bot responsiveness"),
                (f"{self.prefix}invite", "Get bot invite link"),
                (f"{self.prefix}support", "Get support server link"),
                (f"{self.prefix}prefix <new>", "Change command prefix"),
                (f"{self.prefix}status", "Lavalink connection status"),
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=f"`{cmd}`", value=desc, inline=True)
        
        # Add other utility categories...
        
        embed.set_footer(text=f"Utility commands for server management • Prefix: {self.prefix}")
        return embed


class QuickCommandModal(ui.Modal):
    def __init__(self, prefix: str, category: str):
        super().__init__(title=f"🎮 Try {category.title()} Commands")
        self.prefix = prefix
        self.category = category

    command_input = ui.TextInput(
        label="Command to Try",
        placeholder="Enter command without prefix (e.g., 'play never gonna give you up')",
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        command = self.command_input.value.strip()
        
        embed = discord.Embed(
            title="💡 Command Help",
            description=f"**Command:** `{self.prefix}{command}`",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📝 How to Use",
            value=f"Copy and paste this in chat:\n```{self.prefix}{command}```",
            inline=False
        )
        
        if command.startswith('play'):
            embed.add_field(
                name="💡 Play Command Tips",
                value="• Use song names: `play despacito`\n• Use YouTube links\n• Use Spotify links (requires linking)\n• Add multiple songs: `play song1, song2`",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuickPlayModal(ui.Modal):
    def __init__(self, prefix: str):
        super().__init__(title="🎵 Quick Play Song")
        self.prefix = prefix

    song_input = ui.TextInput(
        label="Song to Play",
        placeholder="Enter song name, artist, or URL...",
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        song = self.song_input.value.strip()
        
        embed = discord.Embed(
            title="🎵 Ready to Play!",
            description=f"**Song:** {song}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎮 Command to Use",
            value=f"```{self.prefix}play {song}```",
            inline=False
        )
        
        embed.add_field(
            name="📝 Instructions",
            value="1. Join a voice channel\n2. Copy the command above\n3. Paste it in chat\n4. Enjoy your music!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class HelpDropdown(ui.Select):
    def __init__(self, bot, categories: Dict[str, List[str]], help_view):
        self.bot = bot
        self.categories = categories
        self.help_view = help_view
        
        options = [
            discord.SelectOption(
                label="🏠 Home",
                description="Return to the main help page",
                value="home",
                emoji="🏠"
            )
        ]
        
        category_emojis = {
            "Music": "🎵",
            "Account": "👤", 
            "Spotify": "🎧",
            "Setup": "⚙️",
            "Utility": "🔧"
        }
        
        for category in categories.keys():
            emoji = category_emojis.get(category, "📁")
            options.append(
                discord.SelectOption(
                    label=category,
                    description=f"View {category.lower()} commands",
                    value=category.lower(),
                    emoji=emoji
                )
            )
        
        super().__init__(placeholder="Select a category to explore...", options=options)

    async def get_guild_prefix(self, guild_id: Optional[int]) -> str:
        """Get the guild's prefix from database"""
        if not guild_id:
            return '<'
        
        try:
            db = DatabaseManager()
            guild_data = await db.get_guild(guild_id)
            return guild_data['prefix'] if guild_data else '<'
        except:
            return '<'

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "home":
            await self.show_home_page(interaction)
        else:
            await self.show_category(interaction, self.values[0])

    async def show_home_page(self, interaction: discord.Interaction):
        # Get proper prefix for this guild
        prefix = await self.get_guild_prefix(interaction.guild.id if interaction.guild else None)
        
        embed = discord.Embed(
            title="🎵 Ascend Music Bot - Interactive Help Center",
            description="**Welcome to your complete music companion!**\n\n*Navigate using the dropdown below to explore all features and commands.*",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="🚀 Quick Start",
            value=f"```1. Create account: {prefix}signup\n2. Join voice channel\n3. Play music: {prefix}play <song>\n4. Manage queue: {prefix}queue```",
            inline=False
        )
        
        total_commands = sum(len(commands) for commands in self.categories.values())
        
        embed.add_field(
            name=f"📚 Command Categories ({total_commands} total)",
            value="**Select a category from the dropdown menu below to explore:**",
            inline=False
        )
        
        # Show categories with enhanced information
        for category, commands in self.categories.items():
            emoji = {"Music": "🎵", "Account": "👤", "Spotify": "🎧", "Setup": "⚙️", "Utility": "🔧"}.get(category, "📁")
            
            descriptions = {
                "Music": "Complete audio control & streaming",
                "Account": "Personal profiles & settings", 
                "Spotify": "OAuth integration & playlists",
                "Setup": "Server configuration & permissions",
                "Utility": "Bot info & helpful tools"
            }
            
            embed.add_field(
                name=f"{emoji} {category}",
                value=f"**{len(commands)} commands**\n{descriptions.get(category, 'Various commands')}",
                inline=True
            )
        
        embed.add_field(
            name="✨ What Makes Ascend Special?",
            value="• **Multi-Platform:** YouTube, Spotify, SoundCloud support\n"
                  "• **Advanced Audio:** Real-time equalizer and effects\n"
                  "• **Smart Features:** Auto-queue, lyrics, radio mode\n"
                  "• **User Accounts:** Statistics, preferences, history\n"
                  "• **Modern Interface:** Interactive buttons and menus",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Quick Links",
            value="[Add to Server](https://discord.com/oauth2/authorize?client_id=1424894283441377463&permissions=2184268800&scope=bot%20applications.commands) • [Support](https://discord.gg/zCdWpTNN6Y) • [Documentation](https://ascend-docs.replit.app/) • [GitHub](https://github.com/FrostyTheDevv/Ascend)",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Ascend • Use dropdown to explore • Prefix: {prefix}")
        
        await interaction.response.edit_message(embed=embed, view=self.help_view)

    async def show_category(self, interaction: discord.Interaction, category: str):
        category_title = category.title()
        commands = self.categories.get(category_title, [])
        
        embed = discord.Embed(
            title=f"📚 {category_title} Commands",
            description=f"All available {category.lower()} commands for Ascend:",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        # Get actual command objects for detailed info
        command_details = []
        for cmd_name in commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                command_details.append(cmd)
        
        # Split commands into chunks for multiple fields
        chunk_size = 5
        for i in range(0, len(command_details), chunk_size):
            chunk = command_details[i:i+chunk_size]
            field_value = ""
            
            for cmd in chunk:
                # Get prefix for this guild
                prefix = await self.get_guild_prefix(interaction.guild.id if interaction.guild else None)
                
                field_value += f"**{prefix}{cmd.name}**"
                if cmd.aliases:
                    field_value += f" (`{', '.join(cmd.aliases)}`)"
                field_value += f"\n{cmd.help or 'No description available.'}\n\n"
            
            field_name = f"Commands {i//chunk_size + 1}" if len(command_details) > chunk_size else "Commands"
            embed.add_field(name=field_name, value=field_value.strip(), inline=False)
        
        if not command_details:
            embed.add_field(name="No Commands", value="No commands found in this category.", inline=False)
        
        embed.set_footer(text=f"Use the dropdown to explore other categories • {len(command_details)} commands shown")
        
        await interaction.response.edit_message(embed=embed, view=self.help_view)

class HelpView(ui.View):
    def __init__(self, bot, categories: Dict[str, List[str]]):
        super().__init__(timeout=300)
        self.bot = bot
        self.categories = categories
        
        # Add dropdown
        dropdown = HelpDropdown(bot, categories, self)
        self.add_item(dropdown)

    @ui.button(label="Invite Bot", style=discord.ButtonStyle.secondary, emoji="➕")
    async def invite_bot(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📨 Invite Ascend to Your Server!",
            description="[Click here to invite Ascend](https://discord.com/oauth2/authorize?client_id=1424894283441377463&permissions=2184268800&scope=bot%20applications.commands)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Support Server", style=discord.ButtonStyle.secondary, emoji="🆘")
    async def support_server(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🆘 Need Help?",
            description="[Join our Support Server](https://discord.gg/zCdWpTNN6Y) for assistance!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Bot Stats", style=discord.ButtonStyle.secondary, emoji="📊")
    async def bot_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="🌐 General Stats",
            value=f"```Servers: {len(self.bot.guilds)}\nUsers: {len(self.bot.users)}\nCommands: {len(self.bot.commands)}```",
            inline=True
        )
        
        embed.add_field(
            name="🎵 Music Stats",
            value="```Active Players: 0\nSongs Played Today: 0\nTotal Playtime: 0h```",
            inline=True
        )
        
        embed.add_field(
            name="⚡ Performance",
            value=f"```Latency: {round(self.bot.latency * 1000)}ms\nUptime: Online\nVersion: 2.0.0```",
            inline=True
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        # Disable all items when view times out
        for item in self.children:
            if not isinstance(item, ui.Button) or item.style != discord.ButtonStyle.link:
                item.disabled = True

class CommandInfoModal(ui.Modal, title='Command Information'):
    def __init__(self, command_name: str, bot):
        super().__init__()
        self.command_name = command_name
        self.bot = bot

    command_input = ui.TextInput(
        label='Command Name',
        placeholder='Enter command name (without prefix)...',
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        cmd_name = self.command_input.value.lower()
        cmd = self.bot.get_command(cmd_name)
        
        if not cmd:
            embed = discord.Embed(
                title="❌ Command Not Found",
                description=f"No command named `{cmd_name}` was found.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get prefix for this guild
        db = DatabaseManager()
        guild_data = await db.get_guild(interaction.guild.id) if interaction.guild else None
        prefix = guild_data['prefix'] if guild_data else '<'
        
        embed = discord.Embed(
            title=f"📖 Command: {cmd.name}",
            description=cmd.help or "No description available.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📝 Usage",
            value=f"`{prefix}{cmd.name} {cmd.signature}`",
            inline=False
        )
        
        if cmd.aliases:
            embed.add_field(
                name="🔗 Aliases",
                value=f"`{', '.join(cmd.aliases)}`",
                inline=True
            )
        
        # Add cooldown info if exists
        if cmd.cooldown:
            embed.add_field(
                name="⏱️ Cooldown",
                value=f"{cmd.cooldown.rate} times per {cmd.cooldown.per} seconds",
                inline=True
            )
        
        embed.add_field(
            name="📚 Category",
            value=cmd.cog.qualified_name if cmd.cog else "No Category",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SpotifyHelpView(ui.View):
    def __init__(self, bot, prefix: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix

    @ui.select(placeholder="🎧 Spotify Features", options=[
        discord.SelectOption(label="🏠 Overview", value="overview", description="Spotify integration overview", emoji="🏠"),
        discord.SelectOption(label="🔗 Linking", value="linking", description="Connect your account", emoji="🔗"),
        discord.SelectOption(label="📋 Playlists", value="playlists", description="Access your playlists", emoji="📋"),
        discord.SelectOption(label="🎮 Controls", value="controls", description="Playback control", emoji="🎮"),
    ], row=0)
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        embed = self.create_spotify_embed(select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="🔗", label="Link Spotify", style=discord.ButtonStyle.primary, row=1)
    async def link_spotify(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🔗 Link Your Spotify Account",
            description=f"Use `{self.prefix}spotify link` to connect your Spotify account!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="✨ Benefits",
            value="• Access your Spotify playlists\n• Enhanced music recommendations\n• Cross-platform control\n• Premium features support",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_spotify_embed(self, category: str):
        if category == "overview":
            embed = discord.Embed(
                title="🎧 Spotify Integration",
                description="**Connect your Spotify account for enhanced features**",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🚀 Quick Start",
                value=f"```{self.prefix}spotify link - Connect account\n{self.prefix}spotify status - Check connection\n{self.prefix}spotify playlists - View playlists```",
                inline=False
            )
            
        embed.set_footer(text=f"Spotify integration is free for all users • Prefix: {self.prefix}")
        return embed


class SetupHelpView(ui.View):
    def __init__(self, bot, prefix: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix

    @ui.select(placeholder="⚙️ Setup Categories", options=[
        discord.SelectOption(label="🏠 Overview", value="overview", description="Setup system overview", emoji="🏠"),
        discord.SelectOption(label="👑 Permissions", value="permissions", description="Bot permissions setup", emoji="👑"),
        discord.SelectOption(label="🎵 Music Setup", value="music", description="Music system configuration", emoji="🎵"),
        discord.SelectOption(label="📝 Preferences", value="preferences", description="Server preferences", emoji="📝"),
    ], row=0)
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        embed = self.create_setup_embed(select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="🚀", label="Quick Setup", style=discord.ButtonStyle.primary, row=1)
    async def quick_setup(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🚀 Quick Server Setup",
            description=f"Run `{self.prefix}setup` to configure Ascend for your server!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="✅ What Gets Configured",
            value="• Command prefix\n• Music channels\n• DJ roles\n• Volume limits\n• Auto-moderation",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_setup_embed(self, category: str):
        if category == "overview":
            embed = discord.Embed(
                title="⚙️ Server Setup",
                description="**Configure Ascend for optimal performance on your server**",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="🚀 Essential Setup",
                value=f"```{self.prefix}setup - Interactive setup wizard\n{self.prefix}prefix <symbol> - Change prefix\n{self.prefix}musicchannel - Set music channels```",
                inline=False
            )
            
        embed.set_footer(text=f"Setup is required for optimal performance • Prefix: {self.prefix}")
        return embed


class GenericHelpView(ui.View):
    def __init__(self, bot, prefix: str, category: str, commands: List[str]):
        super().__init__(timeout=300)
        self.bot = bot
        self.prefix = prefix
        self.category = category
        self.commands = commands

    @ui.button(emoji="📋", label="Command List", style=discord.ButtonStyle.secondary, row=0)
    async def show_commands(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title=f"📋 {self.category} Commands",
            color=discord.Color.blue()
        )
        
        command_details = []
        for cmd_name in self.commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                command_details.append(cmd)
        
        if command_details:
            command_text = ""
            for cmd in command_details[:10]:
                aliases = f" (`{', '.join(cmd.aliases)}`)" if cmd.aliases else ""
                description = cmd.help or "No description available"
                command_text += f"**{self.prefix}{cmd.name}**{aliases}\n{description}\n\n"
            
            embed.add_field(
                name=f"Available Commands ({len(command_details)} total)",
                value=command_text.strip(),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_generic_embed(self):
        embed = discord.Embed(
            title=f"📚 {self.category} Help",
            description=f"**Commands and features for {self.category.lower()}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Commands Available",
            value=f"This category has {len(self.commands)} commands.\nUse the button below to see the full list.",
            inline=False
        )
        
        embed.add_field(
            name="💡 Getting Help",
            value=f"• `{self.prefix}help <command>` - Detailed command help\n• Use buttons below for more options\n• Join support server for assistance",
            inline=False
        )
        
        embed.set_footer(text=f"Category: {self.category} • Prefix: {self.prefix}")
        return embed


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.categories = {
            "Music": ["play", "pause", "resume", "skip", "stop", "volume", "queue", "nowplaying", "disconnect", "shuffle", "loop", "seek", "lyrics", "search"],
            "Account": ["signup", "signin", "profile", "account", "settings"],
            "Spotify": ["spotify", "spotify link", "spotify unlink", "spotify status", "spotify confirm", "spotify device", "spotify play", "spotify pause", "spotify skip", "spotify previous", "spotify playlists"],
            "Setup": ["setup"],
            "Utility": ["help", "about", "ping", "invite", "prefix"]
        }

    @commands.command(name='help', aliases=['h', 'commands'])
    async def help_command(self, ctx, *, command_or_category: Optional[str] = None):
        """Shows help information for the bot"""
        
        if command_or_category:
            # Check if it's a specific command
            cmd = self.bot.get_command(command_or_category.lower())
            if cmd:
                await self.show_command_help(ctx, cmd)
                return
            
            # Check if it's a category
            category = command_or_category.title()
            if category in self.categories:
                await self.show_category_help(ctx, category)
                return
            
            # Command/category not found
            embed = discord.Embed(
                title="❌ Not Found",
                description=f"No command or category named `{command_or_category}` was found.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Show main help page with comprehensive command showcase
        embed = discord.Embed(
            title="🎵 Ascend Music Bot - Complete Command Reference",
            description="**Your ultimate Discord music companion with 100+ premium features!**\n\n*Advanced music streaming • Account management • Spotify integration • Custom playlists*",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Get guild prefix
        db = DatabaseManager()
        guild_data = await db.get_guild(ctx.guild.id) if ctx.guild else None
        prefix = guild_data['prefix'] if guild_data else '<'
        
        # Quick start section
        embed.add_field(
            name="🚀 Quick Start Guide",
            value=f"```1. {prefix}signup - Create your account\n2. Join a voice channel\n3. {prefix}play <song> - Start the music!\n4. {prefix}queue - See what's playing```",
            inline=False
        )
        
        # Comprehensive command showcase by category
        total_commands = sum(len(commands) for commands in self.categories.values())
        
        embed.add_field(
            name=f"📚 Complete Command Showcase ({total_commands} total commands)",
            value="**Explore all available commands organized by category:**",
            inline=False
        )
        
        # Enhanced category display with command counts and examples
        category_details = {
            "Music": {"emoji": "🎵", "example": f"{prefix}play, {prefix}queue, {prefix}skip"},
            "Account": {"emoji": "👤", "example": f"{prefix}signup, {prefix}profile, {prefix}settings"},
            "Spotify": {"emoji": "🎧", "example": f"{prefix}spotify link, {prefix}spotify status"},
            "Setup": {"emoji": "⚙️", "example": f"{prefix}setup"},
            "Utility": {"emoji": "🔧", "example": f"{prefix}about, {prefix}ping, {prefix}prefix"}
        }
        
        for category, commands in self.categories.items():
            details = category_details.get(category, {"emoji": "📁", "example": "Various commands"})
            embed.add_field(
                name=f"{details['emoji']} {category} ({len(commands)} commands)",
                value=f"**Examples:** `{details['example']}`\n**Full list:** `{prefix}help {category.lower()}`",
                inline=True
            )
        
        # Feature highlights
        embed.add_field(
            name="✨ Premium Features Included",
            value="• **Multi-Platform Music:** YouTube, Spotify, SoundCloud\n"
                  "• **Advanced Audio:** Equalizer, Bass Boost, Filters\n"
                  "• **Smart Playlists:** Create, share, collaborate\n"
                  "• **Account System:** Statistics, preferences, history\n"
                  "• **Spotify Integration:** Full OAuth linking\n"
                  "• **Server Management:** Custom prefixes, DJ roles",
            inline=False
        )
        
        # Usage statistics and tips
        embed.add_field(
            name="💡 Command Usage Tips",
            value=f"• **Detailed Help:** `{prefix}help <command>` - Get specific command info\n"
                  f"• **Category Help:** `{prefix}help <category>` - Explore command categories\n"
                  f"• **Quick Reference:** Use dropdown below for interactive navigation\n"
                  f"• **Aliases:** Most commands have short aliases (e.g., `h` for `help`)",
            inline=False
        )
        
        # Support and links
        embed.add_field(
            name="🔗 Support & Community",
            value="[📱 Add to Server](https://discord.com/oauth2/authorize?client_id=1424894283441377463&permissions=2184268800&scope=bot%20applications.commands) • [🆘 Support](https://discord.gg/zCdWpTNN6Y) • [📖 Documentation](https://ascend-docs.replit.app/) • [📂 GitHub](https://github.com/FrostyTheDevv/Ascend)",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Ascend • {total_commands} commands across {len(self.categories)} categories • Prefix: {prefix}")
        
        view = HelpView(self.bot, self.categories)
        await ctx.send(embed=embed, view=view)

    async def show_command_help(self, ctx, cmd):
        """Show detailed help for a specific command"""
        embed = discord.Embed(
            title=f"📖 Command: {cmd.name}",
            description=cmd.help or "No description available.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📝 Usage",
            value=f"`{ctx.prefix}{cmd.name} {cmd.signature}`",
            inline=False
        )
        
        if cmd.aliases:
            embed.add_field(
                name="🔗 Aliases",
                value=f"`{', '.join(cmd.aliases)}`",
                inline=True
            )
        
        embed.add_field(
            name="📚 Category",
            value=cmd.cog.qualified_name if cmd.cog else "No Category",
            inline=True
        )
        
        # Add examples if available
        examples = {
            "play": [
                f"{ctx.prefix}play never gonna give you up",
                f"{ctx.prefix}play https://open.spotify.com/track/...",
                f"{ctx.prefix}play https://youtube.com/watch?v=..."
            ],
            "volume": [f"{ctx.prefix}volume 50", f"{ctx.prefix}volume 100"],
            "loop": [f"{ctx.prefix}loop track", f"{ctx.prefix}loop queue", f"{ctx.prefix}loop off"]
        }
        
        if cmd.name in examples:
            embed.add_field(
                name="💡 Examples",
                value="\n".join([f"`{ex}`" for ex in examples[cmd.name]]),
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def show_category_help(self, ctx, category: str):
        """Show interactive help for a specific category with Components v2"""
        
        # Get guild prefix
        db = DatabaseManager()
        guild_data = await db.get_guild(ctx.guild.id) if ctx.guild else None
        prefix = guild_data['prefix'] if guild_data else '<'
        
        # Create category-specific interactive views
        if category.lower() == "music":
            view = MusicHelpView(self.bot, prefix)
            embed = view.create_embed("overview")
            
        elif category.lower() == "account":
            view = AccountHelpView(self.bot, prefix)
            embed = view.create_account_embed("overview")
            
        elif category.lower() == "utility":
            view = UtilityHelpView(self.bot, prefix)
            embed = view.create_utility_embed("overview")
            
        elif category.lower() == "spotify":
            view = SpotifyHelpView(self.bot, prefix)
            embed = view.create_spotify_embed("overview")
            
        elif category.lower() == "setup":
            view = SetupHelpView(self.bot, prefix)
            embed = view.create_setup_embed("overview")
            
        else:
            # Fallback for other categories - create a basic interactive view
            view = GenericHelpView(self.bot, prefix, category, self.categories.get(category, []))
            embed = view.create_generic_embed()
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))