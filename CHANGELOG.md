# Changelog

All notable changes to Operative1 will be documented in this file.

## [0.1.0.0] - 2026-03-22

### Added
- Tier-based rate limiting system with graduated volume ramp (Tier 0-3: 10/20/40/80 posts per day)
- Product-scoped API tokens (`op1_` prefix) for extension autopilot authentication
- Autopilot safety controls: auto-pause on failure streaks, heartbeat monitoring, posting hours
- Autopilot API endpoints: `/queue/auto-approved`, `/queue/autopilot-log`, `/queue/health`, `/queue/pause`, `/queue/resume`, `/queue/extension-heartbeat`
- Extension autopilot polling via `chrome.alarms` API with randomized 10-15 min intervals
- Autopilot health indicator in dashboard header with pause/resume toggle
- 63 unit tests covering all autopilot safety logic (tiers, criteria, pause, health, demotion, timing)

### Fixed
- Race condition in auto-approve status transition (added WHERE old_status check)
- Product token verification performance (JSONB filter instead of full-table scan)
- Auth bypass on mark-posted/mark-failed endpoints (added product token ownership check)
- `/autopilot-log` endpoint KeyError (missing `id` field in product select)
- Dashboard pause/resume sending `product_id` as query param instead of POST body
- `/health` endpoint response shape mismatch with dashboard expectations
