"""
Safety logic tests for the autopilot system.

Tests pure functions and mocks DB calls for:
- Tier configuration and caps
- Autopilot criteria checking
- Health status calculation
- Failure streak detection and escalation
- Pause/resume logic
- Event log management
- Product token validation
- Dynamic timing intervals
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================
# 1. Tier configuration tests (pure, no mocks)
# ============================================================

class TestTierConfig:
    def test_tier_caps(self):
        from services.rate_limiter import TIER_CONFIG, get_tier_daily_cap, get_tier_hourly_cap

        assert get_tier_daily_cap(0) == 10
        assert get_tier_daily_cap(1) == 20
        assert get_tier_daily_cap(2) == 40
        assert get_tier_daily_cap(3) == 80

        assert get_tier_hourly_cap(0) == 3
        assert get_tier_hourly_cap(1) == 5
        assert get_tier_hourly_cap(2) == 10
        assert get_tier_hourly_cap(3) == 20

    def test_unknown_tier_defaults_to_tier0(self):
        from services.rate_limiter import get_tier_daily_cap, get_tier_hourly_cap

        assert get_tier_daily_cap(99) == 10
        assert get_tier_hourly_cap(-1) == 3

    def test_tier3_is_max(self):
        from services.rate_limiter import TIER_CONFIG

        assert TIER_CONFIG[3]['days_to_promote'] is None

    def test_promotion_thresholds(self):
        from services.rate_limiter import PROMOTION_SUCCESS_RATE, PROMOTION_MIN_POSTS

        assert PROMOTION_SUCCESS_RATE == 0.85
        assert PROMOTION_MIN_POSTS == 10

    def test_tier_days_to_promote(self):
        from services.rate_limiter import TIER_CONFIG

        assert TIER_CONFIG[0]['days_to_promote'] == 3
        assert TIER_CONFIG[1]['days_to_promote'] == 7
        assert TIER_CONFIG[2]['days_to_promote'] == 7


# ============================================================
# 2. Autopilot criteria tests (pure, no mocks)
# ============================================================

class TestAutopilotCriteria:
    def test_meets_criteria_happy_path(self):
        from services.autopilot import meets_autopilot_criteria

        product = {
            'autopilot': {
                'enabled': True,
                'min_relevance_score': 7,
                'min_confidence': 0.8,
                'require_no_product_mention': True,
            }
        }
        item = {
            'engagement_metrics': {'relevance_score': 9},
            'confidence_score': 0.95,
            'mentions_product': False,
        }
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is True
        assert reason == 'approved'

    def test_fails_low_relevance(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True, 'min_relevance_score': 7, 'min_confidence': 0.8}}
        item = {'engagement_metrics': {'relevance_score': 5}, 'confidence_score': 0.9, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is False
        assert 'relevance_too_low' in reason

    def test_fails_low_confidence(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True, 'min_relevance_score': 7, 'min_confidence': 0.8}}
        item = {'engagement_metrics': {'relevance_score': 8}, 'confidence_score': 0.5, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is False
        assert 'confidence_too_low' in reason

    def test_allows_product_mention(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True, 'min_relevance_score': 7, 'min_confidence': 0.8}}
        item = {'engagement_metrics': {'relevance_score': 9}, 'confidence_score': 0.95, 'mentions_product': True}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is True

    def test_autopilot_disabled(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': False}}
        item = {'engagement_metrics': {'relevance_score': 10}, 'confidence_score': 1.0, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is False
        assert reason == 'autopilot_disabled'

    def test_missing_autopilot_config(self):
        from services.autopilot import meets_autopilot_criteria

        product = {}
        item = {'engagement_metrics': {'relevance_score': 10}, 'confidence_score': 1.0, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is False

    def test_none_engagement_metrics(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True, 'min_relevance_score': 7, 'min_confidence': 0.8}}
        item = {'engagement_metrics': None, 'confidence_score': 0.9, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is False
        assert 'relevance_too_low' in reason

    def test_default_thresholds(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True}}  # No explicit thresholds
        item = {'engagement_metrics': {'relevance_score': 7}, 'confidence_score': 0.8, 'mentions_product': False}
        meets, reason = meets_autopilot_criteria(item, product)
        assert meets is True

    def test_boundary_values(self):
        from services.autopilot import meets_autopilot_criteria

        product = {'autopilot': {'enabled': True, 'min_relevance_score': 7, 'min_confidence': 0.8}}

        # Exactly at threshold: should pass
        item = {'engagement_metrics': {'relevance_score': 7}, 'confidence_score': 0.8, 'mentions_product': False}
        meets, _ = meets_autopilot_criteria(item, product)
        assert meets is True

        # Just below threshold: should fail
        item = {'engagement_metrics': {'relevance_score': 6}, 'confidence_score': 0.8, 'mentions_product': False}
        meets, _ = meets_autopilot_criteria(item, product)
        assert meets is False


# ============================================================
# 3. Event log tests (pure, no mocks)
# ============================================================

class TestEventLog:
    def test_append_event(self):
        from services.autopilot import append_event_log

        product = {'autopilot': {'event_log': []}}
        log = append_event_log(product, 'test_event', {'key': 'value'})
        assert len(log) == 1
        assert log[0]['event'] == 'test_event'
        assert log[0]['details'] == {'key': 'value'}
        assert 'timestamp' in log[0]

    def test_cap_at_max(self):
        from services.autopilot import append_event_log, EVENT_LOG_MAX

        existing = [{'event': f'event_{i}', 'timestamp': 'ts', 'details': {}} for i in range(EVENT_LOG_MAX)]
        product = {'autopilot': {'event_log': existing}}
        log = append_event_log(product, 'new_event', {})
        assert len(log) == EVENT_LOG_MAX
        assert log[-1]['event'] == 'new_event'
        assert log[0]['event'] == 'event_1'  # First event dropped

    def test_none_event_log(self):
        from services.autopilot import append_event_log

        product = {'autopilot': {'event_log': None}}
        log = append_event_log(product, 'test', {})
        assert len(log) == 1

    def test_missing_autopilot(self):
        from services.autopilot import append_event_log

        product = {}
        log = append_event_log(product, 'test', {})
        assert len(log) == 1


# ============================================================
# 4. Pause/resume logic tests
# ============================================================

class TestPauseLogic:
    def test_not_paused(self):
        from services.autopilot import is_paused

        product = {'id': 'test', 'autopilot': {'enabled': True}}
        paused, reason = is_paused(product)
        assert paused is False
        assert reason == ''

    def test_indefinite_pause(self):
        from services.autopilot import is_paused

        product = {'id': 'test', 'autopilot': {'enabled': True, 'paused': True, 'pause_reason': 'manual'}}
        paused, reason = is_paused(product)
        assert paused is True
        assert reason == 'manual'

    def test_timed_pause_active(self):
        from services.autopilot import is_paused

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        product = {'id': 'test', 'autopilot': {'enabled': True, 'paused_until': future, 'pause_reason': 'failure_streak'}}
        paused, reason = is_paused(product)
        assert paused is True
        assert 'timed_pause_until' in reason

    @patch('services.autopilot.supabase')
    def test_timed_pause_expired_auto_resumes(self, mock_supabase):
        from services.autopilot import is_paused

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        product = {'id': 'test-id', 'autopilot': {'enabled': True, 'paused_until': past, 'pause_reason': 'failure_streak'}}

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        paused, reason = is_paused(product)
        assert paused is False
        # Should have called update to clear pause
        mock_supabase.table.assert_called_with('products')

    def test_missing_autopilot(self):
        from services.autopilot import is_paused

        product = {'id': 'test'}
        paused, reason = is_paused(product)
        assert paused is False


# ============================================================
# 5. Health status calculation tests
# ============================================================

class TestHealthStatus:
    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_green_health(self, mock_recent):
        from services.rate_limiter import get_health_status

        # 10 posts, all successful
        mock_recent.return_value = [{'status': 'posted', 'posted_at': datetime.now(timezone.utc).isoformat()} for _ in range(10)]
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'green'
        assert result['success_rate'] == 1.0
        assert result['consecutive_failures'] == 0

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_yellow_health_low_success(self, mock_recent):
        from services.rate_limiter import get_health_status

        # 10 posts, 8 successful, 2 failed (80% success, <90%)
        posts = [{'status': 'posted'} for _ in range(8)] + [{'status': 'failed'} for _ in range(2)]
        mock_recent.return_value = posts
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'yellow'

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_yellow_health_consecutive_failures(self, mock_recent):
        from services.rate_limiter import get_health_status

        # 10 posts, 2 consecutive failures at the start (most recent)
        posts = [{'status': 'failed'}, {'status': 'failed'}] + [{'status': 'posted'} for _ in range(8)]
        mock_recent.return_value = posts
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'yellow'
        assert result['consecutive_failures'] == 2

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_red_health_low_success(self, mock_recent):
        from services.rate_limiter import get_health_status

        # 10 posts, 6 successful, 4 failed (60% success, <70%)
        posts = [{'status': 'posted'} for _ in range(6)] + [{'status': 'failed'} for _ in range(4)]
        mock_recent.return_value = posts
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'red'

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_red_health_many_consecutive_failures(self, mock_recent):
        from services.rate_limiter import get_health_status

        # Most recent 4 are failures
        posts = [{'status': 'failed'} for _ in range(4)] + [{'status': 'posted'} for _ in range(6)]
        mock_recent.return_value = posts
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'red'
        assert result['consecutive_failures'] == 4

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_insufficient_data(self, mock_recent):
        from services.rate_limiter import get_health_status

        # Only 3 posts — insufficient data
        mock_recent.return_value = [{'status': 'posted'} for _ in range(3)]
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'green'
        assert result['insufficient_data'] is True

    @pytest.mark.asyncio
    @patch('services.rate_limiter.get_recent_posts')
    async def test_no_posts(self, mock_recent):
        from services.rate_limiter import get_health_status

        mock_recent.return_value = []
        result = await get_health_status({'id': 'test'}, 'twitter')
        assert result['status'] == 'green'
        assert result['insufficient_data'] is True
        assert result['success_rate'] == 1.0


# ============================================================
# 6. Failure streak escalation tests
# ============================================================

class TestFailureStreak:
    @pytest.mark.asyncio
    @patch('services.autopilot.supabase')
    @patch('services.autopilot.get_failure_streak')
    async def test_no_pause_under_3_failures(self, mock_streak, mock_supabase):
        from services.autopilot import handle_failure_streak

        mock_streak.return_value = 2
        product = {'id': 'test', 'autopilot': {}}
        result = await handle_failure_streak(product)
        assert result is False

    @pytest.mark.asyncio
    @patch('services.autopilot.supabase')
    @patch('services.autopilot.get_failure_streak')
    async def test_first_streak_2h_pause(self, mock_streak, mock_supabase):
        from services.autopilot import handle_failure_streak

        mock_streak.return_value = 3
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        product = {'id': 'test-id', 'autopilot': {'last_failure_pause_hours': 0}}
        result = await handle_failure_streak(product)
        assert result is True

        # Verify 2h pause was set
        update_call = mock_table.update.call_args
        autopilot = update_call[0][0]['autopilot']
        assert autopilot['last_failure_pause_hours'] == 2
        assert autopilot['paused_until'] is not None
        assert 'failure_streak_2h' in autopilot['pause_reason']

    @pytest.mark.asyncio
    @patch('services.autopilot.supabase')
    @patch('services.autopilot.get_failure_streak')
    async def test_second_streak_6h_pause(self, mock_streak, mock_supabase):
        from services.autopilot import handle_failure_streak

        mock_streak.return_value = 4
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        product = {'id': 'test-id', 'autopilot': {'last_failure_pause_hours': 2}}
        result = await handle_failure_streak(product)
        assert result is True

        update_call = mock_table.update.call_args
        autopilot = update_call[0][0]['autopilot']
        assert autopilot['last_failure_pause_hours'] == 6

    @pytest.mark.asyncio
    @patch('services.autopilot.supabase')
    @patch('services.autopilot.get_failure_streak')
    async def test_third_streak_indefinite_pause(self, mock_streak, mock_supabase):
        from services.autopilot import handle_failure_streak

        mock_streak.return_value = 5
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        product = {'id': 'test-id', 'autopilot': {'last_failure_pause_hours': 6}}
        result = await handle_failure_streak(product)
        assert result is True

        update_call = mock_table.update.call_args
        autopilot = update_call[0][0]['autopilot']
        assert autopilot['paused'] is True
        assert 'indefinite' in autopilot['pause_reason']


# ============================================================
# 7. Tier demotion tests
# ============================================================

class TestTierDemotion:
    @pytest.mark.asyncio
    async def test_red_health_demotes(self):
        from services.rate_limiter import check_tier_demotion

        product = {'id': 'test', 'autopilot': {'tier': 2}}
        health = {'status': 'red', 'success_rate': 0.5, 'consecutive_failures': 5}
        new_tier = await check_tier_demotion(product, health)
        assert new_tier == 1

    @pytest.mark.asyncio
    async def test_tier0_no_demotion(self):
        from services.rate_limiter import check_tier_demotion

        product = {'id': 'test', 'autopilot': {'tier': 0}}
        health = {'status': 'red', 'success_rate': 0.3, 'consecutive_failures': 10}
        new_tier = await check_tier_demotion(product, health)
        assert new_tier is None

    @pytest.mark.asyncio
    async def test_yellow_3_days_demotes(self):
        from services.rate_limiter import check_tier_demotion

        four_days_ago = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        product = {'id': 'test', 'autopilot': {'tier': 1, 'yellow_since': four_days_ago}}
        health = {'status': 'yellow', 'success_rate': 0.85, 'consecutive_failures': 2}
        new_tier = await check_tier_demotion(product, health)
        assert new_tier == 0

    @pytest.mark.asyncio
    async def test_yellow_1_day_no_demotion(self):
        from services.rate_limiter import check_tier_demotion

        one_day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        product = {'id': 'test', 'autopilot': {'tier': 1, 'yellow_since': one_day_ago}}
        health = {'status': 'yellow', 'success_rate': 0.85, 'consecutive_failures': 2}
        new_tier = await check_tier_demotion(product, health)
        assert new_tier is None

    @pytest.mark.asyncio
    async def test_green_health_no_demotion(self):
        from services.rate_limiter import check_tier_demotion

        product = {'id': 'test', 'autopilot': {'tier': 3}}
        health = {'status': 'green', 'success_rate': 0.95, 'consecutive_failures': 0}
        new_tier = await check_tier_demotion(product, health)
        assert new_tier is None


# ============================================================
# 8. Posting hours tests (pure)
# ============================================================

class TestPostingHours:
    def test_no_restrictions(self):
        from services.rate_limiter import is_within_posting_hours

        product = {}
        assert is_within_posting_hours(product) is True

    def test_disabled_restrictions(self):
        from services.rate_limiter import is_within_posting_hours

        product = {'posting_hours': {'enabled': False}}
        assert is_within_posting_hours(product) is True

    def test_valid_timezone(self):
        from services.rate_limiter import is_within_posting_hours

        # Use a wide window that will always include current hour
        product = {'posting_hours': {'enabled': True, 'timezone': 'UTC', 'start_hour': 0, 'end_hour': 23}}
        assert is_within_posting_hours(product) is True


# ============================================================
# 9. Dynamic timing tests
# ============================================================

class TestDynamicTiming:
    @patch('services.global_queue.supabase')
    def test_tier0_interval(self, mock_supabase):
        from services.global_queue import get_dynamic_interval

        mock_result = MagicMock()
        mock_result.data = [{'autopilot': {'enabled': True, 'tier': 0}}]
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_result

        base_gap, jitter = get_dynamic_interval('user-123')

        # Tier 0: 10/day, 18h active => 108 min => 6480s base, 1296s jitter
        assert base_gap == 6480
        assert jitter == 1296

    @patch('services.global_queue.supabase')
    def test_tier3_interval(self, mock_supabase):
        from services.global_queue import get_dynamic_interval

        mock_result = MagicMock()
        mock_result.data = [{'autopilot': {'enabled': True, 'tier': 3}}]
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_result

        base_gap, jitter = get_dynamic_interval('user-123')

        # Tier 3: 80/day, 18h active => 13.5 min => 810s base, 162s jitter
        assert base_gap == 810
        assert jitter == 162

    @patch('services.global_queue.supabase')
    def test_no_enabled_products_uses_tier0(self, mock_supabase):
        from services.global_queue import get_dynamic_interval

        mock_result = MagicMock()
        mock_result.data = []
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_result

        base_gap, jitter = get_dynamic_interval('user-123')
        assert base_gap == 6480  # Tier 0 default

    @patch('services.global_queue.supabase')
    def test_uses_highest_tier(self, mock_supabase):
        from services.global_queue import get_dynamic_interval

        mock_result = MagicMock()
        mock_result.data = [
            {'autopilot': {'enabled': True, 'tier': 1}},
            {'autopilot': {'enabled': True, 'tier': 2}},
        ]
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_result

        base_gap, jitter = get_dynamic_interval('user-123')

        # Should use tier 2 (40/day): 18*60/40*60 = 1620s
        assert base_gap == 1620


# ============================================================
# 10. Heartbeat tests
# ============================================================

class TestHeartbeat:
    def test_no_heartbeat_returns_ok(self):
        from services.autopilot import check_heartbeat

        product = {'id': 'test', 'autopilot': {'enabled': True}}
        assert check_heartbeat(product) is True

    def test_recent_heartbeat_returns_ok(self):
        from services.autopilot import check_heartbeat

        recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        product = {'id': 'test', 'autopilot': {'enabled': True, 'last_heartbeat': recent}}
        assert check_heartbeat(product) is True

    @patch('services.autopilot.supabase')
    def test_stale_heartbeat_with_stale_items(self, mock_supabase):
        from services.autopilot import check_heartbeat

        old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        product = {'id': 'test-id', 'autopilot': {'enabled': True, 'last_heartbeat': old}}

        # Mock stale auto_approved items found
        mock_result = MagicMock()
        mock_result.count = 3
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.lt.return_value = mock_table
        mock_table.execute.return_value = mock_result

        assert check_heartbeat(product) is False

    @patch('services.autopilot.supabase')
    def test_stale_heartbeat_no_stale_items_returns_ok(self, mock_supabase):
        from services.autopilot import check_heartbeat

        old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        product = {'id': 'test-id', 'autopilot': {'enabled': True, 'last_heartbeat': old}}

        # No stale auto_approved items
        mock_result = MagicMock()
        mock_result.count = 0
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.lt.return_value = mock_table
        mock_table.execute.return_value = mock_result

        assert check_heartbeat(product) is True


# ============================================================
# 11. Product token tests (pure)
# ============================================================

class TestProductToken:
    def test_token_format(self):
        from services.auth import generate_product_token, PRODUCT_TOKEN_PREFIX

        token = generate_product_token()
        assert token.startswith(PRODUCT_TOKEN_PREFIX)
        assert len(token) > len(PRODUCT_TOKEN_PREFIX) + 20  # urlsafe(32) is ~43 chars

    def test_tokens_are_unique(self):
        from services.auth import generate_product_token

        tokens = {generate_product_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_token_prefix(self):
        from services.auth import PRODUCT_TOKEN_PREFIX

        assert PRODUCT_TOKEN_PREFIX == 'op1_'


# ============================================================
# 12. Timestamp parsing tests (pure)
# ============================================================

class TestTimestampParsing:
    def test_parse_iso_with_z(self):
        from services.rate_limiter import parse_timestamp

        result = parse_timestamp('2026-03-21T10:00:00Z')
        assert result is not None
        assert result.tzinfo is not None

    def test_parse_iso_with_offset(self):
        from services.rate_limiter import parse_timestamp

        result = parse_timestamp('2026-03-21T10:00:00+00:00')
        assert result is not None

    def test_parse_none(self):
        from services.rate_limiter import parse_timestamp

        assert parse_timestamp(None) is None

    def test_parse_empty_string(self):
        from services.rate_limiter import parse_timestamp

        assert parse_timestamp('') is None

    def test_parse_datetime_object(self):
        from services.rate_limiter import parse_timestamp

        dt = datetime.now(timezone.utc)
        assert parse_timestamp(dt) is dt


# ============================================================
# 13. Tweet ID extraction tests (pure)
# ============================================================

class TestTweetIdExtraction:
    def test_standard_url(self):
        from services.autopilot import extract_tweet_id

        assert extract_tweet_id('https://x.com/user/status/123456789') == '123456789'

    def test_url_with_params(self):
        from services.autopilot import extract_tweet_id

        assert extract_tweet_id('https://x.com/user/status/123456789?t=abc') == '123456789'

    def test_empty_url(self):
        from services.autopilot import extract_tweet_id

        assert extract_tweet_id('') == ''

    def test_no_status(self):
        from services.autopilot import extract_tweet_id

        assert extract_tweet_id('https://x.com/user/likes') == ''
