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

Autopilot endpoints:
- GET /queue/auto-approved — Items ready for extension to post (product token auth)
- GET /queue/autopilot-log — Last 24h autopilot activity log
- GET /queue/health — Account health status (green/yellow/red)
- POST /queue/extension-heartbeat — Extension liveness ping (product token auth)
- POST /queue/pause — Pause autopilot (indefinite or timed)
- POST /queue/resume — Resume autopilot
- POST /queue/generate-token — Generate product-scoped API token
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from pipelines.twitter import run_twitter_pipeline
from services.agent_prompts import QUEUE_RANKER_PROMPT
from services.auth import (
    get_current_user, verify_product_ownership,
    get_user_or_product_token, save_product_token,
)
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
    status: Optional[str] = None,
    since: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """
    Return posted, failed, and rejected items for audit trail.

    product_id is REQUIRED to prevent data leaks.
    Optional filters:
      - status: filter by specific status (posted, failed, rejected)
      - since: ISO datetime string, only return items created after this time
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    query = supabase.table('reply_queue').select('*').eq('product_id', product_id)

    if status:
        query = query.eq('status', status)
    else:
        query = query.neq('status', 'pending')

    if since:
        query = query.gte('created_at', since)

    res = query.order('created_at', desc=True).limit(100).execute()
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
    auth: tuple = Depends(get_user_or_product_token)
):
    """Mark a queue item as posted (called by frontend or extension autopilot).

    Accepts either JWT or product-scoped token.
    NEVER DELETE — audit trail required. Status updates only.
    """
    from services.database import supabase

    user_id, token_product_id = auth
    if not token_product_id:
        await verify_queue_item_ownership(user_id, queue_id)

    existing = supabase.table('reply_queue').select('engagement_metrics,product_id').eq('id', queue_id).execute()

    # Verify product token owns this queue item
    if token_product_id and existing.data:
        if existing.data[0].get('product_id') != token_product_id:
            raise HTTPException(status_code=403, detail="Queue item does not belong to this product")
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
    auth: tuple = Depends(get_user_or_product_token)
):
    """Mark a queue item as failed (called by frontend or extension autopilot).

    Accepts either JWT or product-scoped token.
    NEVER DELETE — audit trail required. Status updates only.
    """
    from services.database import supabase

    user_id, token_product_id = auth
    if not token_product_id:
        await verify_queue_item_ownership(user_id, queue_id)

    # Verify product token owns this queue item
    if token_product_id:
        item = supabase.table('reply_queue').select('product_id').eq('id', queue_id).execute()
        if item.data and item.data[0].get('product_id') != token_product_id:
            raise HTTPException(status_code=403, detail="Queue item does not belong to this product")

    # STATUS UPDATE ONLY — no deletions allowed
    error_msg = body.error or 'Extension posting failed'

    # Permanent failures get 'rejected' (never retried by autopilot)
    permanent_errors = ['duplicate_tweet', 'duplicate', 'already been sent']
    if any(pe in error_msg.lower() for pe in permanent_errors):
        status = 'rejected'
    else:
        status = 'failed'

    supabase.table('reply_queue').update({
        'status': status,
        'rejection_reason': error_msg
    }).eq('id', queue_id).execute()
    return {"status": status}


# ─── Autopilot Endpoints ─────────────────────────────────────────


@router.get("/auto-approved")
async def list_auto_approved(
    product_id: str,
    auth: tuple = Depends(get_user_or_product_token)
):
    """List auto_approved items ready for extension to post.

    Accepts either JWT or product-scoped token.
    Excludes items that already have a posted_tweet_id (double-post prevention).
    """
    from services.database import supabase

    user_id, token_product_id = auth

    # If authed via product token, enforce product scope
    if token_product_id and token_product_id != product_id:
        raise HTTPException(status_code=403, detail="Token does not match product_id")

    if not token_product_id:
        await verify_product_ownership(user_id, product_id)

    res = supabase.table('reply_queue').select('*') \
        .eq('product_id', product_id) \
        .eq('status', 'auto_approved') \
        .order('created_at', desc=False) \
        .limit(10) \
        .execute()

    # Filter out items that already have a posted_tweet_id (double-post prevention)
    items = []
    for item in (res.data or []):
        metrics = item.get('engagement_metrics') or {}
        if not metrics.get('posted_tweet_id'):
            items.append(item)

    return items


@router.get("/autopilot-log")
async def autopilot_log(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """Return last 24h autopilot activity for monitoring.

    Returns auto-approved, posted, and failed items with timestamps,
    scores, reply mode, and tweet text snippets. Also includes
    aggregate stats and current tier/health status.
    """
    from services.database import supabase
    from services.rate_limiter import get_health_status

    await verify_product_ownership(user_id, product_id)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    # Get items from last 24h
    res = supabase.table('reply_queue').select(
        'id,status,platform,original_content,draft_reply,edited_reply,'
        'confidence_score,engagement_metrics,created_at,posted_at,rejection_reason'
    ).eq('product_id', product_id) \
        .gte('created_at', cutoff) \
        .order('created_at', desc=True) \
        .limit(500) \
        .execute()

    items = res.data or []

    # Categorize
    auto_approved = []
    posted = []
    failed = []
    skipped = []

    for item in items:
        metrics = item.get('engagement_metrics') or {}
        summary = {
            'id': item['id'],
            'status': item['status'],
            'platform': item.get('platform', 'twitter'),
            'tweet_snippet': (item.get('original_content') or '')[:100],
            'reply_snippet': (item.get('edited_reply') or item.get('draft_reply') or '')[:100],
            'reply_mode': metrics.get('reply_mode'),
            'relevance_score': metrics.get('relevance_score'),
            'confidence': item.get('confidence_score'),
            'posted_tweet_id': metrics.get('posted_tweet_id'),
            'error': item.get('rejection_reason'),
            'created_at': item.get('created_at'),
            'posted_at': item.get('posted_at'),
        }

        if item['status'] == 'auto_approved':
            auto_approved.append(summary)
        elif item['status'] == 'posted':
            posted.append(summary)
        elif item['status'] == 'failed':
            failed.append(summary)
        else:
            skipped.append(summary)

    # Get product for tier info (must include 'id' for get_health_status)
    product_res = supabase.table('products').select('id,autopilot').eq('id', product_id).single().execute()
    autopilot = (product_res.data.get('autopilot') or {}) if product_res.data else {}

    # Get health
    product_data = product_res.data or {'id': product_id}
    health = await get_health_status(product_data, 'twitter')

    return {
        'auto_approved': auto_approved,
        'posted': posted,
        'failed': failed,
        'skipped': skipped,
        'stats': {
            'total_auto_approved': len(auto_approved),
            'total_posted': len(posted),
            'total_failed': len(failed),
            'total_skipped': len(skipped),
        },
        'tier': autopilot.get('tier', 0),
        'health': health,
        'paused': autopilot.get('paused', False),
        'paused_until': autopilot.get('paused_until'),
        'pause_reason': autopilot.get('pause_reason'),
        'last_heartbeat': autopilot.get('last_heartbeat'),
        'event_log': (autopilot.get('event_log') or [])[-20:],  # Last 20 events
    }


@router.get("/health")
async def get_health(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get account health status for a product."""
    from services.database import supabase
    from services.rate_limiter import get_health_status, get_rate_limit_status

    await verify_product_ownership(user_id, product_id)

    product_res = supabase.table('products').select('*').eq('id', product_id).single().execute()
    product = product_res.data or {'id': product_id}

    health = await get_health_status(product, 'twitter')
    rate_status = await get_rate_limit_status(product, 'twitter')

    autopilot = product.get('autopilot') or {}
    tier = autopilot.get('tier', 0)

    # Import tier config for daily_cap
    from services.rate_limiter import TIER_CONFIG
    tier_config = TIER_CONFIG.get(tier, TIER_CONFIG[0])

    return {
        'health': health.get('status', 'green'),  # Flatten to string for dashboard
        'tier': tier,
        'daily_cap': tier_config['daily_cap'],
        'posts_today': health.get('total_posts_24h', 0),
        'paused': autopilot.get('paused', False),
        'paused_until': autopilot.get('paused_until'),
        'pause_reason': autopilot.get('pause_reason'),
        'last_heartbeat': autopilot.get('last_heartbeat'),
    }


