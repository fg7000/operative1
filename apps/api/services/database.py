import os
import logging
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

# Track which columns exist (populated by migration)
_extra_columns_exist = False


def set_extra_columns_exist(val: bool):
    global _extra_columns_exist
    _extra_columns_exist = val


async def get_active_products():
    res = supabase.table('products').select('*').eq('active', True).execute()
    return res.data


async def is_seen(platform: str, external_id: str) -> bool:
    res = supabase.table('seen_posts').select('id').eq('platform', platform).eq('external_id', external_id).execute()
    return len(res.data) > 0


async def mark_seen(platform: str, external_id: str, post: dict):
    supabase.table('seen_posts').upsert({
        'platform': platform,
        'external_id': external_id,
        'external_url': post.get('url', ''),
        'author': post.get('author', ''),
        'content': post.get('text', ''),
        'engagement_score': post.get('likes', 0)
    }).execute()


async def insert_reply_queue(product: dict, post: dict, reply_data: dict, platform: str) -> str:
    # Build engagement_metrics with all metadata
    engagement_metrics = {
        'reply_mode': reply_data.get('reply_mode', 'helpful_expert'),
        'relevance_reason': reply_data.get('relevance_reason', ''),
        'relevance_score': reply_data.get('relevance_score', 0),
        'original_language': reply_data.get('original_language', 'en'),
    }
    if reply_data.get('translated_content'):
        engagement_metrics['translated_content'] = reply_data['translated_content']

    row = {
        'product_id': product['id'],
        'user_id': product.get('user_id'),
        'platform': platform,
        'original_content': post.get('text', ''),
        'original_url': post.get('url', ''),
        'original_author': post.get('author', ''),
        'draft_reply': reply_data.get('reply', ''),
        'confidence_score': reply_data.get('confidence', 0),
        'mentions_product': reply_data.get('mentions_product', False),
        'engagement_metrics': engagement_metrics,
        'status': 'pending'
    }

    # Write to dedicated columns if migration has run
    if _extra_columns_exist:
        row['relevance_reason'] = reply_data.get('relevance_reason', '')
        row['original_language'] = reply_data.get('original_language', 'en')
        row['translated_content'] = reply_data.get('translated_content')

    res = supabase.table('reply_queue').insert(row).execute()
    return res.data[0]['id']


async def should_auto_post(product: dict, platform: str) -> bool:
    auto_post = product.get('auto_post', {})
    return auto_post.get(platform, False)
