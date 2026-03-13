"""
Products router for Operative1 API.

Endpoints:
- GET /products — List user's products with pending counts (auth required)
- GET /products/check — Check if user has products (for onboarding redirect)
- GET /products/{id} — Get single product (auth + ownership required)
- POST /products/create — Create product (used by onboarding)
- PATCH /products/{id} — Update product settings (auth + ownership required)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Any, Optional, List
import logging

from services.auth import get_current_user, verify_product_ownership

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateProductRequest(BaseModel):
    config: dict[str, Any]
    user_id: str


class TargetingConfig(BaseModel):
    """Tweet targeting thresholds for pre-filtering."""
    max_tweet_age_hours: Optional[int] = Field(None, ge=1, le=168)  # 1h - 1 week
    min_likes: Optional[int] = Field(None, ge=0, le=1000)
    min_author_followers: Optional[int] = Field(None, ge=0, le=100000)
    max_reply_count: Optional[int] = Field(None, ge=1, le=1000)
    min_opportunity_score: Optional[int] = Field(None, ge=0, le=500)
    max_ai_calls_per_run: Optional[int] = Field(None, ge=1, le=100)


class AutopilotConfig(BaseModel):
    """Autopilot settings for automatic reply approval."""
    enabled: Optional[bool] = None
    min_relevance_score: Optional[int] = Field(None, ge=1, le=10)
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    require_no_product_mention: Optional[bool] = None


class PostingHoursConfig(BaseModel):
    """Posting hours configuration."""
    enabled: Optional[bool] = None
    timezone: Optional[str] = Field(None, max_length=50)  # e.g., "America/New_York"
    start_hour: Optional[int] = Field(None, ge=0, le=23)
    end_hour: Optional[int] = Field(None, ge=0, le=23)
    days_of_week: Optional[List[int]] = None  # 0=Monday, 6=Sunday


class UpdateProductRequest(BaseModel):
    """
    Validation rules:
    - name: 1-100 chars
    - keywords: max 50 per platform
    - system_prompt: max 2000 chars
    - reply_mode_distribution: must sum to 100
    - max_replies_per_day: 1-100 per platform
    - max_replies_per_hour: 1-20 per platform
    - min_delay_between_posts: 30-3600 seconds
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = Field(None, max_length=2000)
    keywords: Optional[dict[str, List[str]]] = None
    tone: Optional[str] = Field(None, max_length=50)
    reply_mode_distribution: Optional[dict[str, int]] = None
    auto_post: Optional[dict[str, bool]] = None
    max_daily_replies: Optional[dict[str, int]] = None
    active: Optional[bool] = None

    # Fire rate control fields (Part 2)
    max_replies_per_day: Optional[dict[str, int]] = None
    max_replies_per_hour: Optional[dict[str, int]] = None
    min_delay_between_posts: Optional[int] = Field(None, ge=30, le=3600)

    # Posting hours (Part 2)
    posting_hours: Optional[PostingHoursConfig] = None

    # Autopilot config (Part 2)
    autopilot: Optional[AutopilotConfig] = None

    # Tweet targeting thresholds (Part 2)
    targeting: Optional[TargetingConfig] = None

    @validator('keywords')
    def validate_keywords(cls, v):
        if v is None:
            return v
        for platform, kw_list in v.items():
            if len(kw_list) > 50:
                raise ValueError(f'Max 50 keywords per platform, got {len(kw_list)} for {platform}')
        return v

    @validator('reply_mode_distribution')
    def validate_distribution(cls, v):
        if v is None:
            return v
        total = sum(v.values())
        if total != 100:
            raise ValueError(f'Reply mode distribution must sum to 100, got {total}')
        return v

    @validator('max_replies_per_day')
    def validate_max_daily(cls, v):
        if v is None:
            return v
        for platform, count in v.items():
            if not 1 <= count <= 100:
                raise ValueError(f'max_replies_per_day must be 1-100, got {count} for {platform}')
        return v

    @validator('max_replies_per_hour')
    def validate_max_hourly(cls, v):
        if v is None:
            return v
        for platform, count in v.items():
            if not 1 <= count <= 20:
                raise ValueError(f'max_replies_per_hour must be 1-20, got {count} for {platform}')
        return v

    @validator('posting_hours')
    def validate_posting_hours(cls, v):
        if v is None:
            return v
        if v.days_of_week is not None:
            for day in v.days_of_week:
                if not 0 <= day <= 6:
                    raise ValueError(f'days_of_week must be 0-6, got {day}')
        return v


