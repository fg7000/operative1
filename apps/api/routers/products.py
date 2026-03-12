from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

router = APIRouter()

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
    row = {
        **body.config,
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
