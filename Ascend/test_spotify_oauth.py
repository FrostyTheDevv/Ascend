#!/usr/bin/env python3
"""Test script to isolate Spotify OAuth issues."""

import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables
load_dotenv()

print("=== Spotify OAuth Test ===")
print(f"CLIENT_ID: {os.getenv('SPOTIFY_CLIENT_ID')[:10]}..." if os.getenv('SPOTIFY_CLIENT_ID') else "CLIENT_ID: None")
print(f"CLIENT_SECRET: {os.getenv('SPOTIFY_CLIENT_SECRET')[:10]}..." if os.getenv('SPOTIFY_CLIENT_SECRET') else "CLIENT_SECRET: None")

try:
    # Test the exact same configuration as the bot
    redirect_uri = "https://ascend-api.replit.app/callback"
    scope = "user-read-playback-state user-modify-playback-state streaming user-read-email user-read-private"
    
    print(f"\nTesting with:")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Scope: {scope}")
    
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
        redirect_uri=redirect_uri,
        scope=scope,
        state="test:123",
        show_dialog=True
    )
    
    print("\n✅ SpotifyOAuth object created successfully!")
    
    # Try to get authorization URL
    auth_url = sp_oauth.get_authorize_url()
    print(f"✅ Authorization URL generated: {auth_url[:50]}...")
    
    # Check if redirect URI is properly encoded
    if "redirect_uri" in auth_url:
        import urllib.parse
        parsed_url = urllib.parse.urlparse(auth_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        redirect_uri_in_url = query_params.get('redirect_uri', [''])[0]
        print(f"Redirect URI in URL: {redirect_uri_in_url}")
        
        if redirect_uri_in_url == redirect_uri:
            print("✅ Redirect URI matches!")
        else:
            print(f"❌ Redirect URI mismatch! Expected: {redirect_uri}, Got: {redirect_uri_in_url}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

print("\n=== End Test ===")