from fastapi import APIRouter
from pipelines.twitter import run_twitter_pipeline
import httpx
import json
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')


@router.get("/")
async def list_queue():
    from services.database import supabase
    res = supabase.table('reply_queue').select('*').order('created_at', desc=True).limit(20).execute()
    return res.data

@router.get("/pending")
async def list_pending():
    from services.database import supabase
    res = supabase.table('reply_queue').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    return res.data

@router.post("/test-twitter-pipeline")
async def test_twitter_pipeline():
    await run_twitter_pipeline()
    return {"status": "pipeline run complete"}

@router.post("/rank")
async def rank_queue():
    """AI-powered ranking of all pending queue items by strategic value."""
    from services.database import supabase

    res = supabase.table('reply_queue').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    items = res.data
    if not items:
        return {"ranked_ids": [], "notes": {}}

    # Build summary for AI
    items_summary = []
    for item in items:
        em = item.get('engagement_metrics') or {}
        items_summary.append({
            'id': item['id'],
            'platform': item['platform'],
            'original_content': item['original_content'][:200],
            'original_author': item.get('original_author', ''),
            'draft_reply': item['draft_reply'][:200],
            'confidence_score': item.get('confidence_score', 0),
            'reply_mode': em.get('reply_mode', 'unknown'),
            'relevance_reason': em.get('relevance_reason', ''),
            'relevance_score': em.get('relevance_score', 0),
        })

    prompt = f"""You are a strategic marketing advisor. Given these pending replies, rank them from most to least strategically valuable to post. Consider: original tweet engagement, audience fit, reply quality, timing relevance, and potential for positive brand exposure. Return JSON only: {{"ranked_ids": ["id1", "id2", ...], "notes": {{"id1": "High value - person has 50k followers asking exactly what we solve"}}}}

Pending items:
{json.dumps(items_summary, indent=2)}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 2000
                }
            )
            content = resp.json()['choices'][0]['message']['content']

            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first != -1 and last > first:
                result = json.loads(clean[first:last + 1])
                return result

        return {"error": "Failed to parse AI response"}
    except Exception as e:
        logger.error(f"Queue rank error: {e}", exc_info=True)
        return {"error": str(e)}

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
