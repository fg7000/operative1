import logging
from services.apify import fetch_tweets
from services.scoring import tier1_score, tier2_score
from services.generator import generate_reply
from services.database import get_active_products, is_seen, mark_seen, insert_reply_queue, should_auto_post
from services.poster import post_to_twitter

logger = logging.getLogger(__name__)

async def run_twitter_pipeline():
    logger.info("Twitter pipeline running")
    try:
        products = await get_active_products()
        for product in products:
            keywords = product.get('keywords', {}).get('twitter', [])
            if not keywords:
                continue
            tweets = await fetch_tweets(keywords)
            for tweet in tweets:
                if await is_seen('twitter', tweet['id']):
                    continue
                await mark_seen('twitter', tweet['id'], tweet)
                score = tier1_score(tweet, keywords)
                if score < 30:
                    continue
                relevance = await tier2_score(tweet, product)
                if relevance < 0.6:
                    continue
                reply_data = await generate_reply(tweet, product, 'twitter')
                if not reply_data:
                    continue
                queue_id = await insert_reply_queue(product, tweet, reply_data, 'twitter')
                if await should_auto_post(product, 'twitter'):
                    await post_to_twitter(queue_id, reply_data, tweet, product)
    except Exception as e:
        logger.error(f"Twitter pipeline error: {e}")
