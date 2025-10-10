import discord
from discord.ext import commands
from discord import ui
import datetime
import json
import os
import secrets
import string
from typing import Optional
from database import DatabaseManager
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False

class AccountCreationModal(ui.Modal, title='Create Your Account'):
    def __init__(self):
        super().__init__()

    display_name = ui.TextInput(
        label='Display Name',
        placeholder='Enter your preferred display name...',
        max_length=32,
        required=False
    )

    bio = ui.TextInput(
        label='Bio (Optional)',
        placeholder='Tell us about yourself...',
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        db = DatabaseManager()
        
        # Create user account
        success = await db.create_user(
            user_id=interaction.user.id,
            username=str(interaction.user),
            display_name=self.display_name.value or str(interaction.user)
        )
        
        if success:
            embed = discord.Embed(
                title="🎉 Account Created Successfully!",
                description=f"Welcome to **Ascend**, {self.display_name.value or interaction.user.mention}!",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(
                name="📊 Account Stats",
                value="```Commands Used: 0\nSongs Played: 0\nJoined: Just now```",
                inline=False
            )
            embed.add_field(
                name="🎵 Next Steps",
                value="• Use `!help` to see all commands\n• Join a voice channel and use `!play <song>` to start\n• Create playlists with `!playlist create`",
                inline=False
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text="Ascend • Your music journey starts here")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="⚠️ Account Already Exists",
                description="You already have an account with Ascend!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SettingsModal(ui.Modal, title='⚙️ Update Settings'):
    def __init__(self, current_settings):
        super().__init__()
        self.current_settings = current_settings

    display_name = ui.TextInput(
        label='Display Name',
        placeholder='Your display name...',
        max_length=32,
        required=False
    )

    bio = ui.TextInput(
        label='Bio',
        placeholder='Tell us about yourself...',
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        db = DatabaseManager()
        
        # Update user data
        updates = {}
        if self.display_name.value:
            updates['display_name'] = self.display_name.value
        if self.bio.value:
            updates['bio'] = self.bio.value
        
        if updates:
            success = await db.update_user(interaction.user.id, **updates)
            if success:
                embed = discord.Embed(
                    title="✅ Settings Updated",
                    description="Your account settings have been updated successfully!",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Update Failed",
                    description="Failed to update your settings. Please try again.",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="ℹ️ No Changes",
                description="No changes were made to your settings.",
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SpotifyLinkModal(ui.Modal, title='Link Your Spotify Account'):
    def __init__(self):
        super().__init__()

    spotify_username = ui.TextInput(
        label='Spotify Username (Optional)',
        placeholder='Enter your Spotify username for display...',
        max_length=50,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not SPOTIFY_AVAILABLE:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not currently available. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        db = DatabaseManager()
        
        # Generate a unique state for this user
        state = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # Store the state temporarily (you might want to use a proper cache/database for this in production)
        # For now, we'll store it in the user's settings
        user_data = await db.get_user(interaction.user.id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Account Required",
                description="You need to create an Ascend account first! Use the `account` command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Update user with pending Spotify link
        spotify_data = {
            'spotify_state': state,
            'spotify_username': self.spotify_username.value,
            'spotify_link_pending': True,
            'spotify_link_timestamp': datetime.datetime.now().isoformat()
        }
        
        # Create Spotify OAuth
        try:
            # You'll need to set these environment variables or config
            client_id = os.getenv('SPOTIFY_CLIENT_ID', 'your_spotify_client_id')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', 'your_spotify_client_secret')
            redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'https://ascend-api.replit.app/callback')
            
            sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                state=state,
                scope="user-read-private user-read-email user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative",
                show_dialog=True
            )
            
            auth_url = sp_oauth.get_authorize_url()
            
            # Save the oauth state
            await db.update_user_spotify_data(interaction.user.id, spotify_data)
            
            embed = discord.Embed(
                title="🎵 Link Your Spotify Account",
                description=f"Click the link below to authorize Ascend to access your Spotify account:",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📱 Authorization Link",
                value=f"[Click Here to Link Spotify]({auth_url})",
                inline=False
            )
            embed.add_field(
                name="⚠️ Important",
                value="After authorizing, use the `spotify confirm <authorization_code>` command with the code from the redirect URL.",
                inline=False
            )
            embed.set_footer(text="This link expires in 10 minutes")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Spotify Configuration Error",
                description="There was an error setting up Spotify authentication. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SettingsDropdown(ui.Select):
    def __init__(self, user_data):
        self.user_data = user_data
        self.settings = json.loads(user_data.get('settings', '{}'))
        
        options = [
            discord.SelectOption(
                label="Notification Preferences",
                description="Configure music and bot notifications",
                emoji="🔔",
                value="notifications"
            ),
            discord.SelectOption(
                label="Music Preferences", 
                description="Auto-shuffle, queue behavior, etc.",
                emoji="🎵",
                value="music"
            ),
            discord.SelectOption(
                label="Privacy Settings",
                description="Profile visibility and activity sharing",
                emoji="🔒", 
                value="privacy"
            ),
            discord.SelectOption(
                label="Edit Profile",
                description="Change display name and bio",
                emoji="✏️",
                value="profile"
            ),
            discord.SelectOption(
                label="Reset All Settings",
                description="Restore default settings",
                emoji="🔄",
                value="reset"
            )
        ]
        
        super().__init__(placeholder="Choose a setting to customize...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "notifications":
            await self.show_notification_settings(interaction)
        elif self.values[0] == "music":
            await self.show_music_settings(interaction)
        elif self.values[0] == "privacy":
            await self.show_privacy_settings(interaction)
        elif self.values[0] == "profile":
            modal = SettingsModal(self.settings)
            modal.display_name.default = self.user_data.get('display_name', '')
            modal.bio.default = self.user_data.get('bio', '')
            await interaction.response.send_modal(modal)
            return
        elif self.values[0] == "reset":
            await self.show_reset_confirmation(interaction)

    async def show_notification_settings(self, interaction: discord.Interaction):
        current_notify = self.settings.get('notify_now_playing', True)
        current_queue = self.settings.get('notify_queue', True)
        
        embed = discord.Embed(
            title="🔔 Notification Settings",
            description="Choose your notification preferences:",
            color=discord.Color.blue()
        )
        
        view = ui.View(timeout=300)
        
        # Toggle buttons for notifications
        notify_btn = ui.Button(
            label=f"Now Playing: {'ON' if current_notify else 'OFF'}", 
            style=discord.ButtonStyle.success if current_notify else discord.ButtonStyle.secondary,
            emoji="🎵"
        )
        queue_btn = ui.Button(
            label=f"Queue Updates: {'ON' if current_queue else 'OFF'}",
            style=discord.ButtonStyle.success if current_queue else discord.ButtonStyle.secondary, 
            emoji="📋"
        )
        
        async def toggle_notify(btn_interaction):
            db = DatabaseManager()
            self.settings['notify_now_playing'] = not self.settings.get('notify_now_playing', True)
            await db.update_user_settings(interaction.user.id, self.settings)
            
            embed = discord.Embed(
                title="✅ Notification Updated",
                description=f"Now playing notifications: {'Enabled' if self.settings['notify_now_playing'] else 'Disabled'}",
                color=discord.Color.green()
            )
            
            # Add back button to return to settings
            back_view = ui.View(timeout=300)
            back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
            
            async def back_to_settings(back_interaction):
                settings_view = SettingsView(self.user_data)
                
                embed = discord.Embed(
                    title="⚙️ Account Settings",
                    description="Customize your Ascend experience using the dropdown below",
                    color=discord.Color.blue()
                )
                
                await back_interaction.response.edit_message(embed=embed, view=settings_view)
            
            back_btn.callback = back_to_settings
            back_view.add_item(back_btn)
            
            await btn_interaction.response.edit_message(embed=embed, view=back_view)
        
        async def toggle_queue(btn_interaction):
            db = DatabaseManager()
            self.settings['notify_queue'] = not self.settings.get('notify_queue', True)
            await db.update_user_settings(interaction.user.id, self.settings)
            
            embed = discord.Embed(
                title="✅ Queue Updated", 
                description=f"Queue notifications: {'Enabled' if self.settings['notify_queue'] else 'Disabled'}",
                color=discord.Color.green()
            )
            
            # Add back button to return to settings
            back_view = ui.View(timeout=300)
            back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
            
            async def back_to_settings(back_interaction):
                settings_view = SettingsView(self.user_data)
                
                embed = discord.Embed(
                    title="⚙️ Account Settings",
                    description="Customize your Ascend experience using the dropdown below",
                    color=discord.Color.blue()
                )
                
                await back_interaction.response.edit_message(embed=embed, view=settings_view)
            
            back_btn.callback = back_to_settings
            back_view.add_item(back_btn)
            
            await btn_interaction.response.edit_message(embed=embed, view=back_view)
        
        notify_btn.callback = toggle_notify
        queue_btn.callback = toggle_queue
        
        view.add_item(notify_btn)
        view.add_item(queue_btn)
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_music_settings(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎵 Music Preferences",
            description="Configure your music experience:",
            color=discord.Color.blue()
        )
        
        # Music preferences dropdown
        music_select = ui.Select(
            placeholder="Select a music preference...",
            options=[
                discord.SelectOption(label="Toggle Auto-Shuffle", description="Automatically shuffle new tracks", emoji="🔀", value="shuffle"),
                discord.SelectOption(label="Toggle Auto-Similar", description="Play similar songs automatically", emoji="🎯", value="similar"),
                discord.SelectOption(label="Set Default Volume", description="Your preferred volume level", emoji="🔊", value="volume")
            ]
        )
        
        async def music_callback(select_interaction):
            db = DatabaseManager()
            if select_interaction.data['values'][0] == "shuffle":
                self.settings['auto_shuffle'] = not self.settings.get('auto_shuffle', False)
                status = "enabled" if self.settings['auto_shuffle'] else "disabled"
                await db.update_user_settings(interaction.user.id, self.settings)
                
                embed = discord.Embed(title="🔀 Auto-Shuffle Updated", description=f"Auto-shuffle is now {status}", color=discord.Color.green())
                
                # Add back button
                back_view = ui.View(timeout=300)
                back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
                
                async def back_to_settings(back_interaction):
                    settings_view = SettingsView(self.user_data)
                    
                    embed = discord.Embed(
                        title="⚙️ Account Settings",
                        description="Customize your Ascend experience using the dropdown below",
                        color=discord.Color.blue()
                    )
                    
                    await back_interaction.response.edit_message(embed=embed, view=settings_view)
                
                back_btn.callback = back_to_settings
                back_view.add_item(back_btn)
                
                await select_interaction.response.edit_message(embed=embed, view=back_view)
            
            elif select_interaction.data['values'][0] == "similar":
                self.settings['auto_similar'] = not self.settings.get('auto_similar', False)
                status = "enabled" if self.settings['auto_similar'] else "disabled"
                await db.update_user_settings(interaction.user.id, self.settings)
                
                embed = discord.Embed(title="🎯 Auto-Similar Updated", description=f"Auto-similar is now {status}", color=discord.Color.green())
                
                # Add back button
                back_view = ui.View(timeout=300)
                back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
                
                async def back_to_settings(back_interaction):
                    settings_view = SettingsView(self.user_data)
                    
                    embed = discord.Embed(
                        title="⚙️ Account Settings",
                        description="Customize your Ascend experience using the dropdown below",
                        color=discord.Color.blue()
                    )
                    
                    await back_interaction.response.edit_message(embed=embed, view=settings_view)
                
                back_btn.callback = back_to_settings
                back_view.add_item(back_btn)
                
                await select_interaction.response.edit_message(embed=embed, view=back_view)
        
        music_select.callback = music_callback
        view = ui.View(timeout=300)
        view.add_item(music_select)
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_privacy_settings(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔒 Privacy Settings",
            description="Control your privacy and visibility:",
            color=discord.Color.blue()
        )
        
        privacy_select = ui.Select(
            placeholder="Select a privacy setting...",
            options=[
                discord.SelectOption(label="Toggle Profile Visibility", description="Make profile public or private", emoji="👤", value="profile"),
                discord.SelectOption(label="Toggle Activity Sharing", description="Share your music activity", emoji="📊", value="activity")
            ]
        )
        
        async def privacy_callback(select_interaction):
            db = DatabaseManager()
            if select_interaction.data['values'][0] == "profile":
                self.settings['profile_public'] = not self.settings.get('profile_public', True)
                status = "public" if self.settings['profile_public'] else "private"
                await db.update_user_settings(interaction.user.id, self.settings)
                
                embed = discord.Embed(title="👤 Profile Updated", description=f"Profile is now {status}", color=discord.Color.green())
                
                # Add back button
                back_view = ui.View(timeout=300)
                back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
                
                async def back_to_settings(back_interaction):
                    settings_view = SettingsView(self.user_data)
                    
                    embed = discord.Embed(
                        title="⚙️ Account Settings",
                        description="Customize your Ascend experience using the dropdown below",
                        color=discord.Color.blue()
                    )
                    
                    await back_interaction.response.edit_message(embed=embed, view=settings_view)
                
                back_btn.callback = back_to_settings
                back_view.add_item(back_btn)
                
                await select_interaction.response.edit_message(embed=embed, view=back_view)
            
            elif select_interaction.data['values'][0] == "activity":
                self.settings['show_activity'] = not self.settings.get('show_activity', True)
                status = "visible" if self.settings['show_activity'] else "hidden"
                await db.update_user_settings(interaction.user.id, self.settings)
                
                embed = discord.Embed(title="📊 Activity Updated", description=f"Activity is now {status}", color=discord.Color.green())
                
                # Add back button
                back_view = ui.View(timeout=300)
                back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
                
                async def back_to_settings(back_interaction):
                    settings_view = SettingsView(self.user_data)
                    
                    embed = discord.Embed(
                        title="⚙️ Account Settings",
                        description="Customize your Ascend experience using the dropdown below",
                        color=discord.Color.blue()
                    )
                    
                    await back_interaction.response.edit_message(embed=embed, view=settings_view)
                
                back_btn.callback = back_to_settings
                back_view.add_item(back_btn)
                
                await select_interaction.response.edit_message(embed=embed, view=back_view)
        
        privacy_select.callback = privacy_callback
        view = ui.View(timeout=300)
        view.add_item(privacy_select)
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_reset_confirmation(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ Reset All Settings",
            description="This will restore all settings to their default values. This action cannot be undone.",
            color=discord.Color.orange()
        )
        
        view = ui.View(timeout=30)
        
        confirm_btn = ui.Button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_btn = ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        
        async def confirm_reset(btn_interaction):
            db = DatabaseManager()
            default_settings = {
                'notify_now_playing': True,
                'notify_queue': True,
                'auto_shuffle': False,
                'auto_similar': False,
                'profile_public': True,
                'show_activity': True
            }
            await db.update_user_settings(interaction.user.id, default_settings)
            
            embed = discord.Embed(title="🔄 Settings Reset", description="All settings restored to defaults!", color=discord.Color.green())
            
            # Add back button
            back_view = ui.View(timeout=300)
            back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
            
            async def back_to_settings(back_interaction):
                settings_view = SettingsView(self.user_data)
                
                embed = discord.Embed(
                    title="⚙️ Account Settings",
                    description="Customize your Ascend experience using the dropdown below",
                    color=discord.Color.blue()
                )
                
                await back_interaction.response.edit_message(embed=embed, view=settings_view)
            
            back_btn.callback = back_to_settings
            back_view.add_item(back_btn)
            
            await btn_interaction.response.edit_message(embed=embed, view=back_view)
        
        async def cancel_reset(btn_interaction):
            embed = discord.Embed(title="❌ Reset Cancelled", description="Settings remain unchanged.", color=discord.Color.blue())
            
            # Add back button
            back_view = ui.View(timeout=300)
            back_btn = ui.Button(label="← Back to Settings", style=discord.ButtonStyle.secondary)
            
            async def back_to_settings(back_interaction):
                settings_view = SettingsView(self.user_data)
                
                embed = discord.Embed(
                    title="⚙️ Account Settings",
                    description="Customize your Ascend experience using the dropdown below",
                    color=discord.Color.blue()
                )
                
                await back_interaction.response.edit_message(embed=embed, view=settings_view)
            
            back_btn.callback = back_to_settings
            back_view.add_item(back_btn)
            
            await btn_interaction.response.edit_message(embed=embed, view=back_view)
        
        confirm_btn.callback = confirm_reset
        cancel_btn.callback = cancel_reset
        
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        await interaction.response.edit_message(embed=embed, view=view)

class SettingsView(ui.View):
    def __init__(self, user_data):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.settings = json.loads(user_data.get('settings', '{}'))
        
        # Add the settings dropdown
        self.add_item(SettingsDropdown(user_data))

    @ui.button(label='Link as Spotify Device', style=discord.ButtonStyle.success, emoji='🔗', row=1)
    async def link_spotify(self, interaction: discord.Interaction, button: ui.Button):
        # Check if already linked
        if self.user_data.get('spotify_connected'):
            embed = discord.Embed(
                title="� Spotify Device Already Linked",
                description="Your Spotify account is already connected as a remote device!\n\n• Use `<spotify status` to see device details\n• Use `<spotify unlink` to disconnect\n• Control playback with Discord commands",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎧 Link Ascend as Spotify Device",
            description="**Connect your Spotify account to use Ascend as a remote control device!**\n\nThis allows you to:\n• Control Spotify playback from Discord\n• See what's playing on your Spotify\n• Switch between Spotify devices\n• Use Discord commands to control your music\n\n*Note: Music plays through your Spotify app/device, not Discord voice channels.*",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎮 How Device Control Works",
            value="• Ascend becomes a 'virtual device' in your Spotify\n• Use Discord commands to control your real Spotify\n• Music plays through your chosen Spotify device\n• Perfect for remote control and integration",
            inline=False
        )
        
        embed.add_field(
            name="🎵 Available Commands After Linking",
            value="`<device` - Set active Spotify device\n`<spotify status` - Check connection\n`<nowplaying` - See current track\nAnd more music control commands!",
            inline=False
        )
        
        view = ui.View(timeout=300)
        link_button = ui.Button(label="🔗 Start Device Linking", style=discord.ButtonStyle.success)
        
        async def start_device_linking(btn_interaction):
            modal = SpotifyLinkModal()
            await btn_interaction.response.send_modal(modal)
        
        link_button.callback = start_device_linking
        view.add_item(link_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label='Reset to Defaults', style=discord.ButtonStyle.danger, emoji='🔄', row=1)
    async def reset_settings(self, interaction: discord.Interaction, button: ui.Button):
        # Confirmation view
        confirm_view = ui.View(timeout=30)
        
        async def confirm_reset(confirm_interaction):
            db = DatabaseManager()
            default_settings = {
                'notify_now_playing': True,
                'notify_queue': True,
                'auto_shuffle': False,
                'auto_similar': False,
                'profile_public': True,
                'show_activity': True
            }
            
            await db.update_user_settings(interaction.user.id, default_settings)
            self.settings = default_settings
            
            embed = discord.Embed(
                title="🔄 Settings Reset",
                description="All settings have been reset to default values!",
                color=discord.Color.green()
            )
            await confirm_interaction.response.edit_message(embed=embed, view=None)
        
        async def cancel_reset(cancel_interaction):
            embed = discord.Embed(
                title="❌ Reset Cancelled",
                description="Your settings remain unchanged.",
                color=discord.Color.blue()
            )
            await cancel_interaction.response.edit_message(embed=embed, view=None)
        
        confirm_button = ui.Button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_button = ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        
        confirm_button.callback = confirm_reset
        cancel_button.callback = cancel_reset
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description="Are you sure you want to reset all settings to default values? This cannot be undone.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class ProfileView(ui.View):
    def __init__(self, user_data, user_stats):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.user_stats = user_stats

    @ui.button(label='Statistics', style=discord.ButtonStyle.primary, emoji='📊')
    async def show_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📊 Detailed Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Command usage stats
        if self.user_stats.get('command_stats'):
            top_commands = self.user_stats['command_stats'][:5]
            command_text = "\n".join([f"`{cmd['command_name']}`: {cmd['count']} times" for cmd in top_commands])
            embed.add_field(name="🎯 Top Commands", value=command_text or "No commands used yet", inline=True)
        
        # Music stats
        music_stats = self.user_stats.get('music_stats', {})
        music_text = f"**Total Songs:** {music_stats.get('total_songs', 0)}\n"
        music_text += f"**Servers Used:** {music_stats.get('servers_used', 0)}\n"
        if music_stats.get('avg_duration'):
            avg_duration = int(music_stats['avg_duration'])
            music_text += f"**Avg Duration:** {avg_duration // 60}:{avg_duration % 60:02d}"
        embed.add_field(name="🎵 Music Stats", value=music_text, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label='Playlists', style=discord.ButtonStyle.secondary, emoji='🎶')
    async def show_playlists(self, interaction: discord.Interaction, button: ui.Button):
        db = DatabaseManager()
        playlists = await db.get_user_playlists(interaction.user.id)
        
        embed = discord.Embed(
            title="🎶 Your Playlists",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        if playlists:
            playlist_text = ""
            for playlist in playlists[:10]:  # Show first 10 playlists
                visibility = "🌐" if playlist['is_public'] else "🔒"
                playlist_text += f"{visibility} **{playlist['name']}** ({playlist['track_count']} tracks)\n"
            embed.add_field(name="Your Playlists", value=playlist_text, inline=False)
        else:
            embed.add_field(
                name="No Playlists Yet", 
                value="Create your first playlist with `!playlist create <name>`", 
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label='Settings', style=discord.ButtonStyle.secondary, emoji='⚙️')
    async def show_settings(self, interaction: discord.Interaction, button: ui.Button):
        settings_view = SettingsView(self.user_data)
        
        embed = discord.Embed(
            title="⚙️ Account Settings",
            description="Customize your Ascend experience using the buttons below",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        settings = json.loads(self.user_data.get('settings', '{}'))
        
        embed.add_field(
            name="🔔 Notifications",
            value=f"Now Playing: {'✅' if settings.get('notify_now_playing', True) else '❌'}\nQueue Updates: {'✅' if settings.get('notify_queue', True) else '❌'}",
            inline=True
        )
        
        embed.add_field(
            name="🎵 Music Preferences",
            value=f"Auto-shuffle: {'✅' if settings.get('auto_shuffle', False) else '❌'}\nAuto-play similar: {'✅' if settings.get('auto_similar', False) else '❌'}",
            inline=True
        )
        
        embed.add_field(
            name="🔒 Privacy",
            value=f"Public Profile: {'✅' if settings.get('profile_public', True) else '❌'}\nShow Activity: {'✅' if settings.get('show_activity', True) else '❌'}",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=settings_view)

    @ui.button(label='Back to Profile', style=discord.ButtonStyle.success, emoji='👤')
    async def back_to_profile(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title=f"👤 {self.user_data['display_name']}'s Profile",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📊 Account Stats",
            value=f"```Commands Used: {self.user_data['total_commands_used']}\nMember Since: {self.user_data['created_at'][:10]}\nLast Active: {self.user_data['last_active'][:10]}```",
            inline=False
        )
        
        premium_status = "✨ Premium" if self.user_data.get('premium_status') else "🆓 Free"
        embed.add_field(name="💎 Status", value=premium_status, inline=True)
        
        spotify_status = "🎵 Connected" if self.user_data.get('spotify_connected') else "❌ Not Connected"
        embed.add_field(name="🟢 Spotify", value=spotify_status, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    def __init__(self, user_data, user_stats):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.user_stats = user_stats

    @ui.button(label='Statistics', style=discord.ButtonStyle.primary, emoji='📊')
    async def show_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📊 Detailed Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Command usage stats
        if self.user_stats.get('command_stats'):
            top_commands = self.user_stats['command_stats'][:5]
            command_text = "\n".join([f"`{cmd['command_name']}`: {cmd['count']} times" for cmd in top_commands])
            embed.add_field(name="🎯 Top Commands", value=command_text or "No commands used yet", inline=True)
        
        # Music stats
        music_stats = self.user_stats.get('music_stats', {})
        music_text = f"**Total Songs:** {music_stats.get('total_songs', 0)}\n"
        music_text += f"**Servers Used:** {music_stats.get('servers_used', 0)}\n"
        if music_stats.get('avg_duration'):
            avg_duration = int(music_stats['avg_duration'])
            music_text += f"**Avg Duration:** {avg_duration // 60}:{avg_duration % 60:02d}"
        embed.add_field(name="🎵 Music Stats", value=music_text, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label='Playlists', style=discord.ButtonStyle.secondary, emoji='🎶')
    async def show_playlists(self, interaction: discord.Interaction, button: ui.Button):
        db = DatabaseManager()
        playlists = await db.get_user_playlists(interaction.user.id)
        
        embed = discord.Embed(
            title="🎶 Your Playlists",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now()
        )
        
        if playlists:
            playlist_text = ""
            for playlist in playlists[:10]:  # Show first 10 playlists
                visibility = "🌐" if playlist['is_public'] else "🔒"
                playlist_text += f"{visibility} **{playlist['name']}** ({playlist['track_count']} tracks)\n"
            embed.add_field(name="Your Playlists", value=playlist_text, inline=False)
        else:
            embed.add_field(
                name="No Playlists Yet", 
                value="Create your first playlist with `!playlist create <name>`", 
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label='Settings', style=discord.ButtonStyle.secondary, emoji='⚙️')
    async def show_settings(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="⚙️ Account Settings",
            description="Customize your Ascend experience with the buttons below",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now()
        )
        
        settings = json.loads(self.user_data.get('settings', '{}'))
        
        embed.add_field(
            name="🔔 Current Settings",
            value=f"**Notifications:** {'Enabled' if settings.get('notify_now_playing', True) else 'Disabled'}\n"
                  f"**Auto-shuffle:** {'Enabled' if settings.get('auto_shuffle', False) else 'Disabled'}\n"
                  f"**Profile:** {'Public' if settings.get('profile_public', True) else 'Private'}",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Available Settings",
            value="Use the buttons below to customize your preferences:",
            inline=False
        )
        
        # Create and show the SettingsView with interactive buttons
        settings_view = SettingsView(self.user_data)
        await interaction.response.edit_message(embed=embed, view=settings_view)

    @ui.button(label='Back to Profile', style=discord.ButtonStyle.success, emoji='👤')
    async def back_to_profile(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title=f"👤 {self.user_data['display_name']}'s Profile",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📊 Account Stats",
            value=f"```Commands Used: {self.user_data['total_commands_used']}\nMember Since: {self.user_data['created_at'][:10]}\nLast Active: {self.user_data['last_active'][:10]}```",
            inline=False
        )
        
        premium_status = "✨ Premium" if self.user_data.get('premium_status') else "🆓 Free"
        embed.add_field(name="💎 Status", value=premium_status, inline=True)
        
        spotify_status = "🎵 Connected" if self.user_data.get('spotify_connected') else "❌ Not Connected"
        embed.add_field(name="🟢 Spotify", value=spotify_status, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

class AccountCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    @commands.command(name='signup', aliases=['register', 'create-account'])
    async def signup(self, ctx):
        """Create a new account with Ascend"""
        # Check if user already has account
        user_data = await self.db.get_user(ctx.author.id)
        if user_data:
            embed = discord.Embed(
                title="⚠️ Account Already Exists",
                description=f"You already have an account! Use `{ctx.prefix}profile` to view it.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Show account creation modal
        modal = AccountCreationModal()
        
        embed = discord.Embed(
            title="🚀 Create Your Ascend Account",
            description="Click the button below to create your account and unlock all features!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🎵 What you'll get:",
            value="• Personal music statistics\n• Custom playlists\n• Command preferences\n• Premium features (coming soon)",
            inline=False
        )
        
        view = ui.View()
        
        async def modal_callback(interaction):
            await interaction.response.send_modal(modal)
        
        button = ui.Button(label="Create Account", style=discord.ButtonStyle.success, emoji="✨")
        button.callback = modal_callback
        view.add_item(button)
        
        await ctx.send(embed=embed, view=view)

    @commands.command(name='signin', aliases=['login'])
    async def signin(self, ctx):
        """Sign in to your existing account"""
        user_data = await self.db.get_user(ctx.author.id)
        
        if not user_data:
            embed = discord.Embed(
                title="❌ No Account Found",
                description=f"You don't have an account yet! Use `{ctx.prefix}signup` to create one.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Update last active
        await self.db.update_user_activity(ctx.author.id)
        
        embed = discord.Embed(
            title="✅ Welcome Back!",
            description=f"Successfully signed in, **{user_data['display_name']}**!",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📊 Quick Stats",
            value=f"```Commands Used: {user_data['total_commands_used']}\nLast Active: {user_data['last_active'][:10]}```",
            inline=False
        )
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='profile', aliases=['account', 'me'])
    async def profile(self, ctx, user: discord.Member = None):
        """View your or another user's profile"""
        target_user = user or ctx.author
        
        user_data = await self.db.get_user(target_user.id)
        if not user_data:
            if target_user == ctx.author:
                embed = discord.Embed(
                    title="❌ No Account Found",
                    description=f"You don't have an account yet! Use `{ctx.prefix}signup` to create one.",
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="❌ User Not Found",
                    description=f"{target_user.mention} doesn't have an account with Ascend.",
                    color=discord.Color.red()
                )
            await ctx.send(embed=embed)
            return
        
        # Get detailed stats
        user_stats = await self.db.get_user_stats(target_user.id)
        
        embed = discord.Embed(
            title=f"👤 {user_data['display_name']}'s Profile",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📊 Account Stats",
            value=f"```Commands Used: {user_data['total_commands_used']}\nMember Since: {user_data['created_at'][:10]}\nLast Active: {user_data['last_active'][:10]}```",
            inline=False
        )
        
        premium_status = "✨ Premium" if user_data.get('premium_status') else "🆓 Free"
        embed.add_field(name="💎 Status", value=premium_status, inline=True)
        
        spotify_status = "🎵 Connected" if user_data.get('spotify_connected') else "❌ Not Connected"
        embed.add_field(name="🟢 Spotify", value=spotify_status, inline=True)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.set_footer(text="Use the buttons below to explore more details")
        
        # Only show interactive view for own profile
        if target_user == ctx.author:
            view = ProfileView(user_data, user_stats)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(embed=embed)

    @commands.group(name='link_spotify', aliases=['spotify_link'], invoke_without_command=True)
    async def spotify(self, ctx):
        """Spotify account linking and management commands."""
        embed = discord.Embed(
            title="🎵 Spotify Integration",
            description="Link your Spotify account to Ascend for enhanced music features!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📱 Available Commands",
            value="`link_spotify link` - Link your Spotify account\n"
                  "`link_spotify unlink` - Unlink your Spotify account\n"
                  "`link_spotify status` - Check your connection status\n"
                  "`link_spotify confirm <code>` - Confirm authorization",
            inline=False
        )
        embed.add_field(
            name="✨ Benefits",
            value="• Control Spotify playback through Discord\n"
                  "• Access your Spotify playlists\n"
                  "• Enhanced music recommendations\n"
                  "• Cross-platform music sync",
            inline=False
        )
        await ctx.send(embed=embed)

    @spotify.command(name='link')
    async def spotify_link(self, ctx):
        """Link your Spotify account to Ascend."""
        user_data = await self.db.get_user(ctx.author.id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Account Required",
                description="You need to create an Ascend account first! Use the `account` command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if user_data.get('spotify_connected'):
            embed = discord.Embed(
                title="🎵 Already Connected",
                description="Your Spotify account is already linked! Use `spotify unlink` to disconnect first.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        modal = SpotifyLinkModal()
        embed = discord.Embed(
            title="🎵 Link Your Spotify Account",
            description="Click the button below to start the linking process:",
            color=discord.Color.green()
        )
        
        view = ui.View(timeout=300)
        link_button = ui.Button(label="🔗 Start Linking Process", style=discord.ButtonStyle.success)
        
        async def start_linking(interaction):
            await interaction.response.send_modal(modal)
        
        link_button.callback = start_linking
        view.add_item(link_button)
        
        await ctx.send(embed=embed, view=view)

    @spotify.command(name='confirm')
    async def spotify_confirm(self, ctx, *, authorization_code: str):
        """Confirm Spotify authorization with the provided code."""
        if not SPOTIFY_AVAILABLE:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not currently available.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        user_data = await self.db.get_user(ctx.author.id)
        if not user_data or not user_data.get('spotify_link_pending'):
            embed = discord.Embed(
                title="❌ No Pending Link",
                description="You don't have a pending Spotify link. Use `spotify link` first.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Get the stored state - try both 'spotify_state' and 'state'
            spotify_state = user_data.get('spotify_state') or user_data.get('state')
            
            if not spotify_state:
                embed = discord.Embed(
                    title="❌ Invalid State",
                    description="The linking session has expired. Please start over with `spotify link`.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Set up Spotify OAuth
            client_id = os.getenv('SPOTIFY_CLIENT_ID', 'your_spotify_client_id')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', 'your_spotify_client_secret')
            redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'https://ascend-api.replit.app/callback')
            
            sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                state=spotify_state,
                scope="user-read-private user-read-email user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative"
            )
            
            # Exchange authorization code for access token
            token_info = sp_oauth.get_access_token(authorization_code)
            
            if token_info:
                # Create Spotify client
                sp = spotipy.Spotify(auth=token_info['access_token'])
                
                # Get user info
                spotify_user = sp.current_user()
                
                # Update user data with Spotify connection
                spotify_data = {
                    'spotify_connected': True,
                    'spotify_id': spotify_user['id'],
                    'spotify_display_name': spotify_user.get('display_name', spotify_user['id']),
                    'spotify_email': spotify_user.get('email'),
                    'spotify_followers': spotify_user['followers']['total'],
                    'spotify_access_token': token_info['access_token'],
                    'spotify_refresh_token': token_info['refresh_token'],
                    'spotify_token_expires_at': token_info['expires_at'],
                    'spotify_link_pending': False,
                    'spotify_connected_at': datetime.datetime.now().isoformat()
                }
                
                await self.db.update_user_spotify_data(ctx.author.id, spotify_data)
                
                embed = discord.Embed(
                    title="🎉 Spotify Linked Successfully!",
                    description=f"Your Spotify account **{spotify_user.get('display_name', spotify_user['id'])}** has been linked to Ascend!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📊 Account Info",
                    value=f"**ID:** {spotify_user['id']}\n"
                          f"**Followers:** {spotify_user['followers']['total']:,}\n"
                          f"**Country:** {spotify_user.get('country', 'N/A')}",
                    inline=True
                )
                embed.add_field(
                    name="✨ What's Next?",
                    value="You can now use enhanced music features!\n"
                          "• Use music commands with Spotify integration\n"
                          "• Access your Spotify playlists\n"
                          "• Control Spotify playback",
                    inline=False
                )
                embed.set_thumbnail(url=spotify_user['images'][0]['url'] if spotify_user['images'] else None)
                await ctx.send(embed=embed)
                
            else:
                embed = discord.Embed(
                    title="❌ Authorization Failed",
                    description="Failed to exchange authorization code for access token. Please try again.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Connection Error",
                description=f"An error occurred while linking your Spotify account: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name='unlink')
    async def spotify_unlink(self, ctx):
        """Unlink your Spotify account from Ascend."""
        user_data = await self.db.get_user(ctx.author.id)
        if not user_data or not user_data.get('spotify_connected'):
            embed = discord.Embed(
                title="❌ Not Connected",
                description="You don't have a Spotify account linked to Ascend.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Confirmation view
        view = ui.View(timeout=30)
        
        async def confirm_unlink(interaction):
            # Clear Spotify data
            spotify_data = {
                'spotify_connected': False,
                'spotify_id': None,
                'spotify_display_name': None,
                'spotify_email': None,
                'spotify_followers': None,
                'spotify_access_token': None,
                'spotify_refresh_token': None,
                'spotify_token_expires_at': None,
                'spotify_link_pending': False,
                'spotify_unlinked_at': datetime.datetime.now().isoformat()
            }
            
            await self.db.update_user_spotify_data(ctx.author.id, spotify_data)
            
            embed = discord.Embed(
                title="🎵 Spotify Unlinked",
                description="Your Spotify account has been successfully unlinked from Ascend.",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        
        async def cancel_unlink(interaction):
            embed = discord.Embed(
                title="❌ Unlink Cancelled",
                description="Your Spotify account remains linked.",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        
        confirm_button = ui.Button(label="✅ Confirm Unlink", style=discord.ButtonStyle.danger)
        cancel_button = ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        
        confirm_button.callback = confirm_unlink
        cancel_button.callback = cancel_unlink
        
        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        embed = discord.Embed(
            title="⚠️ Confirm Spotify Unlink",
            description=f"Are you sure you want to unlink your Spotify account **{user_data.get('spotify_display_name', 'Unknown')}**?\n\nThis will remove access to Spotify-specific features.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, view=view)

    @spotify.command(name='status')
    async def spotify_status(self, ctx):
        """Check your Spotify connection status."""
        user_data = await self.db.get_user(ctx.author.id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Account Required",
                description="You need to create an Ascend account first! Use the `account` command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎵 Spotify Connection Status",
            color=discord.Color.green() if user_data.get('spotify_connected') else discord.Color.red()
        )
        
        if user_data.get('spotify_connected'):
            embed.description = "✅ Your Spotify account is connected!"
            embed.add_field(
                name="📊 Connected Account",
                value=f"**Display Name:** {user_data.get('spotify_display_name', 'N/A')}\n"
                      f"**Spotify ID:** {user_data.get('spotify_id', 'N/A')}\n"
                      f"**Followers:** {user_data.get('spotify_followers', 0):,}",
                inline=True
            )
            
            connected_date = user_data.get('spotify_connected_at', '')
            if connected_date:
                try:
                    connected_dt = datetime.datetime.fromisoformat(connected_date)
                    embed.add_field(
                        name="🕒 Connected Since",
                        value=connected_dt.strftime("%B %d, %Y at %I:%M %p"),
                        inline=True
                    )
                except:
                    pass
                    
            embed.add_field(
                name="🎮 Available Features",
                value="• Enhanced music search\n• Playlist access\n• Playback control\n• Music recommendations",
                inline=False
            )
        else:
            embed.description = "❌ No Spotify account connected."
            embed.add_field(
                name="🔗 Get Started",
                value="Use `spotify link` to connect your Spotify account and unlock enhanced music features!",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AccountCog(bot))

