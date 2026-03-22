"""
Fire rate enforcement service for Operative1.

Enforces posting limits to prevent spam detection and maintain healthy engagement:
- Per-product daily and hourly limits (tier-based)
- Minimum delay between consecutive posts
- Posting hours window (time-of-day restrictions)
- Account health monitoring (green/yellow/red)
- Graduated volume ramp with tier promotion/demotion

Tier System:
  Tier 0: 10/day  (first 3 days)
  Tier 1: 20/day  (after 3 days at Tier 0, >85% success + green health)
  Tier 2: 40/day  (after 7 more days at Tier 1, >85% success + green health)
  Tier 3: 80/day  (after 7 more days at Tier 2, >85% success + green health)

Usage:
    from services.rate_limiter import can_post, get_health_status

    if await can_post(product, platform):
        # ... post the reply ...
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

# Tier configuration: tier -> (daily_cap, days_required_at_tier, hourly_cap)
TIER_CONFIG = {
    0: {'daily_cap': 10, 'days_to_promote': 3, 'hourly_cap': 3},
    1: {'daily_cap': 20, 'days_to_promote': 7, 'hourly_cap': 5},
    2: {'daily_cap': 40, 'days_to_promote': 7, 'hourly_cap': 10},
    3: {'daily_cap': 80, 'days_to_promote': None, 'hourly_cap': 20},  # Max tier
}

PROMOTION_SUCCESS_RATE = 0.85  # 85% success rate required
PROMOTION_MIN_POSTS = 10  # Minimum posts at current tier before promotion


def parse_timestamp(ts) -> Optional[datetime]:
    """Parse a timestamp string into a timezone-aware datetime."""
    if not ts:
        return None
    if isinstance(ts, str):
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        return datetime.fromisoformat(ts)
    return ts


def get_tier_daily_cap(tier: int) -> int:
    """Get the daily posting cap for a given tier."""
    config = TIER_CONFIG.get(tier, TIER_CONFIG[0])
    return config['daily_cap']


def get_tier_hourly_cap(tier: int) -> int:
    """Get the hourly posting cap for a given tier."""
    config = TIER_CONFIG.get(tier, TIER_CONFIG[0])
    return config['hourly_cap']


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
        .gte('posted_at', cutoff_str) \
        .execute()

    return res.count or 0


async def get_recent_posts(product_id: str, platform: str, limit: int = 10) -> list:
    """Get recent posts for health/streak calculation. Returns list of dicts with status and posted_at/created_at."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_str = cutoff.isoformat()

    res = supabase.table('reply_queue').select('status,posted_at,rejection_reason') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .in_('status', ['posted', 'failed']) \
        .gte('posted_at', cutoff_str) \
        .order('posted_at', desc=True) \
        .limit(limit) \
        .execute()

    return res.data or []


async def get_last_post_time(product_id: str, platform: str) -> Optional[datetime]:
    """Get the timestamp of the most recent post for this product/platform."""
    res = supabase.table('reply_queue').select('posted_at') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .eq('status', 'posted') \
        .order('posted_at', desc=True) \
        .limit(1) \
        .execute()

    if res.data and res.data[0].get('posted_at'):
        return parse_timestamp(res.data[0]['posted_at'])
    return None


async def get_first_post_time(product_id: str, platform: str) -> Optional[datetime]:
    """Get the timestamp of the first ever post for this product/platform (account age)."""
    res = supabase.table('reply_queue').select('posted_at') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .eq('status', 'posted') \
        .order('posted_at', desc=False) \
        .limit(1) \
        .execute()

    if res.data and res.data[0].get('posted_at'):
        return parse_timestamp(res.data[0]['posted_at'])
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


