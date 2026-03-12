# Launch Readiness Implementation Plan

**Purpose:** Roadmap to raise each audit area to **10/10** where achievable, or **at least 9/10**, based on the Production Readiness Audit.  
**Reference:** `docs/LAUNCH_READINESS_AUDIT.md`  
**Status:** Plan only — no implementation in this document.

---

## Target scores by area

| Area | Current | Target | Notes |
|------|---------|--------|-------|
| Authentication & security | 6/10 | **9–10/10** | 10/10 requires rate limiting, forgot-password, JWT enforcement, and secured status endpoints. |
| Customer onboarding flow | 7/10 | **9–10/10** | 10/10 requires single status API, server-only checklist, no fallback mismatch. |
| Automation reliability | 8/10 | **9–10/10** | 10/10 would need per-schedule failure tracking, optional SMS reconciliation; 9/10 is realistic. |
| Admin operations & observability | 8/10 | **9–10/10** | 10/10 requires alerting config check, optional incident for delivery_unknown stale. |
| Branding & product consistency | 5/10 | **9–10/10** | 10/10 requires assets in repo, single company name/tagline/sign-off, manifest. |
| Marketing vs actual capabilities | 5/10 | **9–10/10** | 10/10 requires copy aligned with plan_registry and checkout; 9/10 with clarifications. |

---

## Phase 0: Launch blockers (must complete before soft launch)

**Goal:** Remove all launch blockers so a GO (or GO WITH CAUTION) is valid.

| # | Work item | Area | Deliverable | Owner |
|---|-----------|------|-------------|--------|
| 0.1 | **Logo and favicon** | Branding | Add `pleerity-logo.png` and `favicon.png` under `frontend/public/branding/` (or document deploy-time supply). Ensure all references (index.html, branding.js, layouts) resolve. | Design/Dev |
| 0.2 | **JWT secret enforcement** | Auth | In production, reject startup or token creation when `JWT_SECRET` is unset or equals the default placeholder. Use env check at app startup (e.g. in `server.py` or `auth.py`) and fail fast with a clear message. | Backend |
| 0.3 | **Portfolio plan alignment** | Marketing | Either (A) update CVP landing and Pricing so Portfolio does **not** list PDF/CSV or Tenant portal, or (B) change `plan_registry` to grant CSV and tenant_portal to Portfolio. Document decision and update all marketing copy and feature matrices. | Product/Marketing + Backend (if B) |

**Exit criteria:** Logo/favicon visible in build; app refuses to run with default JWT secret in prod; marketing and plan_registry agree on Portfolio features.

---

## Phase 1: Authentication & security (target 9–10/10)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 1.1 | **Login rate limiting** | Add rate limiting to `POST /api/auth/login` and `POST /api/auth/admin/login` (e.g. per IP and per email): max attempts per window, lockout or exponential backoff, clear error message. Use existing `rate_limiter` or submission_utils pattern; persist or cache per IP/email. | High |
| 1.2 | **Client forgot-password** | Either implement client self-service forgot-password (request by email → token generation → email with link → set-password flow reusing or extending existing token logic) or remove/rewrite all copy that implies it (support chatbot, login page, help). | High |
| 1.3 | **Secure onboarding-status** | Protect `GET /api/portal/setup-status` and `GET /api/intake/onboarding-status/{client_id}`: require short-lived token (e.g. in query param after checkout) or signed payload; add rate limiting per client_id/IP to prevent enumeration. | High |
| 1.4 | **JWT secret consistency** | Ensure all modules that use JWT (`auth.py`, `order_view_token.py`, `document_access_token.py`) read the same env (e.g. `JWT_SECRET`) and fail or refuse when default. | Medium |
| 1.5 | **Sensitive endpoint audit** | Confirm no other endpoints return sensitive data by client_id or similar without auth; document any that must remain public (e.g. webhooks) and ensure they use signature/token verification. | Medium |

**Success criteria:** Rate-limited login; no misleading “forgot password” copy; status endpoints require token or are rate-limited; single JWT secret policy; no unintended info disclosure.

---

## Phase 2: Customer onboarding flow (target 9–10/10)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 2.1 | **Single onboarding-status API** | Choose one source of truth: either `GET /api/portal/setup-status` or `GET /api/intake/onboarding-status/{client_id}`. Update OnboardingStatusPage to use only that endpoint. Deprecate or remove the other from frontend; optionally keep backend for backward compat with a deprecation notice. | High |
| 2.2 | **Dashboard checklist fallback** | Remove hardcoded fallback checklist when API returns no items, or replace it with server-driven default items from backend so labels match (e.g. “Add properties (or import)”, “Set jurisdiction defaults”). Ensure one source: backend checklist service. | High |
| 2.3 | **Onboarding “ready” definition** | Document and implement a single definition of “onboarding complete” (e.g. provisioning_status completed + password_set). Ensure status page and client_route_guard use the same logic so 403 + X-Redirect and “Ready to Use” stay in sync. | Medium |
| 2.4 | **Intake → status redirect token** | After Stripe success, pass a short-lived token (or signed client_id) to the onboarding-status page so the page can call the status API without exposing raw client_id to enumeration. Phase 1.3 covers API-side validation. | Medium |
| 2.5 | **Portal URL in API** | If intake or any API returns `portal_url`, use `/dashboard` (or the canonical client portal entry) for consistency with app routes. | Low |

