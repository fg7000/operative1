"""
Amplification engine for Operative1.

When a broadcast post is published and amplification is triggered:
1. Take the broadcast post content and product keywords
2. Search for 5-10 ACTIVE conversations (tweets < 6 hours old, related topic)
3. Generate context-aware replies that naturally reference the broadcast topic
4. Queue replies through the normal fire rate system (no bypass)
5. Track amplification reply count on the broadcast

Amplification replies skip AI scoring (Decision 3A) since they're manually triggered.
"""

import logging
import os
import httpx
from datetime import datetime, timezone
import uuid

from services.database import supabase
from services.apify import fetch_tweets
from services.generator import generate_reply
from services.agent_prompts import AMPLIFICATION_REPLY_PROMPT

logger = logging.getLogger(__name__)

# Max conversations to find per amplification
MAX_CONVERSATIONS = 10
# Max hours old for eligible tweets
MAX_TWEET_AGE_HOURS = 6
# Minimum views for a tweet to be worth amplifying
MIN_VIEWS = 1000


async def find_amplification_targets(broadcast: dict, product: dict) -> list:
    """
    Find active conversations related to the broadcast topic.

    Uses product keywords to search for recent, high-engagement tweets
    that are good candidates for contextual replies.
    """
    keywords = product.get('keywords', {}).get('twitter', [])
    if not keywords:
        logger.warning(f"No Twitter keywords for product {product['id']}")
        return []

    # Use first 3 keywords for search
    search_keywords = keywords[:3]

    all_tweets = []
    for keyword in search_keywords:
        try:
            tweets = await fetch_tweets([keyword], max_per_keyword=30)
            all_tweets.extend(tweets)
        except Exception as e:
            logger.error(f"Failed to fetch tweets for keyword '{keyword}': {e}")

    # Deduplicate by tweet ID
    seen_ids = set()
    unique_tweets = []
    for tweet in all_tweets:
        if tweet['id'] not in seen_ids:
            seen_ids.add(tweet['id'])
            unique_tweets.append(tweet)

    # Filter by recency and engagement
    eligible = []
    now = datetime.now(timezone.utc)

    for tweet in unique_tweets:
        # Check age
        created_at = tweet.get('created_at', '')
        if created_at:
            try:
                # Parse various date formats
                from services.prefilter import parse_tweet_age_hours
                age_hours = parse_tweet_age_hours(created_at)
                if age_hours and age_hours > MAX_TWEET_AGE_HOURS:
                    continue
            except Exception:
                pass

        # Check views/engagement
        views = tweet.get('views', 0) or 0
        likes = tweet.get('likes', 0) or 0

        # Either has good views OR good likes
        if views < MIN_VIEWS and likes < 10:
            continue

        # Skip tweets we've already replied to
        from services.database import is_seen
        if await is_seen('twitter', tweet['id']):
            continue

        eligible.append(tweet)

    # Sort by engagement and take top N
    eligible.sort(key=lambda t: (t.get('views', 0) or 0) + (t.get('likes', 0) or 0) * 100, reverse=True)

    return eligible[:MAX_CONVERSATIONS]


async def generate_amplification_reply(tweet: dict, broadcast: dict, product: dict) -> dict:
    """
    Generate a contextual reply that references the broadcast topic.

    Uses a special prompt that:
    - Makes a genuinely helpful reply
    - Connects the conversation to the broadcast theme
    - Doesn't directly pitch the product
    """
    # Build context for the generator
    broadcast_context = {
        'broadcast_content': broadcast['content'],
        'broadcast_url': broadcast.get('external_url', ''),
    }

    # Use the amplification prompt
    reply_data = await generate_reply(
        tweet,
        product,
        'twitter',
        custom_prompt=AMPLIFICATION_REPLY_PROMPT.format(
            broadcast_content=broadcast['content'],
            original_tweet=tweet.get('text', ''),
            product_name=product.get('name', ''),
            product_description=product.get('description', ''),
        )
    )

    if reply_data:
        reply_data['amplification_context'] = broadcast_context
        # Force helpful_expert mode for amplification
        reply_data['reply_mode'] = 'helpful_expert'

    return reply_data


