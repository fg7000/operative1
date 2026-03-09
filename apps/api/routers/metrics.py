from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_metrics():
    from services.database import supabase
    res = supabase.table('daily_stats').select('*').order('date', desc=True).limit(30).execute()
    return res.data

@router.get("/summary")
async def get_summary():
    from services.database import supabase
    queue_res = supabase.table('reply_queue').select('status').execute()
    stats = {'pending': 0, 'approved': 0, 'posted': 0, 'rejected': 0}
    for item in queue_res.data:
        status = item.get('status', 'pending')
        if status in stats:
            stats[status] += 1
    return stats
