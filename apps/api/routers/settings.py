"""
Settings router for managing user configurations including Twitter credentials.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class TwitterCookiesRequest(BaseModel):
    user_id: str
    auth_token: str
    ct0: str


@router.post("/twitter-cookies")
async def save_twitter_cookies(req: TwitterCookiesRequest):
    """Save Twitter cookies from the Chrome extension."""
    from services.database import supabase

    logger.info(f"Received Twitter cookies for user_id: {req.user_id}")

    credentials = {
        'auth_token': req.auth_token,
        'ct0': req.ct0
    }

    try:
        # Check if record exists for this user
        existing = supabase.table('social_accounts').select('id').eq('user_id', req.user_id).eq('platform', 'twitter').execute()

        if existing.data:
            # Update existing record
            supabase.table('social_accounts').update({
                'credentials': credentials
            }).eq('user_id', req.user_id).eq('platform', 'twitter').execute()
            logger.info(f"Updated Twitter cookies for user {req.user_id}")
        else:
            # Insert new record
            supabase.table('social_accounts').insert({
                'user_id': req.user_id,
                'platform': 'twitter',
                'credentials': credentials
            }).execute()
            logger.info(f"Inserted new Twitter cookies for user {req.user_id}")

        return {"status": "success", "message": "Twitter connected successfully"}

    except Exception as e:
        logger.error(f"Error saving Twitter cookies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twitter-status")
async def get_twitter_status(user_id: str):
    """Check if Twitter is connected for a given user."""
    from services.database import supabase

    result = supabase.table('social_accounts').select('id,created_at').eq('user_id', user_id).eq('platform', 'twitter').execute()

    if result.data:
        return {
            "connected": True,
            "last_updated": result.data[0].get('created_at')
        }

    return {"connected": False}


@router.delete("/twitter-disconnect")
async def disconnect_twitter(user_id: str):
    """Disconnect Twitter for a given user."""
    from services.database import supabase

    supabase.table('social_accounts').delete().eq('user_id', user_id).eq('platform', 'twitter').execute()

    return {"status": "success", "message": "Twitter disconnected"}