async def run_amplification(broadcast_id: str) -> dict:
    """
    Main amplification function. Called when user triggers amplification.

    Returns:
        {
            'conversations_found': int,
            'replies_queued': int,
            'errors': list
        }
    """
    logger.info(f"Starting amplification for broadcast {broadcast_id}")

    result = {
        'conversations_found': 0,
        'replies_queued': 0,
        'errors': [],
    }

    try:
        # Get the broadcast
        broadcast_res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
        if not broadcast_res.data:
            result['errors'].append('Broadcast not found')
            return result

        broadcast = broadcast_res.data

        # Get the product
        product_res = supabase.table('products').select('*').eq('id', broadcast['product_id']).single().execute()
        if not product_res.data:
            result['errors'].append('Product not found')
            return result

        product = product_res.data

        # Find target conversations
        targets = await find_amplification_targets(broadcast, product)
        result['conversations_found'] = len(targets)

        logger.info(f"Found {len(targets)} amplification targets for broadcast {broadcast_id[:8]}")

        if not targets:
            # Mark amplification as completed (no targets found)
            supabase.table('broadcast_posts').update({
                'amplification_status': 'completed'
            }).eq('id', broadcast_id).execute()
            return result

        # Generate and queue replies
        for tweet in targets:
            try:
                # Mark as seen to prevent duplicate replies
                from services.database import mark_seen
                await mark_seen('twitter', tweet['id'], tweet)

                # Generate amplification reply
                reply_data = await generate_amplification_reply(tweet, broadcast, product)
                if not reply_data:
                    logger.warning(f"Failed to generate reply for tweet {tweet['id']}")
                    continue

                # Insert into reply_queue with amplification link
                queue_id = str(uuid.uuid4())

                engagement_metrics = {
                    'reply_mode': reply_data.get('reply_mode', 'helpful_expert'),
                    'relevance_reason': 'amplification_target',
                    'relevance_score': 8,  # High score since manually triggered
                    'amplification_source': broadcast_id,
                }

                row = {
                    'id': queue_id,
                    'product_id': product['id'],
                    'user_id': broadcast['user_id'],
                    'platform': 'twitter',
                    'original_content': tweet.get('text', ''),
                    'original_url': tweet.get('url', ''),
                    'original_author': tweet.get('author', ''),
                    'draft_reply': reply_data.get('reply', ''),
                    'confidence_score': reply_data.get('confidence', 0.8),
                    'mentions_product': reply_data.get('mentions_product', False),
                    'engagement_metrics': engagement_metrics,
                    'status': 'pending',
                    'amplifies_broadcast_id': broadcast_id,
                }

                supabase.table('reply_queue').insert(row).execute()
                result['replies_queued'] += 1

                logger.info(f"Queued amplification reply {queue_id[:8]} for tweet {tweet['id']}")

            except Exception as e:
                logger.error(f"Failed to process amplification target {tweet.get('id')}: {e}")
                result['errors'].append(str(e))

        # Update broadcast with amplification count and status
        supabase.table('broadcast_posts').update({
            'amplification_status': 'completed',
            'amplification_replies_count': result['replies_queued'],
        }).eq('id', broadcast_id).execute()

        logger.info(
            f"Amplification complete for broadcast {broadcast_id[:8]}: "
            f"{result['conversations_found']} found, {result['replies_queued']} queued"
        )

    except Exception as e:
        logger.error(f"Amplification error for broadcast {broadcast_id}: {e}", exc_info=True)
        result['errors'].append(str(e))

        # Mark as failed
        supabase.table('broadcast_posts').update({
            'amplification_status': 'none',
            'error_message': str(e),
        }).eq('id', broadcast_id).execute()

    return result
