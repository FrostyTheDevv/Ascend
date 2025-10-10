from flask import Flask, request, render_template_string, redirect, url_for, jsonify
import os
import requests
import json
import secrets
from urllib.parse import parse_qs, urlparse

app = Flask(__name__)

# In-memory storage for tokens (in production, use a database)
tokens_storage = {}
device_sessions = {}
pending_tracks = {}  # Store tracks that need to be played on Discord

# HTML template for displaying the authorization code
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotify Authorization</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1db954, #1ed760);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 600px;
            width: 100%;
        }
        .logo {
            font-size: 2.5em;
            color: #1db954;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .success {
            color: #1db954;
            font-size: 1.5em;
            margin-bottom: 20px;
        }
        .error {
            color: #e22134;
            font-size: 1.5em;
            margin-bottom: 20px;
        }
        .code-container {
            background: #f8f9fa;
            border: 2px solid #1db954;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            font-family: 'Courier New', monospace;
            word-break: break-all;
        }
        .code {
            font-size: 1.2em;
            color: #333;
            font-weight: bold;
        }
        .instructions {
            color: #666;
            margin-top: 20px;
            line-height: 1.6;
        }
        .copy-btn {
            background: #1db954;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            margin-top: 10px;
            transition: background 0.3s;
        }
        .copy-btn:hover {
            background: #1ed760;
        }
        .footer {
            margin-top: 30px;
            color: #999;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎵 Ascend </div>
        
        {% if error %}
            <div class="error">❌ Authorization Failed</div>
            <p>{{ error }}</p>
        {% elif code %}
            <div class="success">✅ Authorization Successful!</div>
            <div class="code-container">
                <div class="code" id="authCode">{{ code }}</div>
                <button class="copy-btn" onclick="copyCode()">📋 Copy Code</button>
            </div>
            <div class="instructions">
                <p><strong>Next Steps:</strong></p>
                <p>1. Copy the authorization code above</p>
                <p>2. Go back to Discord and use the <code>&lt;spotify confirm [code]</code> command</p>
                <p>3. Your Spotify account will be linked to your Discord account!</p>
            </div>
        {% else %}
            <div class="error">❌ No Authorization Data</div>
            <p>This page is used for Spotify OAuth callbacks. Please start the authorization process from Discord.</p>
        {% endif %}
        
        <div class="footer">
            Spotify OAuth Callback Handler for Ascend * Sleepless Development
        </div>
    </div>

    <script>
        function copyCode() {
            const codeElement = document.getElementById('authCode');
            const textArea = document.createElement('textarea');
            textArea.value = codeElement.textContent;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            const button = document.querySelector('.copy-btn');
            const originalText = button.textContent;
            button.textContent = '✅ Copied!';
            button.style.background = '#28a745';
            
            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '#1db954';
            }, 2000);
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, code=None, error="This is the Spotify OAuth callback endpoint for Ascend -Sleepless Developmement.")

@app.route('/callback')
def callback():
    # Get the authorization code from the callback URL
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        error_description = request.args.get('error_description', 'Unknown error occurred')
        return render_template_string(HTML_TEMPLATE, code=None, error=f"Error: {error} - {error_description}")
    
    if code:
        return render_template_string(HTML_TEMPLATE, code=code, error=None)
    else:
        return render_template_string(HTML_TEMPLATE, code=None, error="No authorization code received")

@app.route('/health')
def health():
    return {"status": "healthy", "service": "spotify-oauth-callback"}