@router.get("/")
async def list_products(user_id: str = Depends(get_current_user)):
    """
    List all products for the authenticated user, with pending queue counts.
    """
    from services.database import supabase

    # Fetch products
    products_res = supabase.table('products').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
    products = products_res.data or []

    if not products:
        return []

    # Fetch pending counts for all products in one query
    product_ids = [p['id'] for p in products]
    counts_res = supabase.table('reply_queue').select('product_id', count='exact').eq('status', 'pending').in_('product_id', product_ids).execute()

    # Build counts map
    # Note: Supabase doesn't support GROUP BY easily, so we'll do a simple count per product
    # For better performance with many products, consider a raw SQL query
    pending_counts = {}
    for product_id in product_ids:
        count_res = supabase.table('reply_queue').select('id', count='exact').eq('product_id', product_id).eq('status', 'pending').execute()
        pending_counts[product_id] = count_res.count or 0

    # Add counts to products
    for product in products:
        product['pending_count'] = pending_counts.get(product['id'], 0)

    return products


@router.get("/check")
async def check_user_has_products(user_id: str):
    """
    Check if user has any products. Used by onboarding flow.
    No auth required - user_id passed explicitly.
    """
    from services.database import supabase
    res = supabase.table('products').select('id', count='exact').eq('user_id', user_id).execute()
    return {"has_products": len(res.data) > 0, "count": len(res.data)}


@router.get("/by-email")
async def get_products_by_email(email: str):
    """
    Get products for a user by email. Used by extension popup.
    Returns minimal product info for dropdown selection.
    """
    from services.database import supabase

    # First, look up user_id from auth.users via email
    # Note: We need to query the products table which has user_id
    # The extension will send email, we need to find products for that user

    # Since we can't directly query auth.users with service_role easily,
    # we'll look for products where the user email matches
    # This requires joining with auth data or storing email in products

    # For now, return error - extension should use user_id from session
    # Actually, let's query products and filter by checking auth
    # The simplest approach: products table should have user_id,
    # and the extension should get user_id from the session

    # Alternative: Accept user_id directly in extension after login
    return {"error": "Use user_id parameter instead", "products": []}


@router.get("/by-user/{user_id}")
async def get_products_by_user_id(user_id: str):
    """
    Get products for a user by user_id. Used by extension popup.
    Returns minimal product info for dropdown selection.
    No auth required for extension access.
    """
    from services.database import supabase

    res = supabase.table('products').select('id,name,slug').eq('user_id', user_id).eq('active', True).execute()
    return res.data or []


@router.get("/{product_id}")
async def get_product(product_id: str, user_id: str = Depends(get_current_user)):
    """
    Get a single product. Requires ownership.
    """
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('products').select('*').eq('id', product_id).execute()
    return res.data[0] if res.data else None


