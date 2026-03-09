from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_products():
    from services.database import supabase
    res = supabase.table('products').select('*').execute()
    return res.data

@router.get("/{product_id}")
async def get_product(product_id: str):
    from services.database import supabase
    res = supabase.table('products').select('*').eq('id', product_id).execute()
    return res.data[0] if res.data else None