**Success criteria:** One status API used by the status page; dashboard shows only server-driven checklist; clear “ready” definition; status page uses token where applicable.

---

## Phase 3: Automation reliability (target 9/10; 10/10 if feasible)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 3.1 | **Scheduled reports per-schedule failures** | In `process_scheduled_reports`, catch per-schedule exceptions, increment a failed-schedule counter, and include it in outcome_metrics (e.g. `schedules_failed`). If any schedule fails, set outcome_status to degraded (or failed if all fail). Do not swallow exceptions for the whole job. | High |
| 3.2 | **SMS delivery reconciliation (optional)** | If SMS provider supports delivery webhooks, add SMS template_keys to delivery_reconciliation and map provider status to delivery_delivered / delivery_bounced / delivery_unknown. If no webhook, document “SMS: provider_accepted only” and keep 9/10. | Medium |
| 3.3 | **Reconciliation lag documentation** | Document that delivery_* metrics can lag by up to 15 minutes and 2 hours for webhooks; add to admin guidance so expectations are clear. Optional: surface “last reconciled at” on run detail. | Low |
| 3.4 | **Renewal reminders in RECONCILIATION_JOBS** | Add `renewal_reminders` to delivery_reconciliation RECONCILIATION_JOBS with RENEWAL_REMINDER template so renewal job runs get delivery_* populated (raises observability of that job to “fully observable”). | Low |

**Success criteria:** Scheduled report failures visible in outcome_metrics; SMS either reconciled or explicitly documented as accepted-only; renewal reminders optionally reconciled; docs reflect lag.

---

## Phase 4: Admin operations & observability (target 9–10/10)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 4.1 | **Alerting configuration check** | At startup or in health-summary, detect when `ADMIN_ALERT_EMAILS` and `OPS_ALERT_EMAIL` are both unset; set a flag (e.g. `alerting_configured: false`) and show a prominent notice in System Health and Automation Centre that admin alerts will not be sent until configured. | High |
| 4.2 | **Delivery unknown stale incident** | When `delivery_unknown_stale_runs` is non-empty, create a low-severity (e.g. P2 or P3) incident “Delivery unknown still unresolved for N run(s)” or surface a dedicated “delivery unknown stale” alert in the UI with link to affected runs. Dedupe so one incident per “stale” state. | Medium |
| 4.3 | **Runbook and env documentation** | Document in runbook: required env vars for alerting (`ADMIN_ALERT_EMAILS`, `OPS_ALERT_EMAIL`), how to interpret Automation Centre statuses, and when to act on degraded vs failed. Add link from System Health to runbook or in-app help. | Medium |
| 4.4 | **Execution-only jobs note** | In Automation Centre or System Health, add a short note or tooltip that some jobs (e.g. compliance_recalc_worker, sla_watchdog) are “execution-level only” (no delivery breakdown) so admins do not expect delivery_* for those. | Low |

**Success criteria:** Admins are clearly warned when alerting is not configured; delivery_unknown stale is actionable (incident or alert); runbook and in-app guidance exist; execution-only jobs are explained.

---

## Phase 5: Branding & product consistency (target 9–10/10)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 5.1 | **Logo and favicon (see Phase 0)** | Already in Phase 0. | — |
| 5.2 | **Company name standardisation** | Use “Pleerity Enterprise Ltd” everywhere: backend (`branding.py`, `email_service.py`, `report_service.py`, `jobs.py`, reporting routes), frontend (SEOHead, public pages, any “Pleerity Enterprise” without “Ltd”). Single source in `branding.js` and `branding.py`. | High |
| 5.3 | **Tagline standardisation** | Choose one: “AI-Driven Solutions & Compliance” or “AI-Driven Solutions & Property Compliance”. Update `order_email_templates.py`, `index.html`, and any other reference so tagline is consistent. | High |
| 5.4 | **Sign-off standardisation** | Replace “Pleerity Compliance Vault Pro” as sign-off (e.g. in risk_lead_email_service) with “Compliance Vault Pro by Pleerity Enterprise Ltd” or “Pleerity Enterprise Ltd” consistently across all transactional emails. | Medium |
| 5.5 | **Web app manifest** | Add `frontend/public/manifest.json` with app name, short_name, icons (favicon and optional larger), theme_color, start_url. Reference in index.html. | Low |
| 5.6 | **Brand audit doc** | Update or create a short BRAND.md (or extend BRAND_IDENTITY_IMPLEMENTATION_AUDIT) with: canonical company name, product name, tagline, logo/favicon paths, and where they are used. | Low |

