import os
import httpx
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY = os.getenv('APIFY_API_KEY')

async def fetch_tweets(keywords: list) -> list:
    query = ' OR '.join(keywords)
    url = f"https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items"
    params = {
        'token': APIFY_API_KEY,
        'timeout': 60
    }
    payload = {
        'searchTerms': [query],
        'maxTweets': 20,
        'queryType': 'Latest'
    }
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(url, params=params, json=payload)
        if res.status_code != 200:
            return []
        tweets = res.json()
        return [{
            'id': t.get('id', ''),
            'text': t.get('full_text', t.get('text', '')),
            'author': t.get('author', {}).get('userName', ''),
            'url': t.get('url', ''),
            'likes': t.get('likeCount', 0),
            'replies': t.get('replyCount', 0),
            'created_at': t.get('createdAt', '')
        } for t in tweets if t.get('id')]
