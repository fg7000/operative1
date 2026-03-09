from fastapi import APIRouter

router = APIRouter()

@router.post("/approve/{queue_id}")
async def approve_post(queue_id: str):
    from services.database import supabase
    supabase.table('reply_queue').update({'status': 'approved'}).eq('id', queue_id).execute()
    return {"status": "approved"}

@router.post("/reject/{queue_id}")
async def reject_post(queue_id: str, reason: str = ""):
    from services.database import supabase
    supabase.table('reply_queue').update({'status': 'rejected', 'rejection_reason': reason}).eq('id', queue_id).execute()
    return {"status": "rejected"}
