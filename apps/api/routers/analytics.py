"""
Analytics router for Operative1 API.

Provides aggregated analytics data for the dashboard.

Endpoints:
- GET /analytics/dashboard — Full dashboard data for a product (auth + ownership required)
- GET /analytics/pipeline — Pipeline funnel stats
- GET /analytics/costs — AI cost breakdown
- GET /analytics/rate-limits — Current rate limit status
- GET /analytics/queue-status — Global queue status
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
import logging

from services.auth import get_current_user, verify_product_ownership
from services.analytics import get_pipeline_stats, get_cost_summary
from services.rate_limiter import get_rate_limit_status
from services.global_queue import get_global_queue_stats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def get_dashboard(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get complete analytics dashboard data for a product.

    Returns:
    - status_counts: Count of items by status (posted, pending, failed, rejected)
    - mode_breakdown: Count of posted items by reply_mode
    - score_distribution: Count of items by relevance score buckets
    - daily_timeline: Posted items per day for last 30 days
    """
    from services.database import supabase

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    await verify_product_ownership(user_id, product_id)

    try:
        # Fetch all queue items for this product
        res = supabase.table('reply_queue').select('*').eq('product_id', product_id).execute()
        items = res.data or []

        # Status counts
        status_counts = {
            'posted': 0,
            'pending': 0,
            'failed': 0,
            'rejected': 0,
        }
        for item in items:
            status = item.get('status', 'pending')
            if status in status_counts:
                status_counts[status] += 1

        # Mode breakdown (for posted items only)
        mode_breakdown = {
            'helpful_expert': 0,
            'soft_mention': 0,
            'direct_pitch': 0,
            'unknown': 0,
        }
        mode_engagement = {
            'helpful_expert': {'likes': 0, 'impressions': 0, 'count': 0},
            'soft_mention': {'likes': 0, 'impressions': 0, 'count': 0},
            'direct_pitch': {'likes': 0, 'impressions': 0, 'count': 0},
        }

        for item in items:
            if item.get('status') != 'posted':
                continue
            metrics = item.get('engagement_metrics') or {}
            mode = metrics.get('reply_mode', 'unknown')
            if mode in mode_breakdown:
                mode_breakdown[mode] += 1
            else:
                mode_breakdown['unknown'] += 1

            # Aggregate engagement by mode
            if mode in mode_engagement:
                mode_engagement[mode]['likes'] += metrics.get('likes', 0)
                mode_engagement[mode]['impressions'] += metrics.get('impressions', 0)
                mode_engagement[mode]['count'] += 1

        # Calculate averages
        mode_averages = {}
        for mode, data in mode_engagement.items():
            count = data['count']
            mode_averages[mode] = {
                'avg_likes': round(data['likes'] / count, 2) if count else 0,
                'avg_impressions': round(data['impressions'] / count, 2) if count else 0,
            }

        # Score distribution (relevance scores 0-10)
        score_distribution = {
            '0-3': 0,  # Low relevance
            '4-5': 0,  # Medium relevance
            '6-7': 0,  # Good relevance
            '8-10': 0,  # High relevance
        }
        for item in items:
            metrics = item.get('engagement_metrics') or {}
            score = metrics.get('relevance_score', 0)
            if score <= 3:
                score_distribution['0-3'] += 1
            elif score <= 5:
                score_distribution['4-5'] += 1
            elif score <= 7:
                score_distribution['6-7'] += 1
            else:
                score_distribution['8-10'] += 1

        # Daily timeline for last 30 days
        today = datetime.utcnow().date()
        thirty_days_ago = today - timedelta(days=30)

        daily_counts = {}
        for item in items:
            if item.get('status') != 'posted':
                continue
            posted_at = item.get('posted_at')
            if not posted_at:
                continue
            try:
                # Parse the date
                if isinstance(posted_at, str):
                    posted_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00')).date()
                else:
                    posted_date = posted_at.date()

                if posted_date >= thirty_days_ago:
                    date_str = posted_date.isoformat()
                    daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            except Exception as e:
                logger.warning(f"Failed to parse posted_at {posted_at}: {e}")

        # Build timeline with all 30 days (fill zeros)
        daily_timeline = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            date_str = date.isoformat()
            daily_timeline.append({
                'date': date_str,
                'count': daily_counts.get(date_str, 0)
            })

        return {
            'status_counts': status_counts,
            'mode_breakdown': mode_breakdown,
            'mode_averages': mode_averages,
            'score_distribution': score_distribution,
            'daily_timeline': daily_timeline,
            'total_items': len(items),
        }

    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load analytics")


@router.get("/pipeline")
async def pipeline_analytics(
    product_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    user_id: str = Depends(get_current_user)
):
    """
    Get pipeline funnel analytics.

    Shows how many tweets were fetched, filtered, scored, and converted to replies.
    """
    if product_id:
        await verify_product_ownership(user_id, product_id)

    stats = await get_pipeline_stats(product_id=product_id, platform=platform, days=days)
    return stats


@router.get("/costs")
async def cost_analytics(
    product_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    user_id: str = Depends(get_current_user)
):
    """
    Get AI cost breakdown.

    Shows estimated costs for translation, scoring, and generation.
    """
    if product_id:
        await verify_product_ownership(user_id, product_id)

    costs = await get_cost_summary(product_id=product_id, days=days)
    return costs


@router.get("/rate-limits")
async def rate_limit_analytics(
    product_id: str = Query(...),
    platform: str = Query("twitter"),
    user_id: str = Depends(get_current_user)
):
    """
    Get current rate limit status for a product.

    Shows remaining quota, time until next post, etc.
    """
    from services.database import supabase

    await verify_product_ownership(user_id, product_id)

    # Get product config
    res = supabase.table('products').select('*').eq('id', product_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Product not found")

    product = res.data
    rate_status = await get_rate_limit_status(product, platform)

    return rate_status


@router.get("/queue-status")
async def queue_status_analytics(
    user_id: str = Depends(get_current_user)
):
    """
    Get global queue status for the user's account.

    Shows pending items, next post time, estimated clear time.
    """
    stats = await get_global_queue_stats(user_id)
    return stats