async def get_health_status(product: dict, platform: str = 'twitter') -> dict:
    """
    Calculate account health from rolling 24h post data.

    Returns:
        {
            'status': 'green' | 'yellow' | 'red',
            'success_rate': float (0-1),
            'consecutive_failures': int,
            'total_posts_24h': int,
            'insufficient_data': bool,
        }
    """
    product_id = product['id']
    recent = await get_recent_posts(product_id, platform, limit=50)

    total = len(recent)
    if total < 5:
        return {
            'status': 'green',
            'success_rate': 1.0 if total == 0 else sum(1 for p in recent if p['status'] == 'posted') / total,
            'consecutive_failures': 0,
            'total_posts_24h': total,
            'insufficient_data': True,
        }

    posted = sum(1 for p in recent if p['status'] == 'posted')
    failed = sum(1 for p in recent if p['status'] == 'failed')
    success_rate = posted / total if total > 0 else 1.0

    # Count consecutive failures from most recent
    consecutive_failures = 0
    for p in recent:  # Already ordered desc by posted_at
        if p['status'] == 'failed':
            consecutive_failures += 1
        else:
            break

    # Determine health status
    if success_rate < 0.70 or consecutive_failures >= 4:
        health = 'red'
    elif success_rate < 0.90 or consecutive_failures >= 2:
        health = 'yellow'
    else:
        health = 'green'

    return {
        'status': health,
        'success_rate': round(success_rate, 3),
        'consecutive_failures': consecutive_failures,
        'total_posts_24h': total,
        'insufficient_data': False,
    }


async def get_failure_streak(product_id: str, platform: str = 'twitter') -> int:
    """
    Derive failure streak from DB by querying last 10 posts and counting
    consecutive failures from the most recent. Resilient to backend crashes.
    """
    res = supabase.table('reply_queue').select('status') \
        .eq('product_id', product_id) \
        .eq('platform', platform) \
        .in_('status', ['posted', 'failed']) \
        .order('posted_at', desc=True) \
        .limit(10) \
        .execute()

    streak = 0
    for item in (res.data or []):
        if item['status'] == 'failed':
            streak += 1
        else:
            break
    return streak


async def check_tier_promotion(product: dict, platform: str = 'twitter') -> Optional[int]:
    """
    Check if a product should be promoted to a higher tier.

    Returns the new tier if promotion is warranted, None otherwise.
    """
    autopilot = product.get('autopilot', {}) or {}
    current_tier = autopilot.get('tier', 0)

    if current_tier >= 3:
        return None  # Already at max tier

    tier_config = TIER_CONFIG[current_tier]
    days_needed = tier_config['days_to_promote']
    if days_needed is None:
        return None  # Max tier

    product_id = product['id']

    # Check account age (days since first post)
    first_post = await get_first_post_time(product_id, platform)
    if not first_post:
        return None  # No posts yet

    now = datetime.now(timezone.utc)
    if first_post.tzinfo is None:
        first_post = first_post.replace(tzinfo=timezone.utc)

    # Calculate days at current tier
    tier_started = autopilot.get('tier_started_at')
    if tier_started:
        tier_start = parse_timestamp(tier_started)
        if tier_start and tier_start.tzinfo is None:
            tier_start = tier_start.replace(tzinfo=timezone.utc)
        days_at_tier = (now - tier_start).days if tier_start else 0
    else:
        # No tier_started_at means we've been at tier 0 since first post
        days_at_tier = (now - first_post).days

    if days_at_tier < days_needed:
        return None  # Not enough days at current tier

    # Check minimum posts at current tier
    posts_24h = await get_posts_in_window(product_id, platform, 24 * days_needed)
    if posts_24h < PROMOTION_MIN_POSTS:
        return None  # Not enough posts for meaningful success rate

    # Check success rate
    health = await get_health_status(product, platform)
    if health['insufficient_data']:
        return None

    if health['success_rate'] < PROMOTION_SUCCESS_RATE:
        return None  # Success rate too low

    if health['status'] != 'green':
        return None  # Health not green

    new_tier = current_tier + 1
    logger.info(f"Tier promotion: product {product_id[:8]} {current_tier} -> {new_tier}")
    return new_tier


