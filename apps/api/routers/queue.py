"""
Queue router for Operative1 API.

Endpoints:
- GET /queue/pending — List pending queue items for a product (auth + ownership required)
- GET /queue/history — List posted/failed/rejected items for a product (auth + ownership required)
- POST /queue/rank — AI-powered ranking for a product's queue
- POST /queue/{id}/approve — Approve and post a reply
- POST /queue/{id}/reject — Reject a reply
- PATCH /queue/{id}/edit — Edit reply text
- POST /queue/{id}/mark-posted — Mark as posted (called by extension)
- POST /queue/{id}/mark-failed — Mark as failed (called by extension)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pipelines.twitter import run_twitter_pipeline
from services.agent_prompts import QUEUE_RANKER_PROMPT
from services.auth import get_current_user, verify_product_ownership
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
async def list_queue(
    product_id: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """List recent queue items. Optionally filter by product."""
    from services.database import supabase

    query = supabase.table('reply_queue').select('*').order('created_at', desc=True).limit(20)

    if product_id:
        await verify_product_ownership(user_id, product_id)
        query = query.eq('product_id', product_id)

    res = query.execute()
    return res.data


@router.get("/pending")
async def list_pending(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    List pending queue items for a specific product.

    Sorted by: reply_mode priority (direct_pitch > soft_mention > helpful_expert),
    then by relevance score descending.

    product_id is REQUIRED to prevent data leaks.
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('reply_queue').select('*').eq('product_id', product_id).eq('status', 'pending').order('created_at', desc=True).execute()
    items = res.data or []

    # Sort by reply_mode priority, then by relevance score
    MODE_PRIORITY = {'direct_pitch': 0, 'soft_mention': 1, 'helpful_expert': 2}

    def sort_key(item):
        metrics = item.get('engagement_metrics') or {}
        mode = metrics.get('reply_mode', 'helpful_expert')
        mode_rank = MODE_PRIORITY.get(mode, 3)
        relevance = metrics.get('relevance_score', 0) or 0
        return (mode_rank, -relevance)  # Lower mode_rank first, higher relevance first

    return sorted(items, key=sort_key)


@router.get("/history")
async def list_history(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Return posted, failed, and rejected items for audit trail.

    product_id is REQUIRED to prevent data leaks.
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('reply_queue').select('*').eq('product_id', product_id).neq('status', 'pending').order('created_at', desc=True).limit(100).execute()
    return res.data


@router.delete("/clear-pending")
async def clear_pending(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete all pending queue items for a product."""
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('reply_queue').delete().eq('product_id', product_id).eq('status', 'pending').execute()
    deleted = len(res.data) if res.data else 0
    logger.info(f"Cleared {deleted} pending queue items for product {product_id}")
    return {"status": "cleared", "deleted": deleted}


