"""Google OAuth authentication service."""
import logging
from typing import Dict, Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize OAuth
oauth = OAuth()

# Register Google OAuth provider
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name='google',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    logger.info("Google OAuth configured successfully")
else:
    logger.warning("Google OAuth credentials not configured")


async def get_google_user_info(token: Dict) -> Optional[Dict]:
    """
    Fetch user information from Google using the access token.
    
    Args:
        token: OAuth token dictionary containing access_token
        
    Returns:
        Dictionary with user info (email, name, picture, etc.) or None if failed
    """
    try:
        # Use the token to get user info
        resp = await oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo', token=token)
        user_info = resp.json()
        
        logger.info(f"Successfully fetched Google user info for: {user_info.get('email')}")
        return user_info
    except Exception as e:
        logger.error(f"Failed to fetch Google user info: {e}")
        return None


def validate_google_oauth_config() -> bool:
    """
    Validate that Google OAuth is properly configured.
    
    Returns:
        True if configured, False otherwise
    """
    return bool(settings.google_client_id and settings.google_client_secret)
