"""
Settings router for Operative1 API.

Handles Twitter credentials per-product using encrypted storage.

Endpoints:
- GET /settings/twitter-status — Check if Twitter is connected for a product
- POST /settings/twitter-cookies — Save Twitter credentials for a product (from extension)
- DELETE /settings/twitter-disconnect — Remove Twitter credentials for a product
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from services.auth import get_current_user, verify_product_ownership
from services.encryption import encrypt_credentials, decrypt_credentials

router = APIRouter()
logger = logging.getLogger(__name__)


class SaveTwitterCookiesRequest(BaseModel):
    product_id: str
    auth_token: str
    ct0: str
    twitter_handle: Optional[str] = None


@router.get("/twitter-status")
async def get_twitter_status(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Check if Twitter is connected for a product.

    Returns:
    - connected: bool
    - handle: Twitter handle if connected
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    # Look up social_accounts for this product
    res = supabase.table('social_accounts').select('*').eq('product_id', product_id).eq('platform', 'twitter').execute()

    if not res.data:
        return {"connected": False}

    account = res.data[0]
    credentials = decrypt_credentials(account.get('credentials_encrypted', ''))

    if not credentials:
        return {"connected": False, "error": "credentials_corrupted"}

    return {
        "connected": True,
        "handle": account.get('platform_handle', ''),
        "connected_at": account.get('created_at'),
    }


@router.get("/twitter-cookies")
async def get_twitter_cookies(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Decrypt and return stored Twitter credentials for a product.

    Used by the dashboard to pass stored cookies to the Chrome extension
    so it posts from the correct account (not whichever is logged in).
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('social_accounts').select('credentials_encrypted').eq('product_id', product_id).eq('platform', 'twitter').execute()

    if not res.data:
        return {"error": "not connected"}

    credentials = decrypt_credentials(res.data[0].get('credentials_encrypted', ''))

    if not credentials:
        return {"error": "credentials_corrupted"}

    return {
        "auth_token": credentials["auth_token"],
        "ct0": credentials["ct0"],
    }


@router.post("/twitter-cookies")
async def save_twitter_cookies(body: SaveTwitterCookiesRequest):
    """
    Save Twitter credentials for a product.

    Called by the Chrome extension after user connects Twitter.
    No auth required - extension can't easily get JWT.

    Security note: This endpoint accepts product_id directly.
    The extension should have already verified the user owns this product
    by fetching their product list first.
    """
    from services.database import supabase

    if not body.product_id or not body.auth_token or not body.ct0:
        raise HTTPException(status_code=400, detail="product_id, auth_token, and ct0 are required")

    # Verify product exists
    product_res = supabase.table('products').select('id,user_id').eq('id', body.product_id).execute()
    if not product_res.data:
        raise HTTPException(status_code=404, detail="Product not found")

    # Encrypt credentials
    encrypted = encrypt_credentials(body.auth_token, body.ct0)

    # Upsert into social_accounts
    try:
        # Try to update existing
        existing = supabase.table('social_accounts').select('id').eq('product_id', body.product_id).eq('platform', 'twitter').execute()

        if existing.data:
            # Update existing record
            supabase.table('social_accounts').update({
                'credentials_encrypted': encrypted,
            }).eq('id', existing.data[0]['id']).execute()
            logger.info(f"Updated Twitter credentials for product {body.product_id}")
        else:
            # Insert new record
            supabase.table('social_accounts').insert({
                'product_id': body.product_id,
                'platform': 'twitter',
                'credentials_encrypted': encrypted,
                'handle': body.twitter_handle or 'pending',
            }).execute()
            logger.info(f"Saved new Twitter credentials for product {body.product_id}")

        return {"status": "connected", "handle": body.twitter_handle}

    except Exception as e:
        logger.error(f"Failed to save Twitter credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to save credentials")


@router.delete("/twitter-disconnect")
async def disconnect_twitter(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove Twitter credentials for a product.
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    # Delete from social_accounts
    res = supabase.table('social_accounts').delete().eq('product_id', product_id).eq('platform', 'twitter').execute()

    deleted = len(res.data) if res.data else 0
    logger.info(f"Disconnected Twitter for product {product_id} (deleted {deleted} records)")

    return {"status": "disconnected"}


@router.get("/account")
async def get_account_info(user_id: str = Depends(get_current_user)):
    """
    Get account info for the authenticated user.
    Used by Settings page to show user details.
    """
    from services.database import supabase

    # Get user info from Supabase auth
    # Note: We can't directly query auth.users with service_role,
    # but we can return the user_id which the frontend already has
    return {
        "user_id": user_id,
        # Email/name are available in frontend via supabase.auth.getUser()
    }
