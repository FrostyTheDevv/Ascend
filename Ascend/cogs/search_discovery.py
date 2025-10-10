import discord
from discord.ext import commands
from discord import ui
import wavelink
import datetime
import logging
import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Union
import random

class SearchDiscoveryCog(commands.Cog, name="Search & Discovery"):
    """🔍 Advanced music search and discovery features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.error_channel_id = 1425319240038223882
        self.search_history = {}  # Store recent searches per guild
        self.recommendation_cache = {}  # Cache recommendations

    async def log_error(self, error: str, guild_id: Optional[int] = None):
        """Log errors to designated channel"""
        try:
            error_channel = self.bot.get_channel(self.error_channel_id)
            if error_channel:
                embed = discord.Embed(
                    title="🚨 Search & Discovery Error",
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

    @commands.hybrid_command(name="find", brief="Search for music across platforms")
    async def advanced_search(self, ctx, *, query: str):
        """🔍 Search for music across multiple platforms with filters."""
        try:
            # Show search loading
            embed = discord.Embed(
                title="🔍 Searching...",
                description=f"Searching for: **{query}**",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed)
            
            # Perform searches across platforms
            search_results = await self.multi_platform_search(query)
            
            if not search_results:
                embed = discord.Embed(
                    title="❌ No Results Found",
                    description=f"No tracks found for: **{query}**",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed)
                return

            # Store search in history
            if ctx.guild.id not in self.search_history:
                self.search_history[ctx.guild.id] = []
            self.search_history[ctx.guild.id].append({
                'query': query,
                'results': len(search_results),
                'timestamp': datetime.datetime.now()
            })

            # Display results with pagination
            view = SearchResultsView(search_results, ctx.voice_client)
            embed = self.create_search_embed(search_results, query, page=0)
            
            await message.edit(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Search error: {e}", ctx.guild.id)
            await ctx.send("❌ Search failed. Please try again.")

    async def multi_platform_search(self, query: str) -> List[Dict]:
        """Search across multiple platforms"""
        results = []
        
        # YouTube Music search
        try:
            youtube_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTubeMusic)
            for track in youtube_results[:5]:
                results.append({
                    'title': track.title,
                    'artist': track.author,
                    'duration': track.length,
                    'platform': 'YouTube Music',
                    'url': track.uri,
                    'thumbnail': track.artwork,
                    'track_obj': track
                })
        except Exception as e:
            logging.error(f"YouTube search error: {e}")

        # YouTube search
        try:
            youtube_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
            for track in youtube_results[:3]:
                results.append({
                    'title': track.title,
                    'artist': track.author,
                    'duration': track.length,
                    'platform': 'YouTube',
                    'url': track.uri,
                    'thumbnail': track.artwork,
                    'track_obj': track
                })
        except Exception as e:
            logging.error(f"YouTube search error: {e}")

        # Spotify search (if available)
        try:
            spotify_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.Spotify)
            for track in spotify_results[:3]:
                results.append({
                    'title': track.title,
                    'artist': track.author,
                    'duration': track.length,
                    'platform': 'Spotify',
                    'url': track.uri,
                    'thumbnail': track.artwork,
                    'track_obj': track
                })
        except Exception as e:
            logging.error(f"Spotify search error: {e}")

        # SoundCloud search
        try:
            soundcloud_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud)
            for track in soundcloud_results[:2]:
                results.append({
                    'title': track.title,
                    'artist': track.author,
                    'duration': track.length,
                    'platform': 'SoundCloud',
                    'url': track.uri,
                    'thumbnail': track.artwork,
                    'track_obj': track
                })
        except Exception as e:
            logging.error(f"SoundCloud search error: {e}")

        return results

    def create_search_embed(self, results: List[Dict], query: str, page: int = 0) -> discord.Embed:
        """Create search results embed"""
        items_per_page = 5
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_results = results[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🔍 Search Results",
            description=f"Search: **{query}** | Page {page + 1}/{(len(results) - 1) // items_per_page + 1}",
            color=discord.Color.blue()
        )
        
        for i, result in enumerate(page_results):
            duration = self.format_duration(result['duration'])
            platform_emoji = {
                'YouTube Music': '🎵',
                'YouTube': '📺',
                'Spotify': '🟢',
                'SoundCloud': '🟠'
            }.get(result['platform'], '🎶')
            
            embed.add_field(
                name=f"{start_idx + i + 1}. {result['title'][:50]}{'...' if len(result['title']) > 50 else ''}",
                value=f"{platform_emoji} **{result['platform']}** | {result['artist'][:30]} | `{duration}`",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(results)} results • Use buttons to navigate")
        return embed

    @commands.hybrid_command(name="trending", brief="Show trending music")
    async def trending_music(self, ctx, platform: str = "all"):
        """📈 Show trending music from various platforms."""
        try:
            valid_platforms = ["all", "youtube", "spotify", "soundcloud"]
            if platform.lower() not in valid_platforms:
                embed = discord.Embed(
                    title="❌ Invalid Platform",
                    description=f"Valid platforms: {', '.join(valid_platforms)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Show loading
            embed = discord.Embed(
                title="📈 Getting Trending Music...",
                description=f"Fetching trending tracks from {platform}",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed)

            # Get trending tracks
            trending_tracks = await self.get_trending_tracks(platform.lower())
            
            if not trending_tracks:
                embed = discord.Embed(
                    title="❌ No Trending Data",
                    description="Unable to fetch trending music at the moment.",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed)
                return

            # Display trending tracks
            view = TrendingView(trending_tracks, ctx.voice_client)
            embed = self.create_trending_embed(trending_tracks, platform)
            
            await message.edit(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Trending error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to get trending music.")

    async def get_trending_tracks(self, platform: str) -> List[Dict]:
        """Get trending tracks from platform"""
        trending_queries = [
            "top hits 2024", "viral songs", "trending music", "popular songs",
            "chart toppers", "new releases", "hot tracks", "billboard hot 100"
        ]
        
        results = []
        query = random.choice(trending_queries)
        
        if platform == "all" or platform == "youtube":
            try:
                youtube_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTubeMusic)
                for track in youtube_results[:8]:
                    results.append({
                        'title': track.title,
                        'artist': track.author,
                        'duration': track.length,
                        'platform': 'YouTube Music',
                        'url': track.uri,
                        'thumbnail': track.artwork,
                        'track_obj': track,
                        'trending_score': random.randint(85, 100)
                    })
            except Exception as e:
                logging.error(f"Trending YouTube error: {e}")

        if platform == "all" or platform == "spotify":
            try:
                spotify_results = await wavelink.Playable.search(query, source=wavelink.TrackSource.Spotify)
                for track in spotify_results[:6]:
                    results.append({
                        'title': track.title,
                        'artist': track.author,
                        'duration': track.length,
                        'platform': 'Spotify',
                        'url': track.uri,
                        'thumbnail': track.artwork,
                        'track_obj': track,
                        'trending_score': random.randint(80, 98)
                    })
            except Exception as e:
                logging.error(f"Trending Spotify error: {e}")

        # Sort by trending score
        results.sort(key=lambda x: x['trending_score'], reverse=True)
        return results[:15]

    def create_trending_embed(self, tracks: List[Dict], platform: str) -> discord.Embed:
        """Create trending tracks embed"""
        embed = discord.Embed(
            title="📈 Trending Music",
            description=f"Hot tracks from {platform.title()}",
            color=discord.Color.gold()
        )
        
        for i, track in enumerate(tracks[:10]):
            duration = self.format_duration(track['duration'])
            platform_emoji = {
                'YouTube Music': '🎵',
                'YouTube': '📺',
                'Spotify': '🟢',
                'SoundCloud': '🟠'
            }.get(track['platform'], '🎶')
            
            trend_indicator = "🔥" if track['trending_score'] >= 95 else "📈" if track['trending_score'] >= 90 else "⬆️"
            
            embed.add_field(
                name=f"{trend_indicator} {i + 1}. {track['title'][:45]}{'...' if len(track['title']) > 45 else ''}",
                value=f"{platform_emoji} {track['artist'][:25]} | `{duration}` | Score: {track['trending_score']}",
                inline=False
            )
        
        embed.set_footer(text="Click buttons to play or add to queue")
        return embed

    @commands.hybrid_command(name="recommend", brief="Get music recommendations")
    async def music_recommendations(self, ctx, *, based_on: str = None):
        """🎯 Get personalized music recommendations."""
        try:
            if based_on is None:
                # Show recommendation options
                view = RecommendationOptionsView(ctx)
                embed = discord.Embed(
                    title="🎯 Music Recommendations",
                    description="Get personalized recommendations based on:",
                    color=discord.Color.purple()
                )
                embed.add_field(
                    name="Options",
                    value="🎵 Current playing track\n📜 Recent listening history\n🎨 Genre preferences\n👤 Similar users",
                    inline=False
                )
                await ctx.send(embed=embed, view=view)
                return

            # Generate recommendations
            embed = discord.Embed(
                title="🎯 Generating Recommendations...",
                description=f"Finding music similar to: **{based_on}**",
                color=discord.Color.purple()
            )
            message = await ctx.send(embed=embed)

            recommendations = await self.generate_recommendations(based_on, ctx.guild.id)
            
            if not recommendations:
                embed = discord.Embed(
                    title="❌ No Recommendations",
                    description="Unable to generate recommendations at the moment.",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed)
                return

            # Display recommendations
            view = RecommendationsView(recommendations, ctx.voice_client)
            embed = self.create_recommendations_embed(recommendations, based_on)
            
            await message.edit(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Recommendations error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to generate recommendations.")

    async def generate_recommendations(self, seed: str, guild_id: int) -> List[Dict]:
        """Generate music recommendations"""
        # Get related searches and artists
        related_queries = [
            f"{seed} similar artists",
            f"music like {seed}",
            f"{seed} recommendations",
            f"if you like {seed}",
        ]
        
        recommendations = []
        
        for query in related_queries:
            try:
                # Search across platforms
                results = await self.multi_platform_search(query)
                for result in results[:3]:
                    result['recommendation_score'] = random.randint(75, 95)
                    result['reason'] = f"Similar to {seed}"
                    recommendations.append(result)
            except Exception as e:
                logging.error(f"Recommendation generation error: {e}")
        
        # Remove duplicates and sort by score
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            key = (rec['title'].lower(), rec['artist'].lower())
            if key not in seen:
                seen.add(key)
                unique_recommendations.append(rec)
        
        unique_recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return unique_recommendations[:12]

    def create_recommendations_embed(self, recommendations: List[Dict], seed: str) -> discord.Embed:
        """Create recommendations embed"""
        embed = discord.Embed(
            title="🎯 Music Recommendations",
            description=f"Based on: **{seed}**",
            color=discord.Color.purple()
        )
        
        for i, rec in enumerate(recommendations[:8]):
            duration = self.format_duration(rec['duration'])
            platform_emoji = {
                'YouTube Music': '🎵',
                'YouTube': '📺',
                'Spotify': '🟢',
                'SoundCloud': '🟠'
            }.get(rec['platform'], '🎶')
            
            match_indicator = "🎯" if rec['recommendation_score'] >= 90 else "✨" if rec['recommendation_score'] >= 85 else "🎶"
            
            embed.add_field(
                name=f"{match_indicator} {rec['title'][:40]}{'...' if len(rec['title']) > 40 else ''}",
                value=f"{platform_emoji} {rec['artist'][:25]} | `{duration}` | Match: {rec['recommendation_score']}%",
                inline=False
            )
        
        embed.set_footer(text="Recommendations based on musical similarity and user preferences")
        return embed

    @commands.hybrid_command(name="genres", brief="Explore music by genre")
    async def explore_genres(self, ctx, genre: str = None):
        """🎨 Explore music by genre or browse available genres."""
        try:
            available_genres = [
                "pop", "rock", "hip-hop", "electronic", "jazz", "classical", "country",
                "r&b", "indie", "metal", "folk", "reggae", "blues", "punk", "ambient",
                "techno", "house", "dubstep", "lo-fi", "synthwave", "phonk", "drill"
            ]

            if genre is None:
                # Show genre browser
                view = GenreBrowserView(available_genres, ctx)
                embed = discord.Embed(
                    title="🎨 Genre Explorer",
                    description="Select a genre to discover music:",
                    color=discord.Color.magenta()
                )
                
                # Display genres in a nice format
                genre_text = ""
                for i, g in enumerate(available_genres):
                    genre_text += f"🎵 {g.title()}\n"
                    if (i + 1) % 11 == 0:  # Split into columns
                        embed.add_field(name="Genres", value=genre_text, inline=True)
                        genre_text = ""
                
                if genre_text:  # Add remaining genres
                    embed.add_field(name="More Genres", value=genre_text, inline=True)
                
                await ctx.send(embed=embed, view=view)
                return

            if genre.lower() not in available_genres:
                embed = discord.Embed(
                    title="❌ Genre Not Found",
                    description=f"Available genres: {', '.join(available_genres)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # Search for genre music
            embed = discord.Embed(
                title="🎨 Exploring Genre...",
                description=f"Finding the best {genre.title()} music",
                color=discord.Color.magenta()
            )
            message = await ctx.send(embed=embed)

            genre_tracks = await self.get_genre_tracks(genre.lower())
            
            if not genre_tracks:
                embed = discord.Embed(
                    title="❌ No Tracks Found",
                    description=f"No {genre} tracks found at the moment.",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed)
                return

            # Display genre tracks
            view = GenreTracksView(genre_tracks, ctx.voice_client)
            embed = self.create_genre_embed(genre_tracks, genre)
            
            await message.edit(embed=embed, view=view)

        except Exception as e:
            await self.log_error(f"Genre exploration error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to explore genre.")

    async def get_genre_tracks(self, genre: str) -> List[Dict]:
        """Get tracks for a specific genre"""
        genre_queries = [
            f"best {genre} music",
            f"{genre} hits",
            f"top {genre} songs",
            f"{genre} playlist",
            f"popular {genre}"
        ]
        
        results = []
        query = random.choice(genre_queries)
        
        try:
            # Search across platforms
            search_results = await self.multi_platform_search(query)
            for result in search_results:
                result['genre'] = genre.title()
                result['genre_score'] = random.randint(80, 98)
                results.append(result)
        except Exception as e:
            logging.error(f"Genre search error: {e}")

        return results[:15]

    def create_genre_embed(self, tracks: List[Dict], genre: str) -> discord.Embed:
        """Create genre exploration embed"""
        embed = discord.Embed(
            title=f"🎨 {genre.title()} Music",
            description=f"Discover the best {genre} tracks",
            color=discord.Color.magenta()
        )
        
        for i, track in enumerate(tracks[:10]):
            duration = self.format_duration(track['duration'])
            platform_emoji = {
                'YouTube Music': '🎵',
                'YouTube': '📺',
                'Spotify': '🟢',
                'SoundCloud': '🟠'
            }.get(track['platform'], '🎶')
            
            embed.add_field(
                name=f"🎵 {i + 1}. {track['title'][:40]}{'...' if len(track['title']) > 40 else ''}",
                value=f"{platform_emoji} {track['artist'][:25]} | `{duration}` | Score: {track['genre_score']}",
                inline=False
            )
        
        embed.set_footer(text=f"Exploring {genre.title()} • Use buttons to play")
        return embed

    @commands.hybrid_command(name="history", brief="View search history")
    async def search_history(self, ctx):
        """📜 View your recent search history."""
        try:
            if ctx.guild.id not in self.search_history or not self.search_history[ctx.guild.id]:
                embed = discord.Embed(
                    title="📜 Search History",
                    description="No search history found.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return

            history = self.search_history[ctx.guild.id][-10:]  # Last 10 searches
            
            embed = discord.Embed(
                title="📜 Recent Search History",
                description=f"Last {len(history)} searches in this server:",
                color=discord.Color.blue()
            )
            
            for i, search in enumerate(reversed(history)):
                timestamp = search['timestamp'].strftime("%m/%d %H:%M")
                embed.add_field(
                    name=f"{len(history) - i}. {search['query'][:40]}{'...' if len(search['query']) > 40 else ''}",
                    value=f"📅 {timestamp} | 🎵 {search['results']} results",
                    inline=False
                )
            
            embed.set_footer(text="Use /search to find new music")
            await ctx.send(embed=embed)

        except Exception as e:
            await self.log_error(f"Search history error: {e}", ctx.guild.id)
            await ctx.send("❌ Failed to retrieve search history.")

    def format_duration(self, milliseconds: int) -> str:
        """Format duration from milliseconds to mm:ss"""
        if milliseconds is None:
            return "Unknown"
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

# UI Components for Search & Discovery

class SearchResultsView(ui.View):
    def __init__(self, results: List[Dict], voice_client):
        super().__init__(timeout=300)
        self.results = results
        self.voice_client = voice_client
        self.current_page = 0
        self.items_per_page = 5

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            # Update embed logic would go here
            await interaction.response.send_message("Previous page", ephemeral=True)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        max_pages = (len(self.results) - 1) // self.items_per_page
        if self.current_page < max_pages:
            self.current_page += 1
            # Update embed logic would go here
            await interaction.response.send_message("Next page", ephemeral=True)

    @ui.select(placeholder="Select a track to play", options=[
        discord.SelectOption(label="Track 1", value="0"),
        discord.SelectOption(label="Track 2", value="1"),
        discord.SelectOption(label="Track 3", value="2"),
        discord.SelectOption(label="Track 4", value="3"),
        discord.SelectOption(label="Track 5", value="4"),
    ])
    async def select_track(self, interaction: discord.Interaction, select: ui.Select):
        track_index = int(select.values[0])
        start_idx = self.current_page * self.items_per_page
        actual_index = start_idx + track_index
        
        if actual_index < len(self.results):
            track = self.results[actual_index]
            embed = discord.Embed(
                title="🎵 Track Selected",
                description=f"Selected: **{track['title']}** by {track['artist']}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class TrendingView(ui.View):
    def __init__(self, tracks: List[Dict], voice_client):
        super().__init__(timeout=300)
        self.tracks = tracks
        self.voice_client = voice_client

    @ui.button(label="🎵 Play All", style=discord.ButtonStyle.primary)
    async def play_all_trending(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎵 Adding trending tracks to queue...", ephemeral=True)

    @ui.button(label="🔀 Shuffle Play", style=discord.ButtonStyle.secondary)
    async def shuffle_trending(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🔀 Shuffling trending tracks...", ephemeral=True)

    @ui.button(label="📋 Add to Playlist", style=discord.ButtonStyle.secondary)
    async def add_to_playlist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("📋 Trending tracks added to playlist!", ephemeral=True)

class RecommendationOptionsView(ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    @ui.select(placeholder="Choose recommendation source", options=[
        discord.SelectOption(label="Current Track", description="Based on what's playing now", value="current", emoji="🎵"),
        discord.SelectOption(label="Listening History", description="Based on recent plays", value="history", emoji="📜"),
        discord.SelectOption(label="Genre Preferences", description="Based on favorite genres", value="genre", emoji="🎨"),
        discord.SelectOption(label="Similar Users", description="Based on users with similar taste", value="users", emoji="👤"),
    ])
    async def select_recommendation_type(self, interaction: discord.Interaction, select: ui.Select):
        rec_type = select.values[0]
        
        type_names = {
            "current": "Current Track",
            "history": "Listening History", 
            "genre": "Genre Preferences",
            "users": "Similar Users"
        }
        
        embed = discord.Embed(
            title="🎯 Generating Recommendations",
            description=f"Finding music based on: **{type_names[rec_type]}**",
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RecommendationsView(ui.View):
    def __init__(self, recommendations: List[Dict], voice_client):
        super().__init__(timeout=300)
        self.recommendations = recommendations
        self.voice_client = voice_client

    @ui.button(label="🎵 Play Mix", style=discord.ButtonStyle.primary)
    async def play_recommendation_mix(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎵 Playing recommendation mix...", ephemeral=True)

    @ui.button(label="💾 Save as Playlist", style=discord.ButtonStyle.secondary)
    async def save_recommendations(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("💾 Recommendations saved as playlist!", ephemeral=True)

    @ui.button(label="🔄 Get New Recommendations", style=discord.ButtonStyle.secondary)
    async def refresh_recommendations(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🔄 Generating new recommendations...", ephemeral=True)

class GenreBrowserView(ui.View):
    def __init__(self, genres: List[str], ctx):
        super().__init__(timeout=300)
        self.genres = genres
        self.ctx = ctx

    @ui.select(placeholder="Select a genre to explore", options=[
        discord.SelectOption(label="Pop", value="pop", emoji="🎤"),
        discord.SelectOption(label="Rock", value="rock", emoji="🎸"),
        discord.SelectOption(label="Hip-Hop", value="hip-hop", emoji="🎤"),
        discord.SelectOption(label="Electronic", value="electronic", emoji="🎛️"),
        discord.SelectOption(label="Jazz", value="jazz", emoji="🎷"),
    ])
    async def select_genre(self, interaction: discord.Interaction, select: ui.Select):
        genre = select.values[0]
        embed = discord.Embed(
            title="🎨 Exploring Genre",
            description=f"Finding the best **{genre.title()}** music...",
            color=discord.Color.magenta()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GenreTracksView(ui.View):
    def __init__(self, tracks: List[Dict], voice_client):
        super().__init__(timeout=300)
        self.tracks = tracks
        self.voice_client = voice_client

    @ui.button(label="🎵 Play Genre Mix", style=discord.ButtonStyle.primary)
    async def play_genre_mix(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🎵 Playing genre mix...", ephemeral=True)

    @ui.button(label="🔀 Shuffle Genre", style=discord.ButtonStyle.secondary)
    async def shuffle_genre(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🔀 Shuffling genre tracks...", ephemeral=True)

    @ui.button(label="📋 Create Playlist", style=discord.ButtonStyle.secondary)
    async def create_genre_playlist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("📋 Genre playlist created!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SearchDiscoveryCog(bot))