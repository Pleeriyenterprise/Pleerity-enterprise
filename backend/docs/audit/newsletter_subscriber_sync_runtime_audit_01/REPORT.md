# Newsletter Subscriber Sync Runtime Audit

**Programme:** NEWSLETTER-SUBSCRIBER-SYNC-RUNTIME-AUDIT-01  
**Run tag:** `20260606T165125Z`  
**Staging API:** `https://pleerity-enterprise.onrender.com`  
**Classification:** `ADMIN_DASHBOARD_DRIFT`

## Executive summary

The reported symptom — **Kit has subscribers but Admin Newsletter shows 0** — is **not** caused by website→Kit-only capture or missing local DB writes on the current code path. Runtime proof shows:

1. `POST /api/newsletter/subscribe` writes to MongoDB `newsletter_subscribers` **before** Kit push.
2. Kit sync succeeds (`kit_sync_status=SYNCED`) when `KIT_API_KEY` is configured on Render.
3. Admin API `GET /api/admin/newsletter/subscribers` returns **6+ rows** including audit test emails.
4. **Admin UI reads the wrong localStorage key** (`token` vs `auth_token`), so the fetch silently 401s and the dashboard always renders **0 subscribers**.

Secondary gap: **no Kit→local backfill/webhook** — historical subscribers captured only in Kit (e.g. Kit native forms) remain invisible to the admin dashboard.

---

## PART 1 — Architecture

| Layer | Detail |
|-------|--------|
| Public form | `/newsletter` → `NewsletterPage.js` |
| Submit | `POST {REACT_APP_BACKEND_URL}/api/newsletter/subscribe?email=&source=` |
| Backend route | `backend/routes/admin_modules.py` (public router, no prefix) |
| Local DB | MongoDB `newsletter_subscribers` |
| Kit | `backend/services/kit_integration.py` → `POST /v4/subscribers` with `X-Kit-Api-Key` |
| Admin API | `GET /api/admin/newsletter/subscribers` (admin_route_guard) |
| Admin UI | `/admin/marketing/newsletter` → `AdminNewsletterPage.jsx` |
| Source of truth (admin) | **Local MongoDB** — not Kit API |
| Webhook / backfill | **None** |

Artifact: `newsletter_architecture_runtime.json`

---

## PART 2 — Public subscribe

| Check | Result |
|-------|--------|
| API subscribe | **200** — `Subscribed successfully` |
| Duplicate | **200** — `Already subscribed` |
| Browser form | Email field present; submission created DB row (`newsletter-browser-…@yopmail.com`); Playwright response matcher timed out (URL pattern) |
| Console errors | None observed |

Artifact: `public_subscribe_runtime.json`

---

## PART 3 — Local database

| Check | Result |
|-------|--------|
| Admin API status | **200** |
| Total in DB | **6** at check time (9 after edge-case probes) |
| Test row | `newsletter-audit-20260606t165125z@yopmail.com` — `SUBSCRIBED`, `source=newsletter_page` |
| Kit sync on row | **SYNCED** |

**Not** `LOCAL_CAPTURE_GAP` — local rows are created on website signup.

Artifact: `local_subscriber_runtime.json`

---

## PART 4 — Kit integration

| Check | Result |
|-------|--------|
| `KIT_API_KEY` on staging | Configured (inferred from `SYNCED` status) |
| Kit list/form/tag IDs in code | None — global subscriber create only |
| `kit_subscriber_id` stored locally | No field in model |
| Retry on failure | None |
| Failed rows in DB | 2 of 6 with `kit_sync_status=FAILED` |

Artifact: `kit_sync_runtime.json`

---

## PART 5 — Admin dashboard

| Surface | Count / behaviour |
|---------|-------------------|
| Admin API | **6** subscribers; test email present |
| Admin UI (`auth_token` in storage) | **0 total subscribers**, "No subscribers" — page loads but fetch uses `token` key |
| Admin UI (`token` in storage) | Page may not fully hydrate |
| CSV export logic | Safe — no secrets in sample export |
| Root cause | `AdminNewsletterPage.jsx` line 18: `localStorage.getItem('token')` vs `AuthContext` `auth_token` |

Same drift exists on `AdminFAQPage.jsx` and `AdminInsightsFeedbackPage.jsx`.

Artifact: `admin_newsletter_dashboard_runtime.json`  
Screenshots: `screenshots/admin/newsletter_admin_auth_token.png`

---

## PART 6 — Sync direction

**Actual behaviour:** `A` — Website → local DB → Kit (one-way push).  
**Not supported:** Kit → local sync, webhooks, two-way sync.

If Kit has subscribers not created via this API path, admin dashboard will not show them without backfill.

Artifact: `sync_direction_runtime.json`

---

## PART 7 — Backfill / reconciliation

| Check | Result |
|-------|--------|
| Kit import script | **Missing** |
| Backfill endpoint | **Missing** |
| Classification | `BACKFILL_GAP` |

Artifact: `newsletter_backfill_runtime.json`

---

## PART 8 — Permissions — PASS

- Public can subscribe (200)
- Unauthenticated admin list → 401
- Client → 403, Contractor → 403
- Admin list → 200

Artifact: `newsletter_permissions_runtime.json`

---

## PART 9 — Edge cases — PARTIAL

| Case | Result |
|------|--------|
| Duplicate email | Safe — "Already subscribed" |
| Plus-address | 200, new row |
| Uppercase email | Creates duplicate row (no normalization) |
| Invalid email | **500** (should be 400/422) |

Artifact: `newsletter_edge_cases_runtime.json`

---

## PART 10 — Regression — PARTIAL

- No dedicated `test_newsletter_subscriber.py` in repo
- `test_admin_action_governance_policy.py`: **11 passed**

Artifact: `newsletter_regression_runtime.json`

---

## Classification

```json
{
  "classification": "ADMIN_DASHBOARD_DRIFT",
  "secondary_flags": ["ADMIN_DASHBOARD_DRIFT", "BACKFILL_GAP"],
  "blockers": ["public_subscribe", "admin_dashboard", "backfill", "edge_cases"]
}
```

`VERIFIED_OPERATIONALLY` blocked by admin UI token bug and missing backfill/tests.

---

## Recommended fixes (watchlist)

1. Change `AdminNewsletterPage` (and FAQ/Insights feedback pages) to use `auth_token` or shared API client.
2. Add Kit→local backfill for historical Kit-only subscribers.
3. Normalize email to lowercase on subscribe; return 422 for invalid email.
4. Add unit tests for subscribe route, Kit sync, admin list RBAC.

Harness: `backend/newsletter_subscriber_sync_runtime_audit_01_execute.py`