**Success criteria:** One company name, one tagline, one sign-off; logo and favicon in place; manifest present; brand doc up to date.

---

## Phase 6: Marketing vs actual capabilities (target 9–10/10)

| # | Work item | Deliverable | Priority |
|---|-----------|-------------|----------|
| 6.1 | **Portfolio plan copy (see Phase 0)** | Already in Phase 0. | — |
| 6.2 | **14-day free / no credit card** | Verify Stripe checkout: if trial is used, set `subscription_data.trial_period_days: 14` (or equivalent) and ensure billing only after trial. If no trial, remove “free for 14 days” or change to “14-day money-back guarantee” / “Start your 14-day trial” (with card). Remove “No credit card required” unless a true no-card signup path exists (e.g. request demo only). Update Pricing and any CTA. | High |
| 6.3 | **Reminder and digest timing** | Add one line in help, FAQ, or product features: e.g. “Daily reminders are sent once per day (around 9am UK time). Monthly digest is sent at the start of each month.” So timezone expectations are set. | High |
| 6.4 | **Compliance alerts on marketing** | Add “Compliance status change alerts (twice daily)” or similar to CVP/Pricing/features so the 08:00 and 18:00 UTC compliance check emails are reflected. | Medium |
| 6.5 | **ClearForm vs CVP copy** | Verify ClearForm signup flow (no card vs card); align “No credit card required” with actual behaviour for both ClearForm and CVP. | Medium |
| 6.6 | **Feature matrix audit** | Audit Pricing and CVP feature tables (PDF, CSV, Tenant portal, Scheduled reports, etc.) against `plan_registry` and fix any remaining mismatches. | Medium |
| 6.7 | **“Real-time” claims** | If any page (e.g. AssureStack) says “real-time” for CVP, qualify it (e.g. “Dashboard updates when you load it; compliance score recalculates regularly”) to avoid implying live push. | Low |

**Success criteria:** No claim that requires a card or payment when “no credit card” is stated; trial and billing behaviour match copy; reminder/digest/alert timing and naming are clear; feature matrix matches plan_registry; real-time is qualified.

---

## Phase 7: Minor and polish (all areas)

| # | Work item | Area | Deliverable |
|---|-----------|------|-------------|
| 7.1 | **ProtectedRoute staff roles** | Auth | Align frontend “staff” check with backend: if SUPPORT, CONTENT, AUDITOR can access admin routes, ensure admin UI does not hide features they should see (or document that only OWNER/ADMIN see certain sections). |
| 7.2 | **Intake API portal_url** | Onboarding | Return `portal_url: "/dashboard"` (or canonical entry) from intake/onboarding APIs. |
| 7.3 | **Optional og-default.png** | Branding | Add `og-default.png` under branding if referenced in branding.js for social previews. |

---

## Implementation order (suggested)

1. **Phase 0** (blockers) — before any soft launch.
2. **Phase 1** (auth/security) — next; protects all users.
3. **Phase 5** (branding) — with Phase 0 assets; quick wins (name/tagline/sign-off).
4. **Phase 6** (marketing) — with Phase 0 plan alignment; copy and Stripe verification.
5. **Phase 2** (onboarding) — single API and checklist; improves first-run experience.
6. **Phase 4** (admin) — alerting check and runbook; improves ops safety.
7. **Phase 3** (automation) — scheduled report failures and optional SMS/renewal reconciliation.
8. **Phase 7** (polish) — as capacity allows.

---

## Effort and ownership (high-level)

| Phase | Focus | Est. effort | Typical owner |
|-------|--------|-------------|---------------|
| 0 | Blockers | Small (1–2 days) | Dev + Design/Product |
| 1 | Auth & security | Medium (3–5 days) | Backend + Security |
| 2 | Onboarding | Medium (2–3 days) | Full-stack |
| 3 | Automation | Small–medium (2–3 days) | Backend |
| 4 | Admin observability | Small (1–2 days) | Backend + Docs |
| 5 | Branding | Small (1–2 days) | Full-stack + Design |
| 6 | Marketing alignment | Small–medium (2–3 days) | Product/Marketing + Dev |
| 7 | Polish | Small (0.5–1 day) | Dev |

---

## Definition of “launch ready” (9–10/10)

- **Phase 0** complete: no launch blockers.
- **Phases 1, 5, 6** complete: auth secure, branding consistent, marketing accurate.
- **Phases 2, 3, 4** complete or scheduled immediately post-launch: onboarding single-source, automation failures visible, admin alerting and guidance clear.

**Target:** After this plan, each area scores **at least 9/10**; where feasible (e.g. branding, marketing, admin), **10/10**.
