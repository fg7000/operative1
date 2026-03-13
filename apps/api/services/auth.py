"""
Authentication service for Operative1 API.

JWT Verification Flow:
┌─────────────────────────────────────────────────────────────────┐
│  1. Frontend calls API with Authorization: Bearer <token>       │
│  2. get_current_user() extracts token and calls Supabase API    │
│  3. Supabase auth.get_user() verifies token server-side         │
│  4. Returns user_id from verified user object                   │
│  5. Endpoints use user_id for ownership verification            │
└─────────────────────────────────────────────────────────────────┘

Error Cases:
- Missing Authorization header → 401 Unauthorized
- Invalid/expired JWT → 401 Unauthorized
- Supabase verification failure → 401 Unauthorized
"""

import os
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

logger = logging.getLogger(__name__)

# Supabase configuration for token verification
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verify JWT token via Supabase API and return user_id.

    Raises HTTPException 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    token = credentials.credentials

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth not configured"
        )

    try:
        # Use Supabase client to verify token server-side
        # This is more reliable than local JWT verification
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        user_response = supabase_client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        return user_response.user.id

    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Try to verify JWT token, return user_id or None.

    Use this for endpoints that work with or without auth.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def verify_product_ownership(user_id: str, product_id: str) -> bool:
    """
    Verify that a product belongs to the given user.

    Returns True if ownership verified, raises 403 if not.
    """
    from services.database import supabase

    result = supabase.table('products').select('user_id').eq('id', product_id).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    if result.data[0]['user_id'] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return True
