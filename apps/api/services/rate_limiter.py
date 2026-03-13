"""
Fire rate enforcement service for Operative1.

Enforces posting limits to prevent spam detection and maintain healthy engagement:
- Per-product daily and hourly limits
- Minimum delay between consecutive posts
- Posting hours window (time-of-day restrictions)

Usage:
    from services.rate_limiter import can_post, record_post

    if await can_post(product_id, platform):
        # ... post the reply ...
        await record_post(product_id, platform)
    else:
        # Queue item stays pending, will be retried later
        pass
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from services.database import supabase

logger = logging.getLogger(__name__)


async def get_posts_in_window(
    product_id: str,
    platform: str,
    hours: int
) -> int:
    """Count posts for a product/platform in the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    res = supabase.table('reply_queue').select('id', count='exact') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .eq('status', 'posted') \
        .gte('updated_at', cutoff_str) \
        .execute()

    return res.count or 0


async def get_last_post_time(product_id: str, platform: str) -> Optional[datetime]:
    """Get the timestamp of the most recent post for this product/platform."""
    res = supabase.table('reply_queue').select('updated_at') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .eq('status', 'posted') \
        .order('updated_at', desc=True) \
        .limit(1) \
        .execute()

    if res.data and res.data[0].get('updated_at'):
        # Parse the timestamp
        ts = res.data[0]['updated_at']
        if isinstance(ts, str):
            # Handle ISO format with or without timezone
            if ts.endswith('Z'):
                ts = ts[:-1] + '+00:00'
            return datetime.fromisoformat(ts)
    return None


def is_within_posting_hours(product: dict) -> bool:
    """Check if current time is within configured posting hours."""
    posting_hours = product.get('posting_hours', {}) or {}

    if not posting_hours.get('enabled', False):
        return True  # No restrictions if not enabled

    tz_name = posting_hours.get('timezone', 'UTC')
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.warning(f"Invalid timezone '{tz_name}', defaulting to UTC")
        tz = timezone.utc

    now = datetime.now(tz)

    # Check day of week (0=Monday, 6=Sunday)
    days = posting_hours.get('days_of_week')
    if days and now.weekday() not in days:
        logger.debug(f"Outside posting days: {now.weekday()} not in {days}")
        return False

    # Check hours
    start_hour = posting_hours.get('start_hour', 0)
    end_hour = posting_hours.get('end_hour', 23)

    # Handle overnight windows (e.g., 22:00 - 06:00)
    if start_hour <= end_hour:
        # Normal case: e.g., 9-21
        if not (start_hour <= now.hour <= end_hour):
            logger.debug(f"Outside posting hours: {now.hour} not in {start_hour}-{end_hour}")
            return False
    else:
        # Overnight case: e.g., 22-6 means 22-23 OR 0-6
        if not (now.hour >= start_hour or now.hour <= end_hour):
            logger.debug(f"Outside posting hours (overnight): {now.hour} not in {start_hour}-24 or 0-{end_hour}")
            return False

    return True


async def can_post(product: dict, platform: str) -> tuple[bool, str]:
    """
    Check if a post is allowed right now for this product/platform.

    Args:
        product: Product dict with rate limit config
        platform: Platform name (twitter, reddit, etc.)

    Returns:
        (can_post, reason)
        - can_post: True if posting is allowed
        - reason: Explanation if not allowed (empty if allowed)
    """
    product_id = product['id']

    # Check 1: Posting hours window
    if not is_within_posting_hours(product):
        posting_hours = product.get('posting_hours', {}) or {}
        tz = posting_hours.get('timezone', 'UTC')
        start = posting_hours.get('start_hour', 0)
        end = posting_hours.get('end_hour', 23)
        return False, f"outside_posting_hours:{tz}:{start}-{end}"

    # Check 2: Daily limit
    max_daily = product.get('max_replies_per_day', {}).get(platform, 10)
    posts_today = await get_posts_in_window(product_id, platform, 24)
    if posts_today >= max_daily:
        return False, f"daily_limit_reached:{posts_today}/{max_daily}"

    # Check 3: Hourly limit
    max_hourly = product.get('max_replies_per_hour', {}).get(platform, 3)
    posts_this_hour = await get_posts_in_window(product_id, platform, 1)
    if posts_this_hour >= max_hourly:
        return False, f"hourly_limit_reached:{posts_this_hour}/{max_hourly}"

    # Check 4: Minimum delay between posts
    min_delay = product.get('min_delay_between_posts', 120)  # Default 2 minutes
    last_post = await get_last_post_time(product_id, platform)
    if last_post:
        now = datetime.now(timezone.utc)
        # Ensure last_post is timezone-aware
        if last_post.tzinfo is None:
            last_post = last_post.replace(tzinfo=timezone.utc)
        seconds_since = (now - last_post).total_seconds()
        if seconds_since < min_delay:
            wait_time = int(min_delay - seconds_since)
            return False, f"min_delay_not_met:wait_{wait_time}s"

    return True, ""


async def record_post(product_id: str, platform: str) -> None:
    """
    Record that a post was made.

    Note: The actual post status is updated in poster.py when the reply is posted.
    This function is kept for any additional tracking needs.
    """
    logger.info(f"Post recorded for product {product_id} on {platform}")


async def get_rate_limit_status(product: dict, platform: str) -> dict:
    """
    Get current rate limit status for a product/platform.

    Returns dict with:
        - can_post: bool
        - reason: str (if can't post)
        - posts_today: int
        - max_daily: int
        - posts_this_hour: int
        - max_hourly: int
        - seconds_until_next: int (if rate limited)
    """
    product_id = product['id']

    # Get limits from product config
    max_daily = product.get('max_replies_per_day', {}).get(platform, 10)
    max_hourly = product.get('max_replies_per_hour', {}).get(platform, 3)
    min_delay = product.get('min_delay_between_posts', 120)

    # Get current counts
    posts_today = await get_posts_in_window(product_id, platform, 24)
    posts_this_hour = await get_posts_in_window(product_id, platform, 1)

    # Get last post time
    last_post = await get_last_post_time(product_id, platform)
    seconds_since_last = None
    if last_post:
        now = datetime.now(timezone.utc)
        if last_post.tzinfo is None:
            last_post = last_post.replace(tzinfo=timezone.utc)
        seconds_since_last = int((now - last_post).total_seconds())

    # Check if can post
    allowed, reason = await can_post(product, platform)

    # Calculate seconds until next allowed post
    seconds_until_next = 0
    if not allowed:
        if 'min_delay' in reason and seconds_since_last is not None:
            seconds_until_next = max(0, min_delay - seconds_since_last)
        elif 'hourly_limit' in reason:
            # Need to wait for oldest post in hour to age out
            seconds_until_next = 3600  # Worst case
        elif 'daily_limit' in reason:
            seconds_until_next = 86400  # Worst case

    return {
        'can_post': allowed,
        'reason': reason,
        'posts_today': posts_today,
        'max_daily': max_daily,
        'posts_this_hour': posts_this_hour,
        'max_hourly': max_hourly,
        'min_delay': min_delay,
        'seconds_since_last': seconds_since_last,
        'seconds_until_next': seconds_until_next,
        'within_posting_hours': is_within_posting_hours(product),
    }
