import discord
from discord.ext import commands
from discord import ui
import wavelink
import datetime
import logging
from typing import Dict, List, Optional
from enum import Enum

class AudioQuality(Enum):
    LOW = "96"
    MEDIUM = "128"
    HIGH = "192"
    ULTRA = "320"

class FilterType(Enum):
    NONE = "none"
    BASS_BOOST = "bassboost"
    REVERB = "reverb"
    ECHO = "echo"
    NIGHTCORE = "nightcore"
    VAPORWAVE = "vaporwave"
    DISTORTION = "distortion"

class MusicSettingsCog(commands.Cog, name="Music Settings"):
    """🎛️ Advanced music settings and audio configuration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.guild_settings = {}  # Store per-guild settings
        self.error_channel_id = 1425319240038223882

    async def log_error(self, error: str, guild_id: Optional[int] = None):
        """Log errors to designated channel"""
        try:
            error_channel = self.bot.get_channel(self.error_channel_id)
            if error_channel:
                embed = discord.Embed(
                    title="🚨 Music Settings Error",
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

    def get_guild_settings(self, guild_id: int) -> Dict:
        """Get or create guild-specific settings"""
        if guild_id not in self.guild_settings:
            self.guild_settings[guild_id] = {
                'volume': 50,
                'bass_boost': 0,
                'audio_quality': AudioQuality.HIGH.value,
                'auto_disconnect': True,
                'auto_disconnect_time': 300,  # 5 minutes
                'max_volume': 100,
                'dj_role': None,
                'music_channels': [],
                'filters': FilterType.NONE.value,
                'equalizer': {
                    '25': 0, '40': 0, '63': 0, '100': 0, '160': 0,
                    '250': 0, '400': 0, '630': 0, '1000': 0, '1600': 0,
                    '2500': 0, '4000': 0, '6300': 0, '10000': 0, '16000': 0
                },
                'crossfade': False,
                'crossfade_duration': 3,
                'replay_gain': False,
                'normalize_volume': True
            }
        return self.guild_settings[guild_id]

    @commands.group(name="settings", aliases=["config"], brief="Music settings and configuration")
    async def settings(self, ctx):
        """🎛️ Music settings and audio configuration."""
        if ctx.invoked_subcommand is None:
            await self.show_settings_menu(ctx)

    @settings.command(name="volume", brief="Set default volume")
    async def set_default_volume(self, ctx, volume: int):
        """🔊 Set the default volume for this server (0-100)."""
        try:
            if not 0 <= volume <= 100:
                embed = discord.Embed(
                    title="❌ Invalid Volume",
                    description="Volume must be between 0 and 100.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            settings = self.get_guild_settings(ctx.guild.id)
            settings['volume'] = volume

            embed = discord.Embed(
                title="🔊 Default Volume Set",
                description=f"Default volume set to **{volume}%** for this server.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Default volume setting error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set default volume.")

    @settings.command(name="maxvolume", brief="Set maximum volume limit")
    async def set_max_volume(self, ctx, max_vol: int):
        """🔊 Set the maximum volume limit for this server."""
        try:
            if not 1 <= max_vol <= 200:
                embed = discord.Embed(
                    title="❌ Invalid Maximum Volume",
                    description="Maximum volume must be between 1 and 200.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            settings = self.get_guild_settings(ctx.guild.id)
            settings['max_volume'] = max_vol

            embed = discord.Embed(
                title="🔊 Maximum Volume Set",
                description=f"Maximum volume limit set to **{max_vol}%** for this server.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Max volume setting error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set maximum volume.")

    @settings.command(name="quality", brief="Set audio quality")
    async def set_audio_quality(self, ctx, quality: str = None):
        """🎵 Set audio quality (low/medium/high/ultra)."""
        try:
            if quality is None:
                view = AudioQualityView(self, ctx.guild.id)
                embed = discord.Embed(
                    title="🎵 Audio Quality Settings",
                    description="Select your preferred audio quality:",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed, view=view)
                return

            quality_map = {
                'low': AudioQuality.LOW,
                'medium': AudioQuality.MEDIUM,
                'high': AudioQuality.HIGH,
                'ultra': AudioQuality.ULTRA
            }

            if quality.lower() not in quality_map:
                embed = discord.Embed(
                    title="❌ Invalid Quality",
                    description="Valid options: low, medium, high, ultra",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            settings = self.get_guild_settings(ctx.guild.id)
            settings['audio_quality'] = quality_map[quality.lower()].value

            embed = discord.Embed(
                title="🎵 Audio Quality Set",
                description=f"Audio quality set to **{quality.title()}** ({quality_map[quality.lower()].value}kbps)",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Audio quality setting error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set audio quality.")

    @settings.command(name="djrole", brief="Set DJ role")
    async def set_dj_role(self, ctx, role: discord.Role = None):
        """👑 Set the DJ role for advanced music controls."""
        try:
            settings = self.get_guild_settings(ctx.guild.id)
            
            if role is None:
                settings['dj_role'] = None
                embed = discord.Embed(
                    title="👑 DJ Role Removed",
                    description="DJ role has been removed. Everyone can use music commands.",
                    color=discord.Color.orange()
                )
            else:
                settings['dj_role'] = role.id
                embed = discord.Embed(
                    title="👑 DJ Role Set",
                    description=f"DJ role set to {role.mention}",
                    color=discord.Color.green()
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"DJ role setting error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set DJ role.")

    @settings.command(name="autodisconnect", brief="Set auto-disconnect")
    async def set_auto_disconnect(self, ctx, enabled: bool = None, time: int = 300):
        """⏱️ Configure auto-disconnect when alone (time in seconds)."""
        try:
            settings = self.get_guild_settings(ctx.guild.id)
            
            if enabled is None:
                current = settings['auto_disconnect']
                current_time = settings['auto_disconnect_time']
                
                embed = discord.Embed(
                    title="⏱️ Auto-Disconnect Settings",
                    description=f"**Status:** {'Enabled' if current else 'Disabled'}\n**Time:** {current_time} seconds ({current_time//60}m {current_time%60}s)",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="💡 Usage",
                    value=f"`{ctx.prefix}settings autodisconnect true 300` - Enable with 5 min timer\n`{ctx.prefix}settings autodisconnect false` - Disable",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return

            settings['auto_disconnect'] = enabled
            settings['auto_disconnect_time'] = time

            status = "enabled" if enabled else "disabled"
            time_str = f" ({time//60}m {time%60}s)" if enabled else ""
            
            embed = discord.Embed(
                title="⏱️ Auto-Disconnect Updated",
                description=f"Auto-disconnect {status}{time_str}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Auto-disconnect setting error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to set auto-disconnect.")

    @commands.command(name="equalizer", aliases=["eq"], brief="Open equalizer controls")
    async def equalizer(self, ctx):
        """🎛️ Open the advanced 15-band equalizer."""
        try:
            settings = self.get_guild_settings(ctx.guild.id)
            view = EqualizerView(self, ctx.guild.id, settings['equalizer'])
            
            embed = discord.Embed(
                title="🎛️ Professional 15-Band Equalizer",
                description="Adjust frequency bands to customize your audio experience.",
                color=discord.Color.purple()
            )
            
            # Show current EQ settings
            eq_display = ""
            for freq, gain in settings['equalizer'].items():
                bar = "█" * (10 + gain // 2) if gain >= 0 else "█" * max(1, 10 + gain // 2)
                eq_display += f"`{freq.rjust(5)}Hz` {bar} `{gain:+}dB`\n"
            
            embed.add_field(
                name="Current Settings",
                value=eq_display,
                inline=False
            )
            
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Equalizer error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to open equalizer.")

    @commands.command(name="filters", brief="Audio filters control")
    async def audio_filters(self, ctx):
        """🎚️ Apply audio filters and effects."""
        try:
            settings = self.get_guild_settings(ctx.guild.id)
            view = FiltersView(self, ctx.guild.id, settings['filters'])
            
            embed = discord.Embed(
                title="🎚️ Audio Filters & Effects",
                description="Apply various audio effects to enhance your listening experience.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Available Filters",
                value="• **Bass Boost** - Enhanced low frequencies\n• **Reverb** - Spacious echo effect\n• **Echo** - Delayed repetition\n• **Nightcore** - Higher pitch and speed\n• **Vaporwave** - Slowed and reverbed\n• **Distortion** - Aggressive sound",
                inline=False
            )
            
            embed.add_field(
                name="Current Filter",
                value=f"**{settings['filters'].replace('_', ' ').title()}**",
                inline=True
            )
            
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Filters error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to open filters.")

    async def show_settings_menu(self, ctx):
        """Show the main settings menu."""
        try:
            settings = self.get_guild_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="🎛️ Music Settings Dashboard",
                description="**Configure your server's music experience**",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            # Audio Settings
            embed.add_field(
                name="🔊 Audio Settings",
                value=f"**Volume:** {settings['volume']}%\n**Max Volume:** {settings['max_volume']}%\n**Quality:** {settings['audio_quality']}kbps\n**Filters:** {settings['filters'].replace('_', ' ').title()}",
                inline=True
            )
            
            # Server Settings
            dj_role = f"<@&{settings['dj_role']}>" if settings['dj_role'] else "None"
            auto_dc = "Enabled" if settings['auto_disconnect'] else "Disabled"
            
            embed.add_field(
                name="⚙️ Server Settings",
                value=f"**DJ Role:** {dj_role}\n**Auto-Disconnect:** {auto_dc}\n**Music Channels:** {len(settings['music_channels'])} set",
                inline=True
            )
            
            # Advanced Settings
            embed.add_field(
                name="🎚️ Advanced",
                value=f"**Crossfade:** {'On' if settings['crossfade'] else 'Off'}\n**Replay Gain:** {'On' if settings['replay_gain'] else 'Off'}\n**Normalize:** {'On' if settings['normalize_volume'] else 'Off'}",
                inline=True
            )
            
            # Quick Commands
            embed.add_field(
                name="⚡ Quick Commands",
                value=f"`{ctx.prefix}equalizer` - EQ Controls\n`{ctx.prefix}filters` - Audio Effects\n`{ctx.prefix}settings quality` - Audio Quality\n`{ctx.prefix}settings djrole @role` - Set DJ Role",
                inline=False
            )
            
            view = SettingsMainView(self, ctx.guild.id)
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Settings menu error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to show settings menu.")

# UI Components for Settings

class AudioQualityView(ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @ui.select(placeholder="Select Audio Quality", options=[
        discord.SelectOption(label="Low Quality", description="96kbps - Saves bandwidth", value="low", emoji="📻"),
        discord.SelectOption(label="Medium Quality", description="128kbps - Good balance", value="medium", emoji="🎵"),
        discord.SelectOption(label="High Quality", description="192kbps - Great sound", value="high", emoji="🎧"),
        discord.SelectOption(label="Ultra Quality", description="320kbps - Best quality", value="ultra", emoji="💎"),
    ])
    async def select_quality(self, interaction: discord.Interaction, select: ui.Select):
        try:
            quality_map = {'low': "96", 'medium': "128", 'high': "192", 'ultra': "320"}
            settings = self.cog.get_guild_settings(self.guild_id)
            settings['audio_quality'] = quality_map[select.values[0]]
            
            embed = discord.Embed(
                title="🎵 Audio Quality Updated",
                description=f"Audio quality set to **{select.values[0].title()}** ({quality_map[select.values[0]]}kbps)",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self.cog.log_error(f"Quality selection error: {e}", self.guild_id)
            await interaction.response.send_message("❌ Failed to set quality.", ephemeral=True)

class EqualizerView(ui.View):
    def __init__(self, cog, guild_id, eq_settings):
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = guild_id
        self.eq_settings = eq_settings

    @ui.button(label="Bass Boost", style=discord.ButtonStyle.primary, emoji="🎵")
    async def bass_boost(self, interaction: discord.Interaction, button: ui.Button):
        # Apply bass boost preset
        self.eq_settings.update({'25': 6, '40': 5, '63': 4, '100': 2, '160': 1})
        await self.update_equalizer(interaction, "Bass Boost applied!")

    @ui.button(label="Vocal Boost", style=discord.ButtonStyle.primary, emoji="🎤")
    async def vocal_boost(self, interaction: discord.Interaction, button: ui.Button):
        # Apply vocal boost preset
        self.eq_settings.update({'1000': 3, '1600': 4, '2500': 5, '4000': 3})
        await self.update_equalizer(interaction, "Vocal Boost applied!")

    @ui.button(label="Treble Boost", style=discord.ButtonStyle.primary, emoji="🔊")
    async def treble_boost(self, interaction: discord.Interaction, button: ui.Button):
        # Apply treble boost preset
        self.eq_settings.update({'4000': 3, '6300': 4, '10000': 5, '16000': 6})
        await self.update_equalizer(interaction, "Treble Boost applied!")

    @ui.button(label="Reset", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def reset_eq(self, interaction: discord.Interaction, button: ui.Button):
        # Reset all bands to 0
        for freq in self.eq_settings:
            self.eq_settings[freq] = 0
        await self.update_equalizer(interaction, "Equalizer reset!")

    @ui.button(label="Custom", style=discord.ButtonStyle.success, emoji="⚙️")
    async def custom_eq(self, interaction: discord.Interaction, button: ui.Button):
        modal = CustomEQModal(self.cog, self.guild_id, self.eq_settings)
        await interaction.response.send_modal(modal)

    async def update_equalizer(self, interaction, message):
        embed = discord.Embed(
            title="🎛️ Equalizer Updated",
            description=message,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CustomEQModal(ui.Modal):
    def __init__(self, cog, guild_id, eq_settings):
        super().__init__(title="🎛️ Custom Equalizer Settings")
        self.cog = cog
        self.guild_id = guild_id
        self.eq_settings = eq_settings

    bass_input = ui.TextInput(
        label="Bass (25Hz-100Hz)",
        placeholder="Enter gain values: 25:+3 40:+2 63:+1 100:0",
        max_length=100
    )

    mid_input = ui.TextInput(
        label="Mids (160Hz-2500Hz)",
        placeholder="Enter gain values: 160:0 250:+1 400:0 630:+1 1000:+2 1600:+1 2500:0",
        max_length=150
    )

    treble_input = ui.TextInput(
        label="Treble (4000Hz-16000Hz)",
        placeholder="Enter gain values: 4000:+1 6300:+2 10000:+3 16000:+2",
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse input and update EQ settings
            for input_field in [self.bass_input, self.mid_input, self.treble_input]:
                if input_field.value:
                    pairs = input_field.value.split()
                    for pair in pairs:
                        if ':' in pair:
                            freq, gain = pair.split(':')
                            freq = freq.strip()
                            gain = int(gain.replace('+', ''))
                            if freq in self.eq_settings:
                                self.eq_settings[freq] = max(-12, min(12, gain))

            embed = discord.Embed(
                title="🎛️ Custom EQ Applied",
                description="Your custom equalizer settings have been applied!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await self.cog.log_error(f"Custom EQ error: {e}", self.guild_id)
            await interaction.response.send_message("❌ Invalid EQ format. Use format: 25:+3 40:-2", ephemeral=True)

class FiltersView(ui.View):
    def __init__(self, cog, guild_id, current_filter):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.current_filter = current_filter

    @ui.select(placeholder="Select Audio Filter", options=[
        discord.SelectOption(label="No Filter", description="Clean, unprocessed audio", value="none", emoji="🎵"),
        discord.SelectOption(label="Bass Boost", description="Enhanced low frequencies", value="bassboost", emoji="🔊"),
        discord.SelectOption(label="Reverb", description="Spacious echo effect", value="reverb", emoji="🏛️"),
        discord.SelectOption(label="Echo", description="Delayed repetition", value="echo", emoji="📢"),
        discord.SelectOption(label="Nightcore", description="Higher pitch and speed", value="nightcore", emoji="⚡"),
        discord.SelectOption(label="Vaporwave", description="Slowed and reverbed", value="vaporwave", emoji="🌊"),
        discord.SelectOption(label="Distortion", description="Aggressive sound", value="distortion", emoji="⚡"),
    ])
    async def select_filter(self, interaction: discord.Interaction, select: ui.Select):
        try:
            settings = self.cog.get_guild_settings(self.guild_id)
            settings['filters'] = select.values[0]
            
            embed = discord.Embed(
                title="🎚️ Audio Filter Applied",
                description=f"Filter changed to **{select.values[0].replace('_', ' ').title()}**",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self.cog.log_error(f"Filter selection error: {e}", self.guild_id)
            await interaction.response.send_message("❌ Failed to apply filter.", ephemeral=True)

class SettingsMainView(ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @ui.button(label="Equalizer", style=discord.ButtonStyle.primary, emoji="🎛️")
    async def open_equalizer(self, interaction: discord.Interaction, button: ui.Button):
        settings = self.cog.get_guild_settings(self.guild_id)
        view = EqualizerView(self.cog, self.guild_id, settings['equalizer'])
        
        embed = discord.Embed(
            title="🎛️ Professional 15-Band Equalizer",
            description="Adjust frequency bands to customize your audio experience.",
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Audio Filters", style=discord.ButtonStyle.primary, emoji="🎚️")
    async def open_filters(self, interaction: discord.Interaction, button: ui.Button):
        settings = self.cog.get_guild_settings(self.guild_id)
        view = FiltersView(self.cog, self.guild_id, settings['filters'])
        
        embed = discord.Embed(
            title="🎚️ Audio Filters & Effects",
            description="Apply various audio effects to enhance your listening experience.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Quality Settings", style=discord.ButtonStyle.secondary, emoji="🎵")
    async def open_quality(self, interaction: discord.Interaction, button: ui.Button):
        view = AudioQualityView(self.cog, self.guild_id)
        
        embed = discord.Embed(
            title="🎵 Audio Quality Settings",
            description="Select your preferred audio quality:",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicSettingsCog(bot))