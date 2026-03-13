"""
Pre-filter heuristics for tweet selection.

Runs BEFORE AI scoring to eliminate obviously irrelevant tweets,
saving API costs. Each filter is cheap (no external calls).

Opportunity Score Formula:
  base = (likes * 2) + (replies * 3) + (views / 100)
  author_boost = log10(followers + 1) * 10  # 0-50 range
  recency_boost = max(0, 24 - hours_old) * 2  # 0-48 range
  opportunity_score = base + author_boost + recency_boost

Filters (configurable per-product):
  - max_tweet_age_hours: Skip tweets older than N hours (default: 24)
  - min_likes: Skip tweets with fewer than N likes (default: 2)
  - min_author_followers: Skip authors with fewer than N followers (default: 50)
  - max_reply_count: Skip tweets with more than N replies (default: 100)
  - min_opportunity_score: Skip tweets below score threshold (default: 10)
  - max_ai_calls_per_run: Cap AI scoring calls per pipeline run (default: 20)
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def parse_tweet_age_hours(created_at: str) -> Optional[float]:
    """Parse tweet created_at and return age in hours. Returns None if unparseable."""
    if not created_at:
        return None

    # Try multiple date formats Apify might return
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with ms
        "%Y-%m-%dT%H:%M:%SZ",     # ISO format without ms
        "%Y-%m-%d %H:%M:%S",      # Simple format
        "%a %b %d %H:%M:%S %z %Y", # Twitter's native format
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(created_at, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age = (now - dt).total_seconds() / 3600
            return age
        except ValueError:
            continue

    # Try parsing as Unix timestamp
    try:
        ts = float(created_at)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600
    except (ValueError, TypeError):
        pass

    return None


def calculate_opportunity_score(tweet: dict) -> float:
    """
    Calculate opportunity score for a tweet.

    Higher score = better opportunity for engagement.

    Formula:
      base = (likes * 2) + (replies * 3) + (views / 100)
      author_boost = log10(followers + 1) * 10
      recency_boost = max(0, 24 - hours_old) * 2
      total = base + author_boost + recency_boost
    """
    likes = tweet.get('likes', 0) or 0
    replies = tweet.get('replies', 0) or 0
    views = tweet.get('views', 0) or 0
    followers = tweet.get('author_followers', 0) or 0

    # Base engagement score
    base = (likes * 2) + (replies * 3) + (views / 100)

    # Author influence boost (logarithmic to prevent mega-accounts from dominating)
    # log10(1) = 0, log10(10) = 1, log10(100) = 2, log10(1000) = 3, etc.
    # Multiplied by 10: 0 followers = 0, 100 = 20, 1000 = 30, 10000 = 40, 100000 = 50
    author_boost = math.log10(followers + 1) * 10

    # Recency boost: newer tweets get higher scores
    # Max boost of 48 for brand new tweets, decays to 0 at 24 hours
    age_hours = parse_tweet_age_hours(tweet.get('created_at', ''))
    if age_hours is not None and age_hours < 24:
        recency_boost = max(0, 24 - age_hours) * 2
    else:
        recency_boost = 0

    total = base + author_boost + recency_boost

    return round(total, 2)


def prefilter_tweet(tweet: dict, product: dict) -> tuple[bool, str, float]:
    """
    Apply pre-filter heuristics to a tweet.

    Args:
        tweet: Normalized tweet dict from apify
        product: Product config with targeting settings

    Returns:
        (should_process, skip_reason, opportunity_score)
        - should_process: True if tweet passes all filters
        - skip_reason: Reason for skipping (empty if passes)
        - opportunity_score: Calculated opportunity score
    """
    # Get targeting config from product (with defaults)
    targeting = product.get('targeting', {}) or {}

    max_age = targeting.get('max_tweet_age_hours', 24)
    min_likes = targeting.get('min_likes', 2)
    min_followers = targeting.get('min_author_followers', 50)
    max_replies = targeting.get('max_reply_count', 100)
    min_opportunity = targeting.get('min_opportunity_score', 10)

    # Filter 1: Tweet age
    age_hours = parse_tweet_age_hours(tweet.get('created_at', ''))
    if age_hours is not None and age_hours > max_age:
        return False, f"too_old:{age_hours:.1f}h>{max_age}h", 0

    # Filter 2: Minimum likes (engagement signal)
    likes = tweet.get('likes', 0) or 0
    if likes < min_likes:
        return False, f"low_likes:{likes}<{min_likes}", 0

    # Filter 3: Author followers (reach potential)
    followers = tweet.get('author_followers', 0) or 0
    if followers < min_followers:
        return False, f"low_followers:{followers}<{min_followers}", 0

    # Filter 4: Too many replies (crowded conversation)
    replies = tweet.get('replies', 0) or 0
    if replies > max_replies:
        return False, f"too_crowded:{replies}>{max_replies}", 0

    # Calculate opportunity score
    score = calculate_opportunity_score(tweet)

    # Filter 5: Minimum opportunity score
    if score < min_opportunity:
        return False, f"low_opportunity:{score:.1f}<{min_opportunity}", score

    return True, "", score


def prefilter_tweets(
    tweets: list[dict],
    product: dict,
    max_ai_calls: Optional[int] = None
) -> tuple[list[dict], dict]:
    """
    Apply pre-filtering to a batch of tweets.

    Args:
        tweets: List of normalized tweets
        product: Product config
        max_ai_calls: Maximum tweets to pass through (for AI cost control)

    Returns:
        (filtered_tweets, stats)
        - filtered_tweets: Tweets that passed filtering, sorted by opportunity score
        - stats: Dict with filter statistics
    """
    targeting = product.get('targeting', {}) or {}
    max_ai = max_ai_calls or targeting.get('max_ai_calls_per_run', 20)

    stats = {
        'total_input': len(tweets),
        'passed': 0,
        'filtered': 0,
        'filter_reasons': {},
        'capped_by_ai_limit': False,
        'opportunity_scores': [],
    }

    passed = []

    for tweet in tweets:
        should_process, reason, score = prefilter_tweet(tweet, product)

        if should_process:
            tweet['opportunity_score'] = score
            passed.append(tweet)
            stats['opportunity_scores'].append(score)
        else:
            stats['filtered'] += 1
            # Track filter reasons
            reason_key = reason.split(':')[0] if ':' in reason else reason
            stats['filter_reasons'][reason_key] = stats['filter_reasons'].get(reason_key, 0) + 1

    # Sort by opportunity score (highest first)
    passed.sort(key=lambda t: t.get('opportunity_score', 0), reverse=True)

    # Cap by max AI calls
    if len(passed) > max_ai:
        stats['capped_by_ai_limit'] = True
        stats['capped_from'] = len(passed)
        passed = passed[:max_ai]

    stats['passed'] = len(passed)

    logger.info(
        f"Pre-filter: {stats['total_input']} tweets -> {stats['passed']} passed "
        f"(filtered: {stats['filter_reasons']}, ai_cap: {stats['capped_by_ai_limit']})"
    )

    return passed, stats
