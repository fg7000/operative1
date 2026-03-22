from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def start_scheduler():
    from pipelines.twitter import run_twitter_pipeline
    from pipelines.reddit import run_reddit_pipeline
    from pipelines.hn import run_hn_pipeline
    from pipelines.linkedin import run_linkedin_pipeline
    from pipelines.engagement import run_engagement_pipeline
    from services.optimizer import run_optimizer, run_keyword_optimizer
    from services.autopilot import run_autopilot_processor
    from services.broadcast_scheduler import check_scheduled_broadcasts

    # Twitter: every 2 hours (12 runs/day) to control Apify costs
    scheduler.add_job(run_twitter_pipeline, IntervalTrigger(hours=2), id='twitter', replace_existing=True)
    scheduler.add_job(run_reddit_pipeline, IntervalTrigger(minutes=15), id='reddit', replace_existing=True)
    scheduler.add_job(run_hn_pipeline, IntervalTrigger(minutes=10), id='hn', replace_existing=True)
    scheduler.add_job(run_linkedin_pipeline, IntervalTrigger(hours=2), id='linkedin', replace_existing=True)
    scheduler.add_job(run_engagement_pipeline, IntervalTrigger(hours=6), id='engagement', replace_existing=True)
    scheduler.add_job(run_optimizer, IntervalTrigger(weeks=1), id='optimizer', replace_existing=True)
    scheduler.add_job(run_keyword_optimizer, IntervalTrigger(days=1), id='keyword_optimizer', replace_existing=True)

    # Autopilot processor - runs every 2 minutes to process pending queue items
    # More frequent than main pipelines to quickly post approved items while
    # respecting rate limits
    scheduler.add_job(run_autopilot_processor, IntervalTrigger(minutes=2), id='autopilot', replace_existing=True)

    # Broadcast scheduler - runs every 60 seconds to check for scheduled broadcasts
    # Marks them as 'ready_to_post' for the extension to pick up
    scheduler.add_job(check_scheduled_broadcasts, IntervalTrigger(seconds=60), id='broadcast_scheduler', replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started — all pipelines active (including autopilot and broadcast)")
