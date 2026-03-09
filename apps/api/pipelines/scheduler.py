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

    scheduler.add_job(run_twitter_pipeline, IntervalTrigger(minutes=20), id='twitter', replace_existing=True)
    scheduler.add_job(run_reddit_pipeline, IntervalTrigger(minutes=15), id='reddit', replace_existing=True)
    scheduler.add_job(run_hn_pipeline, IntervalTrigger(minutes=10), id='hn', replace_existing=True)
    scheduler.add_job(run_linkedin_pipeline, IntervalTrigger(hours=2), id='linkedin', replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started — all pipelines active")
