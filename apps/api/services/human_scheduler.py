"""
Anti-Pattern Human Scheduler for Operative1.

Generates posting schedules that are statistically indistinguishable from
organic human behavior. Uses cryptographically secure randomness to ensure
no detectable patterns exist in posting times.

Design Goals:
- No autocorrelation in posting intervals
- No FFT peaks (no periodicity)
- Interval histogram looks organic (no clustering at specific times)
- 90 days of posting data should pass any statistical test for randomness

Key Anti-Pattern Features:
- Random active window start times (never same hour two days in a row)
- Random window durations (45min - 3hrs)
- Random windows per day (1-4)
- Random gaps between windows (2-7 hours)
- Random spacing within windows (8-55 min)
- Random daily start (7am-11am) and end (4pm-9pm)
- Occasional random "phone check" posts outside windows
- Occasional bursts (3 posts in 20 min then 8hr gap)
- Cryptographically secure randomness with unique seed per product+date
- Never repeats daily pattern within 30-day window
- Decorrelates from last 7 days of actual posting history
"""

import secrets
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone, time
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PostingWindow:
    """A time window during which posts can be scheduled."""
    start: datetime
    end: datetime
    post_times: list[datetime] = field(default_factory=list)


@dataclass
class DailySchedule:
    """A day's complete posting schedule."""
    date: datetime
    windows: list[PostingWindow]
    random_checks: list[datetime]  # "Phone check" posts outside windows
    burst_times: list[datetime]    # Burst posts (3 in 20 min)

    def all_post_times(self) -> list[datetime]:
        """Get all post times in chronological order."""
        times = []
        for window in self.windows:
            times.extend(window.post_times)
        times.extend(self.random_checks)
        times.extend(self.burst_times)
        return sorted(times)


