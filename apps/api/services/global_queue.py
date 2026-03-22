"""
Global fire rate coordination for Operative1.

When multiple products are running autopilot, we need to stagger posts
across the account to avoid:
1. Twitter rate limiting the entire account
2. Posts looking bot-like (too regular/predictable)

Strategy:
- Maintain a global FIFO queue of items ready to post
- Dynamic posting intervals based on volume tier:
    Tier 0 (10/day): avg gap ~108 min
    Tier 1 (20/day): avg gap ~54 min
    Tier 2 (40/day): avg gap ~27 min
    Tier 3 (80/day): avg gap ~13.5 min
- Track last global post time (not per-product)
- Jitter: uniform random +/- 20% of base interval

This works at the ACCOUNT level, not product level. Each Twitter account
(connected via cookies) has a global posting cadence.
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.database import supabase

logger = logging.getLogger(__name__)

# Active posting hours per day (6am-12am local time)
ACTIVE_HOURS = 18

# Fallback gap when no tier info is available
DEFAULT_GAP_SECONDS = 600  # 10 min
DEFAULT_JITTER_SECONDS = 120  # 2 min


def get_dynamic_interval(user_id: str) -> tuple[int, int]:
    """Calculate dynamic posting interval based on the highest tier among user's products.

    Returns:
        (base_gap_seconds, jitter_seconds)
    """
    from services.rate_limiter import TIER_CONFIG

    # Get all products for this user to find the highest tier
    res = supabase.table('products').select('autopilot') \
        .eq('user_id', user_id) \
        .eq('active', True) \
        .execute()

    max_tier = 0
    for product in (res.data or []):
        autopilot = product.get('autopilot') or {}
        if autopilot.get('enabled', False):
            tier = autopilot.get('tier', 0)
            max_tier = max(max_tier, tier)

    tier_config = TIER_CONFIG.get(max_tier, TIER_CONFIG[0])
    daily_cap = tier_config['daily_cap']

    # interval = (active_hours * 60 / daily_target) minutes
    base_gap_minutes = (ACTIVE_HOURS * 60) / daily_cap
    base_gap_seconds = int(base_gap_minutes * 60)

    # Jitter: +/- 20% of base interval
    jitter_seconds = int(base_gap_seconds * 0.2)

    logger.debug(
        f"Dynamic interval for user {user_id[:8]}: tier={max_tier}, "
        f"daily_cap={daily_cap}, gap={base_gap_seconds}s +/- {jitter_seconds}s"
    )

    return base_gap_seconds, jitter_seconds


def get_global_last_post_time(user_id: str) -> Optional[datetime]:
    """Get the time of the last post for this user's account (across all products)."""
    # Query all posted items for this user, ordered by posted_at
    res = supabase.table('reply_queue').select('updated_at') \
        .eq('user_id', user_id) \
        .eq('status', 'posted') \
        .order('updated_at', desc=True) \
        .limit(1) \
        .execute()

    if res.data and res.data[0].get('updated_at'):
        ts = res.data[0]['updated_at']
        if isinstance(ts, str):
            if ts.endswith('Z'):
                ts = ts[:-1] + '+00:00'
            return datetime.fromisoformat(ts)
    return None


def calculate_next_post_time(user_id: str) -> datetime:
    """Calculate when the next post can be made for this user's account.

    Uses dynamic interval based on the user's highest product tier:
        Tier 0 (10/day): ~108 min gap
        Tier 1 (20/day): ~54 min gap
        Tier 2 (40/day): ~27 min gap
        Tier 3 (80/day): ~13.5 min gap

    Jitter is +/- 20% of the base interval.
    """
    last_post = get_global_last_post_time(user_id)
    now = datetime.now(timezone.utc)

    if last_post is None:
        # No previous posts - can post immediately
        return now

    # Ensure timezone-aware
    if last_post.tzinfo is None:
        last_post = last_post.replace(tzinfo=timezone.utc)

    # Get dynamic interval based on tier
    base_gap, jitter_range = get_dynamic_interval(user_id)

    # Apply jitter: uniform random +/- jitter_range
    jitter = random.randint(-jitter_range, jitter_range)
    gap = max(60, base_gap + jitter)  # Floor at 60 seconds

    next_allowed = last_post + timedelta(seconds=gap)

    if next_allowed <= now:
        return now
    else:
        return next_allowed


def can_post_globally(user_id: str) -> tuple[bool, int]:
    """Check if a post can be made now at the global/account level.

    Returns:
        (can_post, wait_seconds)
        - can_post: True if posting is allowed now
        - wait_seconds: Seconds to wait if not allowed (0 if allowed)
    """
    now = datetime.now(timezone.utc)
    next_time = calculate_next_post_time(user_id)

    if next_time <= now:
        return True, 0
    else:
        wait = int((next_time - now).total_seconds())
        return False, wait


