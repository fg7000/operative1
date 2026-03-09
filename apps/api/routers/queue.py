from fastapi import APIRouter
from pipelines.twitter import run_twitter_pipeline

router = APIRouter()

@router.get("/")
async def list_queue():
    from services.database import supabase
    res = supabase.table('reply_queue').select('*').order('created_at', desc=True).limit(20).execute()
    return res.data

@router.post("/test-twitter-pipeline")
async def test_twitter_pipeline():
    await run_twitter_pipeline()
    return {"status": "pipeline run complete"}

@router.post("/{queue_id}/approve")
async def approve_reply(queue_id: str):
    from services.database import supabase
    from services.poster import post_to_twitter
    item = supabase.table('reply_queue').select('*').eq('id', queue_id).single().execute()
    if not item.data:
        return {"error": "not found"}
    await post_to_twitter(
        queue_id,
        {"reply": item.data.get('edited_reply') or item.data.get('draft_reply')},
        {"id": item.data.get('original_url', '').split('/')[-1], "url": item.data.get('original_url')},
        {}
    )
    return {"status": "posted"}

@router.post("/{queue_id}/reject")
async def reject_reply(queue_id: str, reason: str = ""):
    from services.database import supabase
    supabase.table('reply_queue').update({
        "status": "rejected",
        "rejection_reason": reason
    }).eq('id', queue_id).execute()
    return {"status": "rejected"}

@router.patch("/{queue_id}/edit")
async def edit_reply(queue_id: str, edited_reply: str):
    from services.database import supabase
    supabase.table('reply_queue').update({
        "edited_reply": edited_reply
    }).eq('id', queue_id).execute()
    return {"status": "updated"}
