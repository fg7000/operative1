from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_queue():
    from services.database import supabase
    res = supabase.table('reply_queue').select('*').order('created_at', desc=True).limit(100).execute()
    return res.data

@router.get("/pending")
async def list_pending():
    from services.database import supabase
    res = supabase.table('reply_queue').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    return res.data
