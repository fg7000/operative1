from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class CreateProductRequest(BaseModel):
    config: dict[str, Any]
    user_id: str

@router.get("/")
async def list_products():
    from services.database import supabase
    res = supabase.table('products').select('*').execute()
    return res.data

@router.post("/create")
async def create_product(body: CreateProductRequest):
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
        "active": True,
    }
    res = supabase.table('products').insert(row).execute()
    return res.data[0] if res.data else {"error": "insert failed"}

@router.get("/check")
async def check_user_has_products(user_id: str):
    from services.database import supabase
    res = supabase.table('products').select('id', count='exact').eq('user_id', user_id).execute()
    return {"has_products": len(res.data) > 0, "count": len(res.data)}

@router.get("/{product_id}")
async def get_product(product_id: str):
    from services.database import supabase
    res = supabase.table('products').select('*').eq('id', product_id).execute()
    return res.data[0] if res.data else None