class HeartbeatRequest(BaseModel):
    product_id: str


@router.post("/extension-heartbeat")
async def extension_heartbeat(
    body: HeartbeatRequest,
    auth: tuple = Depends(get_user_or_product_token)
):
    """Extension heartbeat ping. Updates last_heartbeat timestamp.

    Accepts either JWT or product-scoped token.
    """
    from services.database import supabase

    user_id, token_product_id = auth

    # If authed via product token, enforce product scope
    if token_product_id and token_product_id != body.product_id:
        raise HTTPException(status_code=403, detail="Token does not match product_id")

    if not token_product_id:
        await verify_product_ownership(user_id, body.product_id)

    # Update heartbeat timestamp
    product_res = supabase.table('products').select('autopilot').eq('id', body.product_id).single().execute()
    autopilot = (product_res.data.get('autopilot') or {}) if product_res.data else {}
    autopilot['last_heartbeat'] = datetime.now(timezone.utc).isoformat()

    supabase.table('products').update({'autopilot': autopilot}).eq('id', body.product_id).execute()

    return {"status": "ok", "timestamp": autopilot['last_heartbeat']}


class PauseRequest(BaseModel):
    product_id: str
    duration_hours: Optional[int] = None  # None = indefinite


@router.post("/pause")
async def pause_autopilot(
    body: PauseRequest,
    user_id: str = Depends(get_current_user)
):
    """Pause autopilot for a product. Indefinite or timed."""
    from services.database import supabase
    from services.autopilot import append_event_log

    await verify_product_ownership(user_id, body.product_id)

    product_res = supabase.table('products').select('*').eq('id', body.product_id).single().execute()
    product = product_res.data or {}
    autopilot = product.get('autopilot') or {}

    if body.duration_hours:
        pause_until = datetime.now(timezone.utc) + timedelta(hours=body.duration_hours)
        autopilot['paused_until'] = pause_until.isoformat()
        autopilot['pause_reason'] = f'manual_timed_{body.duration_hours}h'
    else:
        autopilot['paused'] = True
        autopilot['pause_reason'] = 'manual_pause'

    event_log = append_event_log(product, 'manual_pause', {
        'duration_hours': body.duration_hours,
        'user_id': user_id,
    })
    autopilot['event_log'] = event_log

    supabase.table('products').update({'autopilot': autopilot}).eq('id', body.product_id).execute()

    return {
        "status": "paused",
        "paused_until": autopilot.get('paused_until'),
        "indefinite": body.duration_hours is None,
    }