@router.delete("/clear-seen")
async def clear_seen(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """Clear seen_posts so pipeline can re-process tweets with new intelligence."""
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    # Note: seen_posts doesn't have product_id currently, so this clears all twitter seen posts
    # TODO: Add product_id to seen_posts table for proper isolation
    res = supabase.table('seen_posts').delete().eq('platform', 'twitter').execute()
    deleted = len(res.data) if res.data else 0
    logger.info(f"Cleared {deleted} twitter seen posts")
    return {"status": "cleared", "deleted": deleted}


@router.post("/cleanup-errors")
async def cleanup_errors(
    product_id: str,
    include_stale: bool = False,
    user_id: str = Depends(get_current_user)
):
    """
    Mark pending items with errors (like 226 automation detection) as failed.
    Optionally also clean stale tweets (>48h old).

    Items that already have error messages in rejection_reason should not
    remain in pending status - they belong in the failed category.
    """
    from services.database import supabase
    from datetime import datetime, timedelta

    await verify_product_ownership(user_id, product_id)

    # Find pending items
    res = supabase.table('reply_queue').select('id,rejection_reason,engagement_metrics,original_url,created_at').eq('product_id', product_id).eq('status', 'pending').execute()

    cleanup_count = 0
    stale_count = 0
    stale_threshold = datetime.utcnow() - timedelta(hours=48)

    for item in res.data or []:
        reason = item.get('rejection_reason') or ''
        metrics = item.get('engagement_metrics') or {}
        error_msg = metrics.get('error') or ''

        # Check for error indicators
        has_error = (
            '226' in reason or
            '226' in error_msg or
            'automated' in reason.lower() or
            'automated' in error_msg.lower() or
            (reason and len(reason) > 0)  # Any rejection_reason on pending item
        )

        if has_error:
            supabase.table('reply_queue').update({
                'status': 'failed',
                'rejection_reason': reason or error_msg or 'Auto-cleaned: had error in pending state'
            }).eq('id', item['id']).execute()
            cleanup_count += 1
            logger.info(f"Cleaned up item {item['id']}: {reason or error_msg}")
            continue

        # Check if stale (>48h old)
        if include_stale:
            is_stale = False
            # Try to extract tweet timestamp from URL (Twitter snowflake ID)
            url = item.get('original_url') or ''
            if '/status/' in url:
                try:
                    tweet_id = url.split('/status/')[-1].split('?')[0].split('/')[0]
                    if tweet_id.isdigit() and len(tweet_id) > 15:
                        timestamp_ms = (int(tweet_id) >> 22) + 1288834974657
                        tweet_date = datetime.utcfromtimestamp(timestamp_ms / 1000)
                        is_stale = tweet_date < stale_threshold
                except Exception:
                    pass

            # Fallback: check created_at
            if not is_stale and item.get('created_at'):
                try:
                    created = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
                    is_stale = created.replace(tzinfo=None) < stale_threshold
                except Exception:
                    pass

            if is_stale:
                supabase.table('reply_queue').update({
                    'status': 'failed',
                    'rejection_reason': 'Auto-cleaned: tweet is stale (>48h old)'
                }).eq('id', item['id']).execute()
                stale_count += 1
                logger.info(f"Cleaned stale item {item['id']}")

    return {"status": "cleaned", "items_moved_to_failed": cleanup_count, "stale_cleaned": stale_count}


@router.post("/test-twitter-pipeline")
async def test_twitter_pipeline():
    """Manually trigger the Twitter pipeline. Admin only."""
    await run_twitter_pipeline()
    return {"status": "pipeline run complete"}


@router.post("/rank")
async def rank_queue(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """AI-powered ranking of pending queue items by strategic value."""
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    res = supabase.table('reply_queue').select('*').eq('product_id', product_id).eq('status', 'pending').order('created_at', desc=True).execute()
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

    prompt = QUEUE_RANKER_PROMPT + f"""

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


async def verify_queue_item_ownership(user_id: str, queue_id: str):
    """Verify that a queue item belongs to a product owned by the user."""
    from services.database import supabase

    # Get the queue item's product_id
    item = supabase.table('reply_queue').select('product_id').eq('id', queue_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Queue item not found")

    product_id = item.data[0]['product_id']
    await verify_product_ownership(user_id, product_id)


@router.post("/{queue_id}/approve")
async def approve_reply(
    queue_id: str,
    user_id: str = Depends(get_current_user)
):
    """Approve and post a reply via server-side posting."""
    from services.database import supabase
    from services.poster import post_to_twitter

    await verify_queue_item_ownership(user_id, queue_id)

    item = supabase.table('reply_queue').select('*').eq('id', queue_id).single().execute()
    if not item.data:
        return {"error": "not found"}

    await post_to_twitter(
        queue_id,
        {"reply": item.data.get('edited_reply') or item.data.get('draft_reply')},
        {"id": item.data.get('original_url', '').split('/')[-1], "url": item.data.get('original_url')},
        {}
    )
    # Check actual result from database
    result = supabase.table('reply_queue').select('status,rejection_reason,engagement_metrics').eq('id', queue_id).single().execute()
    if result.data and result.data.get('status') == 'posted':
        posted_id = (result.data.get('engagement_metrics') or {}).get('posted_tweet_id')
        return {"status": "posted", "tweet_id": posted_id}
    else:
        return {"status": "failed", "error": result.data.get('rejection_reason') if result.data else "unknown error"}


@router.post("/{queue_id}/reject")
async def reject_reply(
    queue_id: str,
    reason: str = "",
    user_id: str = Depends(get_current_user)
):
    """Reject a reply."""
    from services.database import supabase

    await verify_queue_item_ownership(user_id, queue_id)

    supabase.table('reply_queue').update({
        "status": "rejected",
        "rejection_reason": reason
    }).eq('id', queue_id).execute()
    return {"status": "rejected"}


@router.patch("/{queue_id}/edit")
async def edit_reply(
    queue_id: str,
    edited_reply: str,
    user_id: str = Depends(get_current_user)
):
    """Edit reply text before posting."""
    from services.database import supabase

    await verify_queue_item_ownership(user_id, queue_id)

    supabase.table('reply_queue').update({
        "edited_reply": edited_reply
    }).eq('id', queue_id).execute()
    return {"status": "updated"}


class MarkPostedRequest(BaseModel):
    posted_tweet_id: Optional[str] = None


class MarkFailedRequest(BaseModel):
    error: Optional[str] = None


@router.post("/{queue_id}/mark-posted")
async def mark_posted(
    queue_id: str,
    body: MarkPostedRequest,
    user_id: str = Depends(get_current_user)
):
    """Mark a queue item as posted (called by frontend after extension posts successfully).

    NEVER DELETE — audit trail required. Status updates only.
    """
    from services.database import supabase

    await verify_queue_item_ownership(user_id, queue_id)

    existing = supabase.table('reply_queue').select('engagement_metrics').eq('id', queue_id).execute()
    metrics = (existing.data[0].get('engagement_metrics') or {}) if existing.data else {}
    if body.posted_tweet_id:
        metrics['posted_tweet_id'] = str(body.posted_tweet_id)

    # STATUS UPDATE ONLY — no deletions allowed
    supabase.table('reply_queue').update({
        'status': 'posted',
        'posted_at': 'now()',
        'engagement_metrics': metrics
    }).eq('id', queue_id).execute()
    return {"status": "posted"}


@router.post("/{queue_id}/mark-failed")
async def mark_failed(
    queue_id: str,
    body: MarkFailedRequest,
    user_id: str = Depends(get_current_user)
):
    """Mark a queue item as failed (called by frontend when extension posting fails).

    NEVER DELETE — audit trail required. Status updates only.
    """
    from services.database import supabase

    await verify_queue_item_ownership(user_id, queue_id)

    # STATUS UPDATE ONLY — no deletions allowed
    supabase.table('reply_queue').update({
        'status': 'failed',
        'rejection_reason': body.error or 'Extension posting failed'
    }).eq('id', queue_id).execute()
    return {"status": "failed"}
