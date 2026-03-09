import os
import httpx
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY = os.getenv('APIFY_API_KEY')
logger = logging.getLogger(__name__)

async def fetch_tweets(keywords: list) -> list:
    query = ' OR '.join(keywords[:4])
    logger.info(f"Fetching tweets for query: {query}")

    async with httpx.AsyncClient(timeout=120) as client:
        # Start the run
        start_res = await client.post(
            f"https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs",
            params={'token': APIFY_API_KEY},
            json={
                "searchTerms": [query],
                "maxItems": 20,
                "queryType": "Latest",
                "lang": "en"
            }
        )

        if start_res.status_code not in (200, 201):
            logger.error(f"Failed to start Apify run: {start_res.status_code} {start_res.text}")
            return []

        run_id = start_res.json().get('data', {}).get('id')
        if not run_id:
            logger.error(f"No run ID: {start_res.text}")
            return []

        logger.info(f"Apify run started: {run_id}")

        # Poll until complete
        for attempt in range(30):
            await asyncio.sleep(5)
            status_res = await client.get(
                f"https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs/{run_id}",
                params={'token': APIFY_API_KEY}
            )
            status = status_res.json().get('data', {}).get('status', '')
            logger.info(f"Poll [{attempt}] status: {status}")
            if status == 'SUCCEEDED':
                break
            if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                logger.error(f"Run ended with: {status}")
                return []

        # Fetch dataset
        dataset_id = status_res.json().get('data', {}).get('defaultDatasetId')
        items_res = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={'token': APIFY_API_KEY, 'format': 'json', 'clean': 'true'}
        )

        tweets = items_res.json()
        logger.info(f"Raw tweets returned: {len(tweets)}")
        if tweets:
            logger.info(f"Sample keys: {list(tweets[0].keys())}")
            logger.info(f"Sample tweet: {tweets[0]}")

        results = []
        for t in tweets:
            # Handle multiple possible field names across actors
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
                continue

            author = (
                t.get('author', {}).get('userName') if isinstance(t.get('author'), dict)
                else t.get('username') or t.get('user', {}).get('screen_name') or ''
            )

            results.append({
                'id': tweet_id,
                'text': text,
                'author': author,
                'url': t.get('url') or t.get('tweetUrl') or f"https://twitter.com/i/web/status/{tweet_id}",
                'likes': t.get('likeCount') or t.get('favorite_count') or t.get('likes') or 0,
                'replies': t.get('replyCount') or t.get('reply_count') or t.get('replies') or 0,
                'created_at': t.get('createdAt') or t.get('created_at') or ''
            })

        logger.info(f"Normalized tweets: {len(results)}")
        return results
