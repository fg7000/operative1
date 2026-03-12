"""
Settings router - placeholder endpoints.
Twitter cookies are managed via environment variables for now.
"""
from fastapi import APIRouter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/twitter-status")
async def get_twitter_status(user_id: str = None):
    """Check if Twitter is connected. Returns env var status."""
    import os
    has_cookies = bool(os.getenv('TWITTER_AUTH_TOKEN') and os.getenv('TWITTER_CT0'))
    return {"connected": has_cookies, "method": "environment_variables"}


@router.post("/twitter-cookies")
async def save_twitter_cookies():
    """Placeholder - cookies are managed via env vars."""
    return {"status": "info", "message": "Twitter cookies are managed via environment variables. Set TWITTER_AUTH_TOKEN and TWITTER_CT0."}


@router.delete("/twitter-disconnect")
async def disconnect_twitter():
    """Placeholder - cookies are managed via env vars."""
    return {"status": "info", "message": "Remove TWITTER_AUTH_TOKEN and TWITTER_CT0 environment variables to disconnect."}
