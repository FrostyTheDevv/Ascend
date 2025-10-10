import os
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any

class ReplitAuth:
    def __init__(self):
        self.hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
        self.repl_identity = os.getenv('REPL_IDENTITY')
        self.web_repl_renewal = os.getenv('WEB_REPL_RENEWAL')
        
        self.discord_settings = None
        self.spotify_settings = None
        
    def _get_x_replit_token(self) -> Optional[str]:
        if self.repl_identity:
            return f'repl {self.repl_identity}'
        elif self.web_repl_renewal:
            return f'depl {self.web_repl_renewal}'
        return None
        
    async def _fetch_connection(self, connector_name: str) -> Optional[Dict[str, Any]]:
        if not self.hostname:
            return None
            
        x_replit_token = self._get_x_replit_token()
        if not x_replit_token:
            return None
            
        url = f'https://{self.hostname}/api/v2/connection?include_secrets=true&connector_names={connector_name}'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    'Accept': 'application/json',
                    'X_REPLIT_TOKEN': x_replit_token
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('items', [])
                    return items[0] if items else None
        return None
        
    async def get_discord_token(self) -> Optional[str]:
        if self.discord_settings:
            expires_at = self.discord_settings.get('settings', {}).get('expires_at')
            if expires_at and datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp() > datetime.now().timestamp():
                return self.discord_settings.get('settings', {}).get('access_token')
                
        self.discord_settings = await self._fetch_connection('discord')
        
        if not self.discord_settings:
            return None
            
        settings = self.discord_settings.get('settings', {})
        return (
            settings.get('access_token') or 
            settings.get('oauth', {}).get('credentials', {}).get('access_token')
        )
        
    async def get_spotify_credentials(self) -> Optional[Dict[str, str]]:
        if self.spotify_settings:
            expires_at = self.spotify_settings.get('settings', {}).get('expires_at')
            if expires_at and datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp() > datetime.now().timestamp():
                settings = self.spotify_settings.get('settings', {})
                oauth = settings.get('oauth', {}).get('credentials', {})
                return {
                    'access_token': settings.get('access_token') or oauth.get('access_token'),
                    'client_id': oauth.get('client_id'),
                    'client_secret': oauth.get('client_secret'),
                    'refresh_token': oauth.get('refresh_token')
                }
                
        self.spotify_settings = await self._fetch_connection('spotify')
        
        if not self.spotify_settings:
            return None
            
        settings = self.spotify_settings.get('settings', {})
        oauth = settings.get('oauth', {}).get('credentials', {})
        
        access_token = settings.get('access_token') or oauth.get('access_token')
        client_id = oauth.get('client_id')
        client_secret = oauth.get('client_secret')
        refresh_token = oauth.get('refresh_token')
        
        if not access_token or not client_id or not refresh_token:
            return None
            
        return {
            'access_token': access_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
