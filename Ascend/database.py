import sqlite3
import asyncio
import aiosqlite
import datetime
from typing import Optional, Dict, Any, List
import json

class DatabaseManager:
    def __init__(self, db_path: str = "ascend_bot.db"):
        self.db_path = db_path
        
    async def initialize_database(self):
        """Initialize the database with all required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    display_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_commands_used INTEGER DEFAULT 0,
                    premium_status BOOLEAN DEFAULT FALSE,
                    premium_expires TIMESTAMP NULL,
                    settings TEXT DEFAULT '{}',
                    spotify_connected BOOLEAN DEFAULT FALSE,
                    spotify_tokens TEXT DEFAULT NULL
                )
            """)
            
            # Guilds table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT NOT NULL,
                    owner_id INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prefix TEXT DEFAULT '!',
                    dj_role_id INTEGER NULL,
                    music_channel_id INTEGER NULL,
                    volume_limit INTEGER DEFAULT 100,
                    settings TEXT DEFAULT '{}',
                    total_songs_played INTEGER DEFAULT 0,
                    is_premium BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Music history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS music_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    track_title TEXT NOT NULL,
                    track_artist TEXT,
                    track_url TEXT,
                    platform TEXT DEFAULT 'youtube',
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration INTEGER DEFAULT 0,
                    FOREIGN KEY (guild_id) REFERENCES guilds (guild_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Playlists table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_public BOOLEAN DEFAULT FALSE,
                    play_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Playlist tracks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER,
                    track_title TEXT NOT NULL,
                    track_artist TEXT,
                    track_url TEXT,
                    platform TEXT DEFAULT 'youtube',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    position INTEGER,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id)
                )
            """)
            
            # Bot statistics table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE DEFAULT CURRENT_DATE,
                    commands_executed INTEGER DEFAULT 0,
                    songs_played INTEGER DEFAULT 0,
                    users_active INTEGER DEFAULT 0,
                    guilds_active INTEGER DEFAULT 0,
                    uptime_seconds INTEGER DEFAULT 0
                )
            """)
            
            # Command usage table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS command_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    command_name TEXT NOT NULL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
                )
            """)
            
            await db.commit()
            print("✅ Database initialized successfully")

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data from database"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    user_data = dict(row)
                    # Parse Spotify tokens if available
                    if user_data.get('spotify_tokens'):
                        try:
                            spotify_data = json.loads(user_data['spotify_tokens'])
                            user_data.update(spotify_data)
                        except json.JSONDecodeError:
                            pass
                    return user_data
                return None

    async def create_user(self, user_id: int, username: str, display_name: str = None) -> bool:
        """Create a new user account"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO users (user_id, username, display_name)
                    VALUES (?, ?, ?)
                """, (user_id, username, display_name or username))
                await db.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # User already exists

    async def update_user_activity(self, user_id: int):
        """Update user's last activity and command count"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET last_active = CURRENT_TIMESTAMP, 
                    total_commands_used = total_commands_used + 1
                WHERE user_id = ?
            """, (user_id,))
            await db.commit()

    async def get_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get guild data from database"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_guild(self, guild_id: int, guild_name: str, owner_id: int, prefix: str = "!") -> bool:
        """Create a new guild entry"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO guilds (guild_id, guild_name, owner_id, prefix)
                    VALUES (?, ?, ?, ?)
                """, (guild_id, guild_name, owner_id, prefix))
                await db.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Guild already exists

    async def update_guild_prefix(self, guild_id: int, prefix: str) -> bool:
        """Update guild's command prefix"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE guilds SET prefix = ? WHERE guild_id = ?", (prefix, guild_id))
            await db.commit()
            return True

    async def log_command_usage(self, user_id: int, guild_id: int, command_name: str, success: bool = True):
        """Log command usage statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO command_usage (user_id, guild_id, command_name, success)
                VALUES (?, ?, ?, ?)
            """, (user_id, guild_id, command_name, success))
            await db.commit()

    async def log_music_play(self, guild_id: int, user_id: int, track_title: str, 
                           track_artist: str = None, track_url: str = None, 
                           platform: str = "youtube", duration: int = 0):
        """Log music playback"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO music_history (guild_id, user_id, track_title, track_artist, 
                                         track_url, platform, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, track_title, track_artist, track_url, platform, duration))
            
            # Update guild stats
            await db.execute("""
                UPDATE guilds SET total_songs_played = total_songs_played + 1 
                WHERE guild_id = ?
            """, (guild_id,))
            await db.commit()

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Basic user stats
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()
            
            if not user_data:
                return {}
            
            # Command usage stats
            async with db.execute("""
                SELECT command_name, COUNT(*) as count 
                FROM command_usage 
                WHERE user_id = ? 
                GROUP BY command_name 
                ORDER BY count DESC
            """, (user_id,)) as cursor:
                command_stats = await cursor.fetchall()
            
            # Music history stats
            async with db.execute("""
                SELECT COUNT(*) as total_songs, 
                       COUNT(DISTINCT guild_id) as servers_used,
                       AVG(duration) as avg_duration
                FROM music_history 
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                music_stats = await cursor.fetchone()
            
            return {
                'user_data': dict(user_data),
                'command_stats': [dict(row) for row in command_stats],
                'music_stats': dict(music_stats) if music_stats else {}
            }

    async def get_guild_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get comprehensive guild statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Basic guild stats
            async with db.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)) as cursor:
                guild_data = await cursor.fetchone()
            
            if not guild_data:
                return {}
            
            # Top users in guild
            async with db.execute("""
                SELECT user_id, COUNT(*) as command_count
                FROM command_usage 
                WHERE guild_id = ? 
                GROUP BY user_id 
                ORDER BY command_count DESC 
                LIMIT 10
            """, (guild_id,)) as cursor:
                top_users = await cursor.fetchall()
            
            # Most played songs
            async with db.execute("""
                SELECT track_title, track_artist, COUNT(*) as play_count
                FROM music_history 
                WHERE guild_id = ? 
                GROUP BY track_title, track_artist 
                ORDER BY play_count DESC 
                LIMIT 10
            """, (guild_id,)) as cursor:
                top_songs = await cursor.fetchall()
            
            return {
                'guild_data': dict(guild_data),
                'top_users': [dict(row) for row in top_users],
                'top_songs': [dict(row) for row in top_songs]
            }

    async def create_playlist(self, user_id: int, name: str, description: str = None, is_public: bool = False) -> int:
        """Create a new playlist and return its ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO playlists (user_id, name, description, is_public)
                VALUES (?, ?, ?, ?)
            """, (user_id, name, description, is_public))
            await db.commit()
            return cursor.lastrowid

    async def get_user_playlists(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all playlists for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT p.*, COUNT(pt.id) as track_count
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                WHERE p.user_id = ?
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """, (user_id,)) as cursor:
                playlists = await cursor.fetchall()
                return [dict(row) for row in playlists]

    async def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user data with provided fields"""
        if not kwargs:
            return False
        
        # Build dynamic update query
        set_clauses = []
        values = []
        
        for field, value in kwargs.items():
            if field in ['display_name', 'username', 'premium_status', 'spotify_connected', 'spotify_tokens', 'settings']:
                set_clauses.append(f"{field} = ?")
                values.append(value)
        
        if not set_clauses:
            return False
        
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(set_clauses)}, last_active = CURRENT_TIMESTAMP WHERE user_id = ?"
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, values)
            await db.commit()
            return True

    async def update_user_settings(self, user_id: int, settings: dict) -> bool:
        """Update user settings"""
        settings_json = json.dumps(settings)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET settings = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (settings_json, user_id))
            await db.commit()
            return True

    async def get_user_settings(self, user_id: int) -> dict:
        """Get user settings"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return {}

    async def update_guild_settings(self, guild_id: int, settings: dict) -> bool:
        """Update guild settings"""
        settings_json = json.dumps(settings)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE guilds 
                SET settings = ?
                WHERE guild_id = ?
            """, (settings_json, guild_id))
            await db.commit()
            return True

    async def update_user_spotify_data(self, user_id: int, spotify_data: dict) -> bool:
        """Update user's Spotify connection data"""
        # Convert spotify_data to a format that can be stored
        # We'll store some fields directly and others in the spotify_tokens field
        
        spotify_connected = spotify_data.get('spotify_connected', False)
        
        # Store tokens and sensitive data in JSON format
        token_data = {}
        if spotify_data.get('spotify_access_token'):
            token_data['access_token'] = spotify_data['spotify_access_token']
        if spotify_data.get('spotify_refresh_token'):
            token_data['refresh_token'] = spotify_data['spotify_refresh_token']
        if spotify_data.get('spotify_token_expires_at'):
            token_data['expires_at'] = spotify_data['spotify_token_expires_at']
        if spotify_data.get('spotify_state'):
            token_data['state'] = spotify_data['spotify_state']
        
        # Store other Spotify metadata
        for key in ['spotify_id', 'spotify_display_name', 'spotify_email', 'spotify_followers', 
                   'spotify_username', 'spotify_link_pending', 'spotify_link_timestamp',
                   'spotify_connected_at', 'spotify_unlinked_at']:
            if key in spotify_data:
                token_data[key] = spotify_data[key]
        
        tokens_json = json.dumps(token_data) if token_data else None
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET spotify_connected = ?, spotify_tokens = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (spotify_connected, tokens_json, user_id))
            await db.commit()
            return True

    async def get_user_spotify_data(self, user_id: int) -> dict:
        """Get user's Spotify connection data"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT spotify_connected, spotify_tokens FROM users WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    spotify_data = {
                        'spotify_connected': bool(row[0]),
                    }
                    if row[1]:
                        try:
                            token_data = json.loads(row[1])
                            spotify_data.update(token_data)
                        except json.JSONDecodeError:
                            pass
                    return spotify_data
                return {'spotify_connected': False}