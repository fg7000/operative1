"""
Pipeline analytics for Operative1.

Tracks funnel metrics to understand pipeline efficiency:
- Tweets fetched
- Tweets pre-filtered (and why)
- Tweets AI-scored
- Replies generated
- Replies posted

Also tracks cost estimates based on AI API calls.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.database import supabase

logger = logging.getLogger(__name__)

# Estimated costs per AI call (OpenRouter pricing, approximate)
COST_ESTIMATES = {
    'translation': 0.0001,      # Haiku for translation
    'scoring': 0.0005,          # Haiku for context scoring
    'generation': 0.001,        # Claude for reply generation
}


class PipelineStats:
    """Accumulator for pipeline run statistics."""

    def __init__(self, product_id: str, platform: str):
        self.product_id = product_id
        self.platform = platform
        self.started_at = datetime.now(timezone.utc)

        # Funnel metrics
        self.tweets_fetched = 0
        self.tweets_filtered_reply_restricted = 0
        self.tweets_filtered_already_seen = 0
        self.tweets_filtered_prefilter = 0
        self.prefilter_reasons: dict[str, int] = {}
        self.tweets_translated = 0
        self.tweets_scored = 0
        self.tweets_score_rejected = 0
        self.replies_generated = 0
        self.replies_queued = 0
        self.replies_auto_posted = 0

        # Cost tracking
        self.ai_calls_translation = 0
        self.ai_calls_scoring = 0
        self.ai_calls_generation = 0

    def record_prefilter_skip(self, reason: str):
        """Record a tweet skipped by pre-filter."""
        self.tweets_filtered_prefilter += 1
        reason_key = reason.split(':')[0] if ':' in reason else reason
        self.prefilter_reasons[reason_key] = self.prefilter_reasons.get(reason_key, 0) + 1

    def estimate_cost(self) -> float:
        """Estimate total AI cost for this run."""
        return (
            self.ai_calls_translation * COST_ESTIMATES['translation'] +
            self.ai_calls_scoring * COST_ESTIMATES['scoring'] +
            self.ai_calls_generation * COST_ESTIMATES['generation']
        )

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            'product_id': self.product_id,
            'platform': self.platform,
            'started_at': self.started_at.isoformat(),
            'completed_at': datetime.now(timezone.utc).isoformat(),

            # Funnel
            'tweets_fetched': self.tweets_fetched,
            'tweets_filtered_reply_restricted': self.tweets_filtered_reply_restricted,
            'tweets_filtered_already_seen': self.tweets_filtered_already_seen,
            'tweets_filtered_prefilter': self.tweets_filtered_prefilter,
            'prefilter_reasons': self.prefilter_reasons,
            'tweets_translated': self.tweets_translated,
            'tweets_scored': self.tweets_scored,
            'tweets_score_rejected': self.tweets_score_rejected,
            'replies_generated': self.replies_generated,
            'replies_queued': self.replies_queued,
            'replies_auto_posted': self.replies_auto_posted,

            # Costs
            'ai_calls_translation': self.ai_calls_translation,
            'ai_calls_scoring': self.ai_calls_scoring,
            'ai_calls_generation': self.ai_calls_generation,
            'estimated_cost_usd': self.estimate_cost(),
        }


async def save_pipeline_run(stats: PipelineStats) -> str:
    """Save pipeline run stats to database."""
    try:
        res = supabase.table('pipeline_runs').insert(stats.to_dict()).execute()
        run_id = res.data[0]['id'] if res.data else None
        logger.info(f"Saved pipeline run {run_id}: {stats.tweets_fetched} fetched -> {stats.replies_queued} queued")
        return run_id
    except Exception as e:
        # Table might not exist yet - log and continue
        logger.warning(f"Failed to save pipeline run (table may not exist): {e}")
        return None


async def get_pipeline_stats(
    product_id: Optional[str] = None,
    platform: Optional[str] = None,
    days: int = 7
) -> dict:
    """Get aggregated pipeline statistics.

    Args:
        product_id: Filter by product (None for all)
        platform: Filter by platform (None for all)
        days: Number of days to look back

    Returns:
        Aggregated stats including totals and averages
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()

    query = supabase.table('pipeline_runs').select('*').gte('started_at', cutoff_str)

    if product_id:
        query = query.eq('product_id', product_id)
    if platform:
        query = query.eq('platform', platform)

    try:
        res = query.execute()
        runs = res.data or []
    except Exception:
        # Table might not exist
        return {'error': 'Analytics table not available', 'runs': 0}

    if not runs:
        return {
            'runs': 0,
            'period_days': days,
        }

    # Aggregate stats
    totals = {
        'runs': len(runs),
        'period_days': days,
        'tweets_fetched': sum(r.get('tweets_fetched', 0) for r in runs),
        'tweets_filtered_prefilter': sum(r.get('tweets_filtered_prefilter', 0) for r in runs),
        'tweets_scored': sum(r.get('tweets_scored', 0) for r in runs),
        'replies_generated': sum(r.get('replies_generated', 0) for r in runs),
        'replies_queued': sum(r.get('replies_queued', 0) for r in runs),
        'replies_auto_posted': sum(r.get('replies_auto_posted', 0) for r in runs),
        'total_cost_usd': sum(r.get('estimated_cost_usd', 0) for r in runs),
    }

    # Calculate efficiency rates
    if totals['tweets_fetched'] > 0:
        totals['prefilter_pass_rate'] = round(
            (totals['tweets_fetched'] - totals['tweets_filtered_prefilter']) / totals['tweets_fetched'] * 100, 1
        )
        totals['queue_rate'] = round(totals['replies_queued'] / totals['tweets_fetched'] * 100, 1)

    if totals['tweets_scored'] > 0:
        totals['score_pass_rate'] = round(totals['replies_generated'] / totals['tweets_scored'] * 100, 1)

    # Aggregate prefilter reasons
    all_reasons: dict[str, int] = {}
    for run in runs:
        for reason, count in (run.get('prefilter_reasons') or {}).items():
            all_reasons[reason] = all_reasons.get(reason, 0) + count
    totals['prefilter_reasons'] = all_reasons

    return totals


async def get_cost_summary(product_id: Optional[str] = None, days: int = 30) -> dict:
    """Get cost summary for a product or all products."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()

    query = supabase.table('pipeline_runs').select('estimated_cost_usd,started_at').gte('started_at', cutoff_str)

    if product_id:
        query = query.eq('product_id', product_id)

    try:
        res = query.execute()
        runs = res.data or []
    except Exception:
        return {'error': 'Analytics table not available'}

    total_cost = sum(r.get('estimated_cost_usd', 0) for r in runs)
    daily_costs: dict[str, float] = {}

    for run in runs:
        date = run['started_at'][:10]  # YYYY-MM-DD
        daily_costs[date] = daily_costs.get(date, 0) + run.get('estimated_cost_usd', 0)

    return {
        'period_days': days,
        'total_cost_usd': round(total_cost, 4),
        'avg_daily_cost_usd': round(total_cost / max(len(daily_costs), 1), 4),
        'daily_costs': daily_costs,
    }