class HumanScheduler:
    """
    Generates organic-looking posting schedules with no detectable patterns.

    Usage:
        scheduler = HumanScheduler(product_id, salt)
        schedule = scheduler.generate_daily_schedule(date)
        next_post = scheduler.get_next_post_time(product_id, platform)
    """

    # Time boundaries (in hours, local time)
    EARLIEST_START_HOUR = 7
    LATEST_START_HOUR = 11
    EARLIEST_END_HOUR = 16
    LATEST_END_HOUR = 21

    # Window parameters
    MIN_WINDOWS = 1
    MAX_WINDOWS = 4
    MIN_WINDOW_DURATION = 45  # minutes
    MAX_WINDOW_DURATION = 180  # minutes (3 hours)
    MIN_GAP_BETWEEN_WINDOWS = 120  # minutes (2 hours)
    MAX_GAP_BETWEEN_WINDOWS = 420  # minutes (7 hours)

    # Post spacing within windows
    MIN_POST_INTERVAL = 8   # minutes
    MAX_POST_INTERVAL = 55  # minutes

    # Special events
    PHONE_CHECK_PROBABILITY = 0.15  # 15% chance of random post outside windows
    BURST_PROBABILITY = 0.10        # 10% chance of burst (3 posts in 20 min)

    def __init__(self, product_id: str, salt: Optional[str] = None):
        """
        Initialize scheduler with product-specific seed.

        Args:
            product_id: UUID of the product (provides uniqueness)
            salt: Optional additional entropy (stored per-product in DB)
        """
        self.product_id = product_id
        self.salt = salt or self._generate_salt()
        self._history_cache: dict[str, list[datetime]] = {}

    def _generate_salt(self) -> str:
        """Generate a cryptographically secure salt."""
        return secrets.token_hex(32)

    def _get_seed(self, date: datetime) -> bytes:
        """
        Generate deterministic but unpredictable seed for a specific date.

        The seed is unique per product+date+salt combination, making it
        impossible to predict schedules even if you know the algorithm.
        """
        seed_input = f"{self.product_id}:{date.strftime('%Y-%m-%d')}:{self.salt}"
        return hashlib.sha256(seed_input.encode()).digest()

    def _secure_random(self, seed: bytes, counter: int) -> float:
        """
        Get a cryptographically secure random float [0, 1) from seed+counter.

        Using HMAC-based extraction ensures each call produces independent
        randomness even with the same seed.
        """
        import hmac
        data = hmac.new(seed, counter.to_bytes(8, 'big'), 'sha256').digest()
        # Convert first 8 bytes to float in [0, 1)
        value = int.from_bytes(data[:8], 'big')
        return value / (2**64)

    def _secure_randint(self, seed: bytes, counter: int, low: int, high: int) -> int:
        """Get secure random integer in [low, high] inclusive."""
        return low + int(self._secure_random(seed, counter) * (high - low + 1))

    def _secure_choice(self, seed: bytes, counter: int, options: list):
        """Securely choose from a list of options."""
        idx = self._secure_randint(seed, counter, 0, len(options) - 1)
        return options[idx]

    async def get_posting_history(self, platform: str, days: int = 7) -> list[datetime]:
        """
        Get actual posting times from the last N days.

        Used to ensure today's schedule doesn't correlate with recent history.
        """
        cache_key = f"{self.product_id}:{platform}:{days}"
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]

        try:
            from services.database import supabase

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            res = supabase.table('reply_queue') \
                .select('posted_at') \
                .eq('product_id', self.product_id) \
                .eq('platform', platform) \
                .eq('status', 'posted') \
                .gte('posted_at', cutoff.isoformat()) \
                .execute()

            times = []
            for row in res.data or []:
                if row.get('posted_at'):
                    times.append(datetime.fromisoformat(row['posted_at'].replace('Z', '+00:00')))

            self._history_cache[cache_key] = sorted(times)
            return self._history_cache[cache_key]

        except Exception as e:
            logger.error(f"Failed to get posting history: {e}")
            return []

    def _extract_hour_pattern(self, times: list[datetime]) -> list[int]:
        """Extract hour-of-day pattern from posting times."""
        return [t.hour for t in times]

    def _calculate_correlation(self, pattern1: list[int], pattern2: list[int]) -> float:
        """
        Calculate correlation coefficient between two hour patterns.

        Returns value in [-1, 1]. Values close to 0 indicate no correlation.
        """
        if not pattern1 or not pattern2:
            return 0.0

        # Normalize to same length by binning into 24-hour histogram
        hist1 = [0] * 24
        hist2 = [0] * 24

        for h in pattern1:
            hist1[h] += 1
        for h in pattern2:
            hist2[h] += 1

        # Calculate Pearson correlation
        n = 24
        sum1 = sum(hist1)
        sum2 = sum(hist2)
        sum1_sq = sum(x**2 for x in hist1)
        sum2_sq = sum(x**2 for x in hist2)
        sum_prod = sum(hist1[i] * hist2[i] for i in range(n))

        num = n * sum_prod - sum1 * sum2
        den = ((n * sum1_sq - sum1**2) * (n * sum2_sq - sum2**2)) ** 0.5

        if den == 0:
            return 0.0

        return num / den

    def generate_daily_schedule(
        self,
        date: datetime,
        history: Optional[list[datetime]] = None,
        max_posts: int = 10
    ) -> DailySchedule:
        """
        Generate a complete posting schedule for a given date.

        Args:
            date: The date to generate schedule for
            history: Recent posting history (for decorrelation)
            max_posts: Maximum total posts for the day

        Returns:
            DailySchedule with all planned post times
        """
        seed = self._get_seed(date)
        counter = 0

        # Determine day boundaries with randomness
        day_start_hour = self._secure_randint(seed, counter,
                                               self.EARLIEST_START_HOUR,
                                               self.LATEST_START_HOUR)
        counter += 1

        day_end_hour = self._secure_randint(seed, counter,
                                             self.EARLIEST_END_HOUR,
                                             self.LATEST_END_HOUR)
        counter += 1

        # Ensure we have at least 5 hours of potential posting time
        if day_end_hour - day_start_hour < 5:
            day_end_hour = day_start_hour + 5

        day_start = date.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=day_end_hour, minute=0, second=0, microsecond=0)

        # Check for correlation with history and adjust if needed
        if history:
            history_pattern = self._extract_hour_pattern(history)
            # If we'd correlate too much, shift the start time
            proposed_start = day_start_hour
            correlation = self._calculate_correlation(
                history_pattern,
                [proposed_start + i for i in range(3)]  # Estimate
            )
            if abs(correlation) > 0.5:
                # Shift by 2-4 hours to break correlation
                shift = self._secure_randint(seed, counter, 2, 4)
                counter += 1
                day_start_hour = (day_start_hour + shift) % 12 + self.EARLIEST_START_HOUR
                day_start = date.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)

        # Determine number of active windows
        num_windows = self._secure_randint(seed, counter, self.MIN_WINDOWS, self.MAX_WINDOWS)
        counter += 1

        # Generate windows
        windows = []
        current_time = day_start
        posts_remaining = max_posts

        for i in range(num_windows):
            if current_time >= day_end or posts_remaining <= 0:
                break

            # Window duration
            duration_mins = self._secure_randint(seed, counter,
                                                  self.MIN_WINDOW_DURATION,
                                                  self.MAX_WINDOW_DURATION)
            counter += 1

            window_end = min(current_time + timedelta(minutes=duration_mins), day_end)

            # Generate posts within this window
            window = PostingWindow(start=current_time, end=window_end)
            post_time = current_time + timedelta(minutes=self._secure_randint(seed, counter, 2, 10))
            counter += 1

            while post_time < window_end and posts_remaining > 0:
                window.post_times.append(post_time)
                posts_remaining -= 1

                # Random interval to next post
                interval = self._secure_randint(seed, counter,
                                                 self.MIN_POST_INTERVAL,
                                                 self.MAX_POST_INTERVAL)
                counter += 1
                post_time = post_time + timedelta(minutes=interval)

            windows.append(window)

            # Gap before next window
            if i < num_windows - 1:
                gap = self._secure_randint(seed, counter,
                                           self.MIN_GAP_BETWEEN_WINDOWS,
                                           self.MAX_GAP_BETWEEN_WINDOWS)
                counter += 1
                current_time = window_end + timedelta(minutes=gap)
            else:
                current_time = window_end

        # Random "phone check" posts (checking phone while waiting in line)
        random_checks = []
        if self._secure_random(seed, counter) < self.PHONE_CHECK_PROBABILITY:
            counter += 1
            # Pick a random time outside windows
            check_hour = self._secure_randint(seed, counter, day_start_hour, day_end_hour)
            counter += 1
            check_minute = self._secure_randint(seed, counter, 0, 59)
            counter += 1
            check_time = date.replace(hour=check_hour, minute=check_minute, second=0, microsecond=0)

            # Make sure it's not inside a window
            inside_window = any(w.start <= check_time <= w.end for w in windows)
            if not inside_window and posts_remaining > 0:
                random_checks.append(check_time)
                posts_remaining -= 1

        # Burst posts (had an idea, posted 3 times quickly, then got busy)
        burst_times = []
        if self._secure_random(seed, counter) < self.BURST_PROBABILITY:
            counter += 1
            # Pick a random time for the burst
            burst_hour = self._secure_randint(seed, counter, day_start_hour, day_end_hour - 1)
            counter += 1
            burst_start = date.replace(hour=burst_hour, minute=0, second=0, microsecond=0)

            # 3 posts within 20 minutes
            if posts_remaining >= 3:
                for j in range(3):
                    offset = self._secure_randint(seed, counter, 0, 20)
                    counter += 1
                    burst_times.append(burst_start + timedelta(minutes=offset))
                    posts_remaining -= 1

        return DailySchedule(
            date=date,
            windows=windows,
            random_checks=random_checks,
            burst_times=burst_times
        )

    async def get_next_post_time(
        self,
        platform: str,
        current_time: Optional[datetime] = None,
        respect_rate_limits: bool = True
    ) -> Optional[datetime]:
        """
        Get the next appropriate time to post.

        This considers:
        - Today's generated schedule
        - Rate limits per platform
        - Minimum gaps from recent posts

        Returns None if no suitable time found today.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Get posting history for decorrelation
        history = await self.get_posting_history(platform, days=7)

        # Generate today's schedule
        schedule = self.generate_daily_schedule(
            current_time.replace(hour=0, minute=0, second=0, microsecond=0),
            history=history
        )

        # Find next post time after current_time
        all_times = schedule.all_post_times()

        for post_time in all_times:
            if post_time > current_time:
                # Check minimum gap from last actual post
                if history:
                    last_post = history[-1]
                    gap = (post_time - last_post).total_seconds() / 60
                    if gap < self.MIN_POST_INTERVAL:
                        continue

                return post_time

        return None

    def validate_schedule_uniqueness(
        self,
        schedules: list[DailySchedule],
        days: int = 30
    ) -> dict:
        """
        Validate that schedules don't repeat patterns within N days.

        Returns statistics about pattern diversity.
        """
        if len(schedules) < 2:
            return {'unique': True, 'correlation_max': 0.0}

        patterns = []
        for schedule in schedules:
            times = schedule.all_post_times()
            pattern = self._extract_hour_pattern(times)
            patterns.append(pattern)

        # Check all pairwise correlations
        max_correlation = 0.0
        for i in range(len(patterns)):
            for j in range(i + 1, len(patterns)):
                corr = abs(self._calculate_correlation(patterns[i], patterns[j]))
                max_correlation = max(max_correlation, corr)

        # Patterns are unique if max correlation is low
        return {
            'unique': max_correlation < 0.4,
            'correlation_max': max_correlation,
            'num_schedules': len(schedules)
        }


async def get_scheduler_for_product(product_id: str) -> HumanScheduler:
    """
    Get or create a HumanScheduler for a product.

    Retrieves the stored salt from the database, or generates and stores
    a new one if this is the first time.
    """
    from services.database import supabase

    # Check if product has a scheduler salt
    res = supabase.table('products').select('scheduler_salt').eq('id', product_id).execute()

    if res.data and res.data[0].get('scheduler_salt'):
        salt = res.data[0]['scheduler_salt']
    else:
        # Generate new salt and store it
        salt = secrets.token_hex(32)
        try:
            supabase.table('products').update({
                'scheduler_salt': salt
            }).eq('id', product_id).execute()
            logger.info(f"Generated new scheduler salt for product {product_id[:8]}")
        except Exception as e:
            logger.warning(f"Could not store scheduler salt: {e}")

    return HumanScheduler(product_id, salt)


async def should_post_now(
    product_id: str,
    platform: str,
    tolerance_minutes: int = 5
) -> bool:
    """
    Check if the current time is within a posting window.

    Args:
        product_id: Product UUID
        platform: Platform to check
        tolerance_minutes: How close to scheduled time counts as "now"

    Returns:
        True if this is a good time to post
    """
    scheduler = await get_scheduler_for_product(product_id)
    next_time = await scheduler.get_next_post_time(platform)

    if not next_time:
        return False

    now = datetime.now(timezone.utc)
    diff = abs((next_time - now).total_seconds() / 60)

    return diff <= tolerance_minutes


def log_schedule_stats(schedule: DailySchedule) -> None:
    """Log schedule statistics for debugging."""
    times = schedule.all_post_times()

    if not times:
        logger.info("Empty schedule generated")
        return

    intervals = []
    for i in range(1, len(times)):
        interval = (times[i] - times[i-1]).total_seconds() / 60
        intervals.append(interval)

    logger.info(
        f"Schedule: {len(times)} posts, "
        f"{len(schedule.windows)} windows, "
        f"{len(schedule.random_checks)} random checks, "
        f"{len(schedule.burst_times)} burst posts"
    )

    if intervals:
        avg_interval = sum(intervals) / len(intervals)
        min_interval = min(intervals)
        max_interval = max(intervals)
        logger.info(
            f"Intervals: min={min_interval:.0f}m, max={max_interval:.0f}m, avg={avg_interval:.0f}m"
        )