@app.route('/device/<guild_id>')
def spotify_device_player(guild_id):
    """Serve the Spotify Web Playback SDK player for a specific guild."""
    
    # Get session token from query parameter
    session_token = request.args.get('token')
    if not session_token or session_token not in device_sessions:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Device Setup Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px; background: #1e1e1e; color: white;">
            <h1>❌ Invalid Session</h1>
            <p>This device session has expired or is invalid.</p>
            <p>Please run the <code>!spotify device</code> command again in Discord.</p>
        </body>
        </html>
        '''), 400
    
    session_data = device_sessions[session_token]
    access_token = session_data['access_token']
    guild_name = session_data.get('guild_name', f'Guild {guild_id}')
    
    # Generate the Spotify Web Playback SDK HTML
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ascend Music Bot - Spotify Connect</title>
        <script src="https://sdk.scdn.co/spotify-player.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1e3c72, #2a5298);
                color: white;
                margin: 0;
                padding: 20px;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                text-align: center;
                max-width: 600px;
                padding: 40px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }}
            .status {{
                font-size: 24px;
                margin-bottom: 20px;
            }}
            .emoji {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
            .details {{
                background: rgba(0, 0, 0, 0.2);
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
            }}
            .green {{ color: #1db954; }}
            .orange {{ color: #ff9500; }}
            .red {{ color: #ff3333; }}
            .pulse {{
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
                100% {{ opacity: 1; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji pulse">🎵</div>
            <div id="status" class="status">Initializing Spotify Connect...</div>
            <div id="details" class="details">
                <strong>Device Name:</strong> Ascend Music Bot<br>
                <strong>Server:</strong> {guild_name}<br>
                <strong>Status:</strong> <span id="connection-status">Connecting...</span><br>
                <strong>Guild ID:</strong> {guild_id}
            </div>
        </div>
        
        <script>
            let player;
            let deviceId;
            
            window.onSpotifyWebPlaybackSDKReady = () => {{
                const token = '{access_token}';
                
                player = new Spotify.Player({{
                    name: 'Ascend Music Bot ({guild_name})',
                    getOAuthToken: cb => {{ cb(token); }},
                    volume: 1.0
                }});
                
                // Error handling
                player.addListener('initialization_error', ({{ message }}) => {{
                    console.error('Failed to initialize:', message);
                    document.getElementById('status').innerHTML = '❌ Initialization Failed';
                    document.getElementById('status').className = 'status red';
                    document.getElementById('connection-status').innerHTML = 'Failed: ' + message;
                }});
                
                player.addListener('authentication_error', ({{ message }}) => {{
                    console.error('Failed to authenticate:', message);
                    document.getElementById('status').innerHTML = '❌ Authentication Failed';
                    document.getElementById('status').className = 'status red';
                    document.getElementById('connection-status').innerHTML = 'Auth Error: ' + message;
                }});
                
                player.addListener('account_error', ({{ message }}) => {{
                    console.error('Failed to validate Spotify account:', message);
                    document.getElementById('status').innerHTML = '❌ Account Error';
                    document.getElementById('status').className = 'status red';
                    document.getElementById('connection-status').innerHTML = 'Account Error: ' + message;
                }});
                
                player.addListener('playback_error', ({{ message }}) => {{
                    console.error('Failed to perform playback:', message);
                }});
                
                // Playback status updates
                player.addListener('player_state_changed', state => {{
                    if (!state) return;
                    console.log('Player state changed:', state);
                    
                    // Notify Discord bot about state changes
                    fetch('/device/notify', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            guild_id: '{guild_id}',
                            device_id: deviceId,
                            state: state
                        }})
                    }}).catch(console.error);
                }});
                
                // Ready
                player.addListener('ready', ({{ device_id }}) => {{
                    console.log('Ready with Device ID', device_id);
                    deviceId = device_id;
                    document.getElementById('status').innerHTML = '✅ Spotify Connect Device Ready!';
                    document.getElementById('status').className = 'status green';
                    document.getElementById('connection-status').innerHTML = 'Online - Device ID: ' + device_id;
                    
                    // Remove pulse animation
                    document.querySelector('.emoji').classList.remove('pulse');
                    
                    // Notify Discord bot that device is ready
                    fetch('/device/ready', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            device_id: device_id,
                            guild_id: '{guild_id}',
                            session_token: '{session_token}'
                        }})
                    }}).then(response => response.json())
                      .then(data => console.log('Device registered:', data))
                      .catch(console.error);
                }});
                
                // Not Ready
                player.addListener('not_ready', ({{ device_id }}) => {{
                    console.log('Device ID has gone offline', device_id);
                    document.getElementById('status').innerHTML = '⚠️ Device Offline';
                    document.getElementById('status').className = 'status orange';
                    document.getElementById('connection-status').innerHTML = 'Offline';
                }});
                
                // Connect to the player!
                player.connect().then(success => {{
                    if (success) {{
                        console.log('Successfully connected to Spotify!');
                    }} else {{
                        console.error('Failed to connect to Spotify');
                        document.getElementById('status').innerHTML = '❌ Connection Failed';
                        document.getElementById('status').className = 'status red';
                        document.getElementById('connection-status').innerHTML = 'Connection failed';
                    }}
                }});
                
                // Store player reference globally
                window.spotifyPlayer = player;
            }};
            
            // Keep the page alive
            setInterval(() => {{
                if (deviceId) {{
                    fetch('/device/heartbeat', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            device_id: deviceId,
                            guild_id: '{guild_id}'
                        }})
                    }}).catch(console.error);
                }}
            }}, 30000); // Every 30 seconds
        </script>
    </body>
    </html>
    '''
    
    return html_content

@app.route('/device/ready', methods=['POST'])
def device_ready():
    """Handle device ready notification."""
    data = request.get_json()
    device_id = data.get('device_id')
    guild_id = data.get('guild_id')
    session_token = data.get('session_token')
    
    print(f"Device ready: {device_id} for guild {guild_id}")
    
    # Store device info
    if session_token in device_sessions:
        device_sessions[session_token]['device_id'] = device_id
        device_sessions[session_token]['ready'] = True
    
    return jsonify({"success": True, "device_id": device_id})

