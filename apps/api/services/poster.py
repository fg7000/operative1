"""
Twitter posting via internal GraphQL API (bypasses v2 API reply restrictions).
Uses cookie-based auth (auth_token + ct0) instead of OAuth.
"""
import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Twitter's internal bearer token (public, used by the web client)
TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# GraphQL endpoint and query ID for CreateTweet
# Note: queryId may change when Twitter updates their bundle - check main.js if this breaks
GRAPHQL_CREATE_TWEET_URL = "https://x.com/i/api/graphql/znCTF5Sz05z_JNXM6p5xWg/CreateTweet"


def check_tweet_reply_allowed(tweet_id: str) -> bool:
    """Check if a tweet allows replies.

    With GraphQL posting, we can usually reply to any tweet that allows it.
    This is a fallback check when Apify doesn't provide reply_settings.
    Returns True by default since GraphQL has fewer restrictions.
    """
    # For now, assume replies are allowed - the GraphQL API will fail gracefully
    # if they're not, and we'll catch that in post_tweet_graphql
    return True


def get_twitter_cookies(user_id: str = None) -> dict:
    """Get Twitter cookies for posting.
    Checks social_accounts table by user_id, then falls back to env vars."""
    auth_token = None
    ct0 = None

    # Try to get from database if user_id provided
    if user_id:
        try:
            from services.database import supabase
            result = supabase.table('social_accounts').select('credentials').eq('user_id', user_id).eq('platform', 'twitter').execute()
            if result.data and result.data[0].get('credentials'):
                creds = result.data[0]['credentials']
                auth_token = creds.get('auth_token')
                ct0 = creds.get('ct0')
                logger.info(f"Found Twitter cookies in database for user {user_id}")
        except Exception as e:
            logger.warning(f"Could not fetch cookies from database: {e}")

    # Fall back to environment variables
    if not auth_token or not ct0:
        auth_token = os.getenv('TWITTER_AUTH_TOKEN')
        ct0 = os.getenv('TWITTER_CT0')
        if auth_token and ct0:
            logger.info("Using Twitter cookies from environment variables")

    if not auth_token or not ct0:
        logger.error("No Twitter cookies available - neither in database nor env vars")
        return None

    return {'auth_token': auth_token, 'ct0': ct0}


