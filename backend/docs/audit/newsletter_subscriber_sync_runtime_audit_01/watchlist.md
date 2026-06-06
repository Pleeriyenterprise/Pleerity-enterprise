# Newsletter subscriber sync watchlist

- Classification: `ADMIN_DASHBOARD_DRIFT`
- Run tag: `20260606T165125Z`

## P0 — Admin dashboard shows 0 despite data in DB

- [ ] Fix `AdminNewsletterPage.jsx`: `localStorage.getItem('token')` → `auth_token` (or use `api` client)
- [ ] Fix `AdminFAQPage.jsx` and `AdminInsightsFeedbackPage.jsx` (same drift)
- [ ] Surface fetch errors in admin UI instead of silent empty state
- [ ] Verify admin count matches API after deploy

## P1 — Historical Kit subscribers

- [ ] Add Kit→local backfill script or webhook for subscribers not created via `/api/newsletter/subscribe`
- [ ] Document that Kit native forms bypass local DB unless backfilled

## P2 — Hardening

- [ ] Normalize email to lowercase on subscribe (prevent duplicate rows for case variants)
- [ ] Return 422 for invalid email instead of 500
- [ ] Add `test_newsletter_subscriber.py` (subscribe, Kit mock, admin RBAC, duplicate)
- [ ] Optional: store `kit_subscriber_id` from Kit response
- [ ] Optional: retry FAILED kit_sync_status rows

## Proven working (staging runtime)

- [x] Public API subscribe → local DB write
- [x] Kit sync (`kit_sync_status=SYNCED` when key configured)
- [x] Admin API lists subscribers with correct auth
- [x] Permissions enforced (401/403 for non-admin)
