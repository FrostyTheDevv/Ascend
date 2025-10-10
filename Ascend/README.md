# 🎵 Ascend - Advanced Discord Music Bot

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.6.3+-green.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Spotify](https://img.shields.io/badge/Spotify-Integration-1DB954.svg)](https://developer.spotify.com/)

A feature-rich Discord music bot with Spotify integration, user accounts, and advanced music controls. Built with modern Discord.py components and a robust database system.

## ✨ Features

### 🎵 Music & Audio
- **High-Quality Streaming** - Crystal clear audio playback
- **Multiple Sources** - YouTube, Spotify, SoundCloud support
- **Queue Management** - Add, remove, shuffle, and loop tracks
- **Advanced Controls** - Skip, pause, resume, volume control
- **Search Integration** - Find tracks across multiple platforms

### 🔗 Spotify Integration
- **OAuth Authentication** - Secure Spotify account linking
- **Device Control** - Control Spotify playback on any device
- **Playlist Access** - Import and play your Spotify playlists
- **Real-time Sync** - Display currently playing Spotify tracks
- **Cross-Platform** - Works with Spotify Free and Premium

### 👤 User System
- **Account Management** - Create and manage user accounts
- **Personal Preferences** - Customizable settings and preferences
- **Usage Statistics** - Track your music listening habits
- **Premium Features** - Enhanced functionality for premium users

### ⚙️ Server Management
- **Custom Prefixes** - Set custom command prefixes per server
- **No-Prefix Mode** - Optional prefix-free command usage
- **Role Integration** - Permission-based command access
- **Server Settings** - Configurable bot behavior per server

### 📊 Advanced Features
- **Database Integration** - SQLite with async support
- **Error Handling** - Comprehensive error reporting and recovery
- **Logging System** - Detailed logging for debugging and monitoring
- **Component UI** - Modern Discord buttons, dropdowns, and modals
- **Real-time Updates** - Live status updates and notifications

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** - [Download Python](https://python.org/downloads/)
- **Discord Bot Token** - [Discord Developer Portal](https://discord.com/developers/applications)
- **Spotify App** (Optional) - [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/FrostyTheDevv/Ascend.git
   cd Ascend
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or using uv (recommended):
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Environment Setup**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials:
   ```env
   DISCORD_TOKEN=your_discord_bot_token
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIFY_REDIRECT_URI=https://your-callback-server.com/callback
   ```

4. **Run the Bot**
   ```bash
   python main.py
   ```

## 🔧 Detailed Setup Guide

### Step 1: Discord Bot Setup

1. **Create a Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and name your bot
   - Navigate to the "Bot" section
   - Create a bot and copy the token

2. **Bot Permissions**
   Required permissions:
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
   - `Connect` (for voice channels)
   - `Speak` (for music playback)
   - `Use Voice Activity`

3. **Invite the Bot**
   - Use the OAuth2 URL Generator in Developer Portal
   - Select "bot" and required permissions
   - Visit the generated URL to invite your bot

### Step 2: Spotify Integration Setup

1. **Create Spotify App**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Click "Create app"
   - Fill in app details (name, description)
   - Set app type to "Web API"

2. **Configure Redirect URI**
   
   **Option A: Replit Hosting (Recommended)**
   - Deploy the callback server from `/spotify-oauth-callback/` to Replit
   - Use URL: `https://your-app-name.replit.app/callback`
   
   **Option B: Local Development**
   - Use: `http://localhost:5000/callback`
   - Only for testing, not production

3. **Get Credentials**
   - Copy Client ID and Client Secret from Spotify Dashboard
   - Add them to your `.env` file

### Step 3: Callback Server Deployment

For Spotify OAuth to work, deploy the callback server:

1. **Using Replit (Recommended)**
   ```bash
   # Create new Replit project
   # Upload files from spotify-oauth-callback/ folder
   # Click "Run" - Replit auto-detects Flask app
   ```

2. **Using Other Platforms**
   - Heroku, Railway, or any Flask-compatible hosting
   - Set `PORT` environment variable if required
   - Ensure HTTPS for production use

### Step 4: Database Setup

The bot automatically creates the SQLite database on first run:

```bash
# Database file will be created at:
./ascend_bot.db

# To reset database (CAUTION: Deletes all data):
rm ascend_bot.db
python main.py  # Will recreate database
```

### Step 5: Configuration

1. **Server Prefix Setup**
   ```
   <setup  # Configure server settings
   <prefix !  # Set custom prefix
   <prefix none  # Enable no-prefix mode
   ```

2. **User Account Creation**
   ```
   <account  # Open account management
   # Use dropdown to create new account
   ```

3. **Spotify Linking**
   ```
   <spotify link  # Start OAuth process
   <spotify confirm [code]  # Complete with auth code
   ```

## 📋 Commands Reference

### Music Commands
```
<play [song]        # Play a song or add to queue
<skip              # Skip current track
<pause             # Pause playback
<resume            # Resume playback
<stop              # Stop playback and clear queue
<queue             # Display current queue
<nowplaying        # Show current track info
<volume [1-100]    # Set playback volume
<loop              # Toggle loop mode
<shuffle           # Shuffle queue
<search [query]    # Search for tracks
<lyrics [song]     # Get song lyrics
```

### Spotify Commands
```
<spotify           # Main Spotify menu
<spotify link      # Link Spotify account
<spotify unlink    # Unlink Spotify account
<spotify status    # Current Spotify playback
<spotify confirm   # Complete OAuth linking
```

### Account Commands
```
<account           # Account management menu
<profile           # View user profile
<signup            # Create new account
<signin            # Sign in to existing account
```

### Utility Commands
```
<help              # Show help menu
<about             # Bot information
<ping              # Check bot latency
<invite            # Get bot invite link
<setup             # Server configuration
<prefix [prefix]   # Change command prefix
```

## 🏗️ Architecture

### Project Structure
```
Ascend/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── database.py            # Database operations
├── cogs/                  # Bot command modules
│   ├── music.py          # Music commands
│   ├── accounts.py       # User account system
│   ├── utility.py        # Utility commands
│   └── help.py           # Help system
├── spotify-oauth-callback/ # OAuth callback server
│   ├── app.py            # Flask callback handler
│   ├── requirements.txt  # Callback server dependencies
│   └── README.md         # Deployment instructions
├── TERMS_OF_SERVICE.md   # Legal terms
├── PRIVACY_POLICY.md     # Privacy policy
└── .env.example          # Environment template
```

### Database Schema
```sql
-- Users table
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    spotify_connected BOOLEAN DEFAULT FALSE,
    spotify_tokens TEXT  -- JSON: tokens, state, user info
);

-- Server settings table
CREATE TABLE guild_settings (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT DEFAULT '<',
    volume INTEGER DEFAULT 50,
    -- Additional server-specific settings
);
```

### Technology Stack
- **Discord.py 2.6.3+** - Modern Discord API wrapper
- **SQLite + aiosqlite** - Async database operations
- **Spotipy** - Spotify Web API integration
- **yt-dlp** - YouTube audio extraction
- **PyNaCl** - Voice encryption
- **Flask** - OAuth callback server

## 🔒 Security & Privacy

### Data Protection
- **Encrypted Storage** - Sensitive data encrypted at rest
- **Token Security** - OAuth tokens securely stored and refreshed
- **Access Control** - Limited database access with permissions
- **Privacy Compliance** - GDPR and CCPA compliant

### Security Features
- **Input Validation** - All user inputs validated and sanitized
- **Rate Limiting** - Command cooldowns and spam protection
- **Error Handling** - Graceful error handling without data exposure
- **Audit Logging** - Security events logged for monitoring

## 📈 Performance

### Optimization Features
- **Async Operations** - Non-blocking database and API calls
- **Connection Pooling** - Efficient database connection management
- **Caching** - Smart caching for frequently accessed data
- **Memory Management** - Optimized memory usage for long-running operation

### Monitoring
- **Health Checks** - Built-in health monitoring endpoints
- **Performance Metrics** - Response time and usage tracking
- **Error Reporting** - Comprehensive error logging and reporting

## 🛠️ Development

### Local Development Setup
1. **Clone and Install**
   ```bash
   git clone https://github.com/FrostyTheDevv/Ascend.git
   cd Ascend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # OR
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```

2. **Development Environment**
   ```bash
   cp .env.example .env
   # Edit .env with development credentials
   python main.py
   ```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

### Code Style
- **PEP 8** - Python style guide compliance
- **Type Hints** - Type annotations for better code clarity
- **Docstrings** - Comprehensive function and class documentation
- **Comments** - Clear code comments for complex logic

## 📚 Documentation

### Additional Resources
- **[Discord.py Documentation](https://discordpy.readthedocs.io/)**
- **[Spotify Web API](https://developer.spotify.com/documentation/web-api/)**
- **[Python Async Programming](https://docs.python.org/3/library/asyncio.html)**

### Troubleshooting

**Common Issues:**

1. **Bot Not Responding**
   - Check Discord token validity
   - Verify bot permissions in server
   - Check console for error messages

2. **Spotify Integration Fails**
   - Verify Spotify app credentials
   - Check redirect URI configuration
   - Ensure callback server is accessible

3. **Database Errors**
   - Check file permissions for database
   - Verify SQLite installation
   - Check disk space availability

4. **Voice Connection Issues**
   - Install PyNaCl: `pip install PyNaCl`
   - Check voice channel permissions
   - Verify FFmpeg installation

## 📄 Legal

### License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Terms & Privacy
- **[Terms of Service](TERMS_OF_SERVICE.md)** - Bot usage terms
- **[Privacy Policy](PRIVACY_POLICY.md)** - Data handling and privacy

### Acknowledgments
- **Discord.py** - Excellent Discord API wrapper
- **Spotify** - Music streaming integration
- **YouTube** - Music content source
- **Community** - Contributors and users

## 🤝 Support

### Getting Help
- **GitHub Issues** - [Report bugs or request features](https://github.com/FrostyTheDevv/Ascend/issues)
- **Documentation** - Check this README and code comments
- **Community** - Join our Discord server for community support

### Support the Project
- ⭐ **Star the repository** if you find it useful
- 🐛 **Report bugs** to help improve the bot
- 💡 **Suggest features** for future development
- 🤝 **Contribute code** to help make it better

---

**Made with ❤️ by [FrostyTheDevv](https://github.com/FrostyTheDevv)**

*Ascend - Music above* 🎵