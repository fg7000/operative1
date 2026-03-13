import logging
import httpx
import json
import os
from services.apify import fetch_tweets
from services.scoring import ai_context_score
from services.generator import generate_reply
from services.database import get_active_products, is_seen, mark_seen, insert_reply_queue, should_auto_post
from services.poster import post_to_twitter, check_tweet_reply_allowed
from services.agent_prompts import TRANSLATOR_PROMPT
from services.prefilter import prefilter_tweets
from services.analytics import PipelineStats, save_pipeline_run

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
                    'messages': [{'role': 'user', 'content': f"""Detect the language of this text. If it's English, return JSON: {{"language": "en", "translated": null}}
If it's NOT English, translate it using these instructions:
{TRANSLATOR_PROMPT}
Then return JSON: {{"language": "<iso-639-1 code>", "translated": "<your english translation>"}}

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


_pipeline_running = False

async def run_twitter_pipeline():
    global _pipeline_running
    if _pipeline_running:
        logger.info("Twitter pipeline already running, skipping this scheduled run")
        return
    _pipeline_running = True
    logger.info("Twitter pipeline running")
    try:
        products = await get_active_products()
        logger.info(f"Found {len(products)} active products")
        for product in products:
            # Initialize stats tracking for this product run
            stats = PipelineStats(product['id'], 'twitter')

            keywords = product.get('keywords', {}).get('twitter', [])
            logger.info(f"Product {product.get('name')}: {len(keywords)} twitter keywords")
            if not keywords:
                await save_pipeline_run(stats)
                continue
            tweets = await fetch_tweets(keywords)
            stats.tweets_fetched = len(tweets)
            logger.info(f"Fetched {len(tweets)} tweets for {product.get('name')}")

            # Phase 1: Free filters (reply restrictions, already seen)
            eligible_tweets = []
            for tweet in tweets:
                # Skip tweets with reply restrictions BEFORE any processing
                reply_settings = tweet.get('reply_settings', '')
                if reply_settings and reply_settings.lower() not in ('everyone', 'all', ''):
                    logger.debug(f"Skipped tweet {tweet['id']} - replies restricted ({reply_settings})")
                    stats.tweets_filtered_reply_restricted += 1
                    continue
                # Fallback: if Apify didn't provide reply_settings, check via Twitter API
                if not reply_settings or reply_settings == '':
                    if not check_tweet_reply_allowed(tweet['id']):
                        logger.debug(f"Skipped tweet {tweet['id']} - replies restricted (API check)")
                        stats.tweets_filtered_reply_restricted += 1
                        continue

                if await is_seen('twitter', tweet['id']):
                    logger.debug(f"Tweet {tweet['id']} already seen, skipping")
                    stats.tweets_filtered_already_seen += 1
                    continue

                eligible_tweets.append(tweet)

            logger.info(f"After free filters: {len(eligible_tweets)}/{len(tweets)} tweets eligible")

            # Phase 2: Pre-filter heuristics (cheap, no AI calls)
            filtered_tweets, prefilter_stats = prefilter_tweets(eligible_tweets, product)
            stats.tweets_filtered_prefilter = prefilter_stats['filtered']
            stats.prefilter_reasons = prefilter_stats['filter_reasons']
            logger.info(
                f"Pre-filter results: {prefilter_stats['passed']} passed, "
                f"{prefilter_stats['filtered']} filtered, "
                f"reasons: {prefilter_stats['filter_reasons']}"
            )

            # Phase 3: AI scoring on pre-filtered tweets only
            for tweet in filtered_tweets:
                logger.info(
                    f"Processing tweet {tweet.get('id')} "
                    f"(opportunity: {tweet.get('opportunity_score', 0):.1f}): "
                    f"{tweet.get('text', '')[:60]}..."
                )

                # Mark as seen now (before AI calls)
                await mark_seen('twitter', tweet['id'], tweet)

                # Detect language and translate if needed
                stats.ai_calls_translation += 1
                lang_data = await detect_and_translate(tweet.get('text', ''))
                original_language = lang_data.get('language', 'en')
                translated_content = lang_data.get('translated')

                if translated_content:
                    stats.tweets_translated += 1
                    logger.info(f"Tweet {tweet['id']} detected as {original_language}, translated")

                # Single AI context scoring pass (replaces tier1 + tier2)
                stats.ai_calls_scoring += 1
                stats.tweets_scored += 1
                score_data = await ai_context_score(tweet, product)
                if not score_data:
                    logger.info(f"Tweet {tweet['id']} AI scoring failed, skipping")
                    continue
                score = score_data['score']
                reason = score_data['reason']
                if score < 4:
                    stats.tweets_score_rejected += 1
                    logger.info(f"Tweet {tweet['id']} scored {score}/10 < 4, skipping — {reason}")
                    continue

                logger.info(f"Tweet {tweet['id']} scored {score}/10, generating reply — {reason}")

                # Pass language info so generator can reply in original language
                tweet_for_gen = {**tweet}
                if original_language != 'en':
                    tweet_for_gen['original_language'] = original_language

                stats.ai_calls_generation += 1
                reply_data = await generate_reply(tweet_for_gen, product, 'twitter')
                if not reply_data:
                    logger.info(f"Tweet {tweet['id']} failed to generate reply")
                    continue

                stats.replies_generated += 1

                # Attach scoring + translation metadata
                reply_data['relevance_reason'] = reason
                reply_data['relevance_score'] = score
                reply_data['original_language'] = original_language
                reply_data['translated_content'] = translated_content

                logger.info(f"Generated reply for tweet {tweet['id']}, inserting into queue...")
                queue_id = await insert_reply_queue(product, tweet, reply_data, 'twitter')
                stats.replies_queued += 1
                logger.info(f"Inserted queue item {queue_id}")
                if await should_auto_post(product, 'twitter'):
                    await post_to_twitter(queue_id, reply_data, tweet, product)
                    stats.replies_auto_posted += 1

            # Save pipeline run stats
            await save_pipeline_run(stats)
    except Exception as e:
        logger.error(f"Twitter pipeline error: {e}", exc_info=True)
    finally:
        _pipeline_running = False
        logger.info("Twitter pipeline finished, lock released")
