import logging

logger = logging.getLogger(__name__)

async def run_engagement_pipeline():
    """Fetch engagement metrics for posted Twitter replies.

    NOTE: Disabled after removing tweepy. Engagement tracking via GraphQL
    would require scraping TweetDetail endpoint which is more complex.
    Re-enable when needed.
    """
    logger.info("Engagement pipeline skipped (tweepy removed, GraphQL metrics not implemented)")
    return
