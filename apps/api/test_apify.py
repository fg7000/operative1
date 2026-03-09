import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY = os.getenv('APIFY_API_KEY')

async def test():
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            "https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs",
            params={'token': APIFY_API_KEY},
            json={
                "searchTerms": ["AI privacy"],
                "maxItems": 5,
                "queryType": "Latest",
                "lang": "en"
            }
        )
        print(f"Start: {res.status_code}")
        run_id = res.json().get('data', {}).get('id')
        print(f"Run ID: {run_id}")

        for i in range(30):
            await asyncio.sleep(5)
            s = await client.get(
                f"https://api.apify.com/v2/acts/xtdata~twitter-x-scraper/runs/{run_id}",
                params={'token': APIFY_API_KEY}
            )
            status = s.json().get('data', {}).get('status')
            print(f"[{i}] {status}")
            if status == 'SUCCEEDED':
                dataset_id = s.json().get('data', {}).get('defaultDatasetId')
                items = await client.get(
                    f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                    params={'token': APIFY_API_KEY, 'format': 'json'}
                )
                tweets = items.json()
                print(f"Tweets returned: {len(tweets)}")
                if tweets:
                    print(f"Keys: {list(tweets[0].keys())}")
                    print(f"First tweet: {tweets[0]}")
                break
            if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                print(f"Failed: {status}")
                break

asyncio.run(test())
