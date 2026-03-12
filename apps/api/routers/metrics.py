from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

@router.get("/")
async def get_metrics():
    from services.database import supabase
    res = supabase.table('daily_stats').select('*').order('date', desc=True).limit(30).execute()
    return res.data

@router.get("/summary")
async def get_summary():
    from services.database import supabase
    queue_res = supabase.table('reply_queue').select('status').execute()
    stats = {'pending': 0, 'approved': 0, 'posted': 0, 'rejected': 0}
    for item in queue_res.data:
        status = item.get('status', 'pending')
        if status in stats:
            stats[status] += 1
    return stats

@router.get("/mode-performance")
async def mode_performance(product_id: Optional[str] = Query(None)):
    """Get average engagement metrics grouped by reply_mode."""
    from services.database import supabase

    query = supabase.table('reply_queue').select('*').eq('status', 'posted')
    if product_id:
        query = query.eq('product_id', product_id)
    res = query.execute()

    mode_stats = {}
    for row in res.data:
        metrics = row.get('engagement_metrics') or {}
        mode = metrics.get('reply_mode', 'unknown')
        if mode not in mode_stats:
            mode_stats[mode] = {'count': 0, 'total_likes': 0, 'total_retweets': 0, 'total_replies': 0, 'total_impressions': 0}
        s = mode_stats[mode]
        s['count'] += 1
        s['total_likes'] += metrics.get('likes', 0)
        s['total_retweets'] += metrics.get('retweets', 0)
        s['total_replies'] += metrics.get('replies', 0)
        s['total_impressions'] += metrics.get('impressions', 0)

    results = {}
    for mode, s in mode_stats.items():
        n = s['count']
        results[mode] = {
            'count': n,
            'avg_likes': round(s['total_likes'] / n, 2) if n else 0,
            'avg_retweets': round(s['total_retweets'] / n, 2) if n else 0,
            'avg_replies': round(s['total_replies'] / n, 2) if n else 0,
            'avg_impressions': round(s['total_impressions'] / n, 2) if n else 0,
            'engagement_score': round((s['total_likes'] + s['total_retweets'] * 2 + s['total_replies'] * 3) / n, 2) if n else 0,
        }

    return results
