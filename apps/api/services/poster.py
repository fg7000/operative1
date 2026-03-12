import os
import tweepy
from dotenv import load_dotenv

load_dotenv()

def get_twitter_client():
    return tweepy.Client(
        consumer_key=os.getenv('TWITTER_API_KEY'),
        consumer_secret=os.getenv('TWITTER_API_SECRET'),
        access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
        access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    )

async def post_to_twitter(queue_id: str, reply_data: dict, original_post: dict, product: dict):
    from services.database import supabase
    try:
        client = get_twitter_client()
        reply_text = reply_data.get('reply', '')
        tweet_id = original_post.get('id')
        response = client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        posted_tweet_id = response.data['id'] if response.data else None
        # Merge posted_tweet_id into existing engagement_metrics
        existing = supabase.table('reply_queue').select('engagement_metrics').eq('id', queue_id).execute()
        metrics = (existing.data[0].get('engagement_metrics') or {}) if existing.data else {}
        metrics['posted_tweet_id'] = str(posted_tweet_id) if posted_tweet_id else None
        supabase.table('reply_queue').update({
            'status': 'posted',
            'posted_at': 'now()',
            'engagement_metrics': metrics
        }).eq('id', queue_id).execute()
    except Exception as e:
        supabase.table('reply_queue').update({
            'status': 'failed',
            'rejection_reason': str(e)
        }).eq('id', queue_id).execute()