def build_tweet_payload(text: str, reply_to_tweet_id: str = None) -> dict:
    """Build the GraphQL payload for CreateTweet."""
    variables = {
        "tweet_text": text,
        "dark_request": False,
        "media": {
            "media_entities": [],
            "possibly_sensitive": False
        },
        "semantic_annotation_ids": []
    }

    # Add reply context if this is a reply
    if reply_to_tweet_id:
        variables["reply"] = {
            "in_reply_to_tweet_id": str(reply_to_tweet_id),
            "exclude_reply_user_ids": []
        }
        logger.info(f"Building reply to tweet {reply_to_tweet_id}")
    else:
        logger.info("Building standalone tweet")

    features = {
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "articles_preview_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }

    return {
        "variables": json.dumps(variables),
        "features": json.dumps(features),
        "queryId": "znCTF5Sz05z_JNXM6p5xWg"
    }


async def post_tweet_graphql(text: str, reply_to_tweet_id: str = None, user_id: str = None) -> dict:
    """Post a tweet using Twitter's internal GraphQL API.

    Returns:
        {"success": True, "tweet_id": "123..."} on success
        {"success": False, "error": "error message"} on failure
    """
    cookies = get_twitter_cookies(user_id=user_id)
    if not cookies:
        return {"success": False, "error": "No Twitter cookies configured. Please connect your Twitter account."}

    auth_token = cookies['auth_token']
    ct0 = cookies['ct0']

    headers = {
        "authorization": f"Bearer {TWITTER_BEARER}",
        "x-csrf-token": ct0,
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "content-type": "application/x-www-form-urlencoded",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "origin": "https://x.com",
        "referer": "https://x.com/compose/tweet"
    }

    payload = build_tweet_payload(text, reply_to_tweet_id)

    logger.info(f"Posting tweet via GraphQL: {text[:50]}...")
    logger.info(f"Reply to: {reply_to_tweet_id or 'None (standalone)'}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GRAPHQL_CREATE_TWEET_URL,
                headers=headers,
                data=payload
            )

            logger.info(f"GraphQL response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"GraphQL response: {json.dumps(data)[:500]}")

                # Extract tweet ID from response
                try:
                    tweet_result = data.get('data', {}).get('create_tweet', {}).get('tweet_results', {}).get('result', {})
                    tweet_id = tweet_result.get('rest_id')
                    if tweet_id:
                        logger.info(f"Tweet posted successfully! ID: {tweet_id}")
                        return {"success": True, "tweet_id": tweet_id}
                    else:
                        logger.error(f"Could not extract tweet_id from response: {data}")
                        return {"success": False, "error": "Tweet may have posted but could not confirm ID"}
                except Exception as e:
                    logger.error(f"Error parsing response: {e}")
                    return {"success": False, "error": f"Response parse error: {e}"}

            elif response.status_code == 403:
                error_text = response.text
                logger.error(f"403 Forbidden: {error_text}")
                if "ct0" in error_text.lower() or "csrf" in error_text.lower():
                    return {"success": False, "error": "Twitter session expired. Please reconnect your Twitter account."}
                return {"success": False, "error": f"Twitter rejected the request: {error_text[:200]}"}

            elif response.status_code == 401:
                logger.error(f"401 Unauthorized: {response.text}")
                return {"success": False, "error": "Twitter authentication failed. Please reconnect your Twitter account."}

            else:
                logger.error(f"Unexpected status {response.status_code}: {response.text[:500]}")
                return {"success": False, "error": f"Twitter returned status {response.status_code}"}

    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        return {"success": False, "error": f"Network error: {str(e)}"}


def extract_author_from_url(url: str) -> str:
    """Extract Twitter username from tweet URL."""
    if not url:
        return ''
    parts = url.split('/')
    for i, p in enumerate(parts):
        if p in ('x.com', 'twitter.com') and i + 1 < len(parts):
            return parts[i + 1]
    return ''


def extract_tweet_id_from_url(url: str) -> str:
    """Extract tweet ID from tweet URL."""
    if not url:
        return ''
    parts = url.split('/')
    for i, p in enumerate(parts):
        if p == 'status' and i + 1 < len(parts):
            # Remove any query params
            tweet_id = parts[i + 1].split('?')[0]
            return tweet_id
    return ''


async def post_to_twitter(queue_id: str, reply_data: dict, original_post: dict, product: dict):
    """Post to Twitter using the GraphQL API. Updates queue item status in database."""
    from services.database import supabase

    try:
        reply_text = reply_data.get('reply', '')
        tweet_url = original_post.get('url', '')
        original_tweet_id = original_post.get('id') or extract_tweet_id_from_url(tweet_url)

        # Get user_id from the queue item to look up their cookies
        queue_item = supabase.table('reply_queue').select('user_id').eq('id', queue_id).single().execute()
        user_id = queue_item.data.get('user_id') if queue_item.data else None

        logger.info(f"Posting reply for queue_id={queue_id}, user_id={user_id}, reply_to={original_tweet_id}")

        # Post using user's cookies from social_accounts (falls back to env vars)
        result = await post_tweet_graphql(reply_text, reply_to_tweet_id=original_tweet_id, user_id=user_id)

        if result['success']:
            posted_tweet_id = result['tweet_id']
            logger.info(f"Reply posted successfully: {posted_tweet_id}")

            # Update queue item with success
            existing = supabase.table('reply_queue').select('engagement_metrics').eq('id', queue_id).execute()
            metrics = (existing.data[0].get('engagement_metrics') or {}) if existing.data else {}
            metrics['posted_tweet_id'] = str(posted_tweet_id)

            supabase.table('reply_queue').update({
                'status': 'posted',
                'posted_at': 'now()',
                'engagement_metrics': metrics
            }).eq('id', queue_id).execute()
        else:
            error_msg = result['error']
            logger.error(f"Failed to post reply: {error_msg}")

            supabase.table('reply_queue').update({
                'status': 'failed',
                'rejection_reason': error_msg
            }).eq('id', queue_id).execute()

    except Exception as e:
        logger.error(f"post_to_twitter error: {e}", exc_info=True)
        supabase.table('reply_queue').update({
            'status': 'failed',
            'rejection_reason': str(e)
        }).eq('id', queue_id).execute()