class ResumeRequest(BaseModel):
    product_id: str


@router.post("/resume")
async def resume_autopilot(
    body: ResumeRequest,
    user_id: str = Depends(get_current_user)
):
    """Resume autopilot for a product."""
    from services.database import supabase
    from services.autopilot import append_event_log

    await verify_product_ownership(user_id, body.product_id)

    product_res = supabase.table('products').select('*').eq('id', body.product_id).single().execute()
    product = product_res.data or {}
    autopilot = product.get('autopilot') or {}

    autopilot['paused'] = False
    autopilot['paused_until'] = None
    autopilot['pause_reason'] = None
    autopilot['last_failure_pause_hours'] = 0  # Reset escalation

    event_log = append_event_log(product, 'manual_resume', {'user_id': user_id})
    autopilot['event_log'] = event_log

    supabase.table('products').update({'autopilot': autopilot}).eq('id', body.product_id).execute()

    return {"status": "resumed"}


class GenerateTokenRequest(BaseModel):
    product_id: str


@router.post("/generate-token")
async def generate_token(
    body: GenerateTokenRequest,
    user_id: str = Depends(get_current_user)
):
    """Generate a product-scoped API token for extension authentication."""
    await verify_product_ownership(user_id, body.product_id)

    token = await save_product_token(body.product_id)

    return {"token": token, "product_id": body.product_id}
