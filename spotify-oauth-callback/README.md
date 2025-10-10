# Spotify OAuth Callback Server

This is a simple Flask application that handles Spotify OAuth callbacks for the Ascend bot.

## Features

- 🎵 Clean, Spotify-themed UI
- 📋 One-click code copying
- ✅ Clear success/error handling
- 🔗 Easy integration with Discord bot

## Deployment on Replit

1. Create a new Replit project
2. Upload these files to your Replit project
3. Replit will automatically detect it's a Flask app
4. Click "Run" and your callback server will be live!

## Usage

1. Copy your Replit app URL (e.g., `https://your-app-name.username.repl.co`)
2. Update your Spotify Developer Dashboard with the callback URL: `https://your-app-name.username.repl.co/callback`
3. Update your Discord bot's Spotify OAuth configuration to use the same URL
4. Users can now complete Spotify OAuth through your Replit-hosted callback server!

## Endpoints

- `/` - Home page with instructions
- `/callback` - Spotify OAuth callback handler
- `/health` - Health check endpoint

## Environment Variables

- `PORT` - Server port (automatically set by Replit)

The server will automatically use Replit's provided port and be accessible via your Replit app URL.