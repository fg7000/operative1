"""
Settings router for managing user configurations including Twitter credentials.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class TwitterCookiesRequest(BaseModel):
    email: str
    auth_token: str
    ct0: str


@router.post("/twitter-cookies")
async def save_twitter_cookies(req: TwitterCookiesRequest):
    """Save Twitter cookies from the Chrome extension.

    Uses email as the primary key for social_accounts.
    """
    from services.database import supabase

    logger.info(f"Received Twitter cookies for email: {req.email}")

    credentials = {
        'auth_token': req.auth_token,
        'ct0': req.ct0
    }

    try:
        # Check if record exists for this email
        existing = supabase.table('social_accounts').select('id').eq('email', req.email).eq('platform', 'twitter').execute()

        if existing.data:
            # Update existing record
            supabase.table('social_accounts').update({
                'credentials': credentials
            }).eq('email', req.email).eq('platform', 'twitter').execute()
            logger.info(f"Updated Twitter cookies for {req.email}")
        else:
            # Insert new record
            supabase.table('social_accounts').insert({
                'platform': 'twitter',
                'credentials': credentials,
                'email': req.email
            }).execute()
            logger.info(f"Inserted new Twitter cookies for {req.email}")

        return {"status": "success", "message": "Twitter connected successfully"}

    except Exception as e:
        logger.error(f"Error saving Twitter cookies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twitter-status")
async def get_twitter_status(email: str):
    """Check if Twitter is connected for a given email."""
    from services.database import supabase

    result = supabase.table('social_accounts').select('id,updated_at').eq('email', email).eq('platform', 'twitter').execute()

    if result.data:
        return {
            "connected": True,
            "last_updated": result.data[0].get('updated_at')
        }

    return {"connected": False}


@router.delete("/twitter-disconnect")
async def disconnect_twitter(email: str):
    """Disconnect Twitter for a given email."""
    from services.database import supabase

    supabase.table('social_accounts').delete().eq('email', email).eq('platform', 'twitter').execute()

    return {"status": "success", "message": "Twitter disconnected"}
