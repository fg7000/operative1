import logging
import httpx
import json
import os
from services.apify import fetch_tweets
from services.scoring import ai_context_score
from services.generator import generate_reply
from services.database import get_active_products, is_seen, mark_seen, insert_reply_queue, should_auto_post
from services.poster import post_to_twitter

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')


async def detect_and_translate(text: str) -> dict:
    """Detect language and translate to English if non-English.
    Returns {'language': 'xx', 'translated': 'english text' or None}."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': f"""Detect the language of this text and translate it to English if it's not already English.
Return JSON only: {{"language": "en", "translated": null}} if English, or {{"language": "tr", "translated": "the english translation"}} if non-English.
Use ISO 639-1 language codes.

Text: {text}"""}],
                    'max_tokens': 500
                }
            )
            content = res.json()['choices'][0]['message']['content']
            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first != -1 and last > first:
                parsed = json.loads(clean[first:last + 1])
                return parsed
    except Exception as e:
        logger.error(f"Translation error: {e}")
    return {'language': 'en', 'translated': None}


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

                # Detect language and translate if needed
                lang_data = await detect_and_translate(tweet.get('text', ''))
                original_language = lang_data.get('language', 'en')
                translated_content = lang_data.get('translated')

                if translated_content:
                    logger.info(f"Tweet {tweet['id']} detected as {original_language}, translated")

                # Single AI context scoring pass (replaces tier1 + tier2)
                score_data = await ai_context_score(tweet, product)
                if not score_data:
                    logger.info(f"Tweet {tweet['id']} AI scoring failed, skipping")
                    continue
                score = score_data['score']
                reason = score_data['reason']
                if score < 5:
                    logger.info(f"Tweet {tweet['id']} scored {score}/10 < 5, skipping — {reason}")
                    continue

                logger.info(f"Tweet {tweet['id']} scored {score}/10, generating reply — {reason}")

                # Pass language info so generator can reply in original language
                tweet_for_gen = {**tweet}
                if original_language != 'en':
                    tweet_for_gen['original_language'] = original_language

                reply_data = await generate_reply(tweet_for_gen, product, 'twitter')
                if not reply_data:
                    logger.info(f"Tweet {tweet['id']} failed to generate reply")
                    continue

                # Attach scoring + translation metadata
                reply_data['relevance_reason'] = reason
                reply_data['relevance_score'] = score
                reply_data['original_language'] = original_language
                reply_data['translated_content'] = translated_content

                logger.info(f"Generated reply for tweet {tweet['id']}, inserting into queue...")
                queue_id = await insert_reply_queue(product, tweet, reply_data, 'twitter')
                logger.info(f"Inserted queue item {queue_id}")
                if await should_auto_post(product, 'twitter'):
                    await post_to_twitter(queue_id, reply_data, tweet, product)
    except Exception as e:
        logger.error(f"Twitter pipeline error: {e}", exc_info=True)
