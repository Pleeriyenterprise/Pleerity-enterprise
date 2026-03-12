# Production Readiness Audit — Launch Readiness Report

**Audit date:** 2026-02-20  
**Scope:** Six areas — Authentication & security, Customer onboarding, Automation reliability, Admin operations & observability, Branding & product consistency, Marketing vs actual capabilities.  
**Objective:** Determine soft-launch readiness and identify issues that could cause customer confusion, broken onboarding, failed automations, incorrect expectations, admin blind spots, or reliability risks.

---

## 1. Overall launch readiness (scores 1–10)

| Area | Score | Summary |
|------|--------|----------|
| **Authentication & security** | **6/10** | Flows work; role separation (client vs admin) and JWT/session handling are in place. **Gaps:** No rate limiting on login (brute-force risk); no client self-service forgot-password (support copy implies it exists); default JWT secret if env not set; some info disclosure on unauthenticated status endpoints. |
| **Customer onboarding flow** | **7/10** | Path from marketing → intake → Stripe checkout → onboarding-status → set-password → dashboard is implemented. **Gaps:** Duplicate onboarding-status APIs; dashboard fallback checklist text does not match backend when API returns no items; no single source of truth for “ready” state. |
| **Automation reliability** | **8/10** | Scheduler, heartbeat, critical jobs (reminders, digests, compliance checks, scheduled reports) record job_runs with outcome_status/outcome_metrics; exceptions re-raised; delivery reconciliation and notification health states implemented. **Gaps:** Per-schedule exceptions in scheduled_reports can be undercounted; SMS delivery not reconciled; 15‑min reconciliation lag. |
| **Admin operations & observability** | **8/10** | Automation Centre shows status badges, degraded/failed, stale heartbeat; incidents for missed SLA and degraded runs; message-log drill-down and CSV export; delivery-state guidance and delivery_unknown stale threshold. **Gaps:** Admin must know to set ADMIN_ALERT_EMAILS for email alerts; some jobs execution-only. |
| **Branding & product consistency** | **5/10** | Theme (Midnight Blue, Electric Teal, Montserrat/Inter) and backend/frontend brand config aligned. **Gaps:** Logo and favicon referenced (`/branding/pleerity-logo.png`, `favicon.png`) but **not present** in repo; company name “Pleerity Enterprise” vs “Pleerity Enterprise Ltd”; tagline “Property Compliance” in one email only; no web app manifest. |
| **Marketing vs actual capabilities** | **5/10** | Core value props (reminders, score, vault, reports, risk check) match implementation. **Gaps:** CVP landing lists **PDF/CSV** and **Tenant portal** for **Portfolio** but backend gates both to **Pro**; “14-day free, no credit card required” not clearly implemented in intake/checkout; reminder/digest timing (e.g. 09:00 UTC) not stated. |

---

## 2. Launch blockers

Issues that would **prevent** recommending soft launch until addressed:

| # | Blocker | Severity | Recommendation |
|---|---------|----------|----------------|
| 1 | **Logo and favicon missing** | High | `frontend/public/branding/pleerity-logo.png` and `favicon.png` are referenced in layout and index.html but **not in repo**. Deployed site will show broken images and generic favicon. | Add assets to `frontend/public/branding/` or confirm they are supplied at deploy time. |
| 2 | **JWT secret default in production** | Critical | `backend/auth.py` and other modules use `JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")`. If `JWT_SECRET` is not set in production, tokens are predictable. | Require `JWT_SECRET` in production (fail startup or reject token creation if default). |
| 3 | **Marketing oversells Portfolio plan** | High | CVPLandingPage (and possibly Pricing) states **Portfolio** includes “PDF/CSV reports” and “Tenant portal”. Backend gates **CSV** and **tenant_portal** to **Pro** only. Customers on Portfolio will not get these features. | Align marketing and pricing copy with `plan_registry` (remove CSV and Tenant portal from Portfolio, or move feature to Portfolio in code). |

