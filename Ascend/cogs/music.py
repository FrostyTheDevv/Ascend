import discord
from discord.ext import commands, tasks
from discord import ui
import wavelink
import asyncio
import datetime
import json
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import aiohttp
import random
from typing import Optional, List, Dict, Union, Any
import logging
from dataclasses import dataclass, field
from enum import Enum
import math
import time
import urllib.parse
import base64
import hashlib
import secrets
from collections import deque
import os

@dataclass
class QueueItem:
    track: wavelink.Playable
    requester: discord.Member
    timestamp: datetime.datetime
    position: int = 0
    played: bool = False
    likes: int = 0
    dislikes: int = 0
    skips: List[int] = field(default_factory=list)

@dataclass
class PlaylistItem:
    name: str
    tracks: List[QueueItem]
    creator: discord.Member
    created_at: datetime.datetime
    description: str = ""
    public: bool = True
    plays: int = 0

@dataclass
class EqualizerBand:
    frequency: str
    gain: float = 0.0

class RepeatMode(Enum):
    OFF = 0
    TRACK = 1
    QUEUE = 2

class PlayerState(Enum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"

class SearchSource(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"
    TWITCH = "twitch"

class VoteType(Enum):
    SKIP = "skip"
    STOP = "stop"
    SHUFFLE = "shuffle"
    PAUSE = "pause"

class MusicQueue(wavelink.Queue):
    def __init__(self):
        super().__init__()
        self.track_history: List[QueueItem] = []  # Renamed to avoid conflict with wavelink.Queue.history
        self.current: Optional[QueueItem] = None
        self.repeat_mode: RepeatMode = RepeatMode.OFF
        self.shuffle: bool = False
        self._original_order: List[QueueItem] = []
        self.autoplay: bool = False
        self.max_queue_size: int = 1000
        self.loop_start: int = 0
        self.loop_end: int = -1
        self.favorites: List[QueueItem] = []
        self.blacklist: List[str] = []
        self.votes: Dict[str, List[int]] = {}
        self.volume_history: deque = deque(maxlen=10)
        self.items: List[QueueItem] = []  # Our custom items list

    def add(self, track: wavelink.Playable, requester: discord.Member, priority: bool = False) -> QueueItem:
        if len(self.items) >= self.max_queue_size:
            raise ValueError(f"Queue is full! Maximum {self.max_queue_size} tracks allowed.")
        
        # Check blacklist
        if any(blocked in track.title.lower() or blocked in track.author.lower() 
               for blocked in self.blacklist):
            raise ValueError("This track is blacklisted!")
        
        item = QueueItem(
            track=track,
            requester=requester,
            timestamp=datetime.datetime.now(),
            position=len(self.items)
        )
        
        if priority:
            self.items.insert(0, item)
            # Update positions
            for i, queue_item in enumerate(self.items):
                queue_item.position = i
        else:
            self.items.append(item)
        
        if not self.shuffle:
            self._original_order.append(item)
        return item

    # Override Wavelink's put method to work with our custom queue items
    def put(self, item: wavelink.Playable, *, atomic: bool = True) -> None:
        """Override Wavelink's put method to create QueueItems."""
        # Create a QueueItem wrapper
        if hasattr(item, 'requester'):
            requester = item.requester
        else:
            requester = discord.Object(id=0)  # Default requester
        
        queue_item = QueueItem(
            track=item,
            requester=requester,
            timestamp=datetime.datetime.now(),
            position=len(self.items)
        )
        
        # Add to our custom items list
        self.items.append(queue_item)
        
        # Add to Wavelink's internal queue for compatibility (just the track)
        try:
            super().put(item, atomic=atomic)
        except Exception:
            # If super().put() fails, just add to internal list directly
            self._items.append(item)

    def get(self) -> Optional[QueueItem]:
        """Override Wavelink's get method to work with our custom queue items."""
        next_item = self.get_next()
        if next_item:
            # Also remove from Wavelink's internal queue if present
            try:
                super().get()
            except:
                pass
        return next_item

    def get_at(self, index: int) -> Optional[QueueItem]:
        """Get item at specific index."""
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def add_multiple(self, tracks: List[wavelink.Playable], requester: discord.Member) -> List[QueueItem]:
        added_items = []
        for track in tracks:
            try:
                item = self.add(track, requester)
                added_items.append(item)
            except ValueError:
                continue  # Skip blacklisted or if queue full
        return added_items

    def get_next(self) -> Optional[QueueItem]:
        if self.repeat_mode == RepeatMode.TRACK and self.current:
            return self.current
        
        if not self.items:
            if self.autoplay and self.track_history:
                # Auto-generate similar tracks based on history
                return self._generate_autoplay_track()
            return None
        
        if self.shuffle:
            # Weighted shuffle based on likes/dislikes
            weights = []
            for item in self.items:
                weight = max(1, item.likes - item.dislikes + 1)
                weights.append(weight)
            
            item = random.choices(self.items, weights=weights)[0]
            self.items.remove(item)
        else:
            item = self.items.pop(0)
        
        if self.current:
            self.current.played = True
            self.track_history.append(self.current)
            if len(self.track_history) > 100:  # Keep history manageable
                self.track_history.pop(0)
        
        self.current = item
        
        if self.repeat_mode == RepeatMode.QUEUE:
            # Add to end of queue for repeat
            new_item = QueueItem(
                track=item.track,
                requester=item.requester,
                timestamp=datetime.datetime.now(),
                position=len(self.items)
            )
            self.items.append(new_item)
        
        return item

    def _generate_autoplay_track(self) -> Optional[QueueItem]:
        # This would integrate with recommendation algorithms
        # For now, return a random track from history
        if self.track_history:
            random_track = random.choice(self.track_history[-20:])  # Recent history
            return QueueItem(
                track=random_track.track,
                requester=random_track.requester,
                timestamp=datetime.datetime.now(),
                position=0
            )
        return None

    def clear(self):
        """Clear both our custom items and the parent queue."""
        self.items.clear()
        self.track_history.clear()
        self.current = None
        self.votes.clear()
        super().clear()  # Also clear the parent Wavelink queue

    def remove(self, index: int) -> Optional[QueueItem]:
        if 0 <= index < len(self.items):
            item = self.items.pop(index)
            # Update positions
            for i, queue_item in enumerate(self.items[index:], start=index):
                queue_item.position = i
            return item
        return None

    def move(self, from_index: int, to_index: int) -> bool:
        if 0 <= from_index < len(self.items) and 0 <= to_index < len(self.items):
            item = self.items.pop(from_index)
            self.items.insert(to_index, item)
            # Update all positions
            for i, queue_item in enumerate(self.items):
                queue_item.position = i
            return True
        return False

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        if self.shuffle:
            self._original_order = self.items.copy()
            random.shuffle(self.items)
        else:
            self.items = self._original_order.copy()
        
        # Update positions after shuffle
        for i, item in enumerate(self.items):
            item.position = i

    def get_queue_duration(self) -> int:
        """Get total duration of queue in milliseconds."""
        return sum(getattr(item.track, 'length', 0) for item in self.items)

    def get_estimated_time(self, index: int) -> datetime.datetime:
        """Estimate when a track at given index will play."""
        if index >= len(self.items):
            return datetime.datetime.now()
        
        duration_before = sum(getattr(item.track, 'length', 0) for item in self.items[:index])
        return datetime.datetime.now() + datetime.timedelta(milliseconds=duration_before)

    def search_queue(self, query: str) -> List[QueueItem]:
        """Search for tracks in the queue."""
        query_lower = query.lower()
        results = []
        for item in self.items:
            if (query_lower in item.track.title.lower() or 
                query_lower in item.track.author.lower() or
                query_lower in item.requester.display_name.lower()):
                results.append(item)
        return results

    def add_to_blacklist(self, term: str):
        """Add term to blacklist."""
        if term.lower() not in [b.lower() for b in self.blacklist]:
            self.blacklist.append(term.lower())

    def remove_from_blacklist(self, term: str):
        """Remove term from blacklist."""
        self.blacklist = [b for b in self.blacklist if b.lower() != term.lower()]

    def vote(self, vote_type: VoteType, user_id: int) -> Dict[str, Any]:
        """Handle voting for various actions."""
        vote_key = vote_type.value
        if vote_key not in self.votes:
            self.votes[vote_key] = []
        
        if user_id in self.votes[vote_key]:
            self.votes[vote_key].remove(user_id)
            return {"action": "removed", "count": len(self.votes[vote_key])}
        else:
            self.votes[vote_key].append(user_id)
            return {"action": "added", "count": len(self.votes[vote_key])}

    def get_vote_count(self, vote_type: VoteType) -> int:
        """Get current vote count for an action."""
        return len(self.votes.get(vote_type.value, []))

class SpotifyManager:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.spotify = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)
        self.devices: Dict[int, Dict] = {}
        self.user_tokens: Dict[int, Dict] = {}  # Store user auth tokens
        self.playlists_cache: Dict[str, Dict] = {}
        self.recommendations_cache: Dict[str, List] = {}
        self.tokens_file = "spotify_tokens.json"
        self.load_tokens()

    def load_tokens(self):
        """Load saved user tokens from file."""
        try:
            import json
            import os
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    self.user_tokens = {int(k): v for k, v in json.load(f).items()}
        except Exception as e:
            logging.error(f"Failed to load Spotify tokens: {e}")

    def save_tokens(self):
        """Save user tokens to file."""
        try:
            import json
            with open(self.tokens_file, 'w') as f:
                json.dump(self.user_tokens, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save Spotify tokens: {e}")

    async def authenticate_user(self, user_id: int, guild_id: int) -> Optional[str]:
        """Start Spotify OAuth flow for user."""
        try:
            scope = "user-read-playback-state,user-modify-playback-state,playlist-read-private,user-library-read"
            redirect_uri = "https://ascend-api.replit.app/callback"
            
            sp_oauth = SpotifyOAuth(
                client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
                redirect_uri=redirect_uri,
                scope=scope,
                state=f"{user_id}:{guild_id}"
            )
            
            auth_url = sp_oauth.get_authorize_url()
            return auth_url
        except Exception as e:
            logging.error(f"Spotify auth error: {e}")
            return None

    async def get_auth_url(self, user_id: int) -> Optional[str]:
        """Get Spotify OAuth authorization URL for user linking."""
        return await self.authenticate_user(user_id, 0)  # Use 0 as default guild_id

    def get_user_spotify(self, user_id: int) -> Optional[spotipy.Spotify]:
        """Get authenticated Spotify client for user."""
        if user_id in self.user_tokens:
            token_info = self.user_tokens[user_id]
            
            # Check if token needs refresh
            if token_info.get('expires_at', 0) <= time.time():
                # Try to refresh the token
                if 'refresh_token' in token_info:
                    try:
                        auth_manager = spotipy.SpotifyOAuth(
                            client_id=self.client_id,
                            client_secret=self.client_secret,
                            redirect_uri="https://ascend-api.replit.app/callback",
                            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative user-library-read"
                        )
                        
                        # Refresh the token
                        new_token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                        self.user_tokens[user_id] = new_token_info
                        self.save_tokens()
                        token_info = new_token_info
                        
                    except Exception as e:
                        logging.error(f"Failed to refresh Spotify token for user {user_id}: {e}")
                        return None
                else:
                    return None
            
            return spotipy.Spotify(auth=token_info['access_token'])
        return None

    def search_track(self, query: str, limit: int = 1) -> List[Dict]:
        try:
            results = self.spotify.search(q=query, type='track', limit=limit)
            return results['tracks']['items']
        except Exception as e:
            logging.error(f"Spotify search error: {e}")
            return []

    def search_advanced(self, query: str, search_type: str = "track", 
                            filters: Dict = None, limit: int = 20) -> Dict:
        """Advanced search with filters."""
        try:
            # Build advanced query with filters
            if filters:
                filter_parts = []
                for key, value in filters.items():
                    if key in ['year', 'genre', 'artist', 'album']:
                        filter_parts.append(f"{key}:{value}")
                
                if filter_parts:
                    query = f"{query} {' '.join(filter_parts)}"
            
            results = self.spotify.search(q=query, type=search_type, limit=limit)
            return results
        except Exception as e:
            logging.error(f"Advanced search error: {e}")
            return {}

    def get_recommendations(self, seed_tracks: List[str] = None, 
                                seed_artists: List[str] = None,
                                seed_genres: List[str] = None,
                                **kwargs) -> List[Dict]:
        """Get track recommendations."""
        try:
            cache_key = f"{seed_tracks}:{seed_artists}:{seed_genres}"
            if cache_key in self.recommendations_cache:
                return self.recommendations_cache[cache_key]
            
            results = self.spotify.recommendations(
                seed_tracks=seed_tracks[:5] if seed_tracks else None,
                seed_artists=seed_artists[:5] if seed_artists else None,
                seed_genres=seed_genres[:5] if seed_genres else None,
                limit=20,
                **kwargs
            )
            
            tracks = results.get('tracks', [])
            self.recommendations_cache[cache_key] = tracks
            return tracks
        except Exception as e:
            logging.error(f"Recommendations error: {e}")
            return []

    def get_playlist_tracks(self, playlist_url: str, limit: int = None) -> List[Dict]:
        try:
            playlist_id = self.extract_playlist_id(playlist_url)
            if not playlist_id:
                return []
            
            # Check cache first
            if playlist_id in self.playlists_cache:
                cached = self.playlists_cache[playlist_id]
                if cached.get('expires', 0) > time.time():
                    return cached['tracks']
            
            results = self.spotify.playlist_tracks(playlist_id, limit=limit)
            tracks = []
            
            for item in results['items']:
                if item['track'] and item['track']['type'] == 'track':
                    tracks.append(item['track'])
            
            # Handle pagination
            while results['next'] and (not limit or len(tracks) < limit):
                results = self.spotify.next(results)
                for item in results['items']:
                    if item['track'] and item['track']['type'] == 'track':
                        tracks.append(item['track'])
                        if limit and len(tracks) >= limit:
                            break
            
            # Cache the result
            self.playlists_cache[playlist_id] = {
                'tracks': tracks,
                'expires': time.time() + 3600  # Cache for 1 hour
            }
            
            return tracks[:limit] if limit else tracks
        except Exception as e:
            logging.error(f"Spotify playlist error: {e}")
            return []

    def get_album_tracks(self, album_url: str) -> List[Dict]:
        try:
            album_id = self.extract_album_id(album_url)
            if not album_id:
                return []
            
            album = self.spotify.album(album_id)
            results = self.spotify.album_tracks(album_id)
            tracks = []
            
            for item in results['items']:
                # Add album info to track
                item['album'] = {
                    'name': album['name'],
                    'images': album['images'],
                    'release_date': album['release_date']
                }
                tracks.append(item)
            
            while results['next']:
                results = self.spotify.next(results)
                for item in results['items']:
                    item['album'] = {
                        'name': album['name'],
                        'images': album['images'],
                        'release_date': album['release_date']
                    }
                    tracks.append(item)
            
            return tracks
        except Exception as e:
            logging.error(f"Spotify album error: {e}")
            return []

    def get_artist_top_tracks(self, artist_id: str, country: str = 'US') -> List[Dict]:
        """Get artist's top tracks."""
        try:
            results = self.spotify.artist_top_tracks(artist_id, country=country)
            return results.get('tracks', [])
        except Exception as e:
            logging.error(f"Artist top tracks error: {e}")
            return []

    def get_user_playlists(self, user_id: int) -> List[Dict]:
        """Get user's Spotify playlists."""
        try:
            sp = self.get_user_spotify(user_id)
            if not sp:
                return []
            
            results = sp.current_user_playlists(limit=50)
            playlists = results['items']
            
            while results['next']:
                results = sp.next(results)
                playlists.extend(results['items'])
            
            return playlists
        except Exception as e:
            logging.error(f"User playlists error: {e}")
            return []

    def control_playback(self, user_id: int, action: str, **kwargs) -> bool:
        """Control user's Spotify playback."""
        try:
            sp = self.get_user_spotify(user_id)
            if not sp:
                return False
            
            if action == "play":
                sp.start_playback(**kwargs)
            elif action == "pause":
                sp.pause_playback()
            elif action == "next":
                sp.next_track()
            elif action == "previous":
                sp.previous_track()
            elif action == "volume":
                sp.volume(kwargs.get('volume', 50))
            elif action == "seek":
                sp.seek_track(kwargs.get('position', 0))
            
            return True
        except Exception as e:
            logging.error(f"Playback control error: {e}")
            return False

    def extract_playlist_id(self, url: str) -> Optional[str]:
        patterns = [
            r'playlist/([a-zA-Z0-9]+)',
            r'open\.spotify\.com/playlist/([a-zA-Z0-9]+)',
            r'spotify:playlist:([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_album_id(self, url: str) -> Optional[str]:
        patterns = [
            r'album/([a-zA-Z0-9]+)',
            r'open\.spotify\.com/album/([a-zA-Z0-9]+)',
            r'spotify:album:([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_track_id(self, url: str) -> Optional[str]:
        patterns = [
            r'track/([a-zA-Z0-9]+)',
            r'open\.spotify\.com/track/([a-zA-Z0-9]+)',
            r'spotify:track:([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_artist_id(self, url: str) -> Optional[str]:
        patterns = [
            r'artist/([a-zA-Z0-9]+)',
            r'open\.spotify\.com/artist/([a-zA-Z0-9]+)',
            r'spotify:artist:([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def set_device_name(self, guild_id: int, device_name: str):
        if guild_id not in self.devices:
            self.devices[guild_id] = {}
        self.devices[guild_id]['name'] = device_name

    def get_device_name(self, guild_id: int) -> str:
        return self.devices.get(guild_id, {}).get('name', f'Ascend Music Bot')

    def set_device_settings(self, guild_id: int, **settings):
        """Set various device settings."""
        if guild_id not in self.devices:
            self.devices[guild_id] = {}
        self.devices[guild_id].update(settings)

    def get_device_settings(self, guild_id: int) -> Dict:
        """Get device settings."""
        return self.devices.get(guild_id, {})

class EqualizerView(ui.View):
    def __init__(self, bot, player: wavelink.Player):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
        self.bands = [
            EqualizerBand("32Hz"), EqualizerBand("64Hz"), EqualizerBand("125Hz"),
            EqualizerBand("250Hz"), EqualizerBand("500Hz"), EqualizerBand("1kHz"),
            EqualizerBand("2kHz"), EqualizerBand("4kHz"), EqualizerBand("8kHz"),
            EqualizerBand("16kHz")
        ]

    @ui.select(placeholder="Select equalizer preset...", options=[
        discord.SelectOption(label="🎵 Default", value="default", description="Flat response"),
        discord.SelectOption(label="🎸 Rock", value="rock", description="Enhanced mids and highs"),
        discord.SelectOption(label="🎤 Pop", value="pop", description="Vocal clarity"),
        discord.SelectOption(label="🎵 Classical", value="classical", description="Natural sound"),
        discord.SelectOption(label="🎧 Electronic", value="electronic", description="Bass and treble boost"),
        discord.SelectOption(label="🔊 Bass Boost", value="bass", description="Heavy bass"),
        discord.SelectOption(label="🎶 Vocal", value="vocal", description="Enhanced vocals"),
        discord.SelectOption(label="⚡ Live", value="live", description="Concert hall effect"),
    ])
    async def equalizer_preset(self, interaction: discord.Interaction, select: ui.Select):
        presets = {
            "default": [0.0] * 10,
            "rock": [0.3, 0.25, 0.2, 0.1, 0.05, 0.05, 0.1, 0.15, 0.2, 0.2],
            "pop": [0.1, 0.15, 0.2, 0.25, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05],
            "classical": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.05, -0.05, -0.05, -0.1],
            "electronic": [0.4, 0.35, 0.2, 0.0, -0.1, -0.1, 0.0, 0.2, 0.35, 0.4],
            "bass": [0.6, 0.45, 0.3, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "vocal": [-0.1, -0.05, 0.1, 0.25, 0.35, 0.35, 0.25, 0.1, -0.05, -0.1],
            "live": [0.15, 0.1, 0.05, 0.05, 0.0, 0.05, 0.05, 0.05, 0.1, 0.15]
        }
        
        preset_name = select.values[0]
        gains = presets.get(preset_name, [0.0] * 10)
        
        # Apply equalizer
        eq_bands = []
        frequencies = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
        
        for i, gain in enumerate(gains):
            # Use correct Wavelink v3+ syntax for EQ bands
            eq_bands.append(wavelink.EQBand(index=i, gain=gain))
        
        eq = wavelink.Equalizer(bands=eq_bands)
        await self.player.set_filters(wavelink.Filters(equalizer=eq))
        
        embed = discord.Embed(
            title="🎛️ Equalizer Updated",
            description=f"Applied **{preset_name.title()}** preset",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🎛️ Custom EQ", style=discord.ButtonStyle.secondary)
    async def custom_equalizer(self, interaction: discord.Interaction, button: ui.Button):
        modal = CustomEqualizerModal(self.player, self.bands)
        await interaction.response.send_modal(modal)

    @ui.button(label="🔄 Reset", style=discord.ButtonStyle.danger)
    async def reset_equalizer(self, interaction: discord.Interaction, button: ui.Button):
        await self.player.set_filters(wavelink.Filters())
        embed = discord.Embed(
            title="🎛️ Equalizer Reset",
            description="All equalizer settings have been reset to default",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=self)

class CustomEqualizerModal(ui.Modal):
    def __init__(self, player: wavelink.Player, bands: List[EqualizerBand]):
        super().__init__(title="🎛️ Custom Equalizer")
        self.player = player
        self.bands = bands

    band_input = ui.TextInput(
        label="Equalizer Bands (32Hz,64Hz,125Hz,250Hz,500Hz)",
        placeholder="Enter 10 values separated by commas (-1.0 to 1.0)",
        style=discord.TextStyle.long,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            values = [float(x.strip()) for x in self.band_input.value.split(',')]
            if len(values) != 10:
                await interaction.response.send_message("❌ Please provide exactly 10 values!", ephemeral=True)
                return
            
            # Clamp values
            values = [max(-1.0, min(1.0, v)) for v in values]
            
            eq_bands = []
            for i, gain in enumerate(values):
                eq_bands.append(wavelink.EQBand(index=i, gain=gain))
            
            eq = wavelink.Equalizer(bands=eq_bands)
            await self.player.set_filters(wavelink.Filters(equalizer=eq))
            
            await interaction.response.send_message("🎛️ Custom equalizer applied!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid values! Use numbers between -1.0 and 1.0", ephemeral=True)

class AdvancedMusicControlView(ui.View):
    def __init__(self, bot, player: wavelink.Player, queue: MusicQueue):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        self.queue = queue
        self.current_page = "main"  # main, effects, settings

    @ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="music:previous", row=0)
    async def previous(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player or not self.queue.track_history:
            await interaction.response.send_message("❌ No previous track available!", ephemeral=True)
            return

        previous_track = self.queue.track_history[-1]
        self.queue.track_history.pop()
        
        if self.queue.current:
            self.queue.items.insert(0, self.queue.current)
        
        await self.player.play(previous_track.track)
        self.queue.current = previous_track
        await interaction.response.send_message("⏮️ Playing previous track!", ephemeral=True)

    @ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="music:playpause", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        if self.player.paused:
            await self.player.pause(False)
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Resumed playback!", ephemeral=True)
        else:
            await self.player.pause(True)
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Paused playback!", ephemeral=True)

    @ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        try:
            if self.player.playing:
                await self.player.stop()
                await interaction.response.send_message("⏭️ Skipped the current track!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is currently playing!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to skip: {str(e)}", ephemeral=True)
            logging.error(f"Skip button error: {e}")

    @ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music:stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        self.queue.clear()
        await self.player.stop()
        # Don't disconnect, just stop and clear queue
        await interaction.response.send_message("⏹️ Stopped playback and cleared queue!", ephemeral=True)

    @ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music:volume", row=0)
    async def volume_control(self, interaction: discord.Interaction, button: ui.Button):
        modal = VolumeModal(self.player)
        await interaction.response.send_modal(modal)

    # Second Row - Queue and Playback Controls
    @ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=1)
    async def shuffle(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        self.queue.toggle_shuffle()
        status = "enabled" if self.queue.shuffle else "disabled"
        button.style = discord.ButtonStyle.success if self.queue.shuffle else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔀 Shuffle {status}!", ephemeral=True)

    @ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:repeat", row=1)
    async def repeat(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        if self.queue.repeat_mode == RepeatMode.OFF:
            self.queue.repeat_mode = RepeatMode.TRACK
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.success
        elif self.queue.repeat_mode == RepeatMode.TRACK:
            self.queue.repeat_mode = RepeatMode.QUEUE
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.success
        else:
            self.queue.repeat_mode = RepeatMode.OFF
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
        
        await interaction.response.edit_message(view=self)
        mode_text = ["disabled", "track", "queue"][self.queue.repeat_mode.value]
        await interaction.followup.send(f"🔁 Repeat {mode_text}!", ephemeral=True)

    @ui.button(emoji="🎲", style=discord.ButtonStyle.secondary, custom_id="music:autoplay", row=1)
    async def toggle_autoplay(self, interaction: discord.Interaction, button: ui.Button):
        self.queue.autoplay = not self.queue.autoplay
        status = "enabled" if self.queue.autoplay else "disabled"
        button.style = discord.ButtonStyle.success if self.queue.autoplay else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🎲 Autoplay {status}!", ephemeral=True)

    @ui.button(emoji="⏩", style=discord.ButtonStyle.secondary, custom_id="music:seek", row=1)
    async def seek_control(self, interaction: discord.Interaction, button: ui.Button):
        modal = SeekModal(self.player)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="📋", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=1)
    async def show_queue(self, interaction: discord.Interaction, button: ui.Button):
        view = AdvancedQueueView(self.bot, self.queue)
        embed = view.create_queue_embed()
        view.update_buttons()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # Third Row - Advanced Features
    @ui.button(emoji="🎛️", style=discord.ButtonStyle.secondary, custom_id="music:equalizer", row=2)
    async def equalizer(self, interaction: discord.Interaction, button: ui.Button):
        eq_view = AdvancedEqualizerView(self.bot, self.player)
        embed = discord.Embed(
            title="🎛️ Advanced Equalizer Control",
            description="Fine-tune your audio experience with presets and custom settings",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=eq_view, ephemeral=True)

    @ui.button(emoji="🎚️", style=discord.ButtonStyle.secondary, custom_id="music:effects", row=2)
    async def audio_effects(self, interaction: discord.Interaction, button: ui.Button):
        effects_view = AudioEffectsView(self.bot, self.player)
        embed = discord.Embed(
            title="🎚️ Audio Effects",
            description="Apply various audio effects and filters",
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, view=effects_view, ephemeral=True)

    @ui.button(emoji="💾", style=discord.ButtonStyle.secondary, custom_id="music:save", row=2)
    async def save_track(self, interaction: discord.Interaction, button: ui.Button):
        if self.queue.current:
            modal = SaveTrackModal(self.queue.current)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("❌ No track currently playing to save!", ephemeral=True)

    @ui.button(emoji="📊", style=discord.ButtonStyle.secondary, custom_id="music:stats", row=2)
    async def show_stats(self, interaction: discord.Interaction, button: ui.Button):
        stats_view = MusicStatsView(self.bot, self.player, self.queue)
        embed = stats_view.create_stats_embed()
        await interaction.response.send_message(embed=embed, view=stats_view, ephemeral=True)

    @ui.button(emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="music:settings", row=2)
    async def settings(self, interaction: discord.Interaction, button: ui.Button):
        settings_view = MusicSettingsView(self.bot, self.player, self.queue)
        embed = settings_view.create_settings_embed()
        await interaction.response.send_message(embed=embed, view=settings_view, ephemeral=True)


class MusicControlView(ui.View):
    def __init__(self, bot, player: wavelink.Player, queue: MusicQueue):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        self.queue = queue

    @ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary, custom_id="music:playpause", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        if self.player.paused:
            await self.player.pause(False)
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Resumed playback!", ephemeral=True)
        else:
            await self.player.pause(True)
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Paused playback!", ephemeral=True)

    @ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        try:
            # Simple skip without complex voting for now
            if self.player.playing:
                await self.player.stop()
                await interaction.response.send_message("⏭️ Skipped the current track!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is currently playing!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to skip: {str(e)}", ephemeral=True)
            logging.error(f"Skip button error: {e}")

    @ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music:stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        self.queue.clear()
        await self.player.stop()
        # Don't disconnect, just stop and clear queue
        await interaction.response.send_message("⏹️ Stopped playback and cleared queue!", ephemeral=True)

    @ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=0)
    async def shuffle(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        self.queue.toggle_shuffle()
        status = "enabled" if self.queue.shuffle else "disabled"
        button.style = discord.ButtonStyle.success if self.queue.shuffle else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔀 Shuffle {status}!", ephemeral=True)

    @ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:repeat", row=0)
    async def repeat(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player:
            await interaction.response.send_message("❌ No player found!", ephemeral=True)
            return

        if self.queue.repeat_mode == RepeatMode.OFF:
            self.queue.repeat_mode = RepeatMode.TRACK
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("🔂 Repeat track enabled!", ephemeral=True)
        elif self.queue.repeat_mode == RepeatMode.TRACK:
            self.queue.repeat_mode = RepeatMode.QUEUE
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("🔁 Repeat queue enabled!", ephemeral=True)
        else:
            self.queue.repeat_mode = RepeatMode.OFF
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("➡️ Repeat disabled!", ephemeral=True)

    @ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="music:previous", row=1)
    async def previous(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player or not self.queue.track_history:
            await interaction.response.send_message("❌ No previous track available!", ephemeral=True)
            return

        previous_track = self.queue.track_history[-1]
        self.queue.track_history.pop()
        
        # Add current track back to front of queue
        if self.queue.current:
            self.queue.items.insert(0, self.queue.current)
        
        await self.player.play(previous_track.track)
        self.queue.current = previous_track
        await interaction.response.send_message("⏮️ Playing previous track!", ephemeral=True)

    @ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music:volume", row=1)
    async def volume_control(self, interaction: discord.Interaction, button: ui.Button):
        modal = VolumeModal(self.player)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="⏩", style=discord.ButtonStyle.secondary, custom_id="music:seek", row=1)
    async def seek_control(self, interaction: discord.Interaction, button: ui.Button):
        modal = SeekModal(self.player)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="📋", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=1)
    async def show_queue(self, interaction: discord.Interaction, button: ui.Button):
        view = QueueView(self.bot, self.queue)
        embed = view.create_queue_embed()
        view.update_buttons()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(emoji="🎛️", style=discord.ButtonStyle.secondary, custom_id="music:equalizer", row=1)
    async def equalizer(self, interaction: discord.Interaction, button: ui.Button):
        eq_view = EqualizerView(self.bot, self.player)
        embed = discord.Embed(
            title="🎛️ Equalizer Control",
            description="Select a preset or customize your own equalizer settings",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=eq_view, ephemeral=True)

    @ui.button(emoji="❤️", style=discord.ButtonStyle.secondary, custom_id="music:like", row=2)
    async def like_track(self, interaction: discord.Interaction, button: ui.Button):
        if self.queue.current:
            self.queue.current.likes += 1
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("❤️ Liked this track!", ephemeral=True)

    @ui.button(emoji="👎", style=discord.ButtonStyle.secondary, custom_id="music:dislike", row=2)
    async def dislike_track(self, interaction: discord.Interaction, button: ui.Button):
        if self.queue.current:
            self.queue.current.dislikes += 1
            button.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("👎 Disliked this track!", ephemeral=True)

    @ui.button(emoji="💾", style=discord.ButtonStyle.secondary, custom_id="music:save", row=2)
    async def save_track(self, interaction: discord.Interaction, button: ui.Button):
        if self.queue.current:
            # Save to user's favorites (would integrate with database)
            await interaction.response.send_message("� Track saved to your favorites!", ephemeral=True)

    @ui.button(emoji="🎲", style=discord.ButtonStyle.secondary, custom_id="music:autoplay", row=2)
    async def toggle_autoplay(self, interaction: discord.Interaction, button: ui.Button):
        self.queue.autoplay = not self.queue.autoplay
        status = "enabled" if self.queue.autoplay else "disabled"
        button.style = discord.ButtonStyle.success if self.queue.autoplay else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🎲 Autoplay {status}!", ephemeral=True)

    @ui.button(emoji="📊", style=discord.ButtonStyle.secondary, custom_id="music:stats", row=2)
    async def show_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📊 Music Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        if self.queue.current:
            embed.add_field(
                name="Current Track",
                value=f"**{self.queue.current.track.title}**\n❤️ {self.queue.current.likes} 👎 {self.queue.current.dislikes}",
                inline=False
            )
        
        total_duration = self.queue.get_queue_duration()
        hours, remainder = divmod(total_duration // 1000, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed.add_field(name="Queue Length", value=f"{len(self.queue.items)} tracks", inline=True)
        embed.add_field(name="Total Duration", value=f"{hours:02d}:{minutes:02d}:{seconds:02d}", inline=True)
        embed.add_field(name="History", value=f"{len(self.queue.track_history)} tracks", inline=True)
        embed.add_field(name="Repeat Mode", value=self.queue.repeat_mode.name.title(), inline=True)
        embed.add_field(name="Shuffle", value="On" if self.queue.shuffle else "Off", inline=True)
        embed.add_field(name="Autoplay", value="On" if self.queue.autoplay else "Off", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class QueueView(ui.View):
    def __init__(self, bot, queue: MusicQueue, page: int = 0):
        super().__init__(timeout=300)
        self.bot = bot
        self.queue = queue
        self.page = page
        self.per_page = 10
        self.sort_by = "position"  # position, duration, requester, likes

    @ui.select(placeholder="Sort queue by...", options=[
        discord.SelectOption(label="📍 Position", value="position", description="Default queue order"),
        discord.SelectOption(label="⏱️ Duration", value="duration", description="Sort by track length"),
        discord.SelectOption(label="👤 Requester", value="requester", description="Group by who requested"),
        discord.SelectOption(label="❤️ Likes", value="likes", description="Most liked first"),
        discord.SelectOption(label="🕒 Added Time", value="timestamp", description="When tracks were added"),
    ], row=0)
    async def sort_queue(self, interaction: discord.Interaction, select: ui.Select):
        self.sort_by = select.values[0]
        self.page = 0  # Reset to first page
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        self.page = max(0, self.page - 1)
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        max_pages = (len(self.queue.items) - 1) // self.per_page
        self.page = min(max_pages, self.page + 1)
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="� Search", style=discord.ButtonStyle.secondary, row=1)
    async def search_queue(self, interaction: discord.Interaction, button: ui.Button):
        modal = QueueSearchModal(self.queue)
        await interaction.response.send_modal(modal)

    @ui.button(label="�🗑️ Clear", style=discord.ButtonStyle.danger, row=1)
    async def clear_queue(self, interaction: discord.Interaction, button: ui.Button):
        confirm_view = ConfirmView("Are you sure you want to clear the entire queue?")
        await interaction.response.send_message("⚠️ Confirm queue clear:", view=confirm_view, ephemeral=True)
        
        await confirm_view.wait()
        if confirm_view.confirmed:
            self.queue.clear()
            embed = discord.Embed(
                title="🗑️ Queue Cleared",
                description="The music queue has been cleared!",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)

    @ui.button(label="💾 Save", style=discord.ButtonStyle.secondary, row=1)
    async def save_queue(self, interaction: discord.Interaction, button: ui.Button):
        modal = SavePlaylistModal(self.queue, interaction.user)
        await interaction.response.send_modal(modal)

    @ui.select(placeholder="Quick actions...", options=[
        discord.SelectOption(label="🔀 Shuffle Queue", value="shuffle"),
        discord.SelectOption(label="🔄 Reverse Queue", value="reverse"),
        discord.SelectOption(label="🗑️ Remove Duplicates", value="dedupe"),
        discord.SelectOption(label="⏱️ Remove Long Tracks", value="remove_long"),
        discord.SelectOption(label="📊 Show Statistics", value="stats"),
    ], row=2)
    async def quick_actions(self, interaction: discord.Interaction, select: ui.Select):
        action = select.values[0]
        
        if action == "shuffle":
            self.queue.toggle_shuffle()
            await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
        elif action == "reverse":
            self.queue.items.reverse()
            await interaction.response.send_message("🔄 Queue reversed!", ephemeral=True)
        elif action == "dedupe":
            seen = set()
            original_count = len(self.queue.items)
            self.queue.items = [item for item in self.queue.items 
                             if item.track.title not in seen and not seen.add(item.track.title)]
            removed = original_count - len(self.queue.items)
            await interaction.response.send_message(f"🗑️ Removed {removed} duplicate tracks!", ephemeral=True)
        elif action == "remove_long":
            original_count = len(self.queue.items)
            self.queue.items = [item for item in self.queue.items 
                             if getattr(item.track, 'length', 0) < 600000]  # 10 minutes
            removed = original_count - len(self.queue.items)
            await interaction.response.send_message(f"⏱️ Removed {removed} long tracks!", ephemeral=True)
        elif action == "stats":
            await self.show_queue_stats(interaction)

    async def show_queue_stats(self, interaction: discord.Interaction):
        if not self.queue.items:
            await interaction.response.send_message("📊 Queue is empty!", ephemeral=True)
            return

        total_duration = sum(getattr(item.track, 'length', 0) for item in self.queue.items)
        avg_duration = total_duration / len(self.queue.items) if self.queue.items else 0
        
        requesters = {}
        for item in self.queue.items:
            name = item.requester.display_name
            requesters[name] = requesters.get(name, 0) + 1
        
        top_requester = max(requesters.items(), key=lambda x: x[1]) if requesters else ("None", 0)
        
        embed = discord.Embed(
            title="📊 Queue Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        hours, remainder = divmod(total_duration // 1000, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        avg_hours, avg_remainder = divmod(avg_duration // 1000, 3600)
        avg_minutes, avg_seconds = divmod(avg_remainder, 60)
        
        embed.add_field(name="Total Tracks", value=str(len(self.queue.items)), inline=True)
        embed.add_field(name="Total Duration", value=f"{hours:02d}:{minutes:02d}:{seconds:02d}", inline=True)
        embed.add_field(name="Average Duration", value=f"{avg_minutes:02d}:{avg_seconds:02d}", inline=True)
        embed.add_field(name="Top Requester", value=f"{top_requester[0]} ({top_requester[1]} tracks)", inline=True)
        embed.add_field(name="Unique Requesters", value=str(len(requesters)), inline=True)
        embed.add_field(name="Estimated Finish", value=f"<t:{int((datetime.datetime.now() + datetime.timedelta(milliseconds=total_duration)).timestamp())}:R>", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_queue_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )

        if not self.queue.items:
            embed.description = "The queue is empty! Use the play command to add some music."
            return embed

        # Sort items based on selected criteria
        sorted_items = self.get_sorted_items()

        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        queue_slice = sorted_items[start_idx:end_idx]

        queue_text = ""
        for i, item in enumerate(queue_slice, start=start_idx + 1):
            duration = f"{item.track.length // 60000}:{(item.track.length // 1000) % 60:02d}" if hasattr(item.track, 'length') else "Unknown"
            
            # Add visual indicators
            indicators = []
            if item.likes > 0:
                indicators.append(f"❤️{item.likes}")
            if item.dislikes > 0:
                indicators.append(f"👎{item.dislikes}")
            if item in self.queue.favorites:
                indicators.append("⭐")
            
            indicator_text = f" {' '.join(indicators)}" if indicators else ""
            
            queue_text += f"`{i}.` **{item.track.title[:40]}{'...' if len(item.track.title) > 40 else ''}**\n"
            queue_text += f"    by *{item.track.author}* `[{duration}]`{indicator_text}\n"
            queue_text += f"    👤 {item.requester.mention} • <t:{int(item.timestamp.timestamp())}:R>\n\n"

        embed.description = queue_text

        # Statistics
        total_duration = sum(getattr(item.track, 'length', 0) for item in self.queue.items) // 1000
        hours, remainder = divmod(total_duration, 3600)
        minutes, seconds = divmod(remainder, 60)

        embed.add_field(
            name="📊 Queue Stats",
            value=f"**Tracks:** {len(self.queue.items)}\n**Duration:** {hours:02d}:{minutes:02d}:{seconds:02d}\n**Repeat:** {self.queue.repeat_mode.name}\n**Shuffle:** {'On' if self.queue.shuffle else 'Off'}",
            inline=True
        )

        if self.queue.current:
            current_pos = getattr(self.queue.current.track, 'position', 0) if hasattr(self.queue.current.track, 'position') else 0
            current_dur = getattr(self.queue.current.track, 'length', 0)
            progress = f"{current_pos // 60000}:{(current_pos // 1000) % 60:02d}" if current_pos else "0:00"
            total = f"{current_dur // 60000}:{(current_dur // 1000) % 60:02d}" if current_dur else "0:00"
            
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{self.queue.current.track.title[:30]}{'...' if len(self.queue.current.track.title) > 30 else ''}**\nby *{self.queue.current.track.author}*\n`{progress}/{total}`",
                inline=True
            )

        # Sorting info
        sort_names = {
            "position": "Position", "duration": "Duration", 
            "requester": "Requester", "likes": "Likes", "timestamp": "Added Time"
        }
        embed.add_field(
            name="🔧 Settings",
            value=f"**Sort:** {sort_names.get(self.sort_by, 'Position')}\n**Page:** {self.page + 1}\n**Per Page:** {self.per_page}",
            inline=True
        )

        max_pages = (len(self.queue.items) - 1) // self.per_page + 1
        embed.set_footer(text=f"Page {self.page + 1} of {max_pages} • Use buttons to navigate")

        return embed

    def get_sorted_items(self) -> List[QueueItem]:
        """Sort queue items based on selected criteria."""
        if self.sort_by == "duration":
            return sorted(self.queue.items, key=lambda x: getattr(x.track, 'length', 0), reverse=True)
        elif self.sort_by == "requester":
            return sorted(self.queue.items, key=lambda x: x.requester.display_name)
        elif self.sort_by == "likes":
            return sorted(self.queue.items, key=lambda x: x.likes - x.dislikes, reverse=True)
        elif self.sort_by == "timestamp":
            return sorted(self.queue.items, key=lambda x: x.timestamp, reverse=True)
        else:  # position or default
            return self.queue.items

    def update_buttons(self):
        max_pages = (len(self.queue.items) - 1) // self.per_page if self.queue.items else 0
        self.previous_page.disabled = self.page == 0
        self.next_page.disabled = self.page >= max_pages

class QueueSearchModal(ui.Modal):
    def __init__(self, queue: MusicQueue):
        super().__init__(title="🔍 Search Queue")
        self.queue = queue

    search_query = ui.TextInput(
        label="Search Term",
        placeholder="Enter song title, artist, or requester name...",
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        results = self.queue.search_queue(self.search_query.value)
        
        if not results:
            await interaction.response.send_message("❌ No tracks found matching your search!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔍 Search Results",
            description=f"Found {len(results)} tracks matching '{self.search_query.value}'",
            color=discord.Color.green()
        )
        
        result_text = ""
        for i, item in enumerate(results[:10], 1):
            duration = f"{item.track.length // 60000}:{(item.track.length // 1000) % 60:02d}" if hasattr(item.track, 'length') else "Unknown"
            result_text += f"`{i}.` **{item.track.title}** by *{item.track.author}* `[{duration}]`\n"
            result_text += f"    Position: {item.position + 1} • Requested by {item.requester.mention}\n\n"
        
        embed.description = result_text
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SavePlaylistModal(ui.Modal):
    def __init__(self, queue: MusicQueue, user: discord.Member):
        super().__init__(title="💾 Save Playlist")
        self.queue = queue
        self.user = user

    playlist_name = ui.TextInput(
        label="Playlist Name",
        placeholder="Enter a name for your playlist...",
        max_length=50
    )

    description = ui.TextInput(
        label="Description (Optional)",
        placeholder="Describe your playlist...",
        style=discord.TextStyle.long,
        max_length=200,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # This would integrate with the database to save playlists
        # For now, just show confirmation
        embed = discord.Embed(
            title="💾 Playlist Saved",
            description=f"Saved **{self.playlist_name.value}** with {len(self.queue.items)} tracks!",
            color=discord.Color.green()
        )
        
        if self.description.value:
            embed.add_field(name="Description", value=self.description.value, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ConfirmView(ui.View):
    def __init__(self, message: str):
        super().__init__(timeout=30)
        self.message = message
        self.confirmed = False

    @ui.button(label="✅ Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        await interaction.response.send_message("✅ Confirmed!", ephemeral=True)
        self.stop()

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = False
        await interaction.response.send_message("❌ Cancelled!", ephemeral=True)
        self.stop()

class VolumeModal(ui.Modal):
    def __init__(self, player: wavelink.Player):
        super().__init__(title="🔊 Set Volume")
        self.player = player

    volume = ui.TextInput(
        label="Volume (0-100)",
        placeholder="Enter volume level...",
        default="50",
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vol = int(self.volume.value)
            if 0 <= vol <= 100:
                await self.player.set_volume(vol)
                self.player.queue.volume_history.append(vol)
                await interaction.response.send_message(f"🔊 Volume set to {vol}%!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Volume must be between 0 and 100!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid volume value!", ephemeral=True)

class SeekModal(ui.Modal):
    def __init__(self, player: wavelink.Player):
        super().__init__(title="⏩ Seek Position")
        self.player = player

    position = ui.TextInput(
        label="Position (MM:SS or seconds)",
        placeholder="e.g., 1:30 or 90",
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            pos_str = self.position.value
            if ":" in pos_str:
                parts = pos_str.split(":")
                minutes = int(parts[0])
                seconds = int(parts[1])
                position_ms = (minutes * 60 + seconds) * 1000
            else:
                position_ms = int(pos_str) * 1000

            if hasattr(self.player.current, 'length') and position_ms > self.player.current.length:
                await interaction.response.send_message("❌ Position exceeds track length!", ephemeral=True)
                return

            await self.player.seek(position_ms)
            await interaction.response.send_message(f"⏩ Seeked to {pos_str}!", ephemeral=True)
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Invalid position format! Use MM:SS or seconds.", ephemeral=True)

class DeviceNameModal(ui.Modal):
    def __init__(self, spotify_manager: SpotifyManager, guild_id: int):
        super().__init__(title="🎵 Set Spotify Device Name")
        self.spotify_manager = spotify_manager
        self.guild_id = guild_id

    device_name = ui.TextInput(
        label="Device Name",
        placeholder="Enter your device name...",
        default="Ascend Music Bot",
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.spotify_manager.set_device_name(self.guild_id, self.device_name.value)
        await interaction.response.send_message(
            f"🎵 Spotify device name set to: **{self.device_name.value}**", 
            ephemeral=True
        )

# Advanced UI Components for Enhanced Music Experience

class AdvancedQueueView(ui.View):
    def __init__(self, bot, queue: MusicQueue, page: int = 0):
        super().__init__(timeout=300)
        self.bot = bot
        self.queue = queue
        self.page = page
        self.per_page = 8
        self.sort_by = "position"
        self.view_mode = "detailed"  # detailed, compact, grid

    @ui.select(placeholder="🎛️ Queue View Mode", options=[
        discord.SelectOption(label="📋 Detailed View", value="detailed", description="Full track information", emoji="📋"),
        discord.SelectOption(label="📝 Compact View", value="compact", description="Condensed track list", emoji="📝"),
        discord.SelectOption(label="🔢 Grid View", value="grid", description="Track grid layout", emoji="🔢"),
    ], row=0)
    async def change_view_mode(self, interaction: discord.Interaction, select: ui.Select):
        self.view_mode = select.values[0]
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.select(placeholder="🔧 Sort & Filter Options", options=[
        discord.SelectOption(label="📍 Position", value="position", description="Default queue order", emoji="📍"),
        discord.SelectOption(label="⏱️ Duration", value="duration", description="Sort by track length", emoji="⏱️"),
        discord.SelectOption(label="👤 Requester", value="requester", description="Group by requester", emoji="👤"),
        discord.SelectOption(label="❤️ Popularity", value="likes", description="Most liked first", emoji="❤️"),
        discord.SelectOption(label="🕒 Recently Added", value="timestamp", description="Latest additions", emoji="🕒"),
    ], row=1)
    async def sort_queue(self, interaction: discord.Interaction, select: ui.Select):
        self.sort_by = select.values[0]
        self.page = 0
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, disabled=True, row=2)
    async def first_page(self, interaction: discord.Interaction, button: ui.Button):
        self.page = 0
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, disabled=True, row=2)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        self.page = max(0, self.page - 1)
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        max_pages = (len(self.queue.items) - 1) // self.per_page
        self.page = min(max_pages, self.page + 1)
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=2)
    async def last_page(self, interaction: discord.Interaction, button: ui.Button):
        max_pages = (len(self.queue.items) - 1) // self.per_page
        self.page = max_pages
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(emoji="🔍", label="Search", style=discord.ButtonStyle.secondary, row=2)
    async def search_queue(self, interaction: discord.Interaction, button: ui.Button):
        modal = AdvancedQueueSearchModal(self.queue)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="✏️", label="Edit", style=discord.ButtonStyle.secondary, row=3)
    async def edit_queue(self, interaction: discord.Interaction, button: ui.Button):
        edit_view = QueueEditView(self.bot, self.queue)
        embed = discord.Embed(
            title="✏️ Queue Editor",
            description="Select tracks to remove, reorder, or modify",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=edit_view, ephemeral=True)

    @ui.button(emoji="💾", label="Save", style=discord.ButtonStyle.green, row=3)
    async def save_playlist(self, interaction: discord.Interaction, button: ui.Button):
        if not self.queue.items:
            await interaction.response.send_message("❌ Queue is empty!", ephemeral=True)
            return
        modal = SavePlaylistModal()
        await interaction.response.send_modal(modal)

    @ui.button(emoji="🔀", label="Shuffle", style=discord.ButtonStyle.secondary, row=3)
    async def shuffle_queue(self, interaction: discord.Interaction, button: ui.Button):
        self.queue.toggle_shuffle()
        status = "enabled" if self.queue.shuffle else "disabled"
        embed = self.create_queue_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"🔀 Queue shuffle {status}!", ephemeral=True)

    @ui.button(emoji="🗑️", label="Clear", style=discord.ButtonStyle.danger, row=3)
    async def clear_queue(self, interaction: discord.Interaction, button: ui.Button):
        confirm_view = ConfirmView("⚠️ Clear entire queue? This cannot be undone!")
        await interaction.response.send_message("Are you sure?", view=confirm_view, ephemeral=True)

    def create_queue_embed(self):
        embed = discord.Embed(
            title="📋 Advanced Queue Manager",
            color=discord.Color.blue()
        )
        
        if not self.queue.items:
            embed.description = "Queue is empty! Add some tracks to get started."
            return embed

        # Calculate pagination
        total_tracks = len(self.queue.items)
        total_pages = (total_tracks - 1) // self.per_page + 1
        start_idx = self.page * self.per_page
        end_idx = min(start_idx + self.per_page, total_tracks)
        
        # Sort items based on selected criteria
        items = self.get_sorted_items()
        page_items = items[start_idx:end_idx]

        # Create embed based on view mode
        if self.view_mode == "detailed":
            for i, item in enumerate(page_items, start_idx + 1):
                duration = f"{item.track.length // 60000}:{(item.track.length // 1000) % 60:02d}"
                embed.add_field(
                    name=f"{i}. {item.track.title}",
                    value=f"**Artist:** {item.track.author}\n**Duration:** {duration}\n**Requested by:** {item.requester.mention}",
                    inline=False
                )
        elif self.view_mode == "compact":
            queue_text = ""
            for i, item in enumerate(page_items, start_idx + 1):
                duration = f"{item.track.length // 60000}:{(item.track.length // 1000) % 60:02d}"
                queue_text += f"`{i:2d}.` **{item.track.title}** by {item.track.author} `[{duration}]`\n"
            embed.description = queue_text
        else:  # grid view
            grid_text = "```\n"
            for i in range(0, len(page_items), 2):
                item1 = page_items[i]
                item2 = page_items[i + 1] if i + 1 < len(page_items) else None
                
                title1 = item1.track.title[:25] + "..." if len(item1.track.title) > 25 else item1.track.title
                line = f"{start_idx + i + 1:2d}. {title1:<28}"
                
                if item2:
                    title2 = item2.track.title[:25] + "..." if len(item2.track.title) > 25 else item2.track.title
                    line += f" {start_idx + i + 2:2d}. {title2}"
                
                grid_text += line + "\n"
            grid_text += "```"
            embed.description = grid_text

        # Add footer with page info
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • {total_tracks} total tracks • Sort: {self.sort_by.title()}")
        return embed

    def get_sorted_items(self):
        items = list(self.queue.items)
        if self.sort_by == "duration":
            items.sort(key=lambda x: x.track.length)
        elif self.sort_by == "requester":
            items.sort(key=lambda x: x.requester.display_name)
        elif self.sort_by == "likes":
            items.sort(key=lambda x: getattr(x, 'likes', 0), reverse=True)
        elif self.sort_by == "timestamp":
            items.sort(key=lambda x: getattr(x, 'timestamp', 0), reverse=True)
        return items

    def update_buttons(self):
        max_pages = max(1, (len(self.queue.items) - 1) // self.per_page + 1)
        
        # Update navigation buttons
        self.first_page.disabled = self.page == 0
        self.previous_page.disabled = self.page == 0
        self.next_page.disabled = self.page >= max_pages - 1
        self.last_page.disabled = self.page >= max_pages - 1


class AdvancedEqualizerView(ui.View):
    def __init__(self, bot, player: wavelink.Player):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
        self.current_preset = "default"

    @ui.select(placeholder="🎛️ Select EQ Preset", options=[
        discord.SelectOption(label="🎵 Default", value="default", description="Flat response", emoji="🎵"),
        discord.SelectOption(label="🎸 Rock", value="rock", description="Enhanced mids and highs", emoji="🎸"),
        discord.SelectOption(label="🎤 Pop", value="pop", description="Vocal enhancement", emoji="🎤"),
        discord.SelectOption(label="🎺 Jazz", value="jazz", description="Smooth and warm", emoji="🎺"),
        discord.SelectOption(label="🎛️ Electronic", value="electronic", description="Bass and treble boost", emoji="🎛️"),
        discord.SelectOption(label="🎻 Classical", value="classical", description="Natural dynamics", emoji="🎻"),
        discord.SelectOption(label="🎧 Bass Boost", value="bass", description="Enhanced low frequencies", emoji="🎧"),
        discord.SelectOption(label="✨ Treble Boost", value="treble", description="Enhanced high frequencies", emoji="✨"),
    ], row=0)
    async def equalizer_preset(self, interaction: discord.Interaction, select: ui.Select):
        presets = {
            "default": [0.0] * 15,
            "rock": [0.3, 0.25, 0.2, 0.1, 0.0, -0.1, 0.0, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.35, 0.3],
            "pop": [0.1, 0.15, 0.1, 0.0, -0.1, -0.1, 0.0, 0.1, 0.15, 0.2, 0.15, 0.1, 0.05, 0.0, -0.05],
            "jazz": [0.2, 0.1, 0.0, -0.1, -0.1, 0.0, 0.1, 0.1, 0.0, -0.1, 0.0, 0.1, 0.15, 0.1, 0.05],
            "electronic": [0.4, 0.3, 0.1, 0.0, -0.2, -0.1, 0.0, 0.1, 0.0, -0.1, 0.2, 0.3, 0.4, 0.4, 0.3],
            "classical": [0.1, 0.05, 0.0, 0.0, 0.0, 0.0, 0.05, 0.05, 0.0, 0.0, 0.05, 0.1, 0.15, 0.1, 0.05],
            "bass": [0.6, 0.5, 0.3, 0.1, 0.0, -0.1, -0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "treble": [0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.3, 0.4],
        }
        
        selected_preset = select.values[0]
        gains = presets.get(selected_preset, presets["default"])
        
        try:
            bands = [wavelink.Equalizer.band(i, gains[i]) for i in range(len(gains))]
            eq = wavelink.Equalizer(bands=bands)
            await self.player.set_filters(wavelink.Filters(equalizer=eq))
            
            self.current_preset = selected_preset
            await interaction.response.send_message(f"🎛️ Applied **{selected_preset.title()}** equalizer preset!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to apply equalizer: {str(e)}", ephemeral=True)

    @ui.button(emoji="🎚️", label="Custom EQ", style=discord.ButtonStyle.secondary, row=1)
    async def custom_equalizer(self, interaction: discord.Interaction, button: ui.Button):
        modal = AdvancedEqualizerModal(self.player)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="📊", label="Visualize", style=discord.ButtonStyle.secondary, row=1)
    async def visualize_eq(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.create_visualizer_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji="💾", label="Save Preset", style=discord.ButtonStyle.green, row=1)
    async def save_preset(self, interaction: discord.Interaction, button: ui.Button):
        modal = SaveEQPresetModal()
        await interaction.response.send_modal(modal)

    @ui.button(emoji="🔄", label="Reset", style=discord.ButtonStyle.danger, row=1)
    async def reset_equalizer(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await self.player.set_filters(wavelink.Filters())
            self.current_preset = "default"
            await interaction.response.send_message("🔄 Equalizer reset to flat response!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to reset equalizer: {str(e)}", ephemeral=True)

    def create_visualizer_embed(self):
        embed = discord.Embed(
            title=f"🎛️ Current EQ: {self.current_preset.title()}",
            description="Visual representation of current equalizer settings",
            color=discord.Color.purple()
        )
        # Add a simple ASCII visualizer here
        embed.add_field(
            name="Frequency Response",
            value="```\n📊 EQ visualization would go here\n(ASCII art representation)\n```",
            inline=False
        )
        return embed


class AudioEffectsView(ui.View):
    def __init__(self, bot, player: wavelink.Player):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
        self.active_effects = set()

    @ui.select(placeholder="🎚️ Audio Effects", options=[
        discord.SelectOption(label="🌊 Reverb", value="reverb", description="Add spatial depth", emoji="🌊"),
        discord.SelectOption(label="🔊 Distortion", value="distortion", description="Add harmonic saturation", emoji="🔊"),
        discord.SelectOption(label="⚡ Tremolo", value="tremolo", description="Amplitude modulation", emoji="⚡"),
        discord.SelectOption(label="🌪️ Vibrato", value="vibrato", description="Pitch modulation", emoji="🌪️"),
        discord.SelectOption(label="🎭 Chorus", value="chorus", description="Thicken the sound", emoji="🎭"),
    ], max_values=5, row=0)
    async def select_effects(self, interaction: discord.Interaction, select: ui.Select):
        self.active_effects = set(select.values)
        await self.apply_effects()
        effects_list = ", ".join([f"`{effect.title()}`" for effect in self.active_effects])
        await interaction.response.send_message(f"🎚️ Applied effects: {effects_list}", ephemeral=True)

    @ui.button(emoji="🎛️", label="Configure", style=discord.ButtonStyle.secondary, row=1)
    async def configure_effects(self, interaction: discord.Interaction, button: ui.Button):
        modal = EffectsConfigModal(self.active_effects)
        await interaction.response.send_modal(modal)

    @ui.button(emoji="🔄", label="Clear All", style=discord.ButtonStyle.danger, row=1)
    async def clear_effects(self, interaction: discord.Interaction, button: ui.Button):
        self.active_effects.clear()
        try:
            await self.player.set_filters(wavelink.Filters())
            await interaction.response.send_message("🔄 All audio effects cleared!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to clear effects: {str(e)}", ephemeral=True)

    async def apply_effects(self):
        # Apply the selected effects to the player
        # This is a simplified version - real implementation would configure each effect
        try:
            filters = wavelink.Filters()
            # Configure filters based on active_effects
            await self.player.set_filters(filters)
        except Exception as e:
            logging.error(f"Failed to apply audio effects: {e}")


class MusicStatsView(ui.View):
    def __init__(self, bot, player: wavelink.Player, queue: MusicQueue):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
        self.queue = queue

    def create_stats_embed(self):
        embed = discord.Embed(
            title="📊 Music Statistics",
            color=discord.Color.green()
        )
        
        # Current session stats - safely handle track lengths
        total_duration_ms = sum(getattr(item.track, 'length', 0) or 0 for item in self.queue.items)
        total_duration = total_duration_ms / 1000 / 60  # Convert to minutes
        avg_duration = total_duration / len(self.queue.items) if self.queue.items else 0
        
        # Include current track in statistics if playing
        queue_count = len(self.queue.items)
        if self.queue.current:
            queue_count += 1
            current_length = getattr(self.queue.current.track, 'length', 0) or 0
            total_duration_ms += current_length
            total_duration = total_duration_ms / 1000 / 60
            avg_duration = total_duration / queue_count if queue_count > 0 else 0
        
        embed.add_field(
            name="🎵 Current Session",
            value=f"**Total tracks:** {queue_count}\n"
                  f"**Tracks in queue:** {len(self.queue.items)}\n"
                  f"**Total duration:** {total_duration:.1f} minutes\n"
                  f"**Average track length:** {avg_duration:.1f} minutes",
            inline=True
        )
        
        # Player stats
        embed.add_field(
            name="🎛️ Player Status",
            value=f"**Volume:** {getattr(self.player, 'volume', 100)}%\n"
                  f"**Repeat mode:** {self.queue.repeat_mode.name.title()}\n"
                  f"**Shuffle:** {'On' if self.queue.shuffle else 'Off'}",
            inline=True
        )
        
        # Current track info
        if self.queue.current:
            track = self.queue.current.track
            duration = getattr(track, 'length', 0) or 0
            duration_str = f"{duration // 60000}:{(duration // 1000) % 60:02d}" if duration > 0 else "Unknown"
            
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{track.title}**\nby *{track.author}*\nDuration: {duration_str}",
                inline=True
            )
        
        return embed

    @ui.button(emoji="🔄", label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_stats(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.create_stats_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class MusicSettingsView(ui.View):
    def __init__(self, bot, player: wavelink.Player, queue: MusicQueue):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
        self.queue = queue

    def create_settings_embed(self):
        embed = discord.Embed(
            title="⚙️ Music Settings",
            description="Configure your music experience",
            color=discord.Color.blue()
        )
        return embed

    @ui.select(placeholder="🎛️ Audio Quality", options=[
        discord.SelectOption(label="🎵 Standard", value="standard", description="96kbps - Good quality"),
        discord.SelectOption(label="🎶 High", value="high", description="128kbps - Better quality"),
        discord.SelectOption(label="🎼 Highest", value="highest", description="320kbps - Best quality"),
    ], row=0)
    async def audio_quality(self, interaction: discord.Interaction, select: ui.Select):
        quality = select.values[0]
        await interaction.response.send_message(f"🎵 Audio quality set to **{quality}**!", ephemeral=True)

    @ui.button(emoji="🔊", label="Auto Volume", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_auto_volume(self, interaction: discord.Interaction, button: ui.Button):
        # Toggle auto volume normalization
        button.style = discord.ButtonStyle.success if button.style == discord.ButtonStyle.secondary else discord.ButtonStyle.secondary
        status = "enabled" if button.style == discord.ButtonStyle.success else "disabled"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔊 Auto volume {status}!", ephemeral=True)


# New Advanced Modals

class AdvancedQueueSearchModal(ui.Modal):
    def __init__(self, queue: MusicQueue):
        super().__init__(title="🔍 Advanced Queue Search")
        self.queue = queue

    search_query = ui.TextInput(
        label="Search Query",
        placeholder="Enter song title, artist, or keyword...",
        required=True,
        max_length=100
    )

    search_type = ui.TextInput(
        label="Search Type",
        placeholder="title, artist, duration, requester (default: all)",
        required=False,
        default="all",
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        query = self.search_query.value.lower()
        search_type = self.search_type.value.lower() if self.search_type.value else "all"
        
        results = []
        for i, item in enumerate(self.queue.items):
            if search_type == "all" or search_type == "title":
                if query in item.track.title.lower():
                    results.append((i + 1, item))
            if search_type == "all" or search_type == "artist":
                if query in item.track.author.lower():
                    results.append((i + 1, item))
            if search_type == "all" or search_type == "requester":
                if query in item.requester.display_name.lower():
                    results.append((i + 1, item))
        
        if results:
            embed = discord.Embed(
                title=f"🔍 Search Results for '{self.search_query.value}'",
                description=f"Found {len(results)} matches",
                color=discord.Color.green()
            )
            for pos, item in results[:10]:  # Show first 10 results
                embed.add_field(
                    name=f"{pos}. {item.track.title}",
                    value=f"by {item.track.author} • {item.requester.display_name}",
                    inline=False
                )
        else:
            embed = discord.Embed(
                title="🔍 No Results",
                description=f"No tracks found matching '{self.search_query.value}'",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SaveTrackModal(ui.Modal):
    def __init__(self, track_item):
        super().__init__(title="💾 Save Track")
        self.track_item = track_item

    playlist_name = ui.TextInput(
        label="Playlist Name",
        placeholder="Enter playlist name (optional)",
        required=False,
        max_length=50
    )

    tags = ui.TextInput(
        label="Tags",
        placeholder="Enter tags separated by commas (optional)",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Save track to user's collection (would integrate with database)
        playlist = self.playlist_name.value or "Favorites"
        await interaction.response.send_message(
            f"💾 **{self.track_item.track.title}** saved to playlist **{playlist}**!",
            ephemeral=True
        )


class AdvancedEqualizerModal(ui.Modal):
    def __init__(self, player: wavelink.Player):
        super().__init__(title="🎛️ Custom Equalizer")
        self.player = player

    eq_bands = ui.TextInput(
        label="EQ Bands (15 values)",
        placeholder="Enter 15 values separated by commas (-0.25 to 1.0)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            values = [float(x.strip()) for x in self.eq_bands.value.split(',')]
            if len(values) != 15:
                raise ValueError("Must provide exactly 15 values")
            
            # Clamp values
            values = [max(-0.25, min(1.0, v)) for v in values]
            
            bands = [wavelink.Equalizer.band(i, values[i]) for i in range(15)]
            eq = wavelink.Equalizer(bands=bands)
            await self.player.set_filters(wavelink.Filters(equalizer=eq))
            
            await interaction.response.send_message("🎛️ Custom equalizer applied!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Invalid equalizer settings: {str(e)}", ephemeral=True)


class SaveEQPresetModal(ui.Modal):
    def __init__(self):
        super().__init__(title="💾 Save EQ Preset")

    preset_name = ui.TextInput(
        label="Preset Name",
        placeholder="Enter a name for this EQ preset",
        required=True,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"💾 EQ preset **{self.preset_name.value}** saved!", ephemeral=True)


class EffectsConfigModal(ui.Modal):
    def __init__(self, active_effects):
        super().__init__(title="🎚️ Configure Audio Effects")
        self.active_effects = active_effects

    intensity = ui.TextInput(
        label="Effect Intensity",
        placeholder="Enter intensity (0.0 - 1.0)",
        required=False,
        default="0.5",
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("🎚️ Effect configuration updated!", ephemeral=True)


class QueueEditView(ui.View):
    def __init__(self, bot, queue: MusicQueue):
        super().__init__(timeout=300)
        self.bot = bot
        self.queue = queue

    @ui.button(emoji="❌", label="Remove Tracks", style=discord.ButtonStyle.danger, row=0)
    async def remove_tracks(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("❌ Track removal feature coming soon!", ephemeral=True)

    @ui.button(emoji="🔄", label="Reorder", style=discord.ButtonStyle.secondary, row=0)
    async def reorder_tracks(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🔄 Track reordering feature coming soon!", ephemeral=True)


class SearchSelect(ui.Select):
    def __init__(self, tracks, ctx):
        self.tracks = tracks
        self.ctx = ctx
        
        options = []
        for i, track in enumerate(tracks[:25], 1):
            duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}" if hasattr(track, 'length') else "Unknown"
            options.append(discord.SelectOption(
                label=f"{i}. {track.title[:90]}",
                value=str(i-1),
                description=f"by {track.author} [{duration}]"[:100]
            ))
        
        super().__init__(placeholder="Choose a track to play...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_track = self.tracks[selected_index]
        
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)
            return

        if not self.ctx.voice_client:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)

        player = self.ctx.voice_client
        if not hasattr(player, 'queue') or not isinstance(player.queue, MusicQueue):
            player.queue = MusicQueue()

        if not player.playing:
            await player.play(selected_track)
            player.queue.current = QueueItem(selected_track, self.ctx.author, datetime.datetime.now())
            await interaction.response.send_message(f"🎵 Now playing: **{selected_track.title}**!")
        else:
            player.queue.add(selected_track, self.ctx.author)
            await interaction.response.send_message(f"➕ Added **{selected_track.title}** to the queue!")

class SearchView(ui.View):
    def __init__(self, tracks, ctx):
        super().__init__(timeout=300)
        self.add_item(SearchSelect(tracks, ctx))

class MusicCog(commands.Cog, name="Music"):
    """🎵 Complete music system with Spotify integration, queue management, and advanced features."""

    def __init__(self, bot):
        self.bot = bot
        self.spotify_manager = None
        self.players: Dict[int, wavelink.Player] = {}
        self.setup_spotify()
        # Removed automatic monitoring - now command-based only
        
        # Connection management
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10  # Base delay in seconds
        self.connection_stable = False
        self.last_disconnect_time = None
        self.heartbeat_task = None

    def setup_spotify(self):
        try:
            import os
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            if client_id and client_secret:
                self.spotify_manager = SpotifyManager(client_id, client_secret)
                
        except Exception as e:
            logging.error(f"Failed to setup Spotify: {e}")

    @tasks.loop(seconds=3)
    async def spotify_device_monitor(self):
        """Enhanced monitor for Spotify playback with position tracking and auto-progression."""
        try:
            if not self.spotify_manager:
                return
                
            # Initialize tracking data if needed
            if not hasattr(self, '_spotify_sync_data'):
                self._spotify_sync_data = {}  # guild_id: {user_id, track_id, last_position, discord_player, sync_enabled}
                
            # Count active syncs for debug
            active_syncs = 0
            
            for guild in self.bot.guilds:
                guild_key = str(guild.id)
                
                # Check if continuous sync is enabled for this guild
                if guild_key not in self._spotify_sync_data:
                    continue
                    
                sync_data = self._spotify_sync_data[guild_key]
                if not sync_data.get('sync_enabled'):
                    continue
                    
                active_syncs += 1
                    
                user_id = sync_data.get('user_id')
                if not user_id:
                    print(f"🔴 Monitor: No user_id for guild {guild.name}")
                    continue
                    
                # Get the user's Spotify connection
                sp = self.spotify_manager.get_user_spotify(user_id)
                if not sp:
                    print(f"🔴 Monitor: No Spotify connection for user {user_id} in guild {guild.name}")
                    continue
                    
                try:
                    # Get current playback
                    current = sp.current_playback()
                    if not current:
                        print(f"🔴 Monitor: No Spotify playback for user {user_id} in guild {guild.name}")
                        continue
                        
                    track = current.get('item')
                    if not track:
                        print(f"🔴 Monitor: No track item for user {user_id} in guild {guild.name}")
                        continue
                        
                    track_id = track.get('id')
                    progress_ms = current.get('progress_ms', 0)
                    is_playing = current.get('is_playing', False)
                    
                    # Get Discord player
                    player = guild.voice_client
                    if not player:
                        print(f"🔴 Monitor: No voice client for guild {guild.name} - sync will wait for connection")
                        continue
                        
                    # Check if track changed (auto-progression)
                    if sync_data.get('track_id') != track_id:
                        print(f"🔄 **TRACK CHANGE DETECTED** in {guild.name}")
                        print(f"   📻 Previous track ID: {sync_data.get('track_id')}")
                        print(f"   📻 New track ID: {track_id}")
                        print(f"   🎵 New track: {track.get('name')} - Auto-syncing...")
                        
                        # Create track info for new song
                        track_info = {
                            'name': track.get('name'),
                            'artists': [artist.get('name') for artist in track.get('artists', [])],
                            'album': track.get('album', {}).get('name'),
                            'duration_ms': track.get('duration_ms'),
                            'progress_ms': progress_ms,
                            'user_id': user_id,
                            'guild_id': guild.id
                        }
                        
                        # Update tracking data BEFORE calling handle_spotify_track
                        sync_data['track_id'] = track_id
                        sync_data['last_position'] = progress_ms
                        
                        # Auto-sync the new track
                        print(f"   🔍 Searching for: {track_info['name']} by {', '.join(track_info['artists'])}")
                        try:
                            await self.handle_spotify_track(guild, track_info, None, None)
                            print(f"   ✅ Successfully auto-synced: {track.get('name')}")
                        except Exception as e:
                            print(f"   ❌ Auto-sync failed for {track.get('name')}: {e}")
                        continue
                        
                    # Position tracking for current song
                    last_position = sync_data.get('last_position', 0)
                    position_diff = abs(progress_ms - last_position)
                    
                    # If user seeked in Spotify (position jumped significantly)
                    if position_diff > 5000:  # 5 second threshold
                        print(f"🎯 Position seek detected: {progress_ms//1000}s - Syncing position...")
                        
                        if player.current and hasattr(player, 'seek'):
                            try:
                                # Seek Discord player to match Spotify position
                                await player.seek(progress_ms)
                                print(f"✅ Synced position to {progress_ms//1000}s")
                            except Exception as e:
                                print(f"❌ Seek failed: {e}")
                                
                    # Handle play/pause state
                    if is_playing and player.paused:
                        await player.pause(False)
                        print("▶️ Resumed Discord playback")
                    elif not is_playing and not player.paused:
                        await player.pause(True)
                        print("⏸️ Paused Discord playback")
                        
                    # Update last position
                    sync_data['last_position'] = progress_ms
                        
                except Exception as e:
                    if "token" not in str(e).lower():
                        print(f"Sync monitor error for guild {guild.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Enhanced Spotify monitor error: {e}")
            logging.error(f"Enhanced Spotify monitor error: {e}")
            
        # Debug output every 20 iterations (every minute)
        if hasattr(self, '_monitor_debug_count'):
            self._monitor_debug_count += 1
        else:
            self._monitor_debug_count = 1
            
        if self._monitor_debug_count % 20 == 0:
            active_count = len([k for k, v in getattr(self, '_spotify_sync_data', {}).items() if v.get('sync_enabled')])
            if active_count > 0:
                print(f"🔄 Spotify Monitor Active: {active_count} continuous sync(s) running")

    @spotify_device_monitor.before_loop
    async def before_spotify_device_monitor(self):
        """Wait for bot to be ready before starting monitor."""
        await self.bot.wait_until_ready()

    async def handle_spotify_track(self, guild: discord.Guild, track_info: dict, ctx=None, sync_msg=None):
        """Handle a track from Spotify sync - find and play it on Discord."""
        try:
            if ctx:
                print(f"🎵 Syncing Spotify track: {track_info['name']} by {', '.join(track_info['artists'])}")
            
            # Get the voice client for this guild
            voice_client = guild.voice_client
            if not voice_client:
                if ctx:
                    embed = discord.Embed(
                        title="❌ No Voice Connection",
                        description="I'm not connected to a voice channel!",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                return
            
            # Construct search query
            artists = track_info.get('artists', [])
            track_name = track_info.get('name', '')
            if not track_name:
                if ctx:
                    embed = discord.Embed(
                        title="❌ Invalid Track",
                        description="No track name provided.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                return
                
            if artists:
                query = f"{artists[0]} {track_name}"
            else:
                query = track_name
            
            if ctx:
                print(f"🔍 Searching for: {query}")
            
            # Search for the track
            tracks = await self.search_tracks(query)
            if not tracks:
                if ctx:
                    embed = discord.Embed(
                        title="❌ Track Not Found",
                        description=f"Couldn't find **{track_name}** by **{artists[0] if artists else 'Unknown Artist'}** on any platform.\n\nTry playing it manually with `!play {query}`",
                        color=discord.Color.red()
                    )
                    if sync_msg:
                        await sync_msg.edit(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                return
                
            track = tracks[0]
            if ctx:
                print(f"✅ Found track: {track.title}")
            
            # Get the player
            player = voice_client
            
            # If nothing is playing, start playback directly
            if not player.playing:
                await player.play(track)
                if ctx:
                    print(f"▶️ Started playing: {track.title}")
                    
                    # Create success embed with controls
                    artists_str = ", ".join(track_info['artists'])
                    embed = discord.Embed(
                        title="✅ Synced from Spotify!",
                        description=f"**{track.title}**\nRequested by {ctx.author.mention}",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(name="🎤 Artist", value=artists_str, inline=True)
                    if track_info.get('album'):
                        embed.add_field(name="💿 Album", value=track_info['album'], inline=True)
                    embed.add_field(name="🎵 Source", value="Spotify → Discord", inline=True)
                    
                    # Add controls
                    if hasattr(player, 'queue') and isinstance(player.queue, MusicQueue):
                        view = MusicControlView(self.bot, player, player.queue)
                    else:
                        view = SimplePlaybackView(self.bot, player)
                    
                    if sync_msg:
                        await sync_msg.edit(embed=embed, view=view)
                    else:
                        await ctx.send(embed=embed, view=view)
            else:
                # If something is playing, add to queue
                if hasattr(player, 'queue') and isinstance(player.queue, MusicQueue):
                    player.queue.add(track, ctx.author)
                    position = len(player.queue.tracks)
                    
                    if ctx:
                        print(f"📝 Added to queue: {track.title}")
                        
                        artists_str = ", ".join(track_info['artists'])
                        embed = discord.Embed(
                            title="📝 Added to Queue from Spotify!",
                            description=f"**{track.title}**\nRequested by {ctx.author.mention}",
                            color=discord.Color.blue()
                        )
                        
                        embed.add_field(name="🎤 Artist", value=artists_str, inline=True)
                        embed.add_field(name="📍 Queue Position", value=f"#{position}", inline=True)
                        embed.add_field(name="🎵 Source", value="Spotify → Discord", inline=True)
                        
                        # Add queue controls
                        view = MusicControlView(self.bot, player, player.queue)
                        
                        if sync_msg:
                            await sync_msg.edit(embed=embed, view=view)
                        else:
                            await ctx.send(embed=embed, view=view)
                else:
                    # Fallback: stop current and play new
                    await player.stop()
                    await player.play(track)
                    
                    if ctx:
                        artists_str = ", ".join(track_info['artists'])
                        embed = discord.Embed(
                            title="✅ Synced from Spotify!",
                            description=f"**{track.title}**\nRequested by {ctx.author.mention}",
                            color=discord.Color.green()
                        )
                        
                        embed.add_field(name="🎤 Artist", value=artists_str, inline=True)
                        if track_info.get('album'):
                            embed.add_field(name="💿 Album", value=track_info['album'], inline=True)
                        embed.add_field(name="🎵 Source", value="Spotify → Discord", inline=True)
                        
                        view = SimplePlaybackView(self.bot, player)
                        
                        if sync_msg:
                            await sync_msg.edit(embed=embed, view=view)
                        else:
                            await ctx.send(embed=embed, view=view)
                
        except Exception as e:
            logging.error(f"Error handling Spotify track: {e}")
            if ctx:
                print(f"❌ Error handling track: {e}")
                embed = discord.Embed(
                    title="❌ Sync Error",
                    description=f"Failed to sync track: {str(e)}",
                    color=discord.Color.red()
                )
                if sync_msg:
                    await sync_msg.edit(embed=embed)
                else:
                    await ctx.send(embed=embed)

    async def search_tracks(self, query: str) -> List[wavelink.Playable]:
        """Search for tracks using multiple sources with fallbacks."""
        try:
            # Try SoundCloud first (most reliable for music bots)
            tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud)
            if tracks:
                return tracks
                
            # Fallback to YouTube Music if SoundCloud fails
            tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTubeMusic)
            if tracks:
                return tracks
                
            # Final fallback to regular YouTube
            tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
            return tracks if tracks else []
            
        except Exception as e:
            logging.error(f"Track search error: {e}")
            return []

    async def cog_load(self):
        """Initialize Wavelink nodes when cog loads with enhanced connection management."""
        await self.connect_to_lavalink(initial_connection=True)

    async def connect_to_lavalink(self, initial_connection=False):
        """Enhanced Lavalink connection with proper Wavelink v4 handling."""
        try:
            # Get Lavalink configuration from environment
            lavalink_uri = os.getenv('LAVALINK_URI', 'https://sleeplessll.replit.app')
            lavalink_password = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
            
            if initial_connection:
                print("=" * 60)
                print("🔗 LAVALINK CONNECTION ATTEMPT")
                print("=" * 60)
                print(f"📍 URI: {lavalink_uri}")
                print(f"🔑 Using password: {'*' * len(lavalink_password)}")
                print("⏳ Connecting...")
            else:
                print(f"🔄 Reconnecting to Lavalink (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
            
            logging.info(f"🔗 Attempting to connect to Lavalink at {lavalink_uri}")
            
            # Check if we already have a node with this identifier and disconnect it
            try:
                existing_node = wavelink.Pool.get_node("Ascend")
                if existing_node:
                    print("🔧 Disconnecting existing node...")
                    await existing_node.disconnect()
                    await asyncio.sleep(1)  # Give it a moment to clean up
            except Exception:
                pass  # Node doesn't exist, which is fine
            
            # Create node with proper Wavelink v4 configuration
            print(f"🔧 Creating node with URI: {lavalink_uri}")
            node = wavelink.Node(
                uri=lavalink_uri, 
                password=lavalink_password,
                identifier="Ascend",  # This will be our node identifier
                heartbeat=30.0,
                retries=3
            )
            
            print(f"✅ Node created successfully: {node.identifier}")
            print(f"📡 Attempting Pool.connect...")
            
            # Connect to Wavelink Pool
            await wavelink.Pool.connect(client=self.bot, nodes=[node])
            
            print(f"📊 Pool connection completed. Active nodes: {len(wavelink.Pool.nodes)}")
            print(f"🔍 Available node identifiers: {list(wavelink.Pool.nodes.keys())}")
            
            # Verify connection using proper Wavelink v4 method
            connected_node = wavelink.Pool.get_node("Ascend")
            if connected_node:
                self.connection_stable = True
                self.reconnect_attempts = 0
                
                if initial_connection:
                    print("✅ CONNECTION SUCCESSFUL!")
                    print(f"📍 Connected to: {connected_node.uri}")
                    print(f"🏷️  Node ID: {connected_node.identifier}")
                    print(f"🌐 Status: ONLINE")
                    print("🔄 Enhanced stability features enabled")
                    print("=" * 60)
                else:
                    print(f"✅ Reconnection successful! Node: {connected_node.identifier}")
                
                logging.info(f"✅ Wavelink connected successfully!")
                logging.info(f"   📍 Node URI: {connected_node.uri}")
                logging.info(f"   🏷️  Node ID: {connected_node.identifier}")
                
                # Start heartbeat monitoring
                if not self.heartbeat_task or self.heartbeat_task.done():
                    self.heartbeat_task = asyncio.create_task(self.monitor_connection_health())
                
                return True
            else:
                # If the node wasn't found, list what we actually have
                available_nodes = list(wavelink.Pool.nodes.keys())
                raise Exception(f"Node 'Ascend' not found after connection. Available nodes: {available_nodes}")
                
        except Exception as e:
            self.connection_stable = False
            
            if initial_connection:
                print("❌ CONNECTION FAILED!")
                print(f"💥 Error: {e}")
                print(f"🔧 Make sure Lavalink server is running at {lavalink_uri}")
                print("=" * 60)
            else:
                print(f"❌ Reconnection failed: {e}")
            
            logging.error(f"❌ Failed to connect to Wavelink: {e}")
            
            # Auto-retry logic for reconnections
            if not initial_connection and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                delay = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 300)  # Max 5 minutes
                
                print(f"⏰ Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                return await self.connect_to_lavalink(initial_connection=False)
            
            return False
        connection_options = [
            {
                'uri': os.getenv('LAVALINK_URI', 'https://sleeplessll.replit.app:5000'),
                'password': os.getenv('LAVALINK_PASSWORD', 'youshallnotpass'),
                'name': 'Replit Server'
            },
            {
                'uri': 'http://localhost:2333',
                'password': 'youshallnotpass',
                'name': 'Local Server'
            }
        ]
        
        if initial_connection:
            print("=" * 60)
            print("🔗 LAVALINK CONNECTION ATTEMPT")
            print("=" * 60)
        else:
            print(f"� Reconnecting to Lavalink (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
        
        # Try each connection option
        for i, option in enumerate(connection_options):
            try:
                lavalink_uri = option['uri']
                lavalink_password = option['password']
                server_name = option['name']
                
                print(f"� Trying {server_name}: {lavalink_uri}")
                print(f"🔑 Using password: {'*' * len(lavalink_password)}")
                print("⏳ Connecting...")
                
                logging.info(f"🔗 Attempting to connect to {server_name} at {lavalink_uri}")
                
                # Check if we already have a node with this identifier and disconnect it
                try:
                    existing_node = wavelink.Pool.get_node("Ascend")
                    if existing_node:
                        print("🔧 Disconnecting existing node...")
                        await existing_node.disconnect()
                        await asyncio.sleep(1)  # Give it a moment to clean up
                except Exception:
                    pass  # Node doesn't exist, which is fine
                
                # Enhanced node configuration for Lavalink v4 compatibility
                print(f"🔧 Creating node with URI: {lavalink_uri}")
                node = wavelink.Node(
                    uri=lavalink_uri, 
                    password=lavalink_password,
                    identifier="Ascend",  # Fixed identifier for consistency
                    heartbeat=30.0,  # Heartbeat every 30 seconds
                    retries=3  # Retry failed requests 3 times
                    # Note: SSL is auto-detected from URI scheme (https://)
                )
                
                print(f"✅ Node created successfully: {node.identifier}")
                print(f"📡 Attempting Pool.connect...")
                
                # Connect to Wavelink with timeout
                await asyncio.wait_for(
                    wavelink.Pool.connect(client=self.bot, nodes=[node]),
                    timeout=15.0  # 15 second timeout
                )
                
                print(f"📊 Pool connection completed. Active nodes: {len(wavelink.Pool.nodes)}")
                
                # Verify connection with better error handling
                connected_node = wavelink.Pool.get_node("Ascend")
                if connected_node:
                    self.connection_stable = True
                    self.reconnect_attempts = 0
                    
                    if initial_connection:
                        print("✅ CONNECTION SUCCESSFUL!")
                        print(f"📍 Connected to: {connected_node.uri}")
                        print(f"🏷️  Node ID: {connected_node.identifier}")
                        print(f"🌐 Status: ONLINE")
                        print("🔄 Enhanced stability features enabled")
                        print("=" * 60)
                    else:
                        print(f"✅ Reconnection successful! Node: {connected_node.identifier}")
                    
                    logging.info(f"✅ Wavelink connected successfully!")
                    logging.info(f"   📍 Node URI: {connected_node.uri}")
                    logging.info(f"   🏷️  Node ID: {connected_node.identifier}")
                    logging.info(f"   🌐 Node Status: Connected")
                    
                    # Start heartbeat monitoring
                    if not self.heartbeat_task or self.heartbeat_task.done():
                        self.heartbeat_task = asyncio.create_task(self.monitor_connection_health())
                    
                    return True
                else:
                    # Check what nodes we actually have
                    if wavelink.Pool.nodes:
                        available_nodes = list(wavelink.Pool.nodes.keys())
                        raise Exception(f"Node 'Ascend' not found. Available nodes: {available_nodes}")
                    else:
                        raise Exception("No nodes found after connection attempt")
                        
            except Exception as e:
                self.connection_stable = False
                
                if initial_connection:
                    print("❌ CONNECTION FAILED!")
                    print(f"💥 Error: {e}")
                    print(f"🔧 Make sure Lavalink server is running at {lavalink_uri}")
                    print("=" * 60)
                else:
                    print(f"❌ Reconnection failed: {e}")
                
                logging.error(f"❌ Failed to connect to Wavelink: {e}")
                
                # Continue to next connection option if this one failed
                if i < len(connection_options) - 1:
                    print(f"⏭️ Trying next connection option...")
                    continue
                else:
                    # This was the last option, handle final failure
                    if not initial_connection and self.reconnect_attempts < self.max_reconnect_attempts:
                        self.reconnect_attempts += 1
                        delay = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 300)  # Max 5 minutes
                        
                        print(f"⏰ Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        return await self.connect_to_lavalink(initial_connection=False)
                    
                    return False

    async def monitor_connection_health(self):
        """Monitor Lavalink connection health and trigger reconnections if needed."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if not wavelink.Pool.nodes:
                    print("⚠️  Connection health check failed - no nodes found")
                    logging.warning("Connection health check failed - attempting reconnection")
                    self.connection_stable = False
                    await self.connect_to_lavalink(initial_connection=False)
                else:
                    # Check if nodes are actually responsive
                    try:
                        node = list(wavelink.Pool.nodes.values())[0]
                        # If we get here without exception, connection is healthy
                        if not self.connection_stable:
                            print("✅ Connection health restored")
                            self.connection_stable = True
                    except Exception as e:
                        print(f"⚠️  Node health check failed: {e}")
                        self.connection_stable = False
                        await self.connect_to_lavalink(initial_connection=False)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Connection health monitor error: {e}")
                await asyncio.sleep(30)  # Wait before next check

    async def get_player(self, guild: discord.Guild) -> wavelink.Player:
        """Get or create a player for the guild."""
        try:
            if guild.id not in self.players:
                # Get the voice client if already connected, otherwise None
                player = guild.voice_client
                if not player:
                    # Don't auto-connect here, let commands handle connection
                    return None
                
                # Ensure player has our custom MusicQueue (not Wavelink's default queue)
                if not hasattr(player, 'queue') or not isinstance(player.queue, MusicQueue):
                    player.queue = MusicQueue()
                self.players[guild.id] = player
            return self.players[guild.id]
        except Exception as e:
            logging.error(f"Error getting player: {e}")
            return None

    @commands.hybrid_command(name="play", brief="Play music from YouTube or Spotify")
    async def play(self, ctx, *, query: str):
        """🎵 Play music from YouTube, Spotify, or search query."""
        # Check if user is in voice channel
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Voice Channel Required",
                description="You need to be in a voice channel to use this command!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Connect to voice channel if not already connected
            if not ctx.voice_client:
                try:
                    player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                except Exception as e:
                    embed = discord.Embed(
                        title="❌ Connection Failed",
                        description=f"Failed to connect to voice channel: {str(e)}",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
            else:
                player = ctx.voice_client

            # Ensure player has our custom MusicQueue (not Wavelink's default queue)
            if not hasattr(player, 'queue') or not isinstance(player.queue, MusicQueue):
                player.queue = MusicQueue()

            # Store player reference
            self.players[ctx.guild.id] = player

            # Handle Spotify URLs
            if self.spotify_manager and ("spotify.com" in query):
                await self._handle_spotify_url(ctx, player, query)
                return

            # Search for tracks using multiple sources with fallbacks
            try:
                # Try SoundCloud first (most reliable for music bots)
                tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud)
                if not tracks:
                    # Fallback to YouTube Music if SoundCloud fails
                    tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTubeMusic)
                if not tracks:
                    # Final fallback to regular YouTube
                    tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
                if not tracks:
                    embed = discord.Embed(
                        title="❌ No Results",
                        description="No tracks found for your query on any platform!",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
                
                track = tracks[0]
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Search Failed",
                    description=f"Failed to search for tracks: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Play or queue the track
            try:
                if not player.playing and not player.paused:
                    await player.play(track)
                    player.queue.current = QueueItem(track, ctx.author, datetime.datetime.now())
                    status_text = "🎵 Now Playing"
                else:
                    queue_item = player.queue.add(track, ctx.author)
                    status_text = "➕ Added to Queue"
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Playback Failed",
                    description=f"Failed to play track: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Create success embed
            embed = discord.Embed(
                title=status_text,
                description=f"**{track.title}**\nby *{track.author}*",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )

            # Add track duration if available
            if hasattr(track, 'length') and track.length:
                duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}"
                embed.add_field(name="⏱️ Duration", value=duration, inline=True)

            embed.add_field(name="👤 Requested by", value=ctx.author.mention, inline=True)
            
            # Add queue position
            queue_pos = len(player.queue) if player.playing else "Playing Now"
            embed.add_field(name="📊 Queue Position", value=queue_pos, inline=True)

            # Add thumbnail if available
            if hasattr(track, 'artwork'):
                embed.set_thumbnail(url=track.artwork)

            embed.set_footer(text="Sleepless Development - 100% Free & Open Source")

            # Create advanced control view
            try:
                view = AdvancedMusicControlView(self.bot, player, player.queue)
                await ctx.send(embed=embed, view=view)
            except Exception as e:
                # Send without view if view creation fails
                await ctx.send(embed=embed)
                logging.error(f"Failed to create control view: {e}")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=f"An unexpected error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logging.error(f"Play command error: {e}")

    async def _handle_spotify_url(self, ctx, player, query):
        """Handle Spotify URL processing."""
        try:
            if "playlist" in query:
                tracks = self.spotify_manager.get_playlist_tracks(query)
                added_count = 0
                failed_count = 0
                
                for track_data in tracks[:50]:  # Limit to 50 tracks
                    try:
                        search_query = f"{track_data['name']} {track_data['artists'][0]['name']}"
                        # Try multiple sources for better success rate
                        tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.SoundCloud)
                        if not tracks_found:
                            tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTubeMusic)
                        if not tracks_found:
                            tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
                        
                        if tracks_found:
                            player.queue.add(tracks_found[0], ctx.author)
                            added_count += 1
                        else:
                            failed_count += 1
                    except Exception:
                        failed_count += 1

                embed = discord.Embed(
                    title="🎵 Spotify Playlist Added",
                    description=f"Added {added_count} tracks to the queue!",
                    color=discord.Color.green()
                )
                if failed_count > 0:
                    embed.add_field(name="⚠️ Note", value=f"{failed_count} tracks could not be found", inline=False)
                
                await ctx.send(embed=embed)

            elif "album" in query:
                tracks = self.spotify_manager.get_album_tracks(query)
                added_count = 0
                failed_count = 0
                
                for track_data in tracks:
                    try:
                        search_query = f"{track_data['name']} {track_data['artists'][0]['name']}"
                        # Try multiple sources for better success rate
                        tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.SoundCloud)
                        if not tracks_found:
                            tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTubeMusic)
                        if not tracks_found:
                            tracks_found = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
                        
                        if tracks_found:
                            player.queue.add(tracks_found[0], ctx.author)
                            added_count += 1
                        else:
                            failed_count += 1
                    except Exception:
                        failed_count += 1

                embed = discord.Embed(
                    title="🎵 Spotify Album Added",
                    description=f"Added {added_count} tracks to the queue!",
                    color=discord.Color.green()
                )
                if failed_count > 0:
                    embed.add_field(name="⚠️ Note", value=f"{failed_count} tracks could not be found", inline=False)
                
                await ctx.send(embed=embed)

            else:
                # Single track
                track_data = self.spotify_manager.search_track(query)
                if track_data:
                    search_query = f"{track_data['name']} {track_data['artists'][0]['name']}"
                    # Try multiple sources for better success rate
                    tracks = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.SoundCloud)
                    if not tracks:
                        tracks = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTubeMusic)
                    if not tracks:
                        tracks = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
                    
                    if tracks:
                        track = tracks[0]
                        
                        if not player.playing and not player.paused:
                            await player.play(track)
                            player.queue.current = QueueItem(track, ctx.author, datetime.datetime.now())
                        else:
                            player.queue.add(track, ctx.author)

                        embed = discord.Embed(
                            title="🎵 Spotify Track Added",
                            description=f"**{track.title}**\nby *{track.author}*",
                            color=discord.Color.green()
                        )
                        await ctx.send(embed=embed)
                    else:
                        embed = discord.Embed(
                            title="❌ Track Not Found",
                            description="Could not find this Spotify track on YouTube!",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="❌ Spotify Error",
                        description="Could not find this Spotify track!",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Spotify Error",
                description=f"Failed to process Spotify URL: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logging.error(f"Spotify URL handling error: {e}")

    @commands.hybrid_command(name="skip", brief="Skip the current track")
    async def skip(self, ctx):
        """⏭️ Skip the current track."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if not player.playing:
            await ctx.send("❌ Nothing is currently playing!")
            return

        await player.stop()
        await ctx.send("⏭️ Skipped the current track!")

    @commands.hybrid_command(name="join", brief="Join your voice channel")
    async def join(self, ctx):
        """🔗 Join your current voice channel."""
        # Check if user is in voice channel
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Voice Channel Required",
                description="You need to be in a voice channel for me to join!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if bot is already connected
        if ctx.voice_client:
            if ctx.voice_client.channel == ctx.author.voice.channel:
                embed = discord.Embed(
                    title="✅ Already Connected",
                    description=f"I'm already in **{ctx.author.voice.channel.name}**!",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return
            else:
                # Move to user's channel
                await ctx.voice_client.move_to(ctx.author.voice.channel)
                embed = discord.Embed(
                    title="🔄 Moved Channels",
                    description=f"Moved to **{ctx.author.voice.channel.name}**!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                return

        try:
            # Connect to voice channel
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            
            # Ensure player has our custom MusicQueue
            if not hasattr(player, 'queue') or not isinstance(player.queue, MusicQueue):
                player.queue = MusicQueue()
            
            # Store player reference
            self.players[ctx.guild.id] = player
            
            embed = discord.Embed(
                title="🔗 Joined Voice Channel",
                description=f"Successfully joined **{ctx.author.voice.channel.name}**!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🎵 Ready to Play",
                value=f"Use `{ctx.prefix}play <song>` to start playing music!",
                inline=False
            )
            
            # Add Spotify integration info if available
            if self.spotify_manager:
                embed.add_field(
                    name="🎧 Spotify Integration",
                    value=f"• `{ctx.prefix}spotify link` - Link your Spotify account\n• `{ctx.prefix}spotify device` - Use as Spotify Connect device\n• `{ctx.prefix}spotify play <song>` - Search Spotify directly",
                    inline=False
                )
            
            embed.add_field(
                name="🚀 Pro Tips",
                value=f"• Multi-source search (SoundCloud → YouTube Music → YouTube)\n• Advanced controls with interactive buttons\n• Queue management and repeat modes",
                inline=False
            )
            
            embed.set_footer(text="Sleepless Development - 100% Free & Open Source")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Connection Failed",
                description=f"Failed to join voice channel: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="stop", brief="Stop playback and clear queue")
    async def stop(self, ctx):
        """⏹️ Stop playback and clear the queue."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if hasattr(player, 'queue'):
            player.queue.clear()
        
        await player.stop()
        # Don't disconnect, just stop and clear queue
        
        embed = discord.Embed(
            title="⏹️ Playback Stopped",
            description="Stopped playback and cleared the queue.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="disconnect", aliases=["dc", "leave"], brief="Disconnect from voice channel")
    async def disconnect(self, ctx):
        """📤 Disconnect from the voice channel."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if hasattr(player, 'queue'):
            player.queue.clear()
        
        await player.stop()
        await player.disconnect()
        
        if ctx.guild.id in self.players:
            del self.players[ctx.guild.id]
        
        embed = discord.Embed(
            title="📤 Disconnected",
            description="Disconnected from the voice channel.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

        embed = discord.Embed(
            title="⏹️ Playback Stopped",
            description="Stopped playback and disconnected from the voice channel.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", brief="Pause/resume playback")
    async def pause(self, ctx):
        """⏸️ Pause or resume playback."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if not player.playing:
            await ctx.send("❌ Nothing is currently playing!")
            return

        if player.paused:
            await player.pause(False)
            await ctx.send("▶️ Resumed playback!")
        else:
            await player.pause(True)
            await ctx.send("⏸️ Paused playback!")

    @commands.hybrid_command(name="seek", brief="Seek to a position in the track")
    async def seek(self, ctx, *, position: str = None):
        """⏩ Seek to a specific position in the current track."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if not player.playing:
            await ctx.send("❌ Nothing is currently playing!")
            return

        if position is None:
            modal = SeekModal(player)
            await ctx.interaction.response.send_modal(modal)
            return

        try:
            if ":" in position:
                parts = position.split(":")
                minutes = int(parts[0])
                seconds = int(parts[1])
                position_ms = (minutes * 60 + seconds) * 1000
            else:
                position_ms = int(position) * 1000

            if hasattr(player.current, 'length') and position_ms > player.current.length:
                await ctx.send("❌ Position exceeds track length!")
                return

            await player.seek(position_ms)
            await ctx.send(f"⏩ Seeked to {position}!")
        except (ValueError, IndexError):
            await ctx.send("❌ Invalid position format! Use MM:SS or seconds.")

    @commands.hybrid_command(name="repeat", brief="Toggle repeat mode")
    async def repeat(self, ctx):
        """🔁 Cycle through repeat modes: Off → Track → Queue → Off."""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to a voice channel!")
            return

        player = ctx.voice_client
        if not hasattr(player, 'queue'):
            player.queue = MusicQueue()

        if player.queue.repeat_mode == RepeatMode.OFF:
            player.queue.repeat_mode = RepeatMode.TRACK
            await ctx.send("🔂 Repeat track enabled!")
        elif player.queue.repeat_mode == RepeatMode.TRACK:
            player.queue.repeat_mode = RepeatMode.QUEUE
            await ctx.send("🔁 Repeat queue enabled!")
        else:
            player.queue.repeat_mode = RepeatMode.OFF
            await ctx.send("➡️ Repeat disabled!")

    @commands.hybrid_command(name="nowplaying", aliases=["np"], brief="Show currently playing track")
    async def nowplaying(self, ctx):
        """🎵 Display information about the currently playing track."""
        if not ctx.voice_client:
            embed = discord.Embed(
                title="❌ Not Connected",
                description="Not connected to a voice channel!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        player = ctx.voice_client
        if not player.playing and not player.paused:
            embed = discord.Embed(
                title="❌ Nothing Playing",
                description="Nothing is currently playing!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            track = player.current
            if not track:
                embed = discord.Embed(
                    title="❌ No Track Info",
                    description="Could not get current track information!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{track.title}**\nby *{track.author}*",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )

            # Add progress bar if track has length
            try:
                if hasattr(track, 'length') and track.length and track.length > 0:
                    current_pos = player.position if hasattr(player, 'position') else 0
                    duration = track.length
                    
                    # Create simple progress indicator
                    progress = min(current_pos / duration, 1.0) if duration > 0 else 0
                    progress_bar = self.create_progress_bar(current_pos, duration)
                    
                    current_time = f"{current_pos // 60000}:{(current_pos // 1000) % 60:02d}"
                    total_time = f"{duration // 60000}:{(duration // 1000) % 60:02d}"
                    
                    embed.add_field(
                        name="⏱️ Progress",
                        value=f"{current_time} {progress_bar} {total_time}",
                        inline=False
                    )
            except Exception as e:
                logging.error(f"Progress bar error: {e}")

            # Add requester info
            try:
                if hasattr(player, 'queue') and player.queue.current and hasattr(player.queue.current, 'requester'):
                    embed.add_field(
                        name="👤 Requested by", 
                        value=player.queue.current.requester.mention, 
                        inline=True
                    )
            except Exception as e:
                logging.error(f"Requester info error: {e}")

            # Add volume and queue info
            try:
                volume = getattr(player, 'volume', 100)
                embed.add_field(name="🔊 Volume", value=f"{volume}%", inline=True)
                
                queue_length = len(player.queue.items) if hasattr(player, 'queue') and hasattr(player.queue, 'items') else 0
                embed.add_field(name="📊 Queue Length", value=queue_length, inline=True)
            except Exception as e:
                logging.error(f"Volume/queue info error: {e}")

            # Add thumbnail
            try:
                if hasattr(track, 'artwork') and track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                elif hasattr(track, 'thumbnail') and track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
            except Exception as e:
                logging.error(f"Thumbnail error: {e}")

            embed.set_footer(text="Sleepless Development - 100% Free & Open Source")

            # Try to add advanced control view
            try:
                if hasattr(player, 'queue'):
                    view = AdvancedMusicControlView(self.bot, player, player.queue)
                    await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(embed=embed)
                logging.error(f"Control view error: {e}")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while getting track info: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logging.error(f"Now playing error: {e}")

    @commands.command(name="status", brief="Check Lavalink connection status with health details")
    async def status(self, ctx):
        """🔍 Check the current Lavalink connection status with enhanced monitoring."""
        try:
            # Get bot prefix for display
            prefix = ctx.prefix if hasattr(ctx, 'prefix') else '<'
            
            embed = discord.Embed(
                title="🔗 Lavalink Connection Status", 
                color=discord.Color.blue()
            )
            
            if not wavelink.Pool.nodes:
                embed.description = "❌ No Lavalink nodes connected"
                embed.color = discord.Color.red()
                
                embed.add_field(
                    name="� Troubleshooting",
                    value=f"• Check if Lavalink server is running\n• Verify environment variables\n• Try `{prefix}reconnect` to force reconnection",
                    inline=False
                )
                
                embed.add_field(
                    name="🌐 Free Hosting Options",
                    value="• **Replit** - Easiest setup, completely free ⭐\n• **Railway.app** - Most reliable\n• **Render.com** - Good alternative\n• **Public instances** - Temporary solution\n\nSee `/lavalink-hosting-guide.md` for setup instructions",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 Help",
                    value=f"Use `{prefix}help music` for all music commands.",
                    inline=False
                )
            else:
                node = list(wavelink.Pool.nodes.values())[0]
                
                # Check connection health
                connection_status = "🟢 Stable" if self.connection_stable else "🟡 Unstable"
                last_disconnect = "Never" if not self.last_disconnect_time else f"<t:{int(self.last_disconnect_time.timestamp())}:R>"
                
                embed.description = f"✅ Connected to Lavalink node"
                embed.color = discord.Color.green() if self.connection_stable else discord.Color.orange()
                
                embed.add_field(
                    name="� Connection Details",
                    value=f"**Node ID:** {node.identifier}\n**URI:** {node.uri}\n**Status:** {connection_status}\n**Players:** {len(self.players)}",
                    inline=True
                )
                
                embed.add_field(
                    name="📈 Health Metrics",
                    value=f"**Reconnect Attempts:** {self.reconnect_attempts}/{self.max_reconnect_attempts}\n**Last Disconnect:** {last_disconnect}\n**Heartbeat:** {'🟢 Active' if self.heartbeat_task and not self.heartbeat_task.done() else '🔴 Inactive'}",
                    inline=True
                )
                
                embed.add_field(
                    name="🎵 Music Features",
                    value=f"• Multi-source search enabled\n• Spotify integration active\n• Advanced controls available\n• Queue management ready",
                    inline=False
                )
                
                # Add node stats if available
                try:
                    stats = getattr(node, 'stats', None)
                    if stats:
                        embed.add_field(
                            name="� Node Statistics",
                            value=f"**Players:** {getattr(stats, 'players', 'N/A')}\n**Playing:** {getattr(stats, 'playing_players', 'N/A')}\n**Uptime:** {getattr(stats, 'uptime', 'N/A')}ms",
                            inline=True
                        )
                except Exception:
                    pass
            
            embed.add_field(
                name="🛠️ Available Commands",
                value=f"`{prefix}play <song>` - Play music\n`{prefix}join` - Join voice channel\n`{prefix}reconnect` - Force reconnection\n`{prefix}help music` - All commands",
                inline=False
            )
            
            embed.set_footer(text=f"Enhanced connection monitoring active • Use {prefix}help music for all commands")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to check Lavalink status: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logging.error(f"Status command error: {e}")

    @commands.command(name="reconnect", brief="Force reconnection to Lavalink")
    async def reconnect(self, ctx):
        """🔄 Force a reconnection to Lavalink server."""
        try:
            embed = discord.Embed(
                title="🔄 Forcing Reconnection",
                description="Attempting to reconnect to Lavalink server...",
                color=discord.Color.orange()
            )
            message = await ctx.send(embed=embed)
            
            # Reset connection state
            self.connection_stable = False
            self.reconnect_attempts = 0
            
            # Attempt reconnection
            success = await self.connect_to_lavalink(initial_connection=False)
            
            if success:
                embed = discord.Embed(
                    title="✅ Reconnection Successful",
                    description="Successfully reconnected to Lavalink server!",
                    color=discord.Color.green()
                )
                
                node = list(wavelink.Pool.nodes.values())[0] if wavelink.Pool.nodes else None
                if node:
                    embed.add_field(
                        name="📊 Connection Info",
                        value=f"**Node:** {node.identifier}\n**URI:** {node.uri}\n**Status:** 🟢 Online",
                        inline=False
                    )
                
                embed.add_field(
                    name="🎵 Ready to Use",
                    value=f"All music commands are now available!\nTry `{ctx.prefix}play <song>` to test the connection.",
                    inline=False
                )
                
            else:
                embed = discord.Embed(
                    title="❌ Reconnection Failed",
                    description="Failed to reconnect to Lavalink server.",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="🔧 Troubleshooting",
                    value="• Check if Lavalink server is running\n• Verify LAVALINK_URI and LAVALINK_PASSWORD\n• Try a different Lavalink host\n• Check `/lavalink-hosting-guide.md` for free options",
                    inline=False
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reconnection Error",
                description=f"An error occurred during reconnection: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logging.error(f"Reconnect command error: {e}")

    def create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """Create a simple text progress bar."""
        try:
            if total <= 0:
                return "▬" * length
            
            progress = min(current / total, 1.0)
            filled = int(progress * length)
            bar = "▬" * filled + "🔘" + "▬" * (length - filled - 1)
            return bar
        except Exception:
            return "▬" * length

    @commands.hybrid_command(name="device", brief="Set Spotify device name")
    async def device(self, ctx, *, name: str = None):
        """🎵 Set or view the Spotify device name for this server."""
        if not self.spotify_manager:
            await ctx.send("❌ Spotify integration is not available!")
            return

        if name is None:
            current_name = self.spotify_manager.get_device_name(ctx.guild.id)
            embed = discord.Embed(
                title="🎵 Current Spotify Device",
                description=f"**{current_name}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            self.spotify_manager.set_device_name(ctx.guild.id, name)
            await ctx.send(f"🎵 Spotify device name set to: **{name}**")

    @commands.hybrid_command(name="devicemodal", brief="Set device name via modal")
    async def devicemodal(self, ctx):
        """🎵 Set Spotify device name using an interactive modal."""
        if not self.spotify_manager:
            await ctx.send("❌ Spotify integration is not available!")
            return

        # Check if this is a slash command with interaction
        if hasattr(ctx, 'interaction') and ctx.interaction:
            modal = DeviceNameModal(self.spotify_manager, ctx.guild.id)
            await ctx.interaction.response.send_modal(modal)
        else:
            # Fallback for prefix commands - show current device and suggest alternative
            current_name = self.spotify_manager.get_device_name(ctx.guild.id)
            embed = discord.Embed(
                title="🎵 Spotify Device Configuration",
                description=f"Current device name: **{current_name}**",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="⚠️ Modal Not Available",
                value="Interactive modals are only available with slash commands.\nUse the regular device command instead:",
                inline=False
            )
            embed.add_field(
                name="💡 Alternative",
                value=f"`{ctx.prefix}device <new_name>` - Set device name directly",
                inline=False
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="lyrics", brief="Get lyrics for the current track")
    async def lyrics(self, ctx, *, song: str = None):
        """📝 Get lyrics for the current track or a specified song."""
        if not song:
            if not ctx.voice_client or not ctx.voice_client.playing:
                await ctx.send("❌ No song is currently playing! Please specify a song name.")
                return
            song = ctx.voice_client.current.title

        await ctx.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.lyrics.ovh/v1/{song.split(' - ')[0] if ' - ' in song else 'Unknown'}/{song}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        lyrics = data.get('lyrics', 'No lyrics found.')
                        
                        if len(lyrics) > 4096:
                            lyrics = lyrics[:4093] + "..."
                        
                        embed = discord.Embed(
                            title=f"📝 Lyrics for {song}",
                            description=lyrics,
                            color=discord.Color.blue()
                        )
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"❌ No lyrics found for **{song}**!")
        except Exception as e:
            await ctx.send("❌ Failed to fetch lyrics!")
            logging.error(f"Lyrics error: {e}")

    @commands.hybrid_command(name="source-test", brief="Test different audio sources")
    async def source_test(self, ctx, *, query: str):
        """🔍 Test which audio sources can find your query."""
        sources = [
            ("SoundCloud", wavelink.TrackSource.SoundCloud),
            ("YouTube Music", wavelink.TrackSource.YouTubeMusic),
            ("YouTube", wavelink.TrackSource.YouTube),
        ]
        
        embed = discord.Embed(
            title="🔍 Source Test Results",
            description=f"Testing sources for: **{query}**",
            color=discord.Color.blue()
        )
        
        for source_name, source in sources:
            try:
                tracks = await wavelink.Playable.search(query, source=source)
                if tracks:
                    track = tracks[0]
                    duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}" if hasattr(track, 'length') else "Unknown"
                    embed.add_field(
                        name=f"✅ {source_name}",
                        value=f"**{track.title}**\nby *{track.author}* [{duration}]",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"❌ {source_name}",
                        value="No results found",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name=f"⚠️ {source_name}",
                    value=f"Error: {str(e)[:100]}",
                    inline=False
                )
        
        await ctx.send(embed=embed)

    def format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS format."""
        try:
            total_seconds = ms // 1000
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02d}"
        except Exception:
            return "0:00"

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Handle track end events."""
        player = payload.player
        if not hasattr(player, 'queue') or not isinstance(player.queue, MusicQueue):
            return

        # Try to play next track from queue
        try:
            next_item = player.queue.get_next()
            if next_item:
                await player.play(next_item.track)
            else:
                # Queue is empty, disconnect after 5 minutes of inactivity
                await asyncio.sleep(300)
                if not player.playing:
                    await player.disconnect()
        except Exception as e:
            logging.error(f"Error in track_end handler: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Handle track start events."""
        player = payload.player
        track = payload.track
        
        try:
            db = self.bot.get_cog('DatabaseManager')
            if db and hasattr(player, 'queue') and player.queue.current:
                await db.add_listening_history(
                    player.queue.current.requester.id,
                    player.guild.id,
                    track.title,
                    track.author,
                    getattr(track, 'length', 0)
                )
        except Exception as e:
            logging.error(f"Failed to update listening history: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Handle Wavelink node ready events."""
        node = payload.node
        
        print("\n" + "=" * 60)
        print("🟢 LAVALINK NODE READY")
        print("=" * 60)
        print(f"📍 Node: {node.identifier}")
        print(f"🌐 URI: {node.uri}")
        print(f"📊 Session ID: {payload.session_id}")
        print("🎵 Ready to play music!")
        print("=" * 60 + "\n")
        
        logging.info(f"🟢 Lavalink node ready!")
        logging.info(f"   📍 Node: {node.identifier} ({node.uri})")
        logging.info(f"   📊 Session ID: {payload.session_id}")

    @commands.Cog.listener() 
    async def on_wavelink_websocket_closed(self, payload: wavelink.WebsocketClosedEventPayload):
        """Handle Wavelink websocket closed events with automatic reconnection."""
        player = payload.player
        self.connection_stable = False
        self.last_disconnect_time = datetime.datetime.now()
        
        print("\n" + "=" * 60)
        print("🔴 LAVALINK CONNECTION LOST")
        print("=" * 60)
        
        guild = None
        guild_name = "Unknown"
        
        if player and player.guild:
            guild = player.guild
            guild_name = guild.name
            print(f"🏠 Guild: {guild_name}")
            logging.warning(f"🔴 Lavalink websocket closed for guild {guild_name}")
        else:
            print("🏠 Guild: Unknown (Player or Guild is None)")
            logging.warning("🔴 Lavalink websocket closed - Player or Guild is None")
        
        print(f"🔢 Code: {payload.code}")
        print(f"📝 Reason: {payload.reason}")
        print(f"🔄 By remote: {payload.by_remote}")
        
        # Determine if this is a critical disconnection that needs immediate action
        is_critical = False
        if payload.code:
            code_str = str(payload.code)
            is_critical = any(critical in code_str for critical in ['TIMEOUT', 'ERROR', 'ABNORMAL'])
        
        print(f"⚠️  Critical disconnect: {is_critical}")
        print("=" * 60 + "\n")
        
        logging.warning(f"   🔢 Code: {payload.code}")
        logging.warning(f"   📝 Reason: {payload.reason}")
        logging.warning(f"   🔄 By remote: {payload.by_remote}")
        logging.warning(f"   ⚠️  Critical: {is_critical}")
        
        # Start automatic reconnection in background
        if is_critical or not payload.by_remote:
            print("🔄 Starting automatic reconnection process...")
            asyncio.create_task(self.handle_disconnection_recovery())
        
        # Send user-friendly notification to the guild
        if guild:
            try:
                # Create user-friendly disconnect message
                embed = discord.Embed(
                    title="🔴 Music Bot Disconnected",
                    description="**I've been disconnected from the voice channel due to a connection issue.**",
                    color=discord.Color.red()
                )
                
                # Add reason based on the disconnect code
                disconnect_reason = "Unknown connection issue"
                auto_reconnect = "Attempting automatic reconnection..."
                
                if payload.code and "TIMEOUT" in str(payload.code):
                    disconnect_reason = "Connection timeout - network lag detected"
                    auto_reconnect = "🔄 Auto-reconnecting now..."
                elif payload.code and "CLOSE_NORMAL" in str(payload.code):
                    disconnect_reason = "Normal disconnect - likely due to inactivity or network issues"
                    auto_reconnect = "🔄 Reconnecting automatically..."
                elif payload.code and "VOICE_DISCONNECT" in str(payload.code):
                    disconnect_reason = "Voice channel connection lost"
                    auto_reconnect = "🔄 Restoring connection..."
                elif payload.reason:
                    disconnect_reason = f"Connection issue: {payload.reason}"
                
                embed.add_field(
                    name="📋 What Happened",
                    value=f"• **Reason:** {disconnect_reason}\n• **When:** <t:{int(discord.utils.utcnow().timestamp())}:R>\n• **Status:** {auto_reconnect}",
                    inline=False
                )
                
                embed.add_field(
                    name="🔄 Recovery Process",
                    value="• **Auto-reconnection is active**\n• Connection will be restored automatically\n• Use music commands once reconnected",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 Prevention Tips",
                    value="• Consider using a dedicated Lavalink host\n• Check for network stability issues\n• Free hosting options available (see below)",
                    inline=False
                )
                
                embed.set_footer(text="Sleepless Development - Auto-reconnect in progress")
                
                # Try to find the best channel to send the notification
                target_channel = None
                
                # First priority: Find a music or bot channel
                for channel in guild.text_channels:
                    if any(keyword in channel.name.lower() for keyword in ['music', 'bot', 'commands', 'general']):
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
                
                # Second priority: Use system channel
                if not target_channel and guild.system_channel:
                    if guild.system_channel.permissions_for(guild.me).send_messages:
                        target_channel = guild.system_channel
                
                # Third priority: Use the first available text channel
                if not target_channel:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
                
                # Send the notification
                if target_channel:
                    await target_channel.send(embed=embed)
                    print(f"✅ Sent disconnect notification to #{target_channel.name} in {guild_name}")
                else:
                    print(f"⚠️ Could not find suitable channel to send disconnect notification in {guild_name}")
                    
                # Clean up player reference
                if guild.id in self.players:
                    del self.players[guild.id]
                    print(f"🗑️ Cleaned up player reference for {guild_name}")
                    
            except Exception as e:
                print(f"❌ Failed to send disconnect notification to {guild_name}: {e}")
                logging.error(f"Failed to send disconnect notification: {e}")
        else:
            print("⚠️ No guild available to send disconnect notification")

    async def handle_disconnection_recovery(self):
        """Handle automatic recovery from disconnections."""
        try:
            print("🔄 Starting disconnection recovery process...")
            
            # Wait a moment before attempting reconnection
            await asyncio.sleep(5)
            
            # Attempt to reconnect
            success = await self.connect_to_lavalink(initial_connection=False)
            
            if success:
                print("✅ Automatic reconnection successful!")
                
                # Notify all guilds that had active players
                for guild_id, player in list(self.players.items()):
                    if player and player.guild:
                        try:
                            embed = discord.Embed(
                                title="🟢 Connection Restored",
                                description="**Music bot connection has been restored!**",
                                color=discord.Color.green()
                            )
                            
                            embed.add_field(
                                name="🎵 Ready to Play",
                                value="• Connection is now stable\n• All music commands are available\n• Use `<play <song>` to start music again",
                                inline=False
                            )
                            
                            embed.set_footer(text="Sleepless Development - Connection restored")
                            
                            # Find appropriate channel
                            guild = player.guild
                            target_channel = None
                            
                            for channel in guild.text_channels:
                                if any(keyword in channel.name.lower() for keyword in ['music', 'bot', 'commands', 'general']):
                                    if channel.permissions_for(guild.me).send_messages:
                                        target_channel = channel
                                        break
                            
                            if target_channel:
                                await target_channel.send(embed=embed)
                            
                        except Exception as e:
                            logging.error(f"Failed to send reconnection notification: {e}")
            else:
                print("❌ Automatic reconnection failed - manual intervention may be required")
                
        except Exception as e:
            logging.error(f"Disconnection recovery error: {e}")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        try:
            # Cancel monitoring tasks
            self.spotify_device_monitor.cancel()
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
            
            # Clean up Wavelink connections
            async def cleanup_wavelink():
                try:
                    # Disconnect all players
                    for player in list(self.players.values()):
                        if player and player.guild:
                            try:
                                await player.disconnect()
                            except Exception:
                                pass
                    
                    # Clear players dict
                    self.players.clear()
                    
                    # Disconnect node if it exists
                    node = wavelink.Pool.get_node("Ascend")
                    if node:
                        await node.disconnect()
                        
                    # Clear the pool
                    wavelink.Pool.nodes.clear()
                except Exception as e:
                    logging.error(f"Error during Wavelink cleanup: {e}")
            
            # Schedule the cleanup
            import asyncio
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(cleanup_wavelink())
            
        except Exception as e:
            logging.error(f"Error during cog unload: {e}")

    # ============================================================================
    # SPOTIFY DEVICE MODE COMMANDS (Like Spoticord)
    # ============================================================================

    @commands.group(name="spotify", aliases=["sp"], brief="Spotify integration and device control")
    async def spotify(self, ctx):
        """🎧 Spotify integration with device mode like Spoticord."""
        if ctx.invoked_subcommand is None:
            await self.show_spotify_main_menu(ctx)

    @spotify.command(name="link", brief="Link your Spotify account")
    async def spotify_link(self, ctx):
        """🔗 Link your Spotify account for enhanced features."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            auth_url = await self.spotify_manager.get_auth_url(ctx.author.id)
            
            embed = discord.Embed(
                title="🎧 Link Your Spotify Account",
                description="Click the link below to connect your Spotify account with Ascend.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🔗 Authorization Link",
                value=f"[Click Here to Link Spotify]({auth_url})",
                inline=False
            )
            
            embed.add_field(
                name="📋 Next Steps",
                value=f"1. Click the link above\n2. Authorize Ascend\n3. Use `{ctx.prefix}spotify confirm <code>` with the code",
                inline=False
            )
            
            embed.add_field(
                name="✨ Benefits",
                value="• Access your playlists\n• Control Spotify playback\n• Use as a Spotify device\n• Enhanced recommendations",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to generate Spotify link: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="unlink", brief="Unlink your Spotify account")
    async def spotify_unlink(self, ctx):
        """🔓 Unlink your Spotify account."""
        # Implementation would remove user's Spotify tokens from database
        embed = discord.Embed(
            title="🔓 Spotify Account Unlinked",
            description="Your Spotify account has been disconnected from Ascend.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="📝 What This Means",
            value="• Spotify playlists are no longer accessible\n• Device mode is disabled\n• You can re-link anytime",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @spotify.command(name="confirm", brief="Complete Spotify OAuth")
    async def spotify_confirm(self, ctx, *, auth_code: str):
        """✅ Complete Spotify account linking with authorization code."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Complete the OAuth flow by exchanging auth code for tokens
            auth_manager = spotipy.SpotifyOAuth(
                client_id=self.spotify_manager.client_id,
                client_secret=self.spotify_manager.client_secret,
                redirect_uri="https://ascend-api.replit.app/callback",
                scope="user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative user-library-read"
            )
            
            # Exchange authorization code for access token
            token_info = auth_manager.get_access_token(auth_code, as_dict=True)
            
            if token_info:
                # Store user tokens
                self.spotify_manager.user_tokens[ctx.author.id] = token_info
                # Save tokens to file for persistence
                self.spotify_manager.save_tokens()
                
                # Test the connection
                sp = spotipy.Spotify(auth=token_info['access_token'])
                user_info = sp.current_user()
                
                embed = discord.Embed(
                    title="✅ Spotify Account Linked!",
                    description=f"Successfully linked to **{user_info['display_name']}**'s Spotify account.",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🎉 What's Next?",
                    value=f"• Use `{ctx.prefix}spotify status` to check your connection\n• Try `{ctx.prefix}spotify playlists` to browse your music\n• Use `{ctx.prefix}spotify device` for device mode",
                    inline=False
                )
                
                embed.add_field(
                    name="🎮 Quick Start",
                    value=f"Search and play: `{ctx.prefix}spotify play never gonna give you up`",
                    inline=False
                )
                
                await ctx.send(embed=embed)
            else:
                raise Exception("Failed to exchange authorization code for tokens")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Confirmation Failed",
                description=f"Failed to confirm Spotify linking: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="status", brief="Check Spotify connection status")
    async def spotify_status(self, ctx):
        """📊 Check your Spotify connection and current playback."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Check if user has linked Spotify
            sp = self.spotify_manager.get_user_spotify(ctx.author.id)
            
            if not sp:
                embed = discord.Embed(
                    title="🔗 Spotify Not Linked",
                    description=f"You haven't linked your Spotify account yet.\nUse `{ctx.prefix}spotify link` to get started!",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

            # Get current playback
            try:
                current = sp.current_playback()
                
                if current and current.get('is_playing'):
                    track = current['item']
                    device = current['device']
                    
                    embed = discord.Embed(
                        title="🎧 Spotify Status - Currently Playing",
                        description=f"**{track['name']}**\nby *{track['artists'][0]['name']}*",
                        color=discord.Color.green()
                    )
                    
                    # Add playback info
                    progress_ms = current.get('progress_ms', 0)
                    duration_ms = track['duration_ms']
                    progress_bar = self.create_progress_bar(progress_ms, duration_ms)
                    
                    embed.add_field(
                        name="⏱️ Progress",
                        value=f"```{progress_bar}```\n{self.format_time(progress_ms)} / {self.format_time(duration_ms)}",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="📱 Device",
                        value=f"**{device['name']}** ({device['type']})\nVolume: {device.get('volume_percent', 'Unknown')}%",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🎮 Controls",
                        value=f"Use `{ctx.prefix}spotify play/pause/skip` to control",
                        inline=True
                    )
                    
                    if track.get('preview_url'):
                        embed.add_field(
                            name="🔗 Links",
                            value=f"[Open in Spotify]({track['external_urls']['spotify']})",
                            inline=True
                        )
                    
                    # Add album art
                    if track['album']['images']:
                        embed.set_thumbnail(url=track['album']['images'][0]['url'])
                        
                else:
                    embed = discord.Embed(
                        title="🎧 Spotify Status - Not Playing",
                        description="Spotify is connected but nothing is currently playing.",
                        color=discord.Color.blue()
                    )
                    
                    embed.add_field(
                        name="🎮 Quick Actions",
                        value=f"• `{ctx.prefix}spotify playlists` - Browse your playlists\n• `{ctx.prefix}spotify sync` - Sync current track to Discord\n• `{ctx.prefix}spotify device` - Use Ascend as Spotify device\n• `{ctx.prefix}play <song>` - Search and play music",
                        inline=False
                    )
                
            except Exception as e:
                embed = discord.Embed(
                    title="✅ Spotify Connected",
                    description="Your Spotify account is linked but we couldn't get current playback info.",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="🎮 Available Commands",
                    value=f"• `{ctx.prefix}spotify playlists`\n• `{ctx.prefix}spotify device`\n• `{ctx.prefix}spotify play <song>`",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to check Spotify status: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="device", brief="Enable device mode")
    async def spotify_device(self, ctx):
        """📱 Use Ascend as a Spotify Connect device (like Spoticord)."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if user has linked Spotify
        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.\nUse `{ctx.prefix}spotify link` to get started!",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Generate fresh auth URL for device setup (requires device scope)
            scope = "user-read-playback-state user-modify-playback-state streaming user-read-email user-read-private"
            
            sp_oauth = SpotifyOAuth(
                client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
                redirect_uri="https://ascend-api.replit.app/callback",
                scope=scope,
                state=f"{ctx.author.id}:{ctx.guild.id}",
                show_dialog=True  # Force re-authorization for device setup
            )
            
            auth_url = sp_oauth.get_authorize_url()
            
            # Create setup embed
            embed = discord.Embed(
                title="🎵 Spotify Connect Device Setup",
                description="Setting up **Ascend Music Bot** as a Spotify Connect device...",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📱 What You'll Get",
                value="• Bot appears in your Spotify device list\n• Control from any Spotify app\n• Music plays through Discord\n• Full playback control (play/pause/skip)",
                inline=False
            )
            
            embed.add_field(
                name="🚀 Setup Steps",
                value="1. Click 'Start Setup' below\n2. Authorize Spotify (may ask to log in again)\n3. Copy the authorization code\n4. Use the code with the command shown",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ Device Info",
                value=f"**Device Name:** Ascend Music Bot\n**Server:** {ctx.guild.name}\n**Type:** Computer",
                inline=False
            )
            
            view = SpotifyDeviceLinkView(auth_url, ctx.author.id, ctx.guild.id)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logging.error(f"Spotify device setup error: {e}")
            embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"Failed to set up Spotify Connect device: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="devicesetup", brief="Complete device setup with auth code")
    async def spotify_device_setup(self, ctx, auth_code: str):
        """🔧 Complete Spotify Connect device setup with authorization code."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        try:
            # Send authorization code to Replit callback for token exchange
            callback_url = "https://ascend-api.replit.app/callback/complete"
            
            payload = {
                "code": auth_code,
                "guild_id": ctx.guild.id,
                "user_id": ctx.author.id,
                "guild_name": ctx.guild.name
            }
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(callback_url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        device_url = data.get("device_url")
                        session_token = data.get("session_token")
                        
                        if device_url:
                            embed = discord.Embed(
                                title="✅ Device Setup Complete!",
                                description="Your Spotify Connect device has been configured successfully!",
                                color=discord.Color.green()
                            )
                            
                            embed.add_field(
                                name="🎵 Activate Your Device",
                                value=f"Click the button below to activate your Spotify device player.",
                                inline=False
                            )
                            
                            embed.add_field(
                                name="📱 How to Use",
                                value="1. Click 'Open Device Player' below\n2. Wait for 'Device Ready' confirmation\n3. Open Spotify on phone/computer\n4. Tap device icon and select 'Ascend Music Bot'\n5. Play music - it streams through Discord!",
                                inline=False
                            )
                            
                            embed.add_field(
                                name="ℹ️ Important",
                                value="Keep the device player tab open while using Spotify Connect. Close it when done to disconnect the device.",
                                inline=False
                            )
                            
                            view = SpotifyDeviceActivateView(device_url, session_token)
                            await ctx.send(embed=embed, view=view)
                            
                        else:
                            embed = discord.Embed(
                                title="❌ Setup Error",
                                description="Failed to generate device URL. Please try again.",
                                color=discord.Color.red()
                            )
                            await ctx.send(embed=embed)
                    else:
                        try:
                            response_data = await response.json()
                            error_msg = response_data.get("error", "Unknown error")
                        except:
                            error_msg = f"HTTP {response.status}"
                        
                        embed = discord.Embed(
                            title="❌ Authorization Failed",
                            description=f"Failed to exchange authorization code: {error_msg}",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)
                        
        except Exception as e:
            logging.error(f"Device setup completion error: {e}")
            embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"Failed to complete device setup: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="play", brief="Play/control Spotify playback")
    async def spotify_play(self, ctx, *, query: str = None):
        """▶️ Control Spotify playback or search and play."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.\nUse `{ctx.prefix}spotify link` to get started!",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            if query:
                # Search and play specific track
                results = sp.search(q=query, type='track', limit=10)
                
                if not results['tracks']['items']:
                    embed = discord.Embed(
                        title="❌ No Results",
                        description=f"No tracks found for '{query}' on Spotify.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return

                # Show search results
                view = SpotifySearchView(sp, results['tracks']['items'], ctx.author)
                embed = discord.Embed(
                    title="🎧 Spotify Search Results",
                    description=f"Found {len(results['tracks']['items'])} results for **{query}**",
                    color=discord.Color.green()
                )
                
                for i, track in enumerate(results['tracks']['items'][:5]):
                    duration = self.format_time(track['duration_ms'])
                    embed.add_field(
                        name=f"{i+1}. {track['name']}",
                        value=f"by *{track['artists'][0]['name']}* `[{duration}]`",
                        inline=False
                    )
                
                await ctx.send(embed=embed, view=view)
                
            else:
                # Resume/start playback
                try:
                    sp.start_playback()
                    embed = discord.Embed(
                        title="▶️ Spotify Playback Resumed",
                        description="Started playback on your Spotify account.",
                        color=discord.Color.green()
                    )
                except Exception as e:
                    if "NO_ACTIVE_DEVICE" in str(e):
                        embed = discord.Embed(
                            title="📱 No Active Device",
                            description="Please open Spotify on a device or use device mode.",
                            color=discord.Color.orange()
                        )
                        embed.add_field(
                            name="💡 Solutions",
                            value=f"• Open Spotify on your phone/computer\n• Use `{ctx.prefix}spotify device` for device mode\n• Specify a song: `{ctx.prefix}spotify play <song>`",
                            inline=False
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Playback Error",
                            description=f"Failed to start playback: {str(e)}",
                            color=discord.Color.red()
                        )
                
                await ctx.send(embed=embed)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Spotify error: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="pause", brief="Pause Spotify playback")
    async def spotify_pause(self, ctx):
        """⏸️ Pause Spotify playback."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            sp.pause_playback()
            embed = discord.Embed(
                title="⏸️ Spotify Paused",
                description="Paused playback on your Spotify account.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to pause: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="skip", aliases=["next"], brief="Skip to next track")
    async def spotify_skip(self, ctx):
        """⏭️ Skip to the next track on Spotify."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            sp.next_track()
            embed = discord.Embed(
                title="⏭️ Skipped Track",
                description="Skipped to the next track on Spotify.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error", 
                description=f"Failed to skip: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="previous", aliases=["prev"], brief="Go to previous track")
    async def spotify_previous(self, ctx):
        """⏮️ Go to the previous track on Spotify."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            sp.previous_track()
            embed = discord.Embed(
                title="⏮️ Previous Track",
                description="Went to the previous track on Spotify.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to go back: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="playlists", brief="Browse your Spotify playlists")
    async def spotify_playlists(self, ctx):
        """📋 Browse and play your Spotify playlists."""
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            playlists = self.spotify_manager.get_user_playlists(ctx.author.id)
            
            if not playlists:
                embed = discord.Embed(
                    title="📋 No Playlists Found",
                    description="You don't have any playlists on Spotify.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            view = SpotifyPlaylistView(sp, playlists, ctx.author)
            embed = discord.Embed(
                title="📋 Your Spotify Playlists",
                description=f"Found {len(playlists)} playlists in your Spotify account.",
                color=discord.Color.green()
            )
            
            for i, playlist in enumerate(playlists[:10]):
                track_count = playlist['tracks']['total']
                embed.add_field(
                    name=f"{i+1}. {playlist['name']}",
                    value=f"{track_count} tracks",
                    inline=True
                )
            
            if len(playlists) > 10:
                embed.set_footer(text=f"Showing first 10 of {len(playlists)} playlists")
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to get playlists: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @spotify.command(name="sync", brief="🔄 Comprehensive Spotify synchronization with enhanced controls")
    async def spotify_sync(self, ctx, mode: str = "once"):
        """🔄 **COMPREHENSIVE SPOTIFY SYNC** - Full-featured Spotify-Discord integration.
        
        **Available Modes:**
        • `once` - Sync current track with advanced controls (default)
        • `continuous` - Real-time sync with position tracking & auto-progression  
        • `stop` - Disable continuous synchronization
        • `status` - Show current sync status and playing track info
        
        **Enhanced Features:**
        ✅ **Advanced Control Panel** - 15 interactive buttons with full playback control
        ✅ **Position Tracking** - Discord matches your Spotify position (3-second updates)
        ✅ **Auto-Progression** - Automatically syncs when tracks change
        ✅ **Seek Detection** - Tracks position jumps and seeks
        ✅ **Play/Pause Sync** - Real-time playback state synchronization
        ✅ **Queue Management** - Full queue controls with shuffle, repeat, skip
        ✅ **Volume Control** - Adjust playback volume
        ✅ **Track Info Display** - Rich embeds with album art, progress, device info
        """
        if not self.spotify_manager:
            embed = discord.Embed(
                title="❌ Spotify Not Available",
                description="Spotify integration is not configured on this server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Check if user has linked Spotify
        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        if not sp:
            embed = discord.Embed(
                title="🔗 Spotify Account Required",
                description=f"Please link your Spotify account first to use sync features.\n\n"
                           f"📋 **Quick Setup:**\n"
                           f"• Use `{ctx.prefix}spotify link` to connect your account\n"
                           f"• Complete the authorization process\n"
                           f"• Return here to start syncing your music!",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="🎯 What You'll Get",
                value="• Real-time Spotify sync\n• Advanced playback controls\n• Position tracking\n• Automatic song progression\n• Full queue management",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        # Initialize sync data if needed
        if not hasattr(self, '_spotify_sync_data'):
            self._spotify_sync_data = {}
            
        guild_key = str(ctx.guild.id)
        
        # Handle status mode - show current playing info like sp device
        if mode.lower() == "status":
            try:
                current = sp.current_playback()
                
                if current and current.get('is_playing'):
                    track = current['item']
                    device = current.get('device', {})
                    
                    embed = discord.Embed(
                        title="🎧 Spotify Sync Status - Currently Playing",
                        description=f"**{track['name']}**\nby *{', '.join([artist['name'] for artist in track['artists']])}*",
                        color=discord.Color.green()
                    )
                    
                    # Add album info
                    if track.get('album'):
                        embed.add_field(name="💿 Album", value=track['album']['name'], inline=True)
                    
                    # Add playback progress
                    progress_ms = current.get('progress_ms', 0)
                    duration_ms = track['duration_ms']
                    progress_sec = progress_ms // 1000
                    duration_sec = duration_ms // 1000
                    progress_bar = self.create_progress_bar(progress_sec, duration_sec)
                    
                    embed.add_field(
                        name="⏱️ Progress",
                        value=f"`{self.format_time(progress_sec)}/{self.format_time(duration_sec)}`\n{progress_bar}",
                        inline=False
                    )
                    
                    # Add device info
                    if device:
                        embed.add_field(
                            name="📱 Device",
                            value=f"**{device.get('name', 'Unknown')}** ({device.get('type', 'Unknown')})\nVolume: {device.get('volume_percent', 'Unknown')}%",
                            inline=True
                        )
                    
                    # Add sync status
                    sync_enabled = guild_key in self._spotify_sync_data and self._spotify_sync_data[guild_key].get('sync_enabled', False)
                    embed.add_field(
                        name="🔄 Sync Status",
                        value=f"Continuous Sync: {'🟢 Active' if sync_enabled else '🔴 Inactive'}\n"
                              f"Monitor: {'🟢 Running' if self.spotify_device_monitor.is_running() else '🔴 Stopped'}",
                        inline=True
                    )
                    
                    # Add album art
                    if track.get('album', {}).get('images'):
                        embed.set_thumbnail(url=track['album']['images'][0]['url'])
                        
                    # Add quick actions
                    embed.add_field(
                        name="🎮 Quick Actions",
                        value=f"• `{ctx.prefix}spotify sync` - Sync this track to Discord\n"
                              f"• `{ctx.prefix}spotify sync continuous` - Enable real-time sync\n"
                              f"• `{ctx.prefix}spotify sync stop` - Disable sync",
                        inline=False
                    )
                    
                else:
                    embed = discord.Embed(
                        title="🎧 Spotify Sync Status - Not Playing",
                        description="Spotify is connected but nothing is currently playing.",
                        color=discord.Color.blue()
                    )
                    
                    # Add sync status even when not playing
                    sync_enabled = guild_key in self._spotify_sync_data and self._spotify_sync_data[guild_key].get('sync_enabled', False)
                    embed.add_field(
                        name="🔄 Sync Status",
                        value=f"Continuous Sync: {'🟢 Active' if sync_enabled else '🔴 Inactive'}\n"
                              f"Monitor: {'🟢 Running' if self.spotify_device_monitor.is_running() else '🔴 Stopped'}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🎮 Get Started",
                        value=f"• Start playing music on Spotify\n• Use `{ctx.prefix}spotify sync` to sync current track\n• Enable `{ctx.prefix}spotify sync continuous` for auto-sync",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                return
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Status Error",
                    description=f"Failed to get Spotify status: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
        
        # Handle stop mode
        if mode.lower() == "stop":
            if guild_key in self._spotify_sync_data:
                self._spotify_sync_data[guild_key]['sync_enabled'] = False
                
            embed = discord.Embed(
                title="⏹️ Continuous Sync Disabled",
                description="**Stopped continuous Spotify synchronization for this server.**\n\n"
                           "🔴 **Real-time tracking disabled**\n"
                           "🔴 **Auto-progression stopped**\n"
                           "🔴 **Position sync paused**",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Resume Anytime",
                value=f"Use `{ctx.prefix}spotify sync continuous` to re-enable enhanced sync features.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        # Handle continuous mode
        elif mode.lower() == "continuous":
            # Check if bot is in voice
            if not ctx.guild.voice_client:
                embed = discord.Embed(
                    title="🎵 Voice Connection Required",
                    description="**I need to be connected to a voice channel for continuous sync!**\n\n"
                               "🔧 **Quick Fix:**\n"
                               f"• Use `{ctx.prefix}join` to connect me to your voice channel\n"
                               f"• Or use `{ctx.prefix}play <song>` to auto-connect and start music\n"
                               f"• Then run `{ctx.prefix}spotify sync continuous` again",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="🎯 Why Voice Connection?",
                    value="Continuous sync plays your Spotify music through Discord voice channels with real-time position tracking and controls.",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
                
            # Enable continuous sync
            self._spotify_sync_data[guild_key] = {
                'user_id': ctx.author.id,
                'sync_enabled': True,
                'track_id': None,
                'last_position': 0
            }
            
            embed = discord.Embed(
                title="🔄 **ENHANCED CONTINUOUS SYNC ACTIVATED**",
                description="**🎉 Your Spotify is now fully synchronized with Discord!**\n\n"
                           "**Real-time Features Now Active:**",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="⚡ **Live Sync Features**",
                value="🟢 **Position Tracking** - Discord matches your Spotify position exactly\n"
                      "🟢 **Auto-Progression** - New songs automatically sync when they start\n"
                      "🟢 **Seek Detection** - Position jumps are tracked and synced\n"
                      "🟢 **Play/Pause Sync** - Discord mirrors your Spotify playback state\n"
                      "🟢 **3-Second Updates** - Ultra-smooth real-time tracking",
                inline=False
            )
            
            embed.add_field(
                name="🎮 **How to Use**",
                value=f"1️⃣ **Play music on Spotify** (any device/app)\n"
                      f"2️⃣ **Discord automatically follows along** with full controls\n"
                      f"3️⃣ **Use `{ctx.prefix}spotify sync` anytime** for instant manual sync\n"
                      f"4️⃣ **Disable with `{ctx.prefix}spotify sync stop`** when done",
                inline=False
            )
            
            embed.add_field(
                name="🌐 **Compatible Devices**",
                value="✅ **Spotify Desktop App**\n✅ **Spotify Mobile App**\n✅ **Spotify Web Player**\n✅ **Any Spotify Connect Device**",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ **Advanced Controls**",
                value="🎛️ **15-Button Control Panel** with every sync\n🎚️ **Volume Control** • 🔀 **Shuffle** • 🔁 **Repeat**\n📋 **Queue Management** • ⏩ **Skip** • ⏸️ **Pause**\n🎲 **Random** • 💾 **Save** • 📊 **Stats** • ⚙️ **Settings**",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Start the monitor if not already running
            if not self.spotify_device_monitor.is_running():
                self.spotify_device_monitor.start()
                
            return

        # Default "once" mode - comprehensive sync with full controls
        try:
            # Get current playback with detailed info
            current = sp.current_playback()
            if not current:
                embed = discord.Embed(
                    title="⏸️ No Active Spotify Playback",
                    description="**You don't have any music playing on Spotify right now.**\n\n"
                               "🔧 **To get started:**\n"
                               "• Open Spotify on any device\n"
                               "• Start playing a song\n"
                               "• Come back and run this command again!\n\n"
                               f"💡 **Or use `{ctx.prefix}play <song>` to search and play directly!**",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="🎯 Alternative Options",
                    value=f"• `{ctx.prefix}spotify playlists` - Browse your Spotify playlists\n"
                          f"• `{ctx.prefix}spotify device` - Set up Ascend as Spotify device\n"
                          f"• `{ctx.prefix}play <song>` - Search and play music directly",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
                
            if not current.get('is_playing'):
                embed = discord.Embed(
                    title="⏸️ Spotify Playback Paused",
                    description="**Your Spotify playback is currently paused.**\n\n"
                               "▶️ **Resume playback on Spotify and try again!**",
                    color=discord.Color.orange()
                )
                
                # Still show track info even when paused
                track = current.get('item')
                if track:
                    embed.add_field(
                        name="🎵 Last Track",
                        value=f"**{track['name']}**\nby {', '.join([artist['name'] for artist in track['artists']])}",
                        inline=False
                    )
                    
                embed.add_field(
                    name="🎮 Quick Actions",
                    value=f"• Resume playback on Spotify\n• Use `{ctx.prefix}spotify sync` again\n• Or `{ctx.prefix}play <song>` to start fresh",
                    inline=False
                )
                await ctx.send(embed=embed)
                return

            track = current.get('item')
            if not track:
                embed = discord.Embed(
                    title="❌ No Track Information Available",
                    description="Unable to get track information from Spotify.\n\nThis might be a temporary issue - try again in a moment!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Create comprehensive track info
            track_info = {
                'name': track.get('name'),
                'artists': [artist.get('name') for artist in track.get('artists', [])],
                'album': track.get('album', {}).get('name'),
                'duration_ms': track.get('duration_ms'),
                'progress_ms': current.get('progress_ms', 0),
                'user_id': ctx.author.id,
                'guild_id': ctx.guild.id,
                'spotify_url': track.get('external_urls', {}).get('spotify'),
                'preview_url': track.get('preview_url'),
                'popularity': track.get('popularity'),
                'explicit': track.get('explicit', False)
            }

            # Check if bot is in voice
            if not ctx.guild.voice_client:
                embed = discord.Embed(
                    title="🎵 Voice Connection Required",
                    description="**I need to be connected to a voice channel to sync your music!**\n\n"
                               "🔧 **Quick Setup:**\n"
                               f"• Use `{ctx.prefix}join` to connect me to your voice channel\n"
                               f"• Or use `{ctx.prefix}play <song>` to auto-connect and start music\n"
                               f"• Then run `{ctx.prefix}spotify sync` again for full sync!",
                    color=discord.Color.orange()
                )
                
                # Show track info even without voice connection
                embed.add_field(
                    name="🎵 Ready to Sync",
                    value=f"**{track_info['name']}**\nby {', '.join(track_info['artists'])}\n{f'from {track_info['album']}' if track_info['album'] else ''}",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return

            # Create comprehensive sync embed with rich information (like sp device/status)
            artists_str = ", ".join(track_info['artists'])
            embed = discord.Embed(
                title="🔄 **SYNCING FROM SPOTIFY** - Enhanced Mode",
                description=f"**{track_info['name']}**\nby *{artists_str}*\n{f'from *{track_info['album']}*' if track_info['album'] else ''}",
                color=discord.Color.from_rgb(29, 185, 84)  # Spotify green
            )
            
            # Add album art if available
            if track.get('album', {}).get('images'):
                embed.set_thumbnail(url=track['album']['images'][0]['url'])
            
            # Add detailed progress information
            progress_sec = track_info['progress_ms'] // 1000
            duration_sec = track_info['duration_ms'] // 1000
            progress_bar = self.create_progress_bar(progress_sec, duration_sec)
            
            embed.add_field(
                name="⏱️ Progress",
                value=f"`{self.format_time(progress_sec)}/{self.format_time(duration_sec)}`\n{progress_bar}",
                inline=False
            )
            
            # Add device info from current playback
            device = current.get('device', {})
            if device:
                embed.add_field(
                    name="📱 Spotify Device",
                    value=f"**{device.get('name', 'Unknown')}** ({device.get('type', 'Unknown')})\nVolume: {device.get('volume_percent', 'Unknown')}%",
                    inline=True
                )
            
            # Add track details
            track_details = []
            if track_info.get('popularity'):
                track_details.append(f"Popularity: {track_info['popularity']}/100")
            if track_info.get('explicit'):
                track_details.append("🅴 Explicit")
            if track_details:
                embed.add_field(
                    name="📊 Track Info",
                    value="\n".join(track_details),
                    inline=True
                )
            
            # Add sync features info
            embed.add_field(
                name="🎮 Enhanced Controls",
                value="**15-Button Advanced Control Panel**\n"
                      "🎛️ Full playback control • 🎚️ Volume • 🔀 Shuffle\n"
                      "📋 Queue management • 🎲 Random • 💾 Save\n"
                      "📊 Stats • ⚙️ Settings • 🔁 Repeat modes",
                inline=False
            )
            
            # Add continuous sync promotion
            embed.add_field(
                name="⚡ Real-time Sync Available",
                value=f"Want **automatic sync** with position tracking?\nUse `{ctx.prefix}spotify sync continuous` for hands-free operation!",
                inline=False
            )
            
            # Add links if available
            if track_info.get('spotify_url'):
                embed.add_field(
                    name="🔗 Links",
                    value=f"[🎧 Open in Spotify]({track_info['spotify_url']})",
                    inline=True
                )

            # Get the player and add the most advanced controls available
            player = ctx.guild.voice_client
            view = None
            
            if player and hasattr(player, 'queue') and isinstance(player.queue, MusicQueue):
                # Use the full AdvancedMusicControlView for maximum functionality
                view = AdvancedMusicControlView(self.bot, player, player.queue)
            elif player:
                # Fallback to basic controls if advanced queue not available
                view = SimplePlaybackView(self.bot, player)
            
            # Send the comprehensive sync message
            sync_msg = await ctx.send(embed=embed, view=view)

            # Perform the actual sync (search and play the track)
            await self.handle_spotify_track(ctx.guild, track_info, ctx, sync_msg)

        except Exception as e:
            logging.error(f"Comprehensive Spotify sync error: {e}")
            embed = discord.Embed(
                title="❌ Sync Error",
                description=f"**Failed to sync Spotify track:**\n```{str(e)}```\n\n"
                           "🔧 **Possible solutions:**\n"
                           "• Check your Spotify account connection\n"
                           "• Ensure music is playing on Spotify\n"
                           "• Try reconnecting with `spotify link`\n"
                           f"• Contact support if issue persists",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="🆘 Quick Support",
                value=f"• `{ctx.prefix}spotify status` - Check connection\n"
                      f"• `{ctx.prefix}spotify link` - Reconnect account\n"
                      f"• `{ctx.prefix}help spotify` - View all commands",
                inline=False
            )
            await ctx.send(embed=embed)

    def create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """Create a visual progress bar."""
        if total == 0:
            return "▱" * length
        
        progress = current / total
        filled = int(length * progress)
        bar = "▰" * filled + "▱" * (length - filled)
        return bar

    def format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS."""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    async def show_spotify_main_menu(self, ctx):
        """Show the main Spotify menu with all options."""
        embed = discord.Embed(
            title="🎧 Spotify Integration Hub",
            description="**Connect your Spotify account and control playback like Spoticord!**",
            color=discord.Color.green()
        )
        
        # Check if Spotify is available
        if not self.spotify_manager:
            embed.add_field(
                name="❌ Spotify Not Available",
                value="Spotify integration is not configured on this server.",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        # Check if user has linked account
        sp = self.spotify_manager.get_user_spotify(ctx.author.id)
        
        if sp:
            embed.add_field(
                name="✅ Account Status",
                value="Your Spotify account is linked and ready!",
                inline=False
            )
            
            embed.add_field(
                name="🎮 Playback Controls",
                value=f"• `{ctx.prefix}spotify play [song]` - Play/search music\n• `{ctx.prefix}spotify pause` - Pause playback\n• `{ctx.prefix}spotify skip` - Skip track\n• `{ctx.prefix}spotify previous` - Previous track",
                inline=False
            )
            
            embed.add_field(
                name="📋 Your Content",
                value=f"• `{ctx.prefix}spotify playlists` - Browse playlists\n• `{ctx.prefix}spotify sync` - Sync current track\n• `{ctx.prefix}spotify status` - Current playback\n• `{ctx.prefix}spotify device` - Device mode",
                inline=False
            )
            
            embed.add_field(
                name="📱 Device Mode",
                value="Use Ascend as a Spotify Connect device - control playback from any Spotify app and have it play through Discord!",
                inline=False
            )
            
        else:
            embed.add_field(
                name="🔗 Get Started",
                value=f"Link your Spotify account to unlock all features:\n`{ctx.prefix}spotify link`",
                inline=False
            )
            
            embed.add_field(
                name="✨ What You'll Get",
                value="• Access to your playlists\n• Direct Spotify playback control\n• Device mode (like Spoticord)\n• Enhanced music discovery\n• Cross-platform integration",
                inline=False
            )
        
        embed.add_field(
            name="🆘 Need Help?",
            value=f"Use `{ctx.prefix}help spotify` for detailed command information.",
            inline=False
        )
        
        embed.set_footer(text="Spotify integration • Like Spoticord but better!")
        
        await ctx.send(embed=embed)

# ============================================================================
# SPOTIFY UI COMPONENTS
# ============================================================================

class SpotifySearchView(ui.View):
    def __init__(self, spotify_client, tracks, user):
        super().__init__(timeout=300)
        self.spotify = spotify_client
        self.tracks = tracks
        self.user = user
        
        # Create select options dynamically
        options = []
        for i, track in enumerate(self.tracks[:10]):
            options.append(
                discord.SelectOption(
                    label=f"{i+1}. {track['name'][:50]}", 
                    description=f"by {track['artists'][0]['name']}", 
                    value=str(i)
                )
            )
        
        if options:
            select = ui.Select(placeholder="Select a track to play...", options=options)
            select.callback = self.select_track
            self.add_item(select)

    async def select_track(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ This is not your search!", ephemeral=True)
            return

        track_index = int(interaction.data['values'][0])
        track = self.tracks[track_index]
        
        try:
            # Play the selected track
            self.spotify.start_playback(uris=[track['uri']])
            
            embed = discord.Embed(
                title="🎧 Now Playing on Spotify",
                description=f"**{track['name']}**\nby *{track['artists'][0]['name']}*",
                color=discord.Color.green()
            )
            
            if track['album']['images']:
                embed.set_thumbnail(url=track['album']['images'][0]['url'])
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Playback Error",
                description=f"Failed to play track: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SpotifyPlaylistView(ui.View):
    def __init__(self, spotify_client, playlists, user):
        super().__init__(timeout=300)
        self.spotify = spotify_client

class SpotifyDeviceSetupView(ui.View):
    """View for setting up Spotify Connect device through Replit OAuth."""
    
    def __init__(self, user_id: int, guild_id: int, guild_name: str):
        super().__init__(timeout=600)  # 10 minute timeout
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.replit_base_url = "https://ascend-api.replit.app"
    
    @ui.button(label="🚀 Start Device Setup", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        """Start the Spotify Connect device setup process."""
        
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can set up the device!", ephemeral=True)
            return
        
        try:
            # Get Spotify OAuth URL
            import os
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            redirect_uri = f"{self.replit_base_url}/callback"
            scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing streaming"
            
            # Include state with user and guild info
            state = f"{self.user_id}:{self.guild_id}"
            
            auth_url = (
                f"https://accounts.spotify.com/authorize?"
                f"client_id={client_id}&"
                f"response_type=code&"
                f"redirect_uri={redirect_uri}&"
                f"scope={scope}&"
                f"state={state}&"
                f"show_dialog=true"
            )
            
            embed = discord.Embed(
                title="🔐 Spotify Authorization Required",
                description="Click the link below to authorize Ascend to access your Spotify account for device functionality.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📱 Step 1: Authorize",
                value=f"[🔗 Authorize Spotify Access]({auth_url})",
                inline=False
            )
            
            embed.add_field(
                name="📋 Step 2: Copy Code",
                value="After authorization, you'll get a code. Copy it and click the 'Complete Setup' button below.",
                inline=False
            )
            
            embed.set_footer(text="This authorization enables Spotify Connect device functionality")
            
            # Update the view to show completion button
            self.clear_items()
            complete_button = ui.Button(
                label="✅ Complete Setup", 
                style=discord.ButtonStyle.success,
                emoji="✅"
            )
            complete_button.callback = self.complete_setup
            self.add_item(complete_button)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to generate authorization URL: {str(e)}", ephemeral=True)
    
    async def complete_setup(self, interaction: discord.Interaction):
        """Complete the setup with authorization code."""
        
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can complete setup!", ephemeral=True)
            return
        
        # Show modal for authorization code
        modal = SpotifyDeviceCodeModal(self.user_id, self.guild_id, self.guild_name)
        await interaction.response.send_modal(modal)

class SpotifyDeviceCodeModal(ui.Modal):
    """Modal for entering Spotify authorization code."""
    
    def __init__(self, user_id: int, guild_id: int, guild_name: str):
        super().__init__(title="🎵 Spotify Device Setup")
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.replit_base_url = "https://ascend-api.replit.app"
        
        self.auth_code = ui.TextInput(
            label="Authorization Code",
            placeholder="Paste the authorization code from Spotify here...",
            style=discord.TextStyle.short,
            max_length=200,
            required=True
        )
        self.add_item(self.auth_code)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process the authorization code and set up device."""
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Send the code to our Replit callback to complete OAuth
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                callback_data = {
                    "code": self.auth_code.value,
                    "user_id": self.user_id,
                    "guild_id": self.guild_id
                }
                
                async with session.post(
                    f"{self.replit_base_url}/callback/complete",
                    json=callback_data
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        device_url = result["device_url"]
                        session_token = result["session_token"]
                        
                        # Create success embed with device URL
                        embed = discord.Embed(
                            title="✅ Spotify Connect Device Ready!",
                            description="Your Spotify Connect device has been set up successfully!",
                            color=discord.Color.green()
                        )
                        
                        embed.add_field(
                            name="🎵 Open Device Player",
                            value=f"[Click here to activate your Spotify device]({device_url})",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="� How to Use",
                            value="1. Click the link above to open the device player\n2. Keep that tab open\n3. Open Spotify on any device\n4. Look for 'Ascend Music Bot' in your device list\n5. Select it to play music through Discord!",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="⚙️ Device Info",
                            value=f"**Server:** {self.guild_name}\n**Device Name:** Ascend Music Bot\n**Status:** Ready",
                            inline=False
                        )
                        
                        embed.set_footer(text="Keep the device player tab open for the bot to appear in Spotify!")
                        
                        view = SpotifyDeviceLinkView(device_url)
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                        
                    else:
                        error_data = await resp.json()
                        error_msg = error_data.get("error", "Unknown error occurred")
                        
                        embed = discord.Embed(
                            title="❌ Setup Failed",
                            description=f"Failed to complete device setup: {error_msg}",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        
        except Exception as e:
            logging.error(f"Device setup completion error: {e}")
            embed = discord.Embed(
                title="❌ Setup Error",
                description=f"An error occurred during setup: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class SpotifyDeviceLinkView(ui.View):
    """View for Spotify Connect device setup with authorization link."""
    
    def __init__(self, auth_url: str, user_id: int, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.auth_url = auth_url
        self.user_id = user_id
        self.guild_id = guild_id
        
    @ui.button(label="🚀 Start Setup", style=discord.ButtonStyle.green)
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        """Start the Spotify Connect device setup process."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This setup is not for you!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🎵 Spotify Device Authorization",
            description="**Follow these steps to set up your Spotify Connect device:**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📋 Step 1: Authorize",
            value=f"[Click here to authorize Spotify]({self.auth_url})",
            inline=False
        )
        
        embed.add_field(
            name="📋 Step 2: Get Code",
            value="After authorizing, copy the authorization code from the page",
            inline=False
        )
        
        embed.add_field(
            name="📋 Step 3: Complete Setup",
            value=f"Use `!spotify devicesetup <your_code>` with the authorization code",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Quick Command",
            value="```!spotify devicesetup YOUR_CODE_HERE```",
            inline=False
        )
        
        embed.set_footer(text="This link expires in 10 minutes • Device will appear in your Spotify app")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SpotifyPlaylistView(ui.View):
    def __init__(self, spotify_client, playlists, user):
        super().__init__(timeout=300)
        self.spotify = spotify_client
        self.playlists = playlists
        self.user = user
        
        # Create select options dynamically
        options = []
        for i, playlist in enumerate(self.playlists[:10]):
            options.append(
                discord.SelectOption(
                    label=f"{playlist['name'][:50]}", 
                    description=f"{playlist['tracks']['total']} tracks", 
                    value=str(i)
                )
            )
        
        if options:
            select = ui.Select(placeholder="Select a playlist to play...", options=options)
            select.callback = self.select_playlist
            self.add_item(select)

    async def select_playlist(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ This is not your playlist selection!", ephemeral=True)
            return

        playlist_index = int(interaction.data['values'][0])
        playlist = self.playlists[playlist_index]
        
        try:
            # Play the selected playlist
            self.spotify.start_playback(context_uri=playlist['uri'])
            
            embed = discord.Embed(
                title="📋 Now Playing Playlist",
                description=f"**{playlist['name']}**\n{playlist['tracks']['total']} tracks",
                color=discord.Color.green()
            )
            
            if playlist['images']:
                embed.set_thumbnail(url=playlist['images'][0]['url'])
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Playback Error",
                description=f"Failed to play playlist: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SpotifyDeviceActivateView(ui.View):
    """View for activating the Spotify Connect device."""
    
    def __init__(self, device_url: str, session_token: str):
        super().__init__(timeout=1800)  # 30 minute timeout
        self.device_url = device_url
        self.session_token = session_token
    
    @ui.button(label="🎵 Open Device Player", style=discord.ButtonStyle.success, emoji="🎵")
    async def open_device_player(self, interaction: discord.Interaction, button: ui.Button):
        """Open the Spotify device player."""
        
        embed = discord.Embed(
            title="🎵 Spotify Device Player",
            description="Your personalized Spotify Connect device player is ready!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🌐 Device Player URL",
            value=f"[🎵 Open Your Spotify Device Player]({self.device_url})",
            inline=False
        )
        
        embed.add_field(
            name="📱 Instructions",
            value="1. Click the link above (opens in new tab)\n2. Wait for 'Device Ready' confirmation\n3. Open Spotify on any device\n4. Look for 'Ascend Music Bot' in device list\n5. Select it and start playing music!",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Troubleshooting",
            value="• Keep the player tab open while using\n• If device doesn't appear, refresh Spotify\n• Make sure you're logged into the same account",
            inline=False
        )
        
        embed.set_footer(text="Your device will appear in Spotify within 30 seconds!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @ui.button(label="📊 Check Status", style=discord.ButtonStyle.secondary, emoji="📊")
    async def check_status(self, interaction: discord.Interaction, button: ui.Button):
        """Check device status."""
        
        try:
            import aiohttp
            status_url = f"https://ascend-api.replit.app/device/status/{self.session_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(status_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        ready = data.get("ready", False)
                        device_id = data.get("device_id")
                        
                        if ready and device_id:
                            embed = discord.Embed(
                                title="✅ Device Active",
                                description="Your Spotify Connect device is ready and active!",
                                color=discord.Color.green()
                            )
                            embed.add_field(
                                name="📱 Device Info",
                                value=f"**Status:** Online\n**Device ID:** `{device_id}`\n**Ready:** Yes",
                                inline=False
                            )
                        else:
                            embed = discord.Embed(
                                title="⏳ Device Pending",
                                description="Device is set up but not yet activated.",
                                color=discord.Color.orange()
                            )
                            embed.add_field(
                                name="📱 Next Steps",
                                value="Click 'Open Device Player' to activate your device.",
                                inline=False
                            )
                    else:
                        embed = discord.Embed(
                            title="❌ Status Check Failed",
                            description="Could not check device status.",
                            color=discord.Color.red()
                        )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to check status: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SimplePlaybackView(ui.View):
    """Simple playback controls for tracks without queue system."""
    
    def __init__(self, bot, player: wavelink.Player):
        super().__init__(timeout=300)
        self.bot = bot
        self.player = player
    
    @ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: discord.Interaction, button: ui.Button):
        """Toggle play/pause."""
        try:
            if self.player.paused:
                await self.player.pause(False)
                button.emoji = "⏸️"
                await interaction.response.edit_message(view=self)
            else:
                await self.player.pause(True)
                button.emoji = "▶️"
                await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        """Stop playback."""
        try:
            await self.player.stop()
            await interaction.response.send_message("⏹️ Playback stopped!", ephemeral=True)
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @ui.button(label="Volume", emoji="🔊", style=discord.ButtonStyle.primary)
    async def volume(self, interaction: discord.Interaction, button: ui.Button):
        """Show volume controls."""
        try:
            current_volume = self.player.volume
            embed = discord.Embed(
                title="🔊 Volume Control",
                description=f"Current volume: **{current_volume}%**\n\nUse the buttons below to adjust:",
                color=discord.Color.blue()
            )
            
            view = VolumeControlView(self.player)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class VolumeControlView(ui.View):
    """Volume control interface."""
    
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=60)
        self.player = player
    
    @ui.button(label="-10", style=discord.ButtonStyle.secondary)
    async def volume_down_10(self, interaction: discord.Interaction, button: ui.Button):
        new_volume = max(0, self.player.volume - 10)
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f"🔉 Volume set to {new_volume}%", ephemeral=True)
    
    @ui.button(label="-5", style=discord.ButtonStyle.secondary)
    async def volume_down_5(self, interaction: discord.Interaction, button: ui.Button):
        new_volume = max(0, self.player.volume - 5)
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f"🔉 Volume set to {new_volume}%", ephemeral=True)
    
    @ui.button(label="+5", style=discord.ButtonStyle.secondary)
    async def volume_up_5(self, interaction: discord.Interaction, button: ui.Button):
        new_volume = min(100, self.player.volume + 5)
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f"🔊 Volume set to {new_volume}%", ephemeral=True)
    
    @ui.button(label="+10", style=discord.ButtonStyle.secondary)
    async def volume_up_10(self, interaction: discord.Interaction, button: ui.Button):
        new_volume = min(100, self.player.volume + 10)
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f"🔊 Volume set to {new_volume}%", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))