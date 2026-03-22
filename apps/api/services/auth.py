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

Product Token Flow (for extension autopilot):
┌─────────────────────────────────────────────────────────────────┐
│  1. User generates token via dashboard (stored in products)     │
│  2. Extension stores token for API authentication               │
│  3. Extension sends X-Product-Token header with requests        │
│  4. verify_product_token() validates against products table     │
│  5. Returns (user_id, product_id) tuple                         │
└─────────────────────────────────────────────────────────────────┘

Error Cases:
- Missing Authorization header → 401 Unauthorized
- Invalid/expired JWT → 401 Unauthorized
- Supabase verification failure → 401 Unauthorized
- Invalid product token → 401 Unauthorized
"""

import os
import secrets
import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

logger = logging.getLogger(__name__)

# Supabase configuration for token verification
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Product token prefix for easy identification
PRODUCT_TOKEN_PREFIX = "op1_"

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


def generate_product_token() -> str:
    """Generate a secure product-scoped API token."""
    return PRODUCT_TOKEN_PREFIX + secrets.token_urlsafe(32)


async def save_product_token(product_id: str) -> str:
    """Generate and save a new product token. Returns the token."""
    from services.database import supabase

    token = generate_product_token()

    # Store in products.autopilot.api_token
    product = supabase.table('products').select('autopilot').eq('id', product_id).single().execute()
    autopilot = (product.data.get('autopilot') or {}) if product.data else {}
    autopilot['api_token'] = token

    supabase.table('products').update({'autopilot': autopilot}).eq('id', product_id).execute()
    logger.info(f"Product token generated for product {product_id[:8]}")

    return token


async def verify_product_token(token: str) -> tuple[str, str]:
    """Verify a product-scoped token and return (user_id, product_id).

    Raises HTTPException 401 if token is invalid.
    """
    from services.database import supabase

    if not token or not token.startswith(PRODUCT_TOKEN_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid product token"
        )

    # Search products for matching token
    res = supabase.table('products').select('id,user_id,autopilot').execute()

    for product in (res.data or []):
        autopilot = product.get('autopilot') or {}
        if autopilot.get('api_token') == token:
            return product['user_id'], product['id']

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid product token"
    )


async def get_user_or_product_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_product_token: Optional[str] = Header(None),
    product_token: Optional[str] = Query(None),
) -> tuple[str, Optional[str]]:
    """Dual auth: accepts either JWT bearer token or product-scoped token.

    Returns:
        (user_id, product_id_or_none)
        - JWT auth: (user_id, None)
        - Product token: (user_id, product_id)
    """
    # Try product token first (from header or query param)
    token = x_product_token or product_token
    if token and token.startswith(PRODUCT_TOKEN_PREFIX):
        user_id, product_id = await verify_product_token(token)
        return user_id, product_id

    # Fall back to JWT
    if credentials:
        user_id = await get_current_user(credentials)
        return user_id, None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authorization"
    )