@app.route('/device/notify', methods=['POST'])
def device_notify():
    """Handle device state notifications and forward to Discord bot."""
    data = request.get_json()
    print(f"📱 Device notification received: {data}")
    
    # Extract track information if available
    state = data.get('state', {})
    guild_id = data.get('guild_id')
    device_id = data.get('device_id')
    
    print(f"   Guild ID: {guild_id}")
    print(f"   Device ID: {device_id}")
    print(f"   State keys: {list(state.keys()) if state else 'No state'}")
    
    if state and guild_id:
        track_window = state.get('track_window', {})
        current_track = track_window.get('current_track')
        
        print(f"   Track window: {bool(track_window)}")
        print(f"   Current track: {bool(current_track)}")
        print(f"   Paused: {state.get('paused', True)}")
        
        if current_track and not state.get('paused', True):
            # Track is playing - notify Discord bot
            track_info = {
                'name': current_track.get('name'),
                'artists': [artist.get('name') for artist in current_track.get('artists', [])],
                'album': current_track.get('album', {}).get('name'),
                'duration_ms': current_track.get('duration_ms'),
                'is_playing': not state.get('paused', True),
                'position_ms': state.get('position', 0),
                'device_id': device_id,
                'guild_id': guild_id
            }
            
            # Store track info for Discord bot to pick up
            print(f"🎵 Now playing: {track_info['artists'][0] if track_info['artists'] else 'Unknown'} - {track_info['name']}")
            
            # Store track info for Discord bot to pick up
            if guild_id not in pending_tracks:
                pending_tracks[guild_id] = []
            pending_tracks[guild_id].append(track_info)
            print(f"   Added to pending tracks for guild {guild_id}")
    
    return jsonify({"success": True})

@app.route('/device/heartbeat', methods=['POST'])
def device_heartbeat():
    """Handle device heartbeat."""
    data = request.get_json()
    return jsonify({"success": True})

@app.route('/bot/pending_tracks/<guild_id>')
def get_pending_tracks(guild_id):
    """Get pending tracks for a guild and clear the queue."""
    tracks = pending_tracks.get(guild_id, [])
    pending_tracks[guild_id] = []  # Clear after retrieval
    return jsonify({"tracks": tracks})

@app.route('/callback/complete', methods=['POST'])
def callback_complete():
    """Complete OAuth flow and get access token."""
    data = request.get_json()
    auth_code = data.get('code')
    guild_id = data.get('guild_id')
    user_id = data.get('user_id')
    guild_name = data.get('guild_name', f'Guild {guild_id}')
    
    if not auth_code:
        return jsonify({"error": "No authorization code provided"}), 400
    
    # Exchange authorization code for access token
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'https://ascend-api.replit.app/callback')
    
    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    try:
        response = requests.post('https://accounts.spotify.com/api/token', data=token_data)
        response.raise_for_status()
        token_info = response.json()
        
        # Generate session token for device setup
        session_token = secrets.token_urlsafe(32)
        
        # Store session data
        device_sessions[session_token] = {
            'access_token': token_info['access_token'],
            'refresh_token': token_info.get('refresh_token'),
            'user_id': user_id,
            'guild_id': guild_id,
            'guild_name': guild_name,
            'expires_at': token_info.get('expires_in', 3600),
            'ready': False,
            'device_id': None
        }
        
        # Generate device setup URL
        device_url = f"https://ascend-api.replit.app/device/{guild_id}?token={session_token}"
        
        return jsonify({
            "success": True,
            "device_url": device_url,
            "session_token": session_token
        })
        
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to exchange token: {str(e)}"}), 500

@app.route('/device/status/<session_token>')
def device_status(session_token):
    """Check device status."""
    if session_token not in device_sessions:
        return jsonify({"error": "Invalid session"}), 404
    
    session = device_sessions[session_token]
    return jsonify({
        "ready": session.get('ready', False),
        "device_id": session.get('device_id'),
        "guild_id": session.get('guild_id')
    })

@app.route('/debug/env')
def debug_env():
    """Debug endpoint to check environment variables."""
    return jsonify({
        "client_id": os.environ.get('SPOTIFY_CLIENT_ID', 'NOT_SET')[:10] + "..." if os.environ.get('SPOTIFY_CLIENT_ID') else 'NOT_SET',
        "client_secret": "SET" if os.environ.get('SPOTIFY_CLIENT_SECRET') else 'NOT_SET',
        "redirect_uri": os.environ.get('SPOTIFY_REDIRECT_URI', 'NOT_SET'),
        "port": os.environ.get('PORT', 'NOT_SET')
    })

if __name__ == '__main__':
    # Use PORT environment variable or default to 8080 for Replit
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)