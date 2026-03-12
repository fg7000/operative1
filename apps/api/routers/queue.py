from fastapi import APIRouter
from pipelines.twitter import run_twitter_pipeline
from dotenv import load_dotenv
import httpx
import json
import os
import logging

load_dotenv()

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

    # Use short numeric keys for AI, map back to UUIDs after
    id_map = {str(i): item['id'] for i, item in enumerate(items)}
    items_summary = []
    for i, item in enumerate(items):
        em = item.get('engagement_metrics') or {}
        items_summary.append({
            'idx': i,
            'platform': item['platform'],
            'original': item['original_content'][:150],
            'reply': item['draft_reply'][:150],
            'score': item.get('confidence_score', 0),
            'mode': em.get('reply_mode', ''),
            'reason': em.get('relevance_reason', ''),
        })

    prompt = f"""You are a strategic marketing advisor. Rank these pending replies from most to least strategically valuable to post. Consider: audience fit, reply quality, and potential for positive brand exposure. Return JSON only: {{"ranked": [0, 3, 1, ...], "notes": {{"0": "High value - directly addresses target audience pain point"}}}}
Use the idx numbers.

Items:
{json.dumps(items_summary)}"""

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 4000
                }
            )
            raw_resp = resp.json()
            logger.info(f"Rank API response status: {resp.status_code}")
            logger.info(f"Rank API raw keys: {list(raw_resp.keys())}")
            if 'error' in raw_resp:
                logger.error(f"Rank API error: {raw_resp['error']}")
                return {"error": f"API error: {json.dumps(raw_resp['error'])}"}
            if 'choices' not in raw_resp or not raw_resp['choices']:
                logger.error(f"Rank API no choices: {json.dumps(raw_resp)[:500]}")
                return {"error": f"API returned no choices: {json.dumps(raw_resp)[:200]}"}
            content = raw_resp['choices'][0]['message']['content']
            logger.info(f"Rank raw content: {content[:500]}")

            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first != -1 and last > first:
                try:
                    parsed = json.loads(clean[first:last + 1])
                except json.JSONDecodeError as je:
                    logger.error(f"Rank JSON parse error: {je}, content: {clean[first:first+200]}")
                    return {"ranked_ids": [item['id'] for item in items], "notes": {}}
                # Map numeric indices back to UUIDs
                ranked_indices = parsed.get('ranked', [])
                ranked_ids = [id_map.get(str(idx), '') for idx in ranked_indices if str(idx) in id_map]
                raw_notes = parsed.get('notes', {})
                notes = {id_map.get(str(k), str(k)): v for k, v in raw_notes.items() if str(k) in id_map}
                # Include any items not in the ranking at the end
                remaining = [item['id'] for item in items if item['id'] not in ranked_ids]
                return {"ranked_ids": ranked_ids + remaining, "notes": notes}

            logger.error(f"Rank: no JSON found in response: {content[:300]}")
            return {"ranked_ids": [item['id'] for item in items], "notes": {}}
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
