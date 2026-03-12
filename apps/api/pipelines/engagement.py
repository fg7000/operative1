import logging
from services.poster import get_twitter_client

logger = logging.getLogger(__name__)

async def run_engagement_pipeline():
    """Fetch engagement metrics for posted Twitter replies and update the database."""
    logger.info("Engagement pipeline running")
    try:
        from services.database import supabase

        # Get all posted replies that have a posted_tweet_id
        res = supabase.table('reply_queue').select('*').eq('status', 'posted').eq('platform', 'twitter').execute()
        posted = [r for r in res.data if r.get('engagement_metrics', {}).get('posted_tweet_id')]
        logger.info(f"Found {len(posted)} posted tweets to check engagement")

        if not posted:
            return

        client = get_twitter_client()
        tweet_ids = [r['engagement_metrics']['posted_tweet_id'] for r in posted]

        # Batch lookup (tweepy supports up to 100 per request)
        for i in range(0, len(tweet_ids), 100):
            batch_ids = tweet_ids[i:i+100]
            try:
                tweets_response = client.get_tweets(
                    batch_ids,
                    tweet_fields=['public_metrics', 'created_at']
                )
                if not tweets_response.data:
                    logger.info("No tweet data returned from Twitter API")
                    continue

                metrics_map = {}
                for tweet in tweets_response.data:
                    m = tweet.public_metrics or {}
                    metrics_map[str(tweet.id)] = {
                        'likes': m.get('like_count', 0),
                        'retweets': m.get('retweet_count', 0),
                        'replies': m.get('reply_count', 0),
                        'impressions': m.get('impression_count', 0),
                        'bookmarks': m.get('bookmark_count', 0),
                    }

                # Update each reply_queue row with fresh metrics
                for row in posted:
                    tid = row['engagement_metrics']['posted_tweet_id']
                    if tid in metrics_map:
                        updated_metrics = {**row.get('engagement_metrics', {}), **metrics_map[tid]}
                        supabase.table('reply_queue').update({
                            'engagement_metrics': updated_metrics
                        }).eq('id', row['id']).execute()
                        logger.info(f"Updated engagement for queue {row['id']}: {metrics_map[tid]}")

            except Exception as e:
                logger.error(f"Twitter API error fetching engagement: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Engagement pipeline error: {e}", exc_info=True)
