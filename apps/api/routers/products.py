from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_products():
    from services.database import supabase
    res = supabase.table('products').select('*').execute()
    return res.data

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
