"""
Autopilot queue processor for Operative1.

Automatically approves and posts high-quality replies that meet configured thresholds.
Runs periodically to process pending queue items without manual intervention.

Autopilot criteria (configurable per-product):
- min_relevance_score: Minimum AI relevance score (1-10, default 7)
- min_confidence: Minimum generator confidence (0-1, default 0.8)
- require_no_product_mention: Only auto-approve if product isn't mentioned (default True)

Flow:
1. Get products with autopilot enabled
2. Pre-checks: pause status, heartbeat, failure streak
3. For each product, get pending queue items
4. Check if item meets autopilot thresholds
5. Check per-product rate limits
6. If yes to both: mark as "auto_approved"
7. Process global queue (enforces account-level posting cadence)
8. Post-processing: tier promotion/demotion checks

Pause/Resume (scope 8):
- autopilot.paused = true → indefinite manual pause
- autopilot.paused_until = ISO timestamp → timed pause, auto-resumes

Auto-pause on failure streak (scope 9):
- 3+ consecutive failures → 2h pause
- Fail after 2h resume → 6h pause
- Fail after 6h resume → indefinite pause (manual resume required)
- Streak derived from DB, not JSONB counter (resilient to crashes)

Extension heartbeat (scope 10):
- Extension pings POST /queue/extension-heartbeat every 60s
- If autopilot enabled AND auto_approved items >30 min old AND no heartbeat
  in 5 min → pause with reason "extension_offline"
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.database import supabase
from services.rate_limiter import (
    can_post, get_health_status, get_failure_streak,
    check_tier_promotion, check_tier_demotion
)
from services.poster import post_to_twitter
from services.global_queue import can_post_globally, process_global_queue

logger = logging.getLogger(__name__)

# Event log max entries
EVENT_LOG_MAX = 100


def meets_autopilot_criteria(queue_item: dict, product: dict) -> tuple[bool, str]:
    """
    Check if a queue item meets the product's autopilot criteria.

    Args:
        queue_item: The pending queue item
        product: Product with autopilot config

    Returns:
        (meets_criteria, reason)
    """
    autopilot = product.get('autopilot', {}) or {}

    if not autopilot.get('enabled', False):
        return False, "autopilot_disabled"

    # Get thresholds
    min_relevance = autopilot.get('min_relevance_score', 7)
    min_confidence = autopilot.get('min_confidence', 0.8)
    require_no_mention = autopilot.get('require_no_product_mention', True)

    # Get item scores from engagement_metrics (where they're stored)
    metrics = queue_item.get('engagement_metrics', {}) or {}
    relevance_score = metrics.get('relevance_score', 0)
    confidence = queue_item.get('confidence_score', 0)
    mentions_product = queue_item.get('mentions_product', False)

    # Check relevance score
    if relevance_score < min_relevance:
        return False, f"relevance_too_low:{relevance_score}<{min_relevance}"

    # Check confidence
    if confidence < min_confidence:
        return False, f"confidence_too_low:{confidence}<{min_confidence}"

    # Check product mention
    if require_no_mention and mentions_product:
        return False, "mentions_product"

    return True, "approved"


async def get_autopilot_products() -> list:
    """Get all products with autopilot enabled."""
    res = supabase.table('products').select('*').eq('active', True).execute()
    products = res.data or []

    # Filter to only those with autopilot enabled
    return [p for p in products if (p.get('autopilot', {}) or {}).get('enabled', False)]


async def get_pending_items_for_product(product_id: str, platform: str, limit: int = 10) -> list:
    """Get pending queue items for a product, ordered by opportunity score."""
    res = supabase.table('reply_queue').select('*') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .eq('status', 'pending') \
        .order('created_at', desc=False) \
        .limit(limit) \
        .execute()

    return res.data or []


async def process_autopilot_item(queue_item: dict, product: dict) -> dict:
    """
    Process a single queue item through autopilot approval.

    This only handles APPROVAL - actual posting is done separately
    via the global queue processor to enforce account-level rate limits.

    Returns:
        {
            'action': 'approved' | 'skipped' | 'rate_limited',
            'reason': str,
            'queue_id': str
        }
    """
    queue_id = queue_item['id']
    platform = queue_item['platform']

    # Check if meets autopilot criteria
    meets_criteria, criteria_reason = meets_autopilot_criteria(queue_item, product)
    if not meets_criteria:
        return {
            'action': 'skipped',
            'reason': criteria_reason,
            'queue_id': queue_id
        }

    # Check per-product rate limits
    allowed, rate_reason = await can_post(product, platform)
    if not allowed:
        return {
            'action': 'rate_limited',
            'reason': rate_reason,
            'queue_id': queue_id
        }

    # Mark as auto_approved (posting will be handled by global queue)
    supabase.table('reply_queue').update({
        'status': 'auto_approved',
    }).eq('id', queue_id).execute()

    logger.info(f"Autopilot: auto-approved queue item {queue_id[:8]}")

    return {
        'action': 'approved',
        'reason': 'autopilot_approved',
        'queue_id': queue_id
    }


def extract_tweet_id(url: str) -> str:
    """Extract tweet ID from URL."""
    if not url:
        return ''
    parts = url.split('/')
    for i, p in enumerate(parts):
        if p == 'status' and i + 1 < len(parts):
            return parts[i + 1].split('?')[0]
    return ''


def append_event_log(product: dict, event: str, details: dict) -> list:
    """Append an event to the product's autopilot event log (capped at EVENT_LOG_MAX)."""
    autopilot = product.get('autopilot') or {}
    event_log = autopilot.get('event_log') or []
    entry = {
        'event': event,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'details': details,
    }
    event_log.append(entry)
    # Cap at max entries
    if len(event_log) > EVENT_LOG_MAX:
        event_log = event_log[-EVENT_LOG_MAX:]
    return event_log


def is_paused(product: dict) -> tuple[bool, str]:
    """Check if autopilot is paused for a product.

    Returns:
        (is_paused, reason)
    """
    autopilot = product.get('autopilot') or {}

    # Indefinite pause
    if autopilot.get('paused', False):
        return True, autopilot.get('pause_reason', 'manual_pause')

    # Timed pause
    paused_until = autopilot.get('paused_until')
    if paused_until:
        from services.rate_limiter import parse_timestamp
        until = parse_timestamp(paused_until)
        if until:
            now = datetime.now(timezone.utc)
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if now < until:
                return True, f"timed_pause_until:{paused_until}"
            else:
                # Timed pause expired — auto-resume
                autopilot['paused_until'] = None
                autopilot['pause_reason'] = None
                event_log = append_event_log(product, 'auto_resume', {'reason': 'timed_pause_expired'})
                autopilot['event_log'] = event_log
                supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
                logger.info(f"Autopilot auto-resumed for product {product['id'][:8]} (timed pause expired)")

    return False, ""


def check_heartbeat(product: dict) -> bool:
    """Check if extension heartbeat is recent enough.

    Returns True if heartbeat is OK (or not applicable), False if stale.
    """
    autopilot = product.get('autopilot') or {}
    last_heartbeat = autopilot.get('last_heartbeat')

    if not last_heartbeat:
        # No heartbeat recorded yet — check if there are stale auto_approved items
        return True  # Can't determine without heartbeat data

    from services.rate_limiter import parse_timestamp
    hb_time = parse_timestamp(last_heartbeat)
    if not hb_time:
        return True

    now = datetime.now(timezone.utc)
    if hb_time.tzinfo is None:
        hb_time = hb_time.replace(tzinfo=timezone.utc)

    seconds_since = (now - hb_time).total_seconds()

    # If heartbeat is older than 5 minutes, check for stale auto_approved items
    if seconds_since > 300:
        # Check if there are auto_approved items older than 30 minutes
        cutoff = (now - timedelta(minutes=30)).isoformat()
        stale_items = supabase.table('reply_queue').select('id', count='exact') \
            .eq('product_id', product['id']) \
            .eq('status', 'auto_approved') \
            .lt('updated_at', cutoff) \
            .execute()

        if (stale_items.count or 0) > 0:
            logger.warning(
                f"Extension offline: product {product['id'][:8]} has stale auto_approved items "
                f"and no heartbeat for {int(seconds_since)}s"
            )
            return False

    return True


async def handle_failure_streak(product: dict, platform: str = 'twitter') -> bool:
    """Check and handle failure streak escalation.

    Returns True if autopilot should be paused due to failure streak.
    """
    streak = await get_failure_streak(product['id'], platform)
    autopilot = product.get('autopilot') or {}

    if streak < 3:
        return False

    # Determine pause duration based on escalation level
    last_pause_duration = autopilot.get('last_failure_pause_hours', 0)

    if last_pause_duration == 0:
        # First failure streak: 2 hour pause
        pause_hours = 2
    elif last_pause_duration <= 2:
        # Second failure streak: 6 hour pause
        pause_hours = 6
    else:
        # Third+ failure streak: indefinite pause
        autopilot['paused'] = True
        autopilot['pause_reason'] = 'failure_streak_indefinite'
        autopilot['last_failure_pause_hours'] = 999
        event_log = append_event_log(product, 'auto_pause', {
            'reason': 'failure_streak_indefinite',
            'streak': streak,
            'action': 'indefinite_pause_requires_manual_resume',
        })
        autopilot['event_log'] = event_log
        supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
        logger.warning(f"Autopilot INDEFINITELY PAUSED for product {product['id'][:8]} (streak={streak})")
        return True

    # Timed pause
    pause_until = datetime.now(timezone.utc) + timedelta(hours=pause_hours)
    autopilot['paused_until'] = pause_until.isoformat()
    autopilot['pause_reason'] = f'failure_streak_{pause_hours}h'
    autopilot['last_failure_pause_hours'] = pause_hours
    event_log = append_event_log(product, 'auto_pause', {
        'reason': f'failure_streak',
        'streak': streak,
        'pause_hours': pause_hours,
        'paused_until': pause_until.isoformat(),
    })
    autopilot['event_log'] = event_log
    supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
    logger.warning(f"Autopilot paused {pause_hours}h for product {product['id'][:8]} (streak={streak})")
    return True


async def check_and_apply_tier_changes(product: dict, platform: str = 'twitter'):
    """Check for tier promotion or demotion and apply if warranted."""
    autopilot = product.get('autopilot') or {}
    current_tier = autopilot.get('tier', 0)

    # Check promotion
    new_tier = await check_tier_promotion(product, platform)
    if new_tier is not None:
        autopilot['tier'] = new_tier
        autopilot['tier_started_at'] = datetime.now(timezone.utc).isoformat()
        event_log = append_event_log(product, 'tier_promotion', {
            'from': current_tier,
            'to': new_tier,
        })
        autopilot['event_log'] = event_log
        supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
        logger.info(f"Product {product['id'][:8]} promoted: tier {current_tier} -> {new_tier}")
        return

    # Check demotion
    health = await get_health_status(product, platform)
    demoted_tier = await check_tier_demotion(product, health)
    if demoted_tier is not None:
        autopilot['tier'] = demoted_tier
        autopilot['tier_started_at'] = datetime.now(timezone.utc).isoformat()

        # Track yellow_since for yellow health demotion tracking
        if health['status'] == 'yellow' and not autopilot.get('yellow_since'):
            autopilot['yellow_since'] = datetime.now(timezone.utc).isoformat()
        elif health['status'] != 'yellow':
            autopilot['yellow_since'] = None

        event_log = append_event_log(product, 'tier_demotion', {
            'from': current_tier,
            'to': demoted_tier,
            'health': health['status'],
        })
        autopilot['event_log'] = event_log
        supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
        logger.info(f"Product {product['id'][:8]} demoted: tier {current_tier} -> {demoted_tier}")
        return

    # Track yellow_since transitions even without demotion
    if health['status'] == 'yellow' and not autopilot.get('yellow_since'):
        autopilot['yellow_since'] = datetime.now(timezone.utc).isoformat()
        supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
    elif health['status'] != 'yellow' and autopilot.get('yellow_since'):
        autopilot['yellow_since'] = None
        supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()


async def run_autopilot_processor():
    """
    Main autopilot processor job.

    Pre-checks (per-product):
    0. Skip if paused (manual or timed)
    1. Check failure streak → auto-pause if 3+ consecutive failures
    2. Check heartbeat → pause if extension offline with stale items
    3. Check tier promotion/demotion

    Two phases:
    Phase 1: Approval — mark qualifying items as auto_approved
    Phase 2: Posting — process global queue to post approved items

    This separation allows per-product rate limits during approval
    and account-level rate limits during posting.
    """
    logger.info("Autopilot processor running")

    stats = {
        'products_checked': 0,
        'products_paused': 0,
        'products_heartbeat_offline': 0,
        'items_approved': 0,
        'items_skipped': 0,
        'items_rate_limited': 0,
        'users_processed': 0,
        'posts_attempted': 0,
        'posts_succeeded': 0,
        'tier_changes': 0,
    }

    try:
        # Phase 1: Approve qualifying items (per-product rate limits)
        products = await get_autopilot_products()
        stats['products_checked'] = len(products)

        logger.info(f"Autopilot Phase 1: found {len(products)} products with autopilot enabled")

        user_ids_to_process = set()

        for product in products:
            product_name = product.get('name', product['id'][:8])

            # Pre-check 0: Is autopilot paused?
            paused, pause_reason = is_paused(product)
            if paused:
                stats['products_paused'] += 1
                logger.debug(f"Autopilot: {product_name} paused ({pause_reason})")
                continue

            # Pre-check 1: Failure streak
            should_pause = await handle_failure_streak(product, 'twitter')
            if should_pause:
                stats['products_paused'] += 1
                continue

            # Pre-check 2: Extension heartbeat
            heartbeat_ok = check_heartbeat(product)
            if not heartbeat_ok:
                stats['products_heartbeat_offline'] += 1
                # Auto-pause with extension_offline reason
                autopilot = product.get('autopilot') or {}
                autopilot['paused'] = True
                autopilot['pause_reason'] = 'extension_offline'
                event_log = append_event_log(product, 'auto_pause', {
                    'reason': 'extension_offline',
                    'last_heartbeat': autopilot.get('last_heartbeat'),
                })
                autopilot['event_log'] = event_log
                supabase.table('products').update({'autopilot': autopilot}).eq('id', product['id']).execute()
                logger.warning(f"Autopilot paused for {product_name}: extension offline")
                continue

            # Pre-check 3: Tier promotion/demotion
            try:
                await check_and_apply_tier_changes(product, 'twitter')
            except Exception as e:
                logger.error(f"Tier check error for {product_name}: {e}")

            # Process Twitter queue
            pending = await get_pending_items_for_product(product['id'], 'twitter', limit=5)
            logger.debug(f"Autopilot: {product_name} has {len(pending)} pending Twitter items")

            for item in pending:
                result = await process_autopilot_item(item, product)

                if result['action'] == 'approved':
                    stats['items_approved'] += 1
                    user_id = item.get('user_id')
                    if user_id:
                        user_ids_to_process.add(user_id)
                elif result['action'] == 'skipped':
                    stats['items_skipped'] += 1
                elif result['action'] == 'rate_limited':
                    stats['items_rate_limited'] += 1
                    logger.debug(f"Autopilot: {product_name} rate limited, moving to next product")
                    break

                logger.debug(
                    f"Autopilot: item {item['id'][:8]} -> {result['action']} ({result['reason']})"
                )

        # Phase 2: Process global queue for each user (account-level rate limits)
        logger.info(f"Autopilot Phase 2: processing global queue for {len(user_ids_to_process)} users")

        for user_id in user_ids_to_process:
            stats['users_processed'] += 1

            # Check if can post globally
            can_post_now, wait_seconds = can_post_globally(user_id)
            if not can_post_now:
                logger.debug(f"Autopilot: user {user_id[:8]} global rate limited, wait {wait_seconds}s")
                continue

            # Process one item from the global queue
            result = await process_global_queue(user_id)
            stats['posts_attempted'] += 1

            if result['posted']:
                stats['posts_succeeded'] += 1
                # Reset failure pause escalation on successful post
                queue_id = result.get('queue_id')
                if queue_id:
                    item_res = supabase.table('reply_queue').select('product_id').eq('id', queue_id).execute()
                    if item_res.data:
                        pid = item_res.data[0]['product_id']
                        prod_res = supabase.table('products').select('autopilot').eq('id', pid).execute()
                        if prod_res.data:
                            ap = prod_res.data[0].get('autopilot') or {}
                            if ap.get('last_failure_pause_hours', 0) > 0:
                                ap['last_failure_pause_hours'] = 0
                                supabase.table('products').update({'autopilot': ap}).eq('id', pid).execute()
                                logger.info(f"Reset failure pause escalation for product {pid[:8]}")

                logger.info(f"Autopilot: posted queue item {result['queue_id'][:8]} for user {user_id[:8]}")
            else:
                logger.debug(f"Autopilot: global queue result: {result['reason']}")

    except Exception as e:
        logger.error(f"Autopilot processor error: {e}", exc_info=True)

    logger.info(
        f"Autopilot complete: {stats['items_approved']} approved, "
        f"{stats['items_skipped']} skipped, {stats['items_rate_limited']} rate limited, "
        f"{stats['posts_succeeded']}/{stats['posts_attempted']} posted, "
        f"{stats['products_paused']} paused, {stats['products_heartbeat_offline']} offline"
    )

    return stats
