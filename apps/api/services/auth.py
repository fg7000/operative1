"""
Authentication service for Operative1 API.

JWT Verification Flow:
┌─────────────────────────────────────────────────────────────────┐
│  1. Frontend calls API with Authorization: Bearer <token>       │
│  2. get_current_user() extracts and verifies JWT                │
│  3. JWT signed by Supabase, verified with SUPABASE_JWT_SECRET   │
│  4. Returns user_id from JWT claims                             │
│  5. Endpoints use user_id for ownership verification            │
└─────────────────────────────────────────────────────────────────┘

Error Cases:
- Missing Authorization header → 401 Unauthorized
- Invalid/expired JWT → 401 Unauthorized
- JWT verification failure → 401 Unauthorized
"""

import os
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

logger = logging.getLogger(__name__)

# Supabase JWT secret for verifying tokens
# This is different from the service_role key - it's specifically for JWT verification
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verify JWT token and return user_id.

    Raises HTTPException 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    token = credentials.credentials

    if not SUPABASE_JWT_SECRET:
        logger.error("SUPABASE_JWT_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth not configured"
        )

    try:
        # Supabase uses HS256 for JWT signing
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT verification failed: {e}")
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