---

## 3. High-risk issues

Problems that could **harm customer trust** if discovered early:

| # | Issue | Area | Recommendation |
|---|-------|------|----------------|
| 1 | **No rate limiting on login** | Auth | `POST /api/auth/login` and `POST /api/auth/admin/login` have no rate limiting. Brute-force and credential stuffing are possible. | Add rate limiting (e.g. per IP and per email) with lockout or backoff. |
| 2 | **Client “forgot password” implied but missing** | Auth | Support/chatbot copy says “Forgot Password” on login and “reset link sent to your inbox”. There is no client self-service forgot-password flow; only admin resend/generate link exists. | Either implement client forgot-password (token + email) or remove/rewrite the copy. |
| 3 | **“14-day free, no credit card required”** | Marketing | Pricing page claims “Try Compliance Vault Pro free for 14 days. No credit card required.” Intake/checkout flow redirects to Stripe; no code path found for signup without card or for 14-day trial before charge. | Verify Stripe subscription_data (e.g. trial_period_days) and checkout flow; if no trial/no-card path exists, change copy to match (e.g. “14-day money-back” or “Start with a 14-day trial” with card). |
| 4 | **Onboarding-status by client_id without auth** | Security | `GET /api/portal/setup-status?client_id=...` and `GET /api/intake/onboarding-status/{client_id}` return status for any client_id. If IDs are guessable, status is disclosed. | Add short-lived token or rate limit; avoid exposing sensitive status to unauthenticated callers. |
| 5 | **Dashboard fallback checklist mismatch** | Onboarding | When `GET /api/client/onboarding/checklist` returns no items, dashboard shows a **hardcoded** list (“Confirm your portfolio details”, “Upload or confirm documents”, etc.) that does **not** match backend checklist items (“Add properties (or import)”, “Set jurisdiction defaults”, etc.). | Use only server-driven checklist; remove or align fallback copy with backend. |

---

## 4. Medium-risk issues

Should be **fixed soon after launch** (or before if capacity allows):

| # | Issue | Area | Recommendation |
|---|-------|------|----------------|
| 1 | **Duplicate onboarding-status APIs** | Onboarding | Frontend uses `GET /api/portal/setup-status`; `GET /api/intake/onboarding-status/{client_id}` exists but is not used by the main status page. Two sources of truth can diverge. | Standardise on one endpoint for the status page; deprecate or remove the other from frontend. |
| 2 | **Scheduled reports: per-schedule exceptions not in outcome_metrics** | Automation | In `process_scheduled_reports`, an inner `except Exception` per schedule only logs; it does not increment failed count or re-raise. One failing schedule can be invisible in outcome_metrics. | Count per-schedule failures and include in outcome_metrics; consider degrading run if any schedule fails. |
| 3 | **Company name and tagline inconsistency** | Branding | “Pleerity Enterprise” (no “Ltd”) in several places; “Pleerity Compliance Vault Pro” as sign-off in risk email; “AI-Driven Solutions & **Property** Compliance” only in order emails vs “AI-Driven Solutions & Compliance” elsewhere. | Standardise to “Pleerity Enterprise Ltd” and one tagline; choose one sign-off. |
| 4 | **Reminder/digest timing not stated** | Marketing | Marketing says “daily reminders” and “monthly digest” but not “once per day at 09:00 UTC” or “1st of month at 10:00 UTC”. Users in other timezones may expect different behaviour. | Add short clarification (e.g. “Daily reminder run”, “Monthly digest at the start of each month”) in help or marketing. |
| 5 | **Admin alerting depends on env** | Admin | Incident creation works; email alerts to admin require `ADMIN_ALERT_EMAILS` or `OPS_ALERT_EMAIL`. If not set, admins are not notified of failures. | Document in runbook; consider startup check or health-summary flag when alerting is not configured. |
| 6 | **Delivery “unknown” stale threshold** | Admin | 6‑hour threshold is documented and used; no automatic incident for “delivery_unknown stale” runs. | Optional: create low-severity incident or dedicated alert when delivery_unknown_stale_runs is non-empty. |

