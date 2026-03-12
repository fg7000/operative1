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
    """Normalize a raw Apify tweet into our standard format."""
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

    author = (
        t.get('author', {}).get('userName') if isinstance(t.get('author'), dict)
        else t.get('username') or t.get('user', {}).get('screen_name') or ''
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

    return {
        'id': tweet_id,
        'text': text,
        'author': author,
        'url': t.get('url') or t.get('tweetUrl') or f"https://twitter.com/i/web/status/{tweet_id}",
        'likes': t.get('likeCount') or t.get('favorite_count') or t.get('likes') or 0,
        'replies': t.get('replyCount') or t.get('reply_count') or t.get('replies') or 0,
        'created_at': t.get('createdAt') or t.get('created_at') or '',
        'reply_settings': reply_settings
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
        tasks = [_run_single_search(client, kw, max_items=30) for kw in good_keywords]
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
