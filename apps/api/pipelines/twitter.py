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
        logger.info(f"Found {len(products)} active products")
        for product in products:
            keywords = product.get('keywords', {}).get('twitter', [])
            logger.info(f"Product {product.get('name')}: {len(keywords)} twitter keywords")
            if not keywords:
                continue
            tweets = await fetch_tweets(keywords)
            logger.info(f"Fetched {len(tweets)} tweets for {product.get('name')}")
            for tweet in tweets:
                logger.info(f"Processing tweet {tweet.get('id')}: {tweet.get('text', '')[:60]}...")
                if await is_seen('twitter', tweet['id']):
                    logger.info(f"Tweet {tweet['id']} already seen, skipping")
                    continue
                await mark_seen('twitter', tweet['id'], tweet)
                score = tier1_score(tweet, keywords)
                if score < 30:
                    logger.info(f"Tweet {tweet['id']} scored {score} < 30, skipping")
                    continue
                logger.info(f"Tweet {tweet['id']} passed tier1 with score {score}, running tier2...")
                relevance = await tier2_score(tweet, product)
                logger.info(f"Tweet {tweet['id']} tier2 relevance: {relevance}")
                if relevance < 0.4:
                    logger.info(f"Tweet {tweet['id']} relevance {relevance} < 0.4, skipping")
                    continue
                logger.info(f"Tweet {tweet['id']} passed tier2, generating reply...")
                reply_data = await generate_reply(tweet, product, 'twitter')
                if not reply_data:
                    logger.info(f"Tweet {tweet['id']} failed to generate reply")
                    continue
                logger.info(f"Generated reply for tweet {tweet['id']}, inserting into queue...")
                queue_id = await insert_reply_queue(product, tweet, reply_data, 'twitter')
                logger.info(f"Inserted queue item {queue_id}")
                if await should_auto_post(product, 'twitter'):
                    await post_to_twitter(queue_id, reply_data, tweet, product)
    except Exception as e:
        logger.error(f"Twitter pipeline error: {e}", exc_info=True)