---

## 5. Minor issues

Cosmetic or non-critical improvements:

| # | Issue | Recommendation |
|---|-------|----------------|
| 1 | **No web app manifest** | Add `manifest.json` in `frontend/public` for favicon and app name in “Add to Home Screen”. |
| 2 | **Portal URL in intake API** | Intake API returns `portal_url: "/app/dashboard"`; app redirects to `/dashboard`. Works but could return `/dashboard` for clarity. |
| 3 | **ProtectedRoute “staff” definition** | Frontend uses OWNER or ADMIN only for “staff”; backend allows SUPPORT, CONTENT, AUDITOR for admin routes. Ensure any admin-only UI is consistent with backend roles. |
| 4 | **Twice-daily compliance alerts undersold** | Compliance status checks at 08:00 and 18:00 UTC exist but are not clearly named “compliance alerts” on marketing. | Add one line on features or help. |
| 5 | **ClearForm “No credit card required”** | ClearForm landing states “No credit card required”; CVP Pricing states the same. Verify each product’s signup flow and align copy. |

---

## 6. Soft-launch recommendation

### **GO WITH CAUTION — Soft launch with monitoring**

**Rationale**

- **Authentication & security:** Flows work and role separation is correct, but **missing login rate limiting** and **default JWT secret** are serious. If production **always** sets a strong `JWT_SECRET` and you accept the brute-force risk short-term, you can launch with a clear plan to add rate limiting and fix client forgot-password copy/flow.
- **Onboarding:** End-to-end path exists and is usable. Duplicate APIs and fallback checklist copy are medium risk; fix soon after launch.
- **Automation:** Reliability and observability are in good shape: job_runs, outcome_status/outcome_metrics, delivery reconciliation, heartbeat, incidents, and message-log drill-down are implemented. Remaining gaps (per-schedule undercount, SMS, lag) are acceptable for soft launch with monitoring.
- **Admin:** Automation Centre and System Health give clear visibility; delivery-state guidance and stale-unknown warning are in place. Ensure `ADMIN_ALERT_EMAILS` is set and documented.
- **Branding:** **Logo and favicon must be present** at go-live (or deploy process must add them). Terminology and tagline inconsistencies are medium/minor.
- **Marketing:** **Portfolio plan must not promise CSV or Tenant portal** unless backend is changed. **Pricing “14-day free / no credit card”** must be verified and aligned with Stripe and intake flow before launch.

**Conditions for GO WITH CAUTION**

1. **Before launch:** Resolve **launch blockers**: add or deploy logo and favicon; enforce non-default `JWT_SECRET` in production; align marketing (and pricing) with plan_registry so Portfolio does not claim CSV or Tenant portal (or add those to Portfolio).
2. **At launch:** Set `ADMIN_ALERT_EMAILS` (or `OPS_ALERT_EMAIL`); monitor Automation Centre and System Health; monitor onboarding-status and first-login success.
3. **Shortly after launch:** Add login rate limiting; fix or remove client “forgot password” copy and implement or drop the flow; standardise onboarding-status API and dashboard fallback checklist; clarify “14-day free / no credit card” vs actual checkout.

**If blockers are not fixed:** Treat as **NO-GO** until logo/favicon are in place, JWT secret is safe, and marketing matches plan capabilities.  

**If all blockers and high-risk items are addressed:** A **GO** for soft launch is reasonable, with the above monitoring and follow-up list.

---

## Summary table

| Category | Count |
|----------|--------|
| Launch blockers | 3 |
| High-risk issues | 5 |
| Medium-risk issues | 6 |
| Minor issues | 5 |

**Overall:** The system is **not yet fully launch-ready** without addressing the three blockers. With blockers fixed and high-risk issues scheduled, **GO WITH CAUTION** is appropriate for a soft launch with close monitoring and a clear follow-up plan.
