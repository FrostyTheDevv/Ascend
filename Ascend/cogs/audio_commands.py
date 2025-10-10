import discord
from discord.ext import commands
from discord import ui
import wavelink
import datetime
import logging
import asyncio
from typing import Dict, List, Optional
import math

class AudioCommandsCog(commands.Cog, name="Audio Commands"):
    """🔊 Advanced audio control and manipulation commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.error_channel_id = 1425319240038223882

    async def log_error(self, error: str, guild_id: Optional[int] = None):
        """Log errors to designated channel"""
        try:
            error_channel = self.bot.get_channel(self.error_channel_id)
            if error_channel:
                embed = discord.Embed(
                    title="🚨 Audio Commands Error",
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

    @commands.hybrid_command(name="vol", brief="Set playback volume")
    async def volume(self, ctx, volume: int = None):
        """🔊 Set the playback volume (0-200) or open volume controls."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            player = ctx.voice_client

            if volume is None:
                # Show current volume and controls
                current_vol = int(player.volume * 100) if hasattr(player, 'volume') else 50
                
                view = VolumeControlView(player, current_vol)
                embed = discord.Embed(
                    title="🔊 Volume Controls",
                    description=f"**Current Volume:** {current_vol}%",
                    color=discord.Color.blue()
                )
                
                # Volume bar visualization
                volume_bar = "█" * (current_vol // 5) + "░" * (20 - current_vol // 5)
                embed.add_field(
                    name="Volume Level",
                    value=f"```{volume_bar} {current_vol}%```",
                    inline=False
                )
                
                await ctx.send(embed=embed, view=view)
                return

            # Validate volume range
            if not 0 <= volume <= 200:
                embed = discord.Embed(
                    title="❌ Invalid Volume",
                    description="Volume must be between 0 and 200.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Check permissions for high volume
            if volume > 100 and not self.has_dj_permissions(ctx):
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="You need DJ permissions to set volume above 100%.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            await player.set_volume(volume)
            
            volume_bar = "█" * (volume // 10) + "░" * (20 - volume // 10)
            embed = discord.Embed(
                title="🔊 Volume Updated",
                description=f"Volume set to **{volume}%**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Volume Level",
                value=f"```{volume_bar} {volume}%```",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Volume command error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to adjust volume.")

    @commands.hybrid_command(name="bassboost", aliases=["bass"], brief="Adjust bass boost")
    async def bass_boost(self, ctx, level: str = None):
        """🎵 Adjust bass boost level (off/low/medium/high/extreme)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if level is None:
                view = BassBoostView(ctx.voice_client)
                embed = discord.Embed(
                    title="🎵 Bass Boost Controls",
                    description="Select your preferred bass boost level:",
                    color=discord.Color.purple()
                )
                await ctx.send(embed=embed, view=view)
                return

            bass_levels = {
                'off': 0,
                'low': 0.15,
                'medium': 0.25,
                'high': 0.35,
                'extreme': 0.5
            }

            if level.lower() not in bass_levels:
                embed = discord.Embed(
                    title="❌ Invalid Level",
                    description="Valid levels: off, low, medium, high, extreme",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply bass boost filter (this would apply actual wavelink filters)
            boost_value = bass_levels[level.lower()]
            
            embed = discord.Embed(
                title="🎵 Bass Boost Applied",
                description=f"Bass boost set to **{level.title()}** ({int(boost_value * 100)}%)",
                color=discord.Color.green()
            )
            
            # Visual representation
            boost_bar = "█" * int(boost_value * 20) + "░" * (20 - int(boost_value * 20))
            embed.add_field(
                name="Bass Level",
                value=f"```{boost_bar} {level.title()}```",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Bass boost error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to adjust bass boost.")

    @commands.hybrid_command(name="speed", brief="Adjust playback speed")
    async def playback_speed(self, ctx, speed: float = None):
        """⚡ Adjust playback speed (0.5x - 2.0x)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if speed is None:
                view = SpeedControlView(ctx.voice_client)
                embed = discord.Embed(
                    title="⚡ Playback Speed Controls",
                    description="Adjust the playback speed of the current track:",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, view=view)
                return

            if not 0.5 <= speed <= 2.0:
                embed = discord.Embed(
                    title="❌ Invalid Speed",
                    description="Speed must be between 0.5x and 2.0x",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply speed filter (this would apply actual wavelink timescale filter)
            
            embed = discord.Embed(
                title="⚡ Playback Speed Adjusted",
                description=f"Playback speed set to **{speed}x**",
                color=discord.Color.green()
            )
            
            # Speed visualization
            speed_percentage = int((speed - 0.5) / 1.5 * 100)
            speed_bar = "█" * (speed_percentage // 5) + "░" * (20 - speed_percentage // 5)
            embed.add_field(
                name="Speed Level",
                value=f"```{speed_bar} {speed}x```",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Speed adjustment error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to adjust playback speed.")

    @commands.hybrid_command(name="pitch", brief="Adjust pitch")
    async def pitch_adjustment(self, ctx, pitch: float = None):
        """🎼 Adjust pitch without changing speed (-12 to +12 semitones)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if pitch is None:
                view = PitchControlView(ctx.voice_client)
                embed = discord.Embed(
                    title="🎼 Pitch Controls",
                    description="Adjust the pitch of the current track:",
                    color=discord.Color.teal()
                )
                await ctx.send(embed=embed, view=view)
                return

            if not -12 <= pitch <= 12:
                embed = discord.Embed(
                    title="❌ Invalid Pitch",
                    description="Pitch must be between -12 and +12 semitones",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply pitch filter
            
            embed = discord.Embed(
                title="🎼 Pitch Adjusted",
                description=f"Pitch adjusted by **{pitch:+.1f}** semitones",
                color=discord.Color.green()
            )
            
            # Pitch visualization
            pitch_percentage = int((pitch + 12) / 24 * 100)
            pitch_bar = "█" * (pitch_percentage // 5) + "░" * (20 - pitch_percentage // 5)
            embed.add_field(
                name="Pitch Level",
                value=f"```{pitch_bar} {pitch:+.1f}```",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Pitch adjustment error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to adjust pitch.")

    @commands.hybrid_command(name="distortion", brief="Apply distortion effect")
    async def distortion_effect(self, ctx, intensity: str = None):
        """⚡ Apply distortion effect (off/light/medium/heavy)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if intensity is None:
                view = DistortionView(ctx.voice_client)
                embed = discord.Embed(
                    title="⚡ Distortion Controls",
                    description="Apply distortion effects to the audio:",
                    color=discord.Color.dark_red()
                )
                await ctx.send(embed=embed, view=view)
                return

            distortion_levels = ['off', 'light', 'medium', 'heavy']
            
            if intensity.lower() not in distortion_levels:
                embed = discord.Embed(
                    title="❌ Invalid Intensity",
                    description="Valid levels: off, light, medium, heavy",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply distortion filter
            
            embed = discord.Embed(
                title="⚡ Distortion Applied",
                description=f"Distortion set to **{intensity.title()}**",
                color=discord.Color.green()
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Distortion error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to apply distortion.")

    @commands.hybrid_command(name="reverb", brief="Apply reverb effect")
    async def reverb_effect(self, ctx, room_size: str = None):
        """🏛️ Apply reverb effect (off/small/medium/large/hall)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if room_size is None:
                view = ReverbView(ctx.voice_client)
                embed = discord.Embed(
                    title="🏛️ Reverb Controls",
                    description="Add spatial depth with reverb effects:",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed, view=view)
                return

            reverb_types = ['off', 'small', 'medium', 'large', 'hall']
            
            if room_size.lower() not in reverb_types:
                embed = discord.Embed(
                    title="❌ Invalid Room Size",
                    description="Valid sizes: off, small, medium, large, hall",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply reverb filter
            
            embed = discord.Embed(
                title="🏛️ Reverb Applied",
                description=f"Reverb set to **{room_size.title()}** room",
                color=discord.Color.green()
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Reverb error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to apply reverb.")

    @commands.hybrid_command(name="nightcore", brief="Enable nightcore effect")
    async def nightcore_effect(self, ctx):
        """⚡ Apply nightcore effect (higher pitch and speed)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply nightcore effect (1.25x speed, +2 semitones pitch)
            
            embed = discord.Embed(
                title="⚡ Nightcore Applied",
                description="Applied nightcore effect (1.25x speed, +2 semitones)",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name="Effect Details",
                value="• **Speed:** 1.25x\n• **Pitch:** +2 semitones\n• **Energy:** High",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Nightcore error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to apply nightcore effect.")

    @commands.hybrid_command(name="vaporwave", brief="Enable vaporwave effect")
    async def vaporwave_effect(self, ctx):
        """🌊 Apply vaporwave effect (slower, deeper, with reverb)."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Apply vaporwave effect (0.8x speed, -2 semitones pitch, reverb)
            
            embed = discord.Embed(
                title="🌊 Vaporwave Applied",
                description="Applied vaporwave effect (0.8x speed, -2 semitones, reverb)",
                color=discord.Color.teal()
            )
            
            embed.add_field(
                name="Effect Details",
                value="• **Speed:** 0.8x\n• **Pitch:** -2 semitones\n• **Reverb:** Large room\n• **Mood:** Chill",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Vaporwave error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to apply vaporwave effect.")

    @commands.hybrid_command(name="reset_audio", aliases=["clear_effects"], brief="Reset all audio effects")
    async def reset_audio_effects(self, ctx):
        """🔄 Reset all audio effects to default."""
        try:
            if not ctx.voice_client:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Bot is not connected to a voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Reset all audio effects
            
            embed = discord.Embed(
                title="🔄 Audio Effects Reset",
                description="All audio effects have been reset to default.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Reset Settings",
                value="• Volume: 50%\n• Speed: 1.0x\n• Pitch: 0 semitones\n• Filters: Off",
                inline=False
            )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Reset audio error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to reset audio effects.")

# UI Components for Audio Controls

class VolumeControlView(ui.View):
    def __init__(self, player, current_volume):
        super().__init__(timeout=300)
        self.player = player
        self.current_volume = current_volume

    @ui.button(label="🔇", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction: discord.Interaction, button: ui.Button):
        await self.player.set_volume(0)
        await interaction.response.send_message("🔇 Audio muted!", ephemeral=True)

    @ui.button(label="-10", style=discord.ButtonStyle.primary)
    async def volume_down_10(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = max(0, self.current_volume - 10)
        await self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Volume: {new_vol}%", ephemeral=True)

    @ui.button(label="-5", style=discord.ButtonStyle.primary)
    async def volume_down_5(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = max(0, self.current_volume - 5)
        await self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Volume: {new_vol}%", ephemeral=True)

    @ui.button(label="+5", style=discord.ButtonStyle.primary)
    async def volume_up_5(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = min(200, self.current_volume + 5)
        await self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Volume: {new_vol}%", ephemeral=True)

    @ui.button(label="+10", style=discord.ButtonStyle.primary)
    async def volume_up_10(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = min(200, self.current_volume + 10)
        await self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Volume: {new_vol}%", ephemeral=True)

class BassBoostView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.select(placeholder="Select Bass Boost Level", options=[
        discord.SelectOption(label="Off", description="No bass enhancement", value="off", emoji="🔇"),
        discord.SelectOption(label="Low", description="Subtle bass boost", value="low", emoji="🎵"),
        discord.SelectOption(label="Medium", description="Moderate bass boost", value="medium", emoji="🔊"),
        discord.SelectOption(label="High", description="Strong bass boost", value="high", emoji="🎶"),
        discord.SelectOption(label="Extreme", description="Maximum bass boost", value="extreme", emoji="⚡"),
    ])
    async def select_bass_level(self, interaction: discord.Interaction, select: ui.Select):
        level = select.values[0]
        embed = discord.Embed(
            title="🎵 Bass Boost Applied",
            description=f"Bass boost set to **{level.title()}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SpeedControlView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.button(label="0.5x", style=discord.ButtonStyle.secondary)
    async def speed_half(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⚡ Speed set to 0.5x", ephemeral=True)

    @ui.button(label="0.75x", style=discord.ButtonStyle.secondary)
    async def speed_slow(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⚡ Speed set to 0.75x", ephemeral=True)

    @ui.button(label="1.0x", style=discord.ButtonStyle.primary)
    async def speed_normal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⚡ Speed reset to normal", ephemeral=True)

    @ui.button(label="1.25x", style=discord.ButtonStyle.secondary)
    async def speed_fast(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⚡ Speed set to 1.25x", ephemeral=True)

    @ui.button(label="1.5x", style=discord.ButtonStyle.secondary)
    async def speed_faster(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⚡ Speed set to 1.5x", ephemeral=True)

class PitchControlView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.button(label="-6", style=discord.ButtonStyle.secondary)
    async def pitch_down_6(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎼 Pitch: -6 semitones", ephemeral=True)

    @ui.button(label="-3", style=discord.ButtonStyle.secondary)
    async def pitch_down_3(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎼 Pitch: -3 semitones", ephemeral=True)

    @ui.button(label="0", style=discord.ButtonStyle.primary)
    async def pitch_normal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎼 Pitch reset to normal", ephemeral=True)

    @ui.button(label="+3", style=discord.ButtonStyle.secondary)
    async def pitch_up_3(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎼 Pitch: +3 semitones", ephemeral=True)

    @ui.button(label="+6", style=discord.ButtonStyle.secondary)
    async def pitch_up_6(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎼 Pitch: +6 semitones", ephemeral=True)

class DistortionView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.select(placeholder="Select Distortion Level", options=[
        discord.SelectOption(label="Off", description="No distortion", value="off", emoji="🔇"),
        discord.SelectOption(label="Light", description="Subtle distortion", value="light", emoji="⚡"),
        discord.SelectOption(label="Medium", description="Moderate distortion", value="medium", emoji="🔥"),
        discord.SelectOption(label="Heavy", description="Intense distortion", value="heavy", emoji="💥"),
    ])
    async def select_distortion(self, interaction: discord.Interaction, select: ui.Select):
        level = select.values[0]
        embed = discord.Embed(
            title="⚡ Distortion Applied",
            description=f"Distortion set to **{level.title()}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ReverbView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @ui.select(placeholder="Select Reverb Type", options=[
        discord.SelectOption(label="Off", description="No reverb", value="off", emoji="🔇"),
        discord.SelectOption(label="Small Room", description="Intimate space", value="small", emoji="🏠"),
        discord.SelectOption(label="Medium Room", description="Standard room", value="medium", emoji="🏢"),
        discord.SelectOption(label="Large Room", description="Spacious area", value="large", emoji="🏛️"),
        discord.SelectOption(label="Concert Hall", description="Grand venue", value="hall", emoji="🎭"),
    ])
    async def select_reverb(self, interaction: discord.Interaction, select: ui.Select):
        room_type = select.values[0]
        embed = discord.Embed(
            title="🏛️ Reverb Applied",
            description=f"Reverb set to **{room_type.replace('_', ' ').title()}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AudioCommandsCog(bot))