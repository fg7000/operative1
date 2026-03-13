"""
Broadcast scheduler service for Operative1.

Runs every 60 seconds to check for scheduled broadcasts that are ready to post.
Changes their status from 'scheduled' to 'ready_to_post' so the frontend/extension
can pick them up.

Note: Scheduled posts require the dashboard to be open for the extension to post.
If the user isn't present, the post stays 'ready_to_post' until they return.
"""

import logging
from datetime import datetime, timezone

from services.database import supabase

logger = logging.getLogger(__name__)


async def check_scheduled_broadcasts():
    """
    Find scheduled broadcasts whose scheduled_at time has passed.
    Mark them as 'ready_to_post' for the extension to handle.
    """
    try:
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        # Find broadcasts that are scheduled and due
        res = supabase.table('broadcast_posts') \
            .select('id,product_id,platform,scheduled_at') \
            .eq('status', 'scheduled') \
            .lte('scheduled_at', now_str) \
            .execute()

        broadcasts = res.data or []

        if not broadcasts:
            logger.debug("No scheduled broadcasts ready")
            return {'processed': 0}

        logger.info(f"Found {len(broadcasts)} scheduled broadcasts ready to post")

        processed = 0
        for broadcast in broadcasts:
            try:
                supabase.table('broadcast_posts').update({
                    'status': 'ready_to_post'
                }).eq('id', broadcast['id']).execute()

                logger.info(
                    f"Broadcast {broadcast['id'][:8]} marked ready_to_post "
                    f"(scheduled for {broadcast['scheduled_at']})"
                )
                processed += 1

            except Exception as e:
                logger.error(f"Failed to update broadcast {broadcast['id']}: {e}")

        return {'processed': processed}

    except Exception as e:
        logger.error(f"Broadcast scheduler error: {e}", exc_info=True)
        return {'error': str(e), 'processed': 0}