@router.post("/create")
async def create_product(body: CreateProductRequest):
    """
    Create a new product. Used by onboarding flow.
    user_id is passed explicitly from the frontend session.
    """
    from services.database import supabase
    from services.keyword_quality import filter_keywords, generate_keywords_for_product

    config = {**body.config}

    # Run keyword quality check on all platforms
    keywords = config.get('keywords', {})
    if keywords:
        for platform, kw_list in keywords.items():
            if not isinstance(kw_list, list) or not kw_list:
                continue
            good, filtered_out = filter_keywords(kw_list)
            if filtered_out:
                logger.warning(f"Product creation: filtered generic keywords for {platform}: {filtered_out}")
            if not good:
                # All keywords were too generic — auto-generate better ones
                logger.warning(f"Product creation: ALL {platform} keywords were generic, generating AI replacements")
                ai_keywords = await generate_keywords_for_product(config, platform)
                if ai_keywords:
                    keywords[platform] = ai_keywords
                    logger.info(f"Product creation: replaced {platform} keywords with AI-generated: {ai_keywords}")
                else:
                    keywords[platform] = kw_list  # fallback to originals
            else:
                keywords[platform] = good  # use only the quality keywords
        config['keywords'] = keywords

    row = {
        **config,
        "user_id": body.user_id,
        "auto_post": {"twitter": False, "reddit": False, "linkedin": False, "hn": False},
        "max_daily_replies": {"twitter": 5, "reddit": 3, "linkedin": 3, "hn": 1},
        "reply_mode_distribution": {"direct_pitch": 50, "soft_mention": 35, "helpful_expert": 15},
        "active": True,
        # Fire rate control defaults (Part 2)
        "max_replies_per_day": {"twitter": 10, "reddit": 5, "linkedin": 5, "hn": 2},
        "max_replies_per_hour": {"twitter": 3, "reddit": 2, "linkedin": 2, "hn": 1},
        "min_delay_between_posts": 120,  # 2 minutes minimum between posts
        "posting_hours": {
            "enabled": False,
            "timezone": "UTC",
            "start_hour": 9,
            "end_hour": 21,
            "days_of_week": [0, 1, 2, 3, 4],  # Monday-Friday
        },
        "autopilot": {
            "enabled": False,
            "min_relevance_score": 7,
            "min_confidence": 0.8,
            "require_no_product_mention": True,
        },
        "targeting": {
            "max_tweet_age_hours": 24,
            "min_likes": 2,
            "min_author_followers": 50,
            "max_reply_count": 100,
            "min_opportunity_score": 10,
            "max_ai_calls_per_run": 20,
        },
    }
    res = supabase.table('products').insert(row).execute()
    return res.data[0] if res.data else {"error": "insert failed"}


@router.patch("/{product_id}")
async def update_product(
    product_id: str,
    body: UpdateProductRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Update product settings. Requires ownership.
    Only updates fields that are provided (non-None).
    """
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    # Build update dict with only provided fields
    update_data = {}
    if body.name is not None:
        update_data['name'] = body.name
    if body.description is not None:
        update_data['description'] = body.description
    if body.system_prompt is not None:
        update_data['system_prompt'] = body.system_prompt
    if body.keywords is not None:
        update_data['keywords'] = body.keywords
    if body.tone is not None:
        update_data['tone'] = body.tone
    if body.reply_mode_distribution is not None:
        update_data['reply_mode_distribution'] = body.reply_mode_distribution
    if body.auto_post is not None:
        update_data['auto_post'] = body.auto_post
    if body.max_daily_replies is not None:
        update_data['max_daily_replies'] = body.max_daily_replies
    if body.active is not None:
        update_data['active'] = body.active

    # Fire rate control fields (Part 2)
    if body.max_replies_per_day is not None:
        update_data['max_replies_per_day'] = body.max_replies_per_day
    if body.max_replies_per_hour is not None:
        update_data['max_replies_per_hour'] = body.max_replies_per_hour
    if body.min_delay_between_posts is not None:
        update_data['min_delay_between_posts'] = body.min_delay_between_posts
    if body.posting_hours is not None:
        update_data['posting_hours'] = body.posting_hours.dict(exclude_none=True)
    if body.autopilot is not None:
        update_data['autopilot'] = body.autopilot.dict(exclude_none=True)
    if body.targeting is not None:
        update_data['targeting'] = body.targeting.dict(exclude_none=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    logger.info(f"Updating product {product_id}: {list(update_data.keys())}")

    res = supabase.table('products').update(update_data).eq('id', product_id).execute()
    return res.data[0] if res.data else {"error": "update failed"}
