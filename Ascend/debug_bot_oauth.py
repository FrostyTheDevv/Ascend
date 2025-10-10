#!/usr/bin/env python3
"""Debug the exact OAuth flow that the bot uses."""

import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables
load_dotenv()

print("=== Bot OAuth Debug ===")

# Test the EXACT same parameters as the spotify device command
try:
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = "https://ascend-api.replit.app/callback"
    scope = "user-read-playback-state user-modify-playback-state streaming user-read-email user-read-private"
    
    print(f"CLIENT_ID: {client_id}")
    print(f"CLIENT_SECRET: {client_secret[:10]}..." if client_secret else "CLIENT_SECRET: None")
    print(f"REDIRECT_URI: {redirect_uri}")
    print(f"SCOPE: {scope}")
    
    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        state="123456:789012",
        show_dialog=True
    )
    
    print("\n✅ SpotifyOAuth object created successfully!")
    
    # Try to get authorization URL (this is where the error might occur)
    auth_url = sp_oauth.get_authorize_url()
    print(f"✅ Authorization URL: {auth_url}")
    
    # Parse the URL to see what redirect_uri is actually being sent
    import urllib.parse
    parsed = urllib.parse.urlparse(auth_url)
    params = urllib.parse.parse_qs(parsed.query)
    
    print(f"\nURL Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value[0] if value else 'None'}")
    
    # Specifically check redirect_uri
    redirect_in_url = params.get('redirect_uri', ['None'])[0]
    print(f"\nRedirect URI in URL: {redirect_in_url}")
    
    if redirect_in_url == redirect_uri:
        print("✅ Redirect URI matches expected value")
    else:
        print(f"❌ Redirect URI MISMATCH!")
        print(f"   Expected: {redirect_uri}")
        print(f"   Got:      {redirect_in_url}")

except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")
    
    # If it's a requests exception, get more details
    if hasattr(e, 'response'):
        print(f"HTTP Status: {e.response.status_code}")
        print(f"Response: {e.response.text}")

print("\n=== End Debug ===")