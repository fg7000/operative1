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
2. For each product, get pending queue items
3. Check if item meets autopilot thresholds
4. Check per-product rate limits
5. If yes to both: mark as "auto_approved"
6. Process global queue (enforces account-level posting cadence)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from services.database import supabase
from services.rate_limiter import can_post
from services.poster import post_to_twitter
from services.global_queue import can_post_globally, process_global_queue

logger = logging.getLogger(__name__)


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


async def run_autopilot_processor():
    """
    Main autopilot processor job.

    Two phases:
    1. Approval phase: Mark qualifying items as auto_approved
    2. Posting phase: Process global queue to post approved items

    This separation allows per-product rate limits during approval
    and account-level rate limits during posting.
    """
    logger.info("Autopilot processor running")

    stats = {
        'products_checked': 0,
        'items_approved': 0,
        'items_skipped': 0,
        'items_rate_limited': 0,
        'users_processed': 0,
        'posts_attempted': 0,
        'posts_succeeded': 0,
    }

    try:
        # Phase 1: Approve qualifying items (per-product rate limits)
        products = await get_autopilot_products()
        stats['products_checked'] = len(products)

        logger.info(f"Autopilot Phase 1: found {len(products)} products with autopilot enabled")

        user_ids_to_process = set()

        for product in products:
            product_name = product.get('name', product['id'][:8])

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
                logger.info(f"Autopilot: posted queue item {result['queue_id'][:8]} for user {user_id[:8]}")
            else:
                logger.debug(f"Autopilot: global queue result: {result['reason']}")

    except Exception as e:
        logger.error(f"Autopilot processor error: {e}", exc_info=True)

    logger.info(
        f"Autopilot complete: {stats['items_approved']} approved, "
        f"{stats['items_skipped']} skipped, {stats['items_rate_limited']} rate limited, "
        f"{stats['posts_succeeded']}/{stats['posts_attempted']} posted"
    )

    return stats