async def get_global_queue_position(queue_id: str) -> int:
    """Get the position of a queue item in the global posting queue.

    Position 0 = will be posted next
    Position N = N items ahead of it
    """
    # Get the queue item to find its user_id and created_at
    item_res = supabase.table('reply_queue').select('user_id,created_at') \
        .eq('id', queue_id) \
        .single() \
        .execute()

    if not item_res.data:
        return -1

    user_id = item_res.data['user_id']
    created_at = item_res.data['created_at']

    # Count items ahead of this one (same user, pending/auto_approved, older)
    count_res = supabase.table('reply_queue').select('id', count='exact') \
        .eq('user_id', user_id) \
        .in_('status', ['pending', 'auto_approved']) \
        .lt('created_at', created_at) \
        .execute()

    return count_res.count or 0


async def get_global_queue_stats(user_id: str) -> dict:
    """Get global posting queue statistics for a user's account.

    Returns:
        {
            'pending_count': int,
            'auto_approved_count': int,
            'can_post_now': bool,
            'seconds_until_next': int,
            'last_post_age_seconds': int or None,
            'estimated_clear_time_minutes': int,
        }
    """
    now = datetime.now(timezone.utc)

    # Count pending and auto_approved items
    pending_res = supabase.table('reply_queue').select('id', count='exact') \
        .eq('user_id', user_id) \
        .eq('status', 'pending') \
        .execute()

    approved_res = supabase.table('reply_queue').select('id', count='exact') \
        .eq('user_id', user_id) \
        .eq('status', 'auto_approved') \
        .execute()

    pending_count = pending_res.count or 0
    approved_count = approved_res.count or 0

    # Check if can post now
    can_post, wait_seconds = can_post_globally(user_id)

    # Calculate last post age
    last_post = get_global_last_post_time(user_id)
    last_post_age = None
    if last_post:
        if last_post.tzinfo is None:
            last_post = last_post.replace(tzinfo=timezone.utc)
        last_post_age = int((now - last_post).total_seconds())

    # Estimate time to clear queue using dynamic interval
    base_gap, jitter_range = get_dynamic_interval(user_id)
    avg_interval = base_gap  # Jitter averages out to 0
    total_items = pending_count + approved_count
    estimated_clear = int((total_items * avg_interval) / 60)  # minutes

    return {
        'pending_count': pending_count,
        'auto_approved_count': approved_count,
        'can_post_now': can_post,
        'seconds_until_next': wait_seconds,
        'last_post_age_seconds': last_post_age,
        'estimated_clear_time_minutes': estimated_clear,
    }


async def process_global_queue(user_id: str) -> dict:
    """Process the global queue for a user - post the next item if allowed.

    This is called by the autopilot processor after checking per-product limits.
    It enforces the global posting cadence across all products.

    Uses the human scheduler to only post during organic-looking time windows.
    Posts outside these windows stay in auto_approved state for later.

    Returns:
        {
            'posted': bool,
            'reason': str,
            'queue_id': str or None
        }
    """
    # Check global rate limit
    can_post, wait_seconds = can_post_globally(user_id)
    if not can_post:
        return {
            'posted': False,
            'reason': f'global_rate_limit:wait_{wait_seconds}s',
            'queue_id': None
        }

    # Get oldest auto_approved item for this user
    item_res = supabase.table('reply_queue').select('*') \
        .eq('user_id', user_id) \
        .eq('status', 'auto_approved') \
        .order('created_at', desc=False) \
        .limit(1) \
        .execute()

    if not item_res.data:
        return {
            'posted': False,
            'reason': 'no_approved_items',
            'queue_id': None
        }

    item = item_res.data[0]
    queue_id = item['id']
    platform = item['platform']
    product_id = item['product_id']

    # Get product for autopilot settings and poster
    product_res = supabase.table('products').select('*') \
        .eq('id', product_id) \
        .single() \
        .execute()
    product = product_res.data if product_res.data else {}
    autopilot_config = product.get('autopilot') or {}

    # Check if human schedule is enabled (defaults to True for organic posting)
    use_human_schedule = autopilot_config.get('use_human_schedule', True)

    if use_human_schedule:
        # Check human scheduler - only post during organic-looking windows
        from services.human_scheduler import should_post_now
        try:
            in_window = await should_post_now(product_id, platform, tolerance_minutes=5)
            if not in_window:
                logger.debug(f"Human scheduler: not in posting window for product {product_id[:8]}")
                return {
                    'posted': False,
                    'reason': 'outside_human_schedule_window',
                    'queue_id': queue_id
                }
            logger.info(f"Human scheduler: in posting window for product {product_id[:8]}")
        except Exception as e:
            # If scheduler fails, fall back to posting (don't block on scheduler errors)
            logger.warning(f"Human scheduler error: {e} - falling back to immediate post")

    # Post based on platform
    from services.poster import post_to_twitter

    # Build reply_data and original_post from queue item
    reply_data = {
        'reply': item.get('edited_reply') or item.get('draft_reply', ''),
    }

    original_post = {
        'id': extract_tweet_id(item.get('original_url', '')),
        'url': item.get('original_url', ''),
    }

    if platform == 'twitter':
        await post_to_twitter(queue_id, reply_data, original_post, product)

    # Check result
    updated = supabase.table('reply_queue').select('status') \
        .eq('id', queue_id) \
        .single() \
        .execute()
    final_status = updated.data.get('status') if updated.data else 'unknown'

    return {
        'posted': final_status == 'posted',
        'reason': 'posted' if final_status == 'posted' else f'failed:{final_status}',
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