async def check_tier_demotion(product: dict, health_status: dict) -> Optional[int]:
    """
    Check if a product should be demoted to a lower tier.

    Returns the new tier if demotion is warranted, None otherwise.
    """
    autopilot = product.get('autopilot', {}) or {}
    current_tier = autopilot.get('tier', 0)

    if current_tier <= 0:
        return None  # Already at minimum

    # Red health → immediate demotion
    if health_status['status'] == 'red':
        new_tier = current_tier - 1
        logger.info(f"Tier demotion (red health): product {product['id'][:8]} {current_tier} -> {new_tier}")
        return new_tier

    # Yellow health for 3+ days → demotion
    if health_status['status'] == 'yellow':
        yellow_since = autopilot.get('yellow_since')
        if yellow_since:
            yellow_start = parse_timestamp(yellow_since)
            if yellow_start:
                if yellow_start.tzinfo is None:
                    yellow_start = yellow_start.replace(tzinfo=timezone.utc)
                days_yellow = (datetime.now(timezone.utc) - yellow_start).days
                if days_yellow >= 3:
                    new_tier = current_tier - 1
                    logger.info(f"Tier demotion (yellow 3d): product {product['id'][:8]} {current_tier} -> {new_tier}")
                    return new_tier

    return None


async def can_post(product: dict, platform: str) -> tuple[bool, str]:
    """
    Check if a post is allowed right now for this product/platform.
    Uses tier-based daily caps.

    Returns:
        (can_post, reason)
    """
    product_id = product['id']
    autopilot = product.get('autopilot', {}) or {}
    tier = autopilot.get('tier', 0)

    # Check 1: Posting hours window
    if not is_within_posting_hours(product):
        posting_hours = product.get('posting_hours', {}) or {}
        tz = posting_hours.get('timezone', 'UTC')
        start = posting_hours.get('start_hour', 0)
        end = posting_hours.get('end_hour', 23)
        return False, f"outside_posting_hours:{tz}:{start}-{end}"

    # Check 2: Daily limit (tier-based)
    max_daily = get_tier_daily_cap(tier)
    posts_today = await get_posts_in_window(product_id, platform, 24)
    if posts_today >= max_daily:
        return False, f"daily_limit_reached:{posts_today}/{max_daily}:tier{tier}"

    # Check 3: Hourly limit (tier-based)
    max_hourly = get_tier_hourly_cap(tier)
    posts_this_hour = await get_posts_in_window(product_id, platform, 1)
    if posts_this_hour >= max_hourly:
        return False, f"hourly_limit_reached:{posts_this_hour}/{max_hourly}"

    # Check 4: Minimum delay between posts
    min_delay = product.get('min_delay_between_posts', 120)  # Default 2 minutes
    last_post = await get_last_post_time(product_id, platform)
    if last_post:
        now = datetime.now(timezone.utc)
        if last_post.tzinfo is None:
            last_post = last_post.replace(tzinfo=timezone.utc)
        seconds_since = (now - last_post).total_seconds()
        if seconds_since < min_delay:
            wait_time = int(min_delay - seconds_since)
            return False, f"min_delay_not_met:wait_{wait_time}s"

    return True, ""


async def record_post(product_id: str, platform: str) -> None:
    """Record that a post was made."""
    logger.info(f"Post recorded for product {product_id} on {platform}")


async def get_rate_limit_status(product: dict, platform: str) -> dict:
    """Get current rate limit status for a product/platform."""
    product_id = product['id']
    autopilot = product.get('autopilot', {}) or {}
    tier = autopilot.get('tier', 0)

    max_daily = get_tier_daily_cap(tier)
    max_hourly = get_tier_hourly_cap(tier)
    min_delay = product.get('min_delay_between_posts', 120)

    posts_today = await get_posts_in_window(product_id, platform, 24)
    posts_this_hour = await get_posts_in_window(product_id, platform, 1)

    last_post = await get_last_post_time(product_id, platform)
    seconds_since_last = None
    if last_post:
        now = datetime.now(timezone.utc)
        if last_post.tzinfo is None:
            last_post = last_post.replace(tzinfo=timezone.utc)
        seconds_since_last = int((now - last_post).total_seconds())

    allowed, reason = await can_post(product, platform)

    seconds_until_next = 0
    if not allowed:
        if 'min_delay' in reason and seconds_since_last is not None:
            seconds_until_next = max(0, min_delay - seconds_since_last)
        elif 'hourly_limit' in reason:
            seconds_until_next = 3600
        elif 'daily_limit' in reason:
            seconds_until_next = 86400

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
        'tier': tier,
    }
