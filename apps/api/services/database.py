import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

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
    res = supabase.table('reply_queue').insert({
        'product_id': product['id'],
        'user_id': product.get('user_id'),
        'platform': platform,
        'original_content': post.get('text', ''),
        'original_url': post.get('url', ''),
        'original_author': post.get('author', ''),
        'draft_reply': reply_data.get('reply', ''),
        'confidence_score': reply_data.get('confidence', 0),
        'mentions_product': reply_data.get('mentions_product', False),
        'engagement_metrics': {'reply_mode': reply_data.get('reply_mode', 'helpful_expert')},
        'status': 'pending'
    }).execute()
    return res.data[0]['id']

async def should_auto_post(product: dict, platform: str) -> bool:
    auto_post = product.get('auto_post', {})
    return auto_post.get(platform, False)
