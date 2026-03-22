import os
import httpx
import asyncio
import logging
from dotenv import load_dotenv
from services.keyword_quality import filter_keywords

load_dotenv()

APIFY_API_KEY = os.getenv('APIFY_API_KEY')
logger = logging.getLogger(__name__)


async def _run_single_search(client: httpx.AsyncClient, query: str, max_items: int = 20) -> list:
    """Run a single Apify search and return raw tweet dicts."""
    try:
        start_res = await client.post(
            f"https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs",
            params={'token': APIFY_API_KEY},
            json={
                "searchTerms": [query],
                "maxItems": max_items,
                "queryType": "Latest"
            }
        )
        if start_res.status_code not in (200, 201):
            logger.error(f"Apify start failed for '{query}': {start_res.status_code}")
            return []

        run_id = start_res.json().get('data', {}).get('id')
        if not run_id:
            return []

        logger.info(f"Apify run started for '{query}': {run_id}")

        # Poll until complete
        status_res = None
        for attempt in range(30):
            await asyncio.sleep(5)
            status_res = await client.get(
                f"https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs/{run_id}",
                params={'token': APIFY_API_KEY}
            )
            status = status_res.json().get('data', {}).get('status', '')
            if status == 'SUCCEEDED':
                break
            if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                logger.error(f"Apify run for '{query}' ended: {status}")
                return []

        dataset_id = status_res.json().get('data', {}).get('defaultDatasetId')
        items_res = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={'token': APIFY_API_KEY, 'format': 'json', 'clean': 'true'}
        )
        tweets = items_res.json()
        logger.info(f"Search '{query}': {len(tweets)} raw tweets")
        return tweets
    except Exception as e:
        logger.error(f"Apify search error for '{query}': {e}")
        return []


def _normalize_tweet(t: dict) -> dict | None:
    """Normalize a raw Apify tweet into our standard format.

    Extracts all fields needed for pre-filtering and scoring:
    - Basic: id, text, author, url
    - Engagement: likes, replies, views, retweets, quotes
    - Author: followers, following, verified, created_at
    - Timing: created_at, reply_settings
    """
    tweet_id = str(
        t.get('id') or
        t.get('tweet_id') or
        t.get('tweetId') or
        t.get('rest_id') or ''
    )
    text = (
        t.get('full_text') or
        t.get('text') or
        t.get('rawContent') or
        t.get('content') or ''
    )
    if not tweet_id or not text:
        return None

    # Author info - can be nested object or flat fields
    author_obj = t.get('author', {}) if isinstance(t.get('author'), dict) else {}
    user_obj = t.get('user', {}) if isinstance(t.get('user'), dict) else {}

    author = (
        author_obj.get('userName') or
        author_obj.get('username') or
        t.get('username') or
        user_obj.get('screen_name') or ''
    )

    # Author follower count - try multiple field locations
    author_followers = (
        author_obj.get('followers') or
        author_obj.get('followersCount') or
        author_obj.get('followers_count') or
        user_obj.get('followers_count') or
        t.get('author_followers') or
        0
    )

    # Author following count
    author_following = (
        author_obj.get('following') or
        author_obj.get('followingCount') or
        author_obj.get('friends_count') or
        user_obj.get('friends_count') or
        0
    )

    # Author verified status
    author_verified = (
        author_obj.get('isVerified') or
        author_obj.get('verified') or
        author_obj.get('isBlueVerified') or
        user_obj.get('verified') or
        False
    )

    # Author account creation date
    author_created_at = (
        author_obj.get('createdAt') or
        author_obj.get('created_at') or
        user_obj.get('created_at') or
        ''
    )

    # Check for reply restrictions - Apify may use various field names
    reply_settings = (
        t.get('reply_settings') or
        t.get('replySettings') or
        t.get('conversation_control') or
        t.get('conversationControl') or
        t.get('limited_actions', {}).get('reply') or
        'everyone'  # default to everyone if not specified
    )
    # Normalize: could be dict or string
    if isinstance(reply_settings, dict):
        reply_settings = reply_settings.get('type', 'everyone')

    # Views/impressions - Apify may use different field names
    views = (
        t.get('viewCount') or
        t.get('views') or
        t.get('impressionCount') or
        t.get('impressions') or
        0
    )

    # Retweets
    retweets = (
        t.get('retweetCount') or
        t.get('retweet_count') or
        t.get('retweets') or
        0
    )

    # Quote tweets
    quotes = (
        t.get('quoteCount') or
        t.get('quote_count') or
        t.get('quotes') or
        0
    )

    return {
        'id': tweet_id,
        'text': text,
        'author': author,
        'url': t.get('url') or t.get('tweetUrl') or f"https://twitter.com/i/web/status/{tweet_id}",
        'likes': t.get('likeCount') or t.get('favorite_count') or t.get('likes') or 0,
        'replies': t.get('replyCount') or t.get('reply_count') or t.get('replies') or 0,
        'views': views,
        'retweets': retweets,
        'quotes': quotes,
        'created_at': t.get('createdAt') or t.get('created_at') or '',
        'reply_settings': reply_settings,
        # Author metadata for pre-filtering
        'author_followers': author_followers,
        'author_following': author_following,
        'author_verified': author_verified,
        'author_created_at': author_created_at,
    }


async def fetch_tweets(keywords: list) -> list:
    """Fetch tweets using multiple targeted searches, then deduplicate."""
    # Filter out generic keywords
    good_keywords, filtered_out = filter_keywords(keywords)
    if filtered_out:
        logger.info(f"Filtered out generic keywords: {filtered_out}")
    if not good_keywords:
        logger.warning(f"All keywords filtered out! Original: {keywords}")
        return []

    logger.info(f"Searching ALL {len(good_keywords)} quality keywords: {good_keywords}")

    async with httpx.AsyncClient(timeout=300) as client:
        # Run ALL searches in parallel
        tasks = [_run_single_search(client, kw, max_items=20) for kw in good_keywords]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Deduplicate by tweet ID
    seen_ids = set()
    results = []
    for batch in search_results:
        if isinstance(batch, Exception):
            logger.error(f"Search batch failed: {batch}")
            continue
        for raw_tweet in batch:
            normalized = _normalize_tweet(raw_tweet)
            if normalized and normalized['id'] not in seen_ids:
                seen_ids.add(normalized['id'])
                results.append(normalized)

    logger.info(f"Total unique tweets after dedup: {len(results)} (from {len(good_keywords)} searches)")
    return results
