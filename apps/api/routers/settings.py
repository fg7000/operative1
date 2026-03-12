"""
Settings router for managing user configurations including Twitter credentials.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
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

    Looks up user by email, creates/updates their social_accounts record.
    """
    from services.database import supabase

    logger.info(f"Received Twitter cookies for email: {req.email}")

    # Look up user by email in auth.users
    # Note: We need to query products table since that has user_id linked
    user_result = supabase.table('products').select('user_id').eq('user_email', req.email).execute()

    if not user_result.data:
        # Try alternate approach: check if email exists in any form
        # For now, create a placeholder that will be linked later
        logger.warning(f"No product found for email {req.email}, storing with email as identifier")
        user_id = None
    else:
        user_id = user_result.data[0]['user_id']
        logger.info(f"Found user_id: {user_id} for email: {req.email}")

    credentials = {
        'auth_token': req.auth_token,
        'ct0': req.ct0
    }

    try:
        # Use upsert to avoid race conditions from concurrent extension clicks
        upsert_data = {
            'platform': 'twitter',
            'credentials': credentials,
            'email': req.email
        }
        if user_id:
            upsert_data['user_id'] = user_id

        # Upsert: insert or update on conflict (requires unique index on user_id+platform or email+platform)
        # If no unique index exists, this falls back to insert which may create duplicates,
        # but the query logic handles that by always using the first match
        supabase.table('social_accounts').upsert(
            upsert_data,
            on_conflict='user_id,platform' if user_id else 'email,platform'
        ).execute()
        logger.info(f"Upserted Twitter cookies for {req.email}")

        return {"status": "success", "message": "Twitter connected successfully"}

    except Exception as e:
        logger.error(f"Error saving Twitter cookies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twitter-status")
async def get_twitter_status(email: str):
    """Check if Twitter is connected for a given email."""
    from services.database import supabase

    # First try to find by user_id via products
    user_result = supabase.table('products').select('user_id').eq('user_email', email).execute()

    if user_result.data:
        user_id = user_result.data[0]['user_id']
        result = supabase.table('social_accounts').select('id,updated_at').eq('user_id', user_id).eq('platform', 'twitter').execute()
    else:
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

    # First try to find by user_id via products
    user_result = supabase.table('products').select('user_id').eq('user_email', email).execute()

    if user_result.data:
        user_id = user_result.data[0]['user_id']
        supabase.table('social_accounts').delete().eq('user_id', user_id).eq('platform', 'twitter').execute()
    else:
        supabase.table('social_accounts').delete().eq('email', email).eq('platform', 'twitter').execute()

    return {"status": "success", "message": "Twitter disconnected"}
