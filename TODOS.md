# Operative1 - Deferred Work Items

Items from the multi-product dashboard implementation that were deferred for future work.

## P1 - High Priority

### Add Comprehensive API Tests
- **What:** Add pytest tests for auth middleware, ownership verification, and key endpoints
- **Why:** Critical security code paths need test coverage to prevent regressions
- **Context:** The auth.py middleware verifies JWT tokens and product ownership. Without tests, refactors could break security guarantees silently.
- **Effort:** M
- **Where to start:** Create `apps/api/tests/test_auth.py` with cases for: valid JWT, expired JWT, missing JWT, product ownership pass/fail

### Add React Error Boundaries
- **What:** Wrap dashboard pages with error boundaries to catch render errors gracefully
- **Why:** Without them, a single component crash shows a blank page instead of a helpful error
- **Context:** Especially important for pages that fetch data (Queue, History, Analytics) where API errors could cascade.
- **Effort:** S
- **Where to start:** Create `apps/web/components/ErrorBoundary.tsx`, wrap each page in `(dashboard)/`

### Rate Limiting on Auth Endpoints
- **What:** Add rate limiting to `/settings/twitter-cookies` and other unauthenticated endpoints
- **Why:** The twitter-cookies endpoint accepts product_id without auth (for extension). Without rate limiting, it's vulnerable to credential stuffing.
- **Context:** Consider using fastapi-limiter or similar. 10 requests/min per IP is a reasonable start.
- **Effort:** S
- **Where to start:** Add dependency in `apps/api/services/rate_limit.py`, apply to sensitive endpoints

## P2 - Medium Priority

### Extension Icons Generation
- **What:** Generate proper 16x16, 48x48, 128x128 PNG icons for the Chrome extension
- **Why:** Currently missing or placeholder icons. Required for Chrome Web Store listing.
- **Context:** Should be simple "O1" logo on dark background
- **Effort:** S

### Chrome Web Store Listing
- **What:** Create screenshots, description, and submit extension for review
- **Why:** Currently extension must be loaded manually. Store listing enables easy install.
- **Context:** Requires privacy policy URL (done: /privacy), screenshots of popup flow, description
- **Effort:** M

### Delete Product Functionality
- **What:** Implement actual product deletion (currently shows alert)
- **Why:** Users need ability to remove products they no longer need
- **Context:** Should cascade delete: social_accounts, reply_queue items. Confirm dialog required.
- **Effort:** S
- **Where to start:** Add `DELETE /products/{id}` endpoint, update Settings page danger zone

### Onboarding Twitter Connect Step
- **What:** Add optional step to onboarding flow to connect Twitter after product creation
- **Why:** Reduces friction - users can connect immediately without navigating to Settings
- **Context:** Show extension install instructions + product ID after product is created
- **Effort:** S

## P3 - Lower Priority

### GraphQL Metrics Collection
- **What:** Re-implement engagement metrics collection using GraphQL API instead of tweepy
- **Why:** Tweepy was removed when switching to GraphQL posting. Engagement data is now stale.
- **Context:** engagement.py pipeline is stubbed out. Need to use Twitter internal API to fetch like/impression counts.
- **Effort:** L

### Product Archive/Soft Delete
- **What:** Archive products instead of hard delete, with ability to restore
- **Why:** Prevents accidental data loss, keeps historical data for analytics
- **Effort:** M

### Bulk Queue Actions
- **What:** Add select-all, approve-selected, reject-selected to Queue page
- **Why:** When queue has many items, approving one-by-one is tedious
- **Effort:** M

### Export Queue History
- **What:** Add CSV/JSON export of history data
- **Why:** Users may want to analyze their engagement data externally
- **Effort:** S

## NOT in Scope (Explicitly Deferred)

### Multi-tenancy / Team Support
Not building teams/organizations in this iteration. Each user owns their own products.

### OAuth Twitter Login
Sticking with cookie-based auth via extension. OAuth requires Twitter API approval which is increasingly restricted.

### Real-time WebSocket Updates
Using polling/refresh for queue updates. WebSockets would add complexity without proportional benefit.

### Mobile App
Web-only for now. Extension-based posting requires desktop browser.
