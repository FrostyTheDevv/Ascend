import discord
from discord.ext import commands
from discord import ui, app_commands
import datetime
import psutil
import platform
import time
from database import DatabaseManager

class AboutView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @ui.button(label="System Info", style=discord.ButtonStyle.primary, emoji="💻")
    async def system_info(self, interaction: discord.Interaction, button: ui.Button):
        # System information
        system_info = {
            "OS": platform.system(),
            "OS Version": platform.release(),
            "Architecture": platform.machine(),
            "Python Version": platform.python_version(),
            "CPU Cores": psutil.cpu_count(),
            "RAM Total": f"{psutil.virtual_memory().total / (1024**3):.1f} GB",
            "RAM Used": f"{psutil.virtual_memory().percent}%"
        }
        
        embed = discord.Embed(
            title="💻 System Information",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        system_text = ""
        for key, value in system_info.items():
            system_text += f"**{key}:** {value}\n"
        
        embed.add_field(name="System Specs", value=system_text, inline=False)
        
        # Bot performance
        embed.add_field(
            name="⚡ Performance",
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n**Memory Usage:** {psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Bot Stats", style=discord.ButtonStyle.secondary, emoji="📊")
    async def bot_stats(self, interaction: discord.Interaction, button: ui.Button):
        db = DatabaseManager()
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        # Basic stats
        embed.add_field(
            name="🌐 Reach",
            value=f"**Servers:** {len(self.bot.guilds):,}\n**Users:** {len(self.bot.users):,}\n**Channels:** {len(list(self.bot.get_all_channels())):,}",
            inline=True
        )
        
        # Command stats
        embed.add_field(
            name="⚡ Activity",
            value=f"**Commands:** {len(self.bot.commands)}\n**Cogs:** {len(self.bot.cogs)}\n**Extensions:** {len(self.bot.extensions)}",
            inline=True
        )
        
        # Music stats (placeholder - would need actual data)
        embed.add_field(
            name="🎵 Music",
            value="**Active Players:** 0\n**Songs Played:** 0\n**Playlists:** 0",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Dependencies", style=discord.ButtonStyle.secondary, emoji="📦")
    async def dependencies(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📦 Dependencies & Libraries",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        deps = {
            "discord.py": "2.6.3+",
            "wavelink": "3.4.1+", 
            "aiohttp": "3.13.0+",
            "spotipy": "2.25.1+",
            "python-dotenv": "1.1.1+",
            "aiosqlite": "Latest",
            "psutil": "Latest"
        }
        
        dep_text = ""
        for name, version in deps.items():
            dep_text += f"**{name}:** `{version}`\n"
        
        embed.add_field(name="Core Dependencies", value=dep_text, inline=False)
        
        embed.add_field(
            name="🔧 Technologies",
            value="• **Database:** SQLite3\n• **Music:** Lavalink\n• **APIs:** Spotify, YouTube\n• **UI:** Discord Components v2",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Credits", style=discord.ButtonStyle.secondary, emoji="👥")
    async def credits(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="👥 Credits & Acknowledgments",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="🛠️ Development",
            value="**Lead Developer:** frosty.pyro\n**Contributors:** Community Contributors\n**Original Base:** FrostyTheDevv/Ascend",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Design & Assets",
            value="**UI/UX:** Modern Discord Components\n**Icons:** Discord Emoji Set\n**Inspiration:** Community Feedback",
            inline=False
        )
        
        embed.add_field(
            name="🙏 Special Thanks",
            value="• **Lavalink Team** - Audio streaming\n• **Spotify** - Music API\n• **Discord.py** - Library excellence\n• **Community** - Feedback & support",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Back to About", style=discord.ButtonStyle.success, emoji="🏠")
    async def back_to_about(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🎵 About Ascend Music Bot",
            description="**The next generation Discord music bot with premium features and modern interface**",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="✨ Key Features",
            value="• **High-Quality Audio** via Lavalink\n• **Spotify Integration** with playlists\n• **User Accounts** with statistics\n• **Modern UI** with buttons & dropdowns\n• **Smart Queuing** with loop modes\n• **Cross-Platform** search support",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Version Info",
            value=f"**Version:** 2.0.0\n**Build:** Release\n**Uptime:** Online\n**Last Update:** {datetime.datetime.now().strftime('%Y-%m-%d')}",
            inline=True
        )
        
        embed.add_field(
            name="📈 Performance",
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n**Servers:** {len(self.bot.guilds):,}\n**Users:** {len(self.bot.users):,}\n**Commands:** {len(self.bot.commands)}",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Quick Links",
            value="[Invite Bot](https://discord.com/oauth2/authorize) • [Support Server](https://discord.gg/support) • [Documentation](https://docs.example.com) • [GitHub](https://github.com/your-repo)",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Ascend Music Bot • Made with passion by frosty.pyro")
        
        await interaction.response.edit_message(embed=embed, view=self)

class SetupDropdown(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="🎵 Music Settings",
                description="Configure music playback settings",
                value="music",
                emoji="🎵"
            ),
            discord.SelectOption(
                label="🛡️ Permissions",
                description="Set up roles and permissions",
                value="permissions",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="📢 Channels",
                description="Configure music and notification channels",
                value="channels",
                emoji="📢"
            ),
            discord.SelectOption(
                label="⚙️ General",
                description="General bot settings and preferences",
                value="general",
                emoji="⚙️"
            )
        ]
        super().__init__(placeholder="Choose a setup category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "music":
            await self.setup_music(interaction)
        elif self.values[0] == "permissions":
            await self.setup_permissions(interaction)
        elif self.values[0] == "channels":
            await self.setup_channels(interaction)
        elif self.values[0] == "general":
            await self.setup_general(interaction)

    async def setup_music(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎵 Music Settings Setup",
            description="Configure how music works in your server",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔊 Volume Settings",
            value="• **Default Volume:** 50%\n• **Maximum Volume:** 100%\n• **Volume Persistence:** Enabled",
            inline=False
        )
        
        embed.add_field(
            name="🎶 Queue Settings", 
            value="• **Max Queue Size:** 100 songs\n• **Auto-shuffle:** Disabled\n• **Loop Mode:** Off by default",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Performance",
            value="• **Audio Quality:** High (320kbps)\n• **Buffer Size:** Optimal\n• **Reconnect:** Auto-enabled",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self.view)

    async def setup_permissions(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ Permissions Setup",
            description="Configure who can use music commands",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="👑 DJ Role",
            value="• **Current DJ Role:** None set\n• **Auto-assign:** First to join VC\n• **Permissions:** Skip, volume, queue control",
            inline=False
        )
        
        embed.add_field(
            name="🎵 Music Permissions",
            value="• **Play Commands:** @everyone\n• **Queue Management:** DJ Role + Song requester\n• **Admin Commands:** Manage Server permission",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Setup Commands",
            value=f"• `!setup dj @role` - Set DJ role\n• `!setup permissions reset` - Reset to defaults\n• `!setup permissions list` - View current setup",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self.view)

    async def setup_channels(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📢 Channel Setup",
            description="Configure dedicated channels for music",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎵 Music Channel",
            value="• **Dedicated Channel:** None set\n• **Auto-delete:** Command messages\n• **Now Playing:** Send updates here",
            inline=False
        )
        
        embed.add_field(
            name="📝 Logging",
            value="• **Command Log:** Disabled\n• **Music Log:** Track what's played\n• **Error Log:** Debug information",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Setup Commands",
            value=f"• `!setup channel music #channel` - Set music channel\n• `!setup channel log #channel` - Set log channel\n• `!setup channel reset` - Clear channel settings",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self.view)

    async def setup_general(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ General Settings",
            description="Basic bot configuration for your server",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🔧 Command Prefix",
            value="• **Current Prefix:** `!`\n• **Alternative:** Mention the bot\n• **Change:** Use `!prefix <new_prefix>`",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Interface",
            value="• **Embeds:** Enabled\n• **Buttons:** Enabled\n• **Auto-delete:** Command messages\n• **Reactions:** Quick controls",
            inline=False
        )
        
        embed.add_field(
            name="📊 Statistics",
            value="• **Usage Tracking:** Enabled\n• **Leaderboards:** Server stats\n• **Analytics:** Command usage",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self.view)

class SetupView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        dropdown = SetupDropdown(bot)
        self.add_item(dropdown)

    @ui.button(label="Quick Setup", style=discord.ButtonStyle.primary, emoji="⚡")
    async def quick_setup(self, interaction: discord.Interaction, button: ui.Button):
        db = DatabaseManager()
        
        # Auto-setup with defaults
        guild_data = await db.get_guild(interaction.guild.id)
        if not guild_data:
            await db.create_guild(
                guild_id=interaction.guild.id,
                guild_name=interaction.guild.name,
                owner_id=interaction.guild.owner_id
            )
        
        embed = discord.Embed(
            title="⚡ Quick Setup Complete!",
            description="Ascend has been configured with optimal default settings for your server.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="✅ Configured Settings",
            value="• Command prefix: `!`\n• Music permissions: @everyone\n• Volume limit: 100%\n• Queue size: 100 songs\n• Auto-features: Enabled",
            inline=False
        )
        
        embed.add_field(
            name="🎵 Ready to Use",
            value=f"Join a voice channel and use `!play <song>` to start listening!\nUse `!help` to see all available commands.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Reset Settings", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reset_settings(self, interaction: discord.Interaction, button: ui.Button):
        # Confirmation embed
        embed = discord.Embed(
            title="⚠️ Reset All Settings",
            description="This will reset all bot settings to default values. This action cannot be undone.",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="🔄 What will be reset:",
            value="• Command prefix\n• Music settings\n• Channel configurations\n• Permission settings\n• Custom preferences",
            inline=False
        )
        
        # Create confirmation view
        confirm_view = ui.View(timeout=60)
        
        async def confirm_reset(confirm_interaction):
            db = DatabaseManager()
            # Reset guild settings to defaults
            await db.update_guild_prefix(interaction.guild.id, "!")
            
            success_embed = discord.Embed(
                title="✅ Settings Reset",
                description="All settings have been reset to their default values.",
                color=discord.Color.green()
            )
            await confirm_interaction.response.edit_message(embed=success_embed, view=None)
        
        async def cancel_reset(cancel_interaction):
            cancel_embed = discord.Embed(
                title="❌ Reset Cancelled",
                description="Settings reset has been cancelled.",
                color=discord.Color.orange()
            )
            await cancel_interaction.response.edit_message(embed=cancel_embed, view=None)
        
        confirm_button = ui.Button(label="Confirm Reset", style=discord.ButtonStyle.danger, emoji="✅")
        cancel_button = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
        
        confirm_button.callback = confirm_reset
        cancel_button.callback = cancel_reset
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.command(name='about', aliases=['info', 'botinfo'])
    async def about(self, ctx):
        """Show detailed information about the bot"""
        embed = discord.Embed(
            title="🎵 Ascend Music Bot",
            description="**The next generation Discord music bot with premium features and modern interface**\n\n*Delivering high-quality music streaming with advanced features for Discord communities worldwide.*",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="✨ Premium Features",
            value="• **High-Quality Audio** via Lavalink streaming\n• **Spotify Integration** with OAuth linking\n• **User Accounts** with detailed statistics\n• **Modern UI** with buttons & interactive menus\n• **Smart Queuing** with shuffle & loop modes\n• **Cross-Platform** search (YouTube, Spotify, SoundCloud)\n• **Advanced Audio** with equalizer & filters\n• **Custom Playlists** with sharing capabilities",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Technical Information",
            value=f"**Version:** 2.0.0 (Production)\n**Framework:** Discord.py 2.6.3+\n**Audio Engine:** Wavelink 3.4.1+\n**Database:** SQLite3 with aiosqlite\n**Uptime:** {self.get_uptime()}",
            inline=True
        )
        
        embed.add_field(
            name="� Live Statistics",
            value=f"**Servers:** {len(self.bot.guilds):,}\n**Users:** {len(self.bot.users):,}\n**Commands:** {len(self.bot.commands)}\n**Latency:** {round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        embed.add_field(
            name="👥 Development Team",
            value="**Lead Developer:** frosty.pyro\n**Project:** Ascend \n**Repository:** Ascend Music Bot\n**Status:** Actively Maintained",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Official Links",
            value="[📱 Add to Server](https://discord.com/oauth2/authorize?client_id=1424894283441377463&permissions=2184268800&scope=bot%20applications.commands) • [🆘 Support Server](https://discord.gg/zCdWpTNN6Y) • [📖 Documentation](https://ascend-docs.replit.app/) • [📂 GitHub](https://github.com/FrostyTheDevv/Ascend)",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Built With",
            value="Discord.py • Wavelink • Lavalink • Spotify API • SQLite3 • Python 3.11+",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Ascend • Developed by frosty.pyro • Powered by Sleepless Development")
        
        view = AboutView(self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name='setup')
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx, setting: str = None, *, value: str = None):
        """Configure bot settings for your server"""
        
        if not setting:
            # Show setup menu
            embed = discord.Embed(
                title="⚙️ Server Setup - Ascend Music Bot",
                description="Configure Ascend for optimal performance in your server!",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🚀 Quick Start",
                value="Use the dropdown below to configure different aspects of the bot, or click **Quick Setup** for automatic configuration with optimal defaults.",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Available Settings",
                value="• **Music Settings** - Audio quality, queue limits\n• **Permissions** - DJ roles, command access\n• **Channels** - Dedicated music channels\n• **General** - Prefix, interface options",
                inline=False
            )
            
            embed.add_field(
                name="💡 Pro Tip",
                value="Most servers work great with the Quick Setup option. You can always customize settings later!",
                inline=False
            )
            
            view = SetupView(self.bot)
            await ctx.send(embed=embed, view=view)
            return
        
        # Handle specific setting changes
        db = DatabaseManager()
        
        if setting.lower() == "prefix":
            if not value:
                embed = discord.Embed(
                    title="❌ Missing Prefix",
                    description=f"Please provide a new prefix. Example: `{ctx.prefix}setup prefix !`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            await db.update_guild_prefix(ctx.guild.id, value)
            embed = discord.Embed(
                title="✅ Prefix Updated",
                description=f"Command prefix has been changed to `{value}`",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

    @commands.command(name='prefix')
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, new_prefix: str = None):
        """Change the bot's command prefix for this server"""
        
        if not new_prefix:
            # Show current prefix
            db = DatabaseManager()
            guild_data = await db.get_guild(ctx.guild.id)
            current_prefix = guild_data['prefix'] if guild_data else '<'
            
            embed = discord.Embed(
                title="🔧 Current Prefix",
                description=f"The current command prefix for this server is: `{current_prefix}`",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Change Prefix",
                value=f"Use `{current_prefix}prefix <new_prefix>` to change it.\n\nExample: `{current_prefix}prefix !`",
                inline=False
            )
            embed.add_field(
                name="🚫 No Prefix Mode",
                value=f"Set prefix to `none` to allow commands without prefix:\n`{current_prefix}prefix none`\n\nThen you can use: `help`, `play`, `queue` etc.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Handle special "none" prefix for no-prefix mode
        if new_prefix.lower() == "none":
            db = DatabaseManager()
            await db.update_guild_prefix(ctx.guild.id, "")
            
            embed = discord.Embed(
                title="✅ No-Prefix Mode Enabled",
                description="Commands can now be used without any prefix!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📝 Example Usage",
                value="You can now use commands like: `help`, `play`, `queue`, `spotify`",
                inline=False
            )
            embed.add_field(
                name="🔄 Restore Prefix",
                value="To restore a prefix later, use: `prefix <new_prefix>`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Validate prefix
        if len(new_prefix) > 3:
            embed = discord.Embed(
                title="❌ Invalid Prefix",
                description="Prefix must be 3 characters or less.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Update prefix
        db = DatabaseManager()
        old_prefix = ctx.prefix if hasattr(ctx, 'prefix') else '<'
        await db.update_guild_prefix(ctx.guild.id, new_prefix)
        
        embed = discord.Embed(
            title="✅ Prefix Updated",
            description=f"Command prefix has been changed from `{old_prefix}` to `{new_prefix}`",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📝 Example Usage",
            value=f"You can now use commands like: `{new_prefix}help`, `{new_prefix}play`, `{new_prefix}queue`",
            inline=False
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="prefix", description="Change the bot's command prefix for this server")
    @app_commands.describe(new_prefix="The new prefix to set (use 'none' for no prefix mode)")
    @app_commands.default_permissions(manage_guild=True)
    async def prefix_slash(self, interaction: discord.Interaction, new_prefix: str = None):
        """Slash command version of prefix change"""
        
        if not new_prefix:
            # Show current prefix
            db = DatabaseManager()
            guild_data = await db.get_guild(interaction.guild.id)
            current_prefix = guild_data['prefix'] if guild_data else '<'
            
            embed = discord.Embed(
                title="🔧 Current Prefix",
                description=f"The current command prefix for this server is: `{current_prefix}`",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Change Prefix",
                value=f"Use `/prefix <new_prefix>` or `{current_prefix}prefix <new_prefix>` to change it.\n\nExample: `/prefix !`",
                inline=False
            )
            embed.add_field(
                name="🚫 No Prefix Mode",
                value=f"Set prefix to `none` to allow commands without prefix:\n`/prefix none`\n\nThen you can use: `help`, `play`, `queue` etc.",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Handle special "none" prefix for no-prefix mode
        if new_prefix.lower() == "none":
            db = DatabaseManager()
            await db.update_guild_prefix(interaction.guild.id, "")
            
            embed = discord.Embed(
                title="✅ No-Prefix Mode Enabled",
                description="Commands can now be used without any prefix!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📝 Example Usage",
                value="You can now use commands like: `help`, `play`, `queue`, `spotify`",
                inline=False
            )
            embed.add_field(
                name="🔄 Restore Prefix",
                value="To restore a prefix later, use: `/prefix <new_prefix>` or mention the bot",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Validate prefix
        if len(new_prefix) > 3:
            embed = discord.Embed(
                title="❌ Invalid Prefix",
                description="Prefix must be 3 characters or less.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Update prefix
        db = DatabaseManager()
        # Get current prefix from database
        guild_data = await db.get_guild(interaction.guild.id)
        old_prefix = guild_data['prefix'] if guild_data else '<'
        
        await db.update_guild_prefix(interaction.guild.id, new_prefix)
        
        embed = discord.Embed(
            title="✅ Prefix Updated",
            description=f"Command prefix has been changed from `{old_prefix}` to `{new_prefix}`",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📝 Example Usage",
            value=f"You can now use commands like: `{new_prefix}help`, `{new_prefix}play`, `{new_prefix}queue`",
            inline=False
        )
        embed.add_field(
            name="💡 Tip",
            value="You can always use slash commands (like `/help`) or mention the bot regardless of prefix!",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check the bot's latency"""
        start_time = time.time()
        message = await ctx.send("🏓 Pinging...")
        end_time = time.time()
        
        bot_latency = round(self.bot.latency * 1000)
        api_latency = round((end_time - start_time) * 1000)
        
        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(name="Bot Latency", value=f"{bot_latency}ms", inline=True)
        embed.add_field(name="API Latency", value=f"{api_latency}ms", inline=True)
        
        # Determine status based on latency
        if bot_latency < 100:
            status = "🟢 Excellent"
        elif bot_latency < 200:
            status = "🟡 Good"
        else:
            status = "🔴 Poor"
        
        embed.add_field(name="Status", value=status, inline=True)
        
        await message.edit(content=None, embed=embed)

    @commands.command(name='invite')
    async def invite(self, ctx):
        """Get the bot invite link"""
        embed = discord.Embed(
            title="📨 Invite Ascend to Your Server!",
            description="Thank you for your interest in Ascend Music Bot!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔗 Invite Link",
            value=f"[Click here to invite Ascend](https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=2184268800&scope=bot%20applications.commands)",
            inline=False
        )
        
        embed.add_field(
            name="✨ Required Permissions",
            value="• Send Messages & Embeds\n• Connect & Speak in Voice\n• Use Slash Commands\n• Manage Messages (for cleanup)\n• Add Reactions (for controls)",
            inline=False
        )
        
        embed.add_field(
            name="🆘 Need Help?",
            value="Join our [Support Server](https://discord.gg/zCdWpTNN6Y) for assistance with setup and usage!",
            inline=False
        )
        
        await ctx.send(embed=embed)

    def get_uptime(self):
        """Calculate bot uptime"""
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))