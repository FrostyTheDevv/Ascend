# Ascend Discord Music Bot

## Overview

Ascend is a fully-featured Discord music bot inspired by Spoticord, designed to play music in Discord voice channels with extensive Spotify integration. The bot uses Lavalink v4+ as an external audio processing server and supports multiple music sources including Spotify, YouTube, Bandcamp, SoundCloud, Twitch, and more. Built with Discord.py and Wavelink 3.4.1, it provides comprehensive music controls via slash commands.

## Recent Changes

- **2025-10-06**: Complete implementation of Ascend bot
  - Implemented core bot structure with Discord.py slash commands
  - Integrated Wavelink 3.4.1 for Lavalink audio streaming
  - Added Spotify support via Lavalink's LavaSrc plugin
  - Created comprehensive music commands (play, pause, skip, etc.)
  - Implemented queue management system with loop modes
  - Added advanced controls (volume, seek, previous, nowplaying)
  - Created Spotify-specific commands for playlists and albums
  - Integrated Replit authentication for Discord and Spotify
  - Fixed playlist autoplay functionality
  - Fixed queue clearing to reset all state

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Technology**: Discord.py with commands and app_commands (slash commands) support
- **Rationale**: Discord.py provides a robust Python framework for Discord bots with built-in support for both traditional prefix commands and modern slash commands
- **Design Pattern**: Cog-based architecture for modular command organization
- **Intents**: Configured with message_content, voice_states, and guilds intents to support music playback and command handling

### Audio Streaming Architecture
- **Solution**: Lavalink server (v4.0+) as external audio processing service
- **Connection**: Wavelink 3.4.1 library for Python-to-Lavalink communication
- **Spotify Support**: LavaSrc plugin (v4.2.0) configured in Lavalink for Spotify track resolution
- **Rationale**: Offloading audio processing to a dedicated Lavalink server reduces bot resource usage and provides better audio quality
- **Configuration**: Single node setup with customizable host, port, and password authentication
- **Supported Sources**: Spotify (via LavaSrc), YouTube, Bandcamp, SoundCloud, Twitch, Vimeo, HTTP streams
- **Important**: Wavelink 3.4.1 removed built-in Spotify support; all Spotify functionality now requires LavaSrc plugin on Lavalink server

### Queue Management System
- **Implementation**: Custom Queue class with track history tracking
- **Features**:
  - Linear queue with FIFO (First In, First Out) processing
  - Playback history for previous track functionality
  - Loop modes: off, track (repeat current), queue (repeat all)
  - Multiple track addition support for playlists
- **Rationale**: Custom implementation provides fine-grained control over playback logic and loop behaviors

### Configuration Management
- **Approach**: Environment variable-based configuration with dotenv
- **Settings Managed**:
  - Discord bot credentials (token, client ID, client secret)
  - Spotify API credentials and redirect URI
  - Lavalink server connection details
  - Bot command prefix
- **Rationale**: Environment variables enable secure credential management and easy deployment configuration changes

### Authentication System
- **Replit Integration**: ReplitAuth class for Replit-specific authentication
- **Token Management**: Supports both REPL_IDENTITY and WEB_REPL_RENEWAL tokens
- **API Communication**: Uses Replit Connectors API for OAuth credential retrieval
- **Token Refresh Logic**: Includes expiration checking and automatic token renewal for Discord connections
- **Rationale**: Enables seamless integration with Replit's authentication system for managed OAuth flows

## External Dependencies

### Music Services
- **Lavalink Server**: Self-hosted audio processing server (v4.0+)
  - Handles audio streaming, transcoding, and playback
  - Requires separate deployment with application.yml configuration
  - Communicates via WebSocket on port 2333 (configurable)

- **Spotify API**: Music metadata and playlist resolution
  - Requires client ID and client secret credentials
  - Uses SpotifyOAuth for authentication flow
  - Redirect URI configured for OAuth callbacks

### Discord Platform
- **Discord Bot API**: Core bot functionality
  - Requires bot token for authentication
  - Uses OAuth2 with client ID and client secret
  - Supports both REST API and Gateway connections

### Python Libraries
- **discord.py**: Discord bot framework (v2.6.3) with slash command support
- **wavelink**: Lavalink client library (v3.4.1) for audio streaming
- **spotipy**: Spotify Web API wrapper (v2.25.1) for direct Spotify API access
- **aiohttp**: Asynchronous HTTP client for API requests
- **python-dotenv**: Environment variable management

### Lavalink Plugins
- **LavaSrc** (v4.2.0): Spotify track resolution and search
  - Configured in Lavalink's application.yml
  - Requires Spotify client ID and secret
  - Enables Spotify URL playback (tracks, playlists, albums)

### Replit Platform Services
- **Replit Connectors API**: OAuth credential management
  - Hostname: REPLIT_CONNECTORS_HOSTNAME
  - Authentication via X_REPLIT_TOKEN header
  - Provides secure credential storage and retrieval